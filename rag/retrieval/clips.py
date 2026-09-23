"""
ANSWER GATE — the difference between "relevant to your topic" and "answers your question".

Ordinary retrieval returns topically similar chunks. That is why a summarizer can never
tell you a video is padding: it has no notion of a chunk FAILING to answer. The gate adds
one batched LLM call that labels each reranked chunk `answers` / `mentions` / `unrelated`,
which is what makes "9 videos mention creatine, none answer this" possible.

Two guards, both mirroring knowledge/claim_extractor.py's evidence validation:
  1. A verdict naming a chunk_id we never sent is discarded outright.
  2. An `answers` verdict must quote a span that is really in the chunk. If it isn't, the
     chunk is downgraded to `mentions`. We never display text a source did not say.

IMPORTANT: heavy imports (sentence_transformers via the reranker, qdrant_client via the
vector store) are deliberately deferred into function bodies — same pattern as
knowledge/claim_clusterer.py's _call_gemini. Everything above find_clips() is pure and
testable with no models, no network, and no API key.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GATE_VERDICTS = {"answers", "mentions", "unrelated"}


def normalize_whitespace(text: str) -> str:
    """Collapse all whitespace runs to single spaces and strip the ends.

    Models reproduce quotes with different line breaks and spacing than the source.
    Normalizing both sides before the containment check keeps the verbatim guarantee
    meaningful (same words, same order) without failing on cosmetic differences.
    """
    return " ".join(text.split())


def build_answer_gate_prompt(question: str, chunks: list[dict]) -> str:
    """One prompt covering EVERY candidate chunk — one call, not one per chunk."""
    blocks = "\n\n".join(
        f'[chunk_id: {c["chunk_id"]}]\n"{c["text"]}"' for c in chunks
    )
    return f"""You decide, for each excerpt below, whether it ANSWERS a specific question
or merely MENTIONS the topic. This distinction is the entire point — be strict.

QUESTION: "{question}"

Label each excerpt with exactly one verdict:
- "answers"   — the excerpt contains information that actually answers the question
- "mentions"  — the excerpt is about the topic but does not answer the question
- "unrelated" — the excerpt is not about the question's topic at all

For "answers" ONLY, also return "span": the shortest run of text COPIED WORD FOR WORD
from that excerpt that does the answering. Do not paraphrase, do not correct, do not
summarize. If you cannot copy an exact span, the verdict is "mentions", not "answers".
For "mentions" and "unrelated", use an empty span.

Return ONLY JSON, no markdown fences:
{{"verdicts": [{{"chunk_id": "...", "verdict": "...", "span": "..."}}]}}

Use only the chunk_id values given below. Include every excerpt exactly once.

EXCERPTS:
{blocks}
"""


def _strip_fences(raw: str) -> str:
    """Drop ```json ... ``` wrappers. Same handling as claim_clusterer.adjudicate_merge."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


def _load_json_or_raise(raw: str, what: str) -> dict:
    """Both parsers need the same thing: fenced JSON in, dict out, ValueError on garbage.

    ValueError here always means INFRASTRUCTURE failure (a model returned something
    unusable), never a verdict. Callers must keep that distinction — see find_clips.
    """
    try:
        return json.loads(_strip_fences(raw))
    except Exception as e:
        raise ValueError(f"unparseable {what} reply: {e}")


