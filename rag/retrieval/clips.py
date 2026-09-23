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
    try:
        parsed = json.loads(_strip_fences(raw))
    except Exception as e:
        raise ValueError(f"unparseable conflict reply: {e}")

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
