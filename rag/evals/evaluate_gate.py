"""
ANSWER-GATE EVALUATION

evals/evaluate.py measures RETRIEVAL, which is provider-independent — it runs on local
embeddings and a local cross-encoder, so swapping the LLM cannot change its numbers.

The answer gate is different: it is an LLM call, so its quality varies by provider. This
harness measures it against hand labels so "runs fully local on Ollama" can be published
as a number instead of a hope. Run it once per provider and put BOTH numbers in the README.

  python3 evals/evaluate_gate.py <workspace_id>
  LLM_BACKEND=ollama python3 evals/evaluate_gate.py <workspace_id>
  python3 evals/evaluate_gate.py --test-scoring     # offline, no network
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DATASET_PATH = Path(__file__).resolve().parent / "dataset_answergate_v1.json"


def score_gate(dataset: list[dict], verdict_by_key: dict) -> dict:
    """Compare predicted verdicts against hand labels.

    `verdict_by_key` maps (question, chunk_id) -> predicted verdict.

    A MISSING prediction counts as wrong and is ALSO reported separately: a model that
    silently omits a chunk is failing, and averaging that into accuracy would hide it.
    """
    correct = 0
    missing = 0
    confusion: Counter = Counter()

    for row in dataset:
        key = (row["question"], row["chunk_id"])
        actual = row["label"]
        predicted = verdict_by_key.get(key)
        if predicted is None:
            missing += 1
            confusion[(actual, "MISSING")] += 1
            continue
        confusion[(actual, predicted)] += 1
        if predicted == actual:
            correct += 1

    total = len(dataset)
    return {
        "total": total,
        "correct": correct,
        "accuracy": (correct / total) if total else 0.0,
        "confusion": dict(confusion),
        "missing": missing,
    }


def run(workspace_id: str) -> dict:
    """Call the real gate once per question group, then score the verdicts."""
    from core.llm import generate_content
    from retrieval.clips import build_answer_gate_prompt, parse_answer_gate_response

    dataset = json.loads(DATASET_PATH.read_text())
    chunks_path = Path("data/workspaces") / workspace_id / "chunks.json"
    if not chunks_path.exists():
        raise SystemExit(
            f"no chunks at {chunks_path}. Run: python3 cli.py ingest <raw.json> {workspace_id}")
    chunk_by_id = {c["chunk_id"]: c for c in json.loads(chunks_path.read_text())}

    by_question: dict[str, list[dict]] = {}
    for row in dataset:
        by_question.setdefault(row["question"], []).append(row)

    verdict_by_key: dict = {}
    unusable = 0          # replies we could not parse at all
    rejected_total = 0    # individual verdicts thrown out by validation

    for question, rows in by_question.items():
        missing_ids = [r["chunk_id"] for r in rows if r["chunk_id"] not in chunk_by_id]
        if missing_ids:
            raise SystemExit(
                f"dataset references chunk_ids absent from workspace '{workspace_id}': "
                f"{missing_ids}")
        chunks = [chunk_by_id[r["chunk_id"]] for r in rows]

        # A model that emits unparseable output is FAILING, not erroring — that is a real
        # property of the provider and exactly what this harness exists to measure. Crashing
        # here would let the worst providers avoid producing a number at all.
        try:
            raw = generate_content(build_answer_gate_prompt(question, chunks), task="gate")
            verdicts, rejections = parse_answer_gate_response(raw, chunks)
        except ValueError as e:
            unusable += 1
            print(f"  [{question[:44]}] UNPARSEABLE reply — {e}")
            continue
        except Exception as e:
            unusable += 1
            print(f"  [{question[:44]}] provider error — {e}")
            continue

        for v in verdicts:
            verdict_by_key[(question, v["chunk_id"])] = v["verdict"]
        if rejections:
            rejected_total += len(rejections)
            print(f"  [{question[:44]}] {len(rejections)} verdict(s) rejected by validation")

    result = score_gate(dataset, verdict_by_key)
    result["unusable_replies"] = unusable
    result["question_groups"] = len(by_question)
    result["rejected_verdicts"] = rejected_total
    return result


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test-scoring":
        # Offline self-check, matching the convention in evals/evaluate.py.
        fake = [{"question": "q", "chunk_id": "c1", "label": "answers"}]
        assert score_gate(fake, {("q", "c1"): "answers"})["accuracy"] == 1.0
        assert score_gate(fake, {})["missing"] == 1
        assert score_gate([], {})["accuracy"] == 0.0
        print("scoring OK")
        sys.exit(0)

    workspace = sys.argv[1] if len(sys.argv) > 1 else "rag_research"
    result = run(workspace)
    print(f"\nprovider (LLM_BACKEND): {os.environ.get('LLM_BACKEND', 'auto')}")
    print(f"accuracy: {result['correct']}/{result['total']} = {result['accuracy']:.0%}")
    print(f"unusable replies: {result['unusable_replies']}/{result['question_groups']} "
          f"question groups (output could not be parsed at all)")
    print(f"rejected verdicts: {result['rejected_verdicts']} (failed validation)")
    print(f"missing predictions: {result['missing']}")
    print("\nconfusion (actual -> predicted):")
    for (actual, predicted), n in sorted(result["confusion"].items()):
        flag = "" if actual == predicted else "   <-- wrong"
        print(f"  {actual:10s} -> {predicted:10s}  {n}{flag}")