def parse_answer_gate_response(raw: str, chunks: list[dict]) -> tuple[list[dict], list[dict]]:
    """Validate the gate's reply against the chunks we actually sent.

    Returns (verdicts, rejections). A rejection is never silently dropped — callers
    surface the count so a degraded model is visible rather than looking like a corpus
    with nothing to say.

    Raises ValueError if the reply is not parseable JSON at all. That is an infrastructure
    failure, not a verdict, and the caller must treat it as such.
    """
    parsed = _load_json_or_raise(raw, "answer-gate")

    text_by_id = {c["chunk_id"]: c["text"] for c in chunks}
    verdicts: list[dict] = []
    rejections: list[dict] = []
    seen_ids: set[str] = set()

    for item in parsed.get("verdicts", []):
        chunk_id = item.get("chunk_id", "")
        verdict = item.get("verdict", "")
        span = (item.get("span") or "").strip()

        # Guard 0: one verdict per chunk. A model that returns the same chunk twice with
        # conflicting verdicts is not giving us a decision — keeping both would let the
        # later one silently overwrite the earlier, so first wins and the rest are rejected.
        if chunk_id in seen_ids:
            rejections.append({
                "reason": f"duplicate verdict for chunk_id '{chunk_id}'; kept the first",
                "chunk_id": chunk_id,
            })
            continue

        # Guard 1: a chunk_id we never sent means the model invented a source.
        if chunk_id not in text_by_id:
            rejections.append({
                "reason": f"unknown chunk_id '{chunk_id}' (not in the candidates sent)",
                "chunk_id": chunk_id,
            })
            continue

        if verdict not in GATE_VERDICTS:
            rejections.append({
                "reason": f"invalid verdict '{verdict}'",
                "chunk_id": chunk_id,
            })
            continue

        # Guard 2: an "answers" claim must quote the chunk, not paraphrase it.
        if verdict == "answers":
            if not span:
                rejections.append({
                    "reason": "verdict 'answers' with an empty span; downgraded to 'mentions'",
                    "chunk_id": chunk_id,
                })
                verdict = "mentions"
            elif normalize_whitespace(span) not in normalize_whitespace(text_by_id[chunk_id]):
                rejections.append({
                    "reason": "span is not verbatim in the chunk; downgraded to 'mentions'",
                    "chunk_id": chunk_id,
                })
                verdict = "mentions"

        seen_ids.add(chunk_id)
        verdicts.append({"chunk_id": chunk_id, "verdict": verdict, "span": span})

    return verdicts, rejections


def build_watch_url(video_id: str, start_seconds: float, lead: int | None = None) -> str:
    """A YouTube link that seeks a few seconds BEFORE the span.

    Chunk timestamps are partly estimated by word position (ingestion/chunker.py), so they
    drift. Landing slightly early means the viewer hears the lead-in; landing late means
    they missed the answer and think the tool is broken. Clamped at 0 — a negative t would
    be ignored by YouTube and silently start from the beginning.
    """
    from core.config import CLIP_LINK_LEAD_SECONDS
    if lead is None:
        lead = CLIP_LINK_LEAD_SECONDS
    t = max(0, int(start_seconds) - lead)
    return f"https://youtu.be/{video_id}?t={t}"


def build_skip_report(all_videos: list[dict], answering_video_ids: set[str]) -> dict:
    """Which videos contributed nothing, and how much runtime that is.

    The honest inverse of the answer: not just "here is your answer" but "here is what you
    can safely not watch." A missing or null duration counts as 0 rather than raising — an
    un-scraped duration should not take down a query.
    """
    skipped = [v for v in all_videos if v["video_id"] not in answering_video_ids]
    return {
        "video_count": len(skipped),
        "total_seconds": sum(int(v.get("duration_seconds") or 0) for v in skipped),
        "video_ids": [v["video_id"] for v in skipped],
    }


def format_duration(seconds: int) -> str:
    """13860 -> '3h 51m'. Minutes only under an hour, so short corpora don't read '0h 12m'."""
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def build_conflict_prompt(clips: list[dict]) -> str:
    """Ask, in ONE call, which of these clips actually contradict each other.

    Deliberately NOT knowledge/synthesizer.build_relationship_prompt: that returns a single
    label for a whole group, so it cannot say which PAIR conflicts, and running it pairwise
    over 5 clips would cost 10 calls instead of 1.

    Clips are numbered from 1 to match what the user sees in the rendered output.
    """
    blocks = "\n".join(
        f'[{i}] ({c.get("channel", "unknown")}) "{c.get("span", "")}"'
        for i, c in enumerate(clips, start=1)
    )
    return f"""These numbered excerpts all answer the same question. Identify only the pairs
that GENUINELY CONTRADICT each other — asserting incompatible things about the same
situation.

Do NOT report a pair as conflicting when they:
- agree, or mostly agree with minor differences
- describe different situations, populations, or timeframes (both can be true at once)
- are simply about different aspects of the topic

Return ONLY JSON, no markdown fences. Use the bracket numbers shown:
{{"conflicts": [[1, 2]]}}

If nothing genuinely contradicts, return {{"conflicts": []}}.

EXCERPTS:
{blocks}
"""


