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


def parse_answer_gate_response(raw: str, chunks: list[dict]) -> tuple[list[dict], list[dict]]:
    """Validate the gate's reply against the chunks we actually sent.

    Returns (verdicts, rejections). A rejection is never silently dropped — callers
    surface the count so a degraded model is visible rather than looking like a corpus
    with nothing to say.

    Raises ValueError if the reply is not parseable JSON at all. That is an infrastructure
    failure, not a verdict, and the caller must treat it as such.
    """
    try:
        parsed = json.loads(_strip_fences(raw))
    except Exception as e:
        raise ValueError(f"unparseable answer-gate reply: {e}")

    text_by_id = {c["chunk_id"]: c["text"] for c in chunks}
    verdicts: list[dict] = []
    rejections: list[dict] = []

    for item in parsed.get("verdicts", []):
        chunk_id = item.get("chunk_id", "")
        verdict = item.get("verdict", "")
        span = (item.get("span") or "").strip()

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

        verdicts.append({"chunk_id": chunk_id, "verdict": verdict, "span": span})

    return verdicts, rejections