def parse_conflict_response(raw: str, clip_count: int) -> list[tuple[int, int]]:
    """Validate conflict pairs against the clips we actually sent.

    Every index must refer to a real clip — an invented index is discarded rather than
    rendered, mirroring synthesizer.parse_relationship_response's valid_claim_ids check.
    Pairs are normalized ascending and deduplicated so (2,1) and (1,2) are one conflict.

    Raises ValueError on unparseable JSON — an infrastructure failure, not a verdict.
    """
    parsed = _load_json_or_raise(raw, "conflict")

    seen: set[tuple[int, int]] = set()
    for pair in parsed.get("conflicts", []):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        try:
            a, b = int(pair[0]), int(pair[1])
        except (TypeError, ValueError):
            continue
        if a == b:
            continue
        if not (1 <= a <= clip_count and 1 <= b <= clip_count):
            continue
        seen.add((min(a, b), max(a, b)))

    return sorted(seen)


def _default_retrieve(question: str, workspace_id: str) -> list[dict]:
    """Real retrieval: existing hybrid search + cross-encoder rerank, unchanged.

    Imported HERE rather than at module scope so the pure functions above stay importable
    without torch or qdrant — see this module's docstring.
    """
    from core.config import RERANK_KEEP_TOP, VECTOR_TOP_K
    from retrieval.bm25 import load_workspace_chunks
    from retrieval.hybrid import hybrid_search
    from retrieval.reranker import rerank

    fused = hybrid_search(question, workspace_id=workspace_id, top_k=VECTOR_TOP_K)
    reranked = rerank(question, fused, top_k=RERANK_KEEP_TOP)

    # is_estimated is NOT in the Qdrant payload (see vector_store.py), but BM25 loads
    # chunks.json and carries it. RRF keeps whichever copy it saw first, so without this
    # join the field's presence depends on which retriever surfaced the chunk — making the
    # `~` marker and the ranking tie-break fire nondeterministically. Joining here fixes it
    # for ALREADY-INDEXED workspaces too, which adding it to the payload would not.
    estimated_by_id = {c["chunk_id"]: bool(c.get("is_estimated"))
                       for c in load_workspace_chunks(workspace_id)}
    for c in reranked:
        c["is_estimated"] = estimated_by_id.get(c["chunk_id"], c.get("is_estimated", False))
    return reranked


def _default_generate(prompt: str, task: str | None = None) -> str:
    from core.llm import generate_content
    return generate_content(prompt, task=task)


def _default_load_videos(workspace_id: str) -> list[dict]:
    from core.config import WORKSPACES_DIR
    path = Path(WORKSPACES_DIR) / workspace_id / "videos.json"
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def find_clips(
    question: str,
    workspace_id: str,
    retrieve_fn=None,
    generate_fn=None,
    load_videos_fn=None,
) -> dict:
    """Return only the clips that ANSWER the question, plus what you can skip.

    retrieve_fn / generate_fn / load_videos_fn are injectable so this is testable with no
    network and no models — the same pattern evals/evaluate.py uses for retrieve_fn.

    Cost: 2 LLM calls (gate + conflicts), or 1 when fewer than two clips survive the gate.

    An infrastructure failure is recorded in `errors` and never rendered as "nothing
    answers your question" — those two outcomes look identical to a user and must not be
    conflated (see knowledge/claim_clusterer.py:53-108 for the same distinction).
    """
    from core.config import CLIP_MAX_RETURNED

    retrieve_fn = retrieve_fn or _default_retrieve
    generate_fn = generate_fn or _default_generate
    load_videos_fn = load_videos_fn or _default_load_videos

    errors: list[str] = []
    rejections: list[dict] = []
    llm_calls = 0

    candidates = retrieve_fn(question, workspace_id)
    all_videos = load_videos_fn(workspace_id)

    # ─── The gate: one batched call over every candidate ───────────────────────
    verdicts = []
    gate_ran = True
    if candidates:
        try:
            raw = generate_fn(build_answer_gate_prompt(question, candidates), task="gate")
            llm_calls += 1
            verdicts, rejections = parse_answer_gate_response(raw, candidates)
        except Exception as e:
            gate_ran = False
            errors.append(f"answer gate failed (no verdicts obtained): {e}")

    answering_ids = {v["chunk_id"] for v in verdicts if v["verdict"] == "answers"}
    span_by_id = {v["chunk_id"]: v["span"] for v in verdicts}

    kept = [c for c in candidates if c["chunk_id"] in answering_ids]
    # Relevance is PRIMARY: the cross-encoder score decides the order. is_estimated is only
    # a TIE-BREAK, so an exactly-anchored clip wins over an estimated one of equal
    # relevance — it must never outrank a genuinely more relevant clip.
    kept.sort(key=lambda c: (-(c.get("rerank_score") or 0.0), bool(c.get("is_estimated"))))

    # Chunks OVERLAP by design (CHUNK_OVERLAP_WORDS), so one sentence lives in two chunks
    # and the gate rightly labels both "answers" — producing two clips with the same quote
    # at nearly the same timestamp. knowledge/claim_clusterer.py documents this exact
    # failure mode for claims; it applies identically here.
    #
    # Dedupe AFTER sorting so the best-ranked survives, and BEFORE the cap so the freed
    # slots go to genuinely different answers. We keep the first and drop the later rather
    # than merging spans: a span may only be shown against a chunk that actually contains
    # it, so adopting a longer span from a different chunk would break the verbatim guarantee.
    deduped: list[dict] = []
    kept_spans: list[str] = []
    for c in kept:
        span_norm = normalize_whitespace(span_by_id.get(c["chunk_id"], "")).lower()
        if span_norm and any(span_norm in s or s in span_norm for s in kept_spans):
            continue
        kept_spans.append(span_norm)
        deduped.append(c)

    kept = deduped[:CLIP_MAX_RETURNED]

    clips = [
        {
            "rank": i,
            "chunk_id": c["chunk_id"],
            "video_id": c["video_id"],
            "video_title": c.get("video_title", ""),
            "channel": c.get("channel", ""),
            # Coerced to a number: a chunk missing a timestamp would otherwise crash the
            # renderer's format_timestamp on int(None).
            "start_seconds": float(c.get("start_seconds") or 0.0),
            "end_seconds": float(c.get("end_seconds") or 0.0),
            "is_estimated": bool(c.get("is_estimated")),
            "span": span_by_id.get(c["chunk_id"], ""),
            "watch_url": build_watch_url(c["video_id"], c.get("start_seconds") or 0),
            "conflicts_with": [],
        }
        for i, c in enumerate(kept, start=1)
    ]

    # ─── Conflicts: one batched call, only worth making with 2+ clips ──────────
    if len(clips) >= 2:
        try:
            raw = generate_fn(build_conflict_prompt(clips), task="gate")
            llm_calls += 1
            for a, b in parse_conflict_response(raw, len(clips)):
                clips[a - 1]["conflicts_with"].append(b)
                clips[b - 1]["conflicts_with"].append(a)
        except Exception as e:
            # A conflict-check failure must not discard perfectly good clips.
            errors.append(f"conflict check unavailable: {e}")

    # The skip report is a claim: "these videos contain nothing that answers you." If the
    # gate never returned verdicts we have not checked, so we must not make that claim —
    # otherwise a rate limit renders as "4h you can skip", which is worse than no answer.
    # A failed CONFLICT check does not invalidate it; only a failed gate does.
    skipped = (build_skip_report(all_videos, {c["video_id"] for c in clips}) if gate_ran
               else {"video_count": 0, "total_seconds": 0, "video_ids": []})

    return {
        "question": question,
        "workspace_id": workspace_id,
        "provider": os.environ.get("LLM_BACKEND", "auto"),
        "clips": clips,
        "skipped": skipped,
        "gate_ran": gate_ran,
        "llm_calls": llm_calls,
        "rejections": rejections,
        "errors": errors,
    }


def render_clips(result: dict) -> str:
    """Plain-text output. No rich dependency, so it works when piped or in CI."""
    from retrieval.context import format_timestamp

    lines: list[str] = []
    clips = result["clips"]
    skipped = result["skipped"]

    if result["errors"]:
        lines.append("ERRORS (results below may be incomplete):")
        for err in result["errors"]:
            lines.append(f"  ! {err}")
        lines.append("")

    if not clips:
        # "we checked and found nothing" and "we could not check" are different facts.
        # Reporting the second as the first is how a tool teaches people not to trust it.
        if result.get("gate_ran", True):
            lines.append(f'No clip in this workspace answers: "{result["question"]}"')
            lines.append("The topic may be mentioned without being answered.")
        else:
            lines.append(f'COULD NOT DETERMINE an answer for: "{result["question"]}"')
            lines.append("The answer gate did not run, so nothing here has been checked. "
                         "This is not the same as 'no answer exists' — retry.")
        return "\n".join(lines)

    lines.append(f'{len(clips)} clip(s) answer: "{result["question"]}"')
    lines.append("")

    for c in clips:
        mark = "~" if c["is_estimated"] else ""
        start = format_timestamp(c["start_seconds"])
        end = format_timestamp(c["end_seconds"])
        lines.append(f'[{c["rank"]}] {c["channel"]} — {c["video_title"]}')
        lines.append(f'    {mark}{start} → {mark}{end}   {c["watch_url"]}')
        lines.append(f'    "{c["span"]}"')
        if c["conflicts_with"]:
            others = ", ".join(f"[{n}]" for n in c["conflicts_with"])
            lines.append(f"    ! CONFLICTS with {others}")
        lines.append("")

    if skipped["video_count"]:
        saved = format_duration(skipped["total_seconds"])
        lines.append(f'{skipped["video_count"]} video(s) had no answering clip '
                     f'— {saved} you can skip')

    if result["rejections"]:
        lines.append(f'({len(result["rejections"])} model output(s) rejected by validation)')

    return "\n".join(lines)


if __name__ == "__main__":
    # Offline self-tests, matching the convention in rag/README.md "Offline self-tests".
    # No network, no models, no API key — every guard below is a pure function.
    #
    #   python3 retrieval/clips.py --test-gate
    if len(sys.argv) > 1 and sys.argv[1] == "--test-gate":
        chunks = [{"chunk_id": "c1", "video_id": "v1", "text": "Creatine retention is intramuscular."}]

        # A span the chunk really contains survives as "answers".
        v, r = parse_answer_gate_response(
            json.dumps({"verdicts": [
                {"chunk_id": "c1", "verdict": "answers", "span": "retention is intramuscular"}]}),
            chunks)
        assert v[0]["verdict"] == "answers" and not r, (v, r)

        # A span the chunk does NOT contain is refused, not shown.
        v, r = parse_answer_gate_response(
            json.dumps({"verdicts": [
                {"chunk_id": "c1", "verdict": "answers", "span": "creatine is dangerous"}]}),
            chunks)
        assert v[0]["verdict"] == "mentions" and r, (v, r)

        # An invented chunk_id never reaches the caller.
        v, r = parse_answer_gate_response(
            json.dumps({"verdicts": [
                {"chunk_id": "nope", "verdict": "answers", "span": "x"}]}),
            chunks)
        assert v == [] and r, (v, r)

        # Conflict indices outside the clip list are discarded.
        assert parse_conflict_response('{"conflicts": [[1, 2]]}', 2) == [(1, 2)]
        assert parse_conflict_response('{"conflicts": [[1, 9]]}', 2) == []

        # Links seek early and clamp at zero.
        assert build_watch_url("abc", 1170.0) == "https://youtu.be/abc?t=1167"
        assert build_watch_url("abc", 1.0) == "https://youtu.be/abc?t=0"

        # Unparseable output is an INFRA failure (ValueError), never a quiet verdict.
        try:
            parse_answer_gate_response("not json", chunks)
            raise AssertionError("expected ValueError on unparseable output")
        except ValueError:
            pass

        print("gate guards OK (verbatim, invented ids, conflict indices, links, infra errors)")
        sys.exit(0)

    print(__doc__)
    print("Run the offline guards with:  python3 retrieval/clips.py --test-gate")
