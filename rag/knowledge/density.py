"""
CLAIM DENSITY — how much of a video's runtime contains checkable claims.

Answers the question you have BEFORE you have a question: is this 24-minute video worth
24 minutes? One URL, no query, no prompt.

Read the honesty rules before changing anything here, because they are the point:

  1. It is a FLOOR, never a measurement. Claim extraction is an LLM step with imperfect
     recall, so a chunk may hold a claim the model missed. Always "AT LEAST n minutes",
     never "only n minutes".
  2. It is CLAIM density, not quality. A good explainer, a story, or a worked example
     legitimately yields few atomic claims and is not padding. This module must never be
     renamed or re-presented as a "slop score" — that would be a judgement we cannot
     defend, on data that does not support it.
  3. Percentages round to whole numbers. Chunk boundaries are partly estimated by word
     position (ingestion/chunker.py), so a decimal place would be false precision.

Chunks deliberately OVERLAP (CHUNK_OVERLAP_WORDS), so summing their durations
double-counts. The interval union below is not an optimization — it is required for the
number to mean anything.

Offline self-test (no network, no models):
  python3 knowledge/density.py --test-union
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def merge_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Union of possibly-overlapping [start, end] spans, sorted and coalesced.

    Touching spans (end == next start) merge: a chunk boundary is not a gap in speech.
    """
    if not intervals:
        return []
    ordered = sorted((min(a, b), max(a, b)) for a, b in intervals)
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:                      # overlapping or touching
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def union_seconds(intervals: list[tuple[float, float]]) -> float:
    return sum(end - start for start, end in merge_intervals(intervals))


def compute_density(videos: list[dict], chunks: list[dict], claims: list[dict]) -> list[dict]:
    """Per-video claim density, derived entirely from counted data.

    A chunk is "claim-bearing" if at least one validated claim cites it as evidence. We go
    through claim.evidence[].chunk_id rather than claim.video_id because evidence is the
    thing claim_extractor validates against real chunks — it is the trustworthy link.
    """
    chunk_by_id = {c["chunk_id"]: c for c in chunks}

    bearing_by_video: dict[str, list[tuple[float, float]]] = {}
    claims_by_video: dict[str, int] = {}
    estimated_by_video: dict[str, bool] = {}
    counted_chunks: set[str] = set()

    for claim in claims:
        for ref in claim.get("evidence") or []:
            chunk = chunk_by_id.get(ref.get("chunk_id"))
            if chunk is None:
                continue                            # evidence we cannot verify earns nothing
            vid = chunk["video_id"]
            claims_by_video[vid] = claims_by_video.get(vid, 0) + 1
            if chunk["chunk_id"] in counted_chunks:
                continue                            # one chunk contributes its span once
            counted_chunks.add(chunk["chunk_id"])
            bearing_by_video.setdefault(vid, []).append(
                (float(chunk["start_seconds"]), float(chunk["end_seconds"])))
            if chunk.get("is_estimated"):
                estimated_by_video[vid] = True

    out = []
    for video in videos:
        vid = video["video_id"]
        duration = int(video.get("duration_seconds") or 0)
        segments = merge_intervals(bearing_by_video.get(vid, []))
        bearing = sum(e - s for s, e in segments)
        claim_count = claims_by_video.get(vid, 0)
        out.append({
            "video_id": vid,
            "video_title": video.get("title", ""),
            "channel": video.get("channel", ""),
            "upload_date": video.get("upload_date", ""),
            "duration_seconds": duration,
            "claim_bearing_seconds": round(bearing),
            # Whole-number percent on purpose (see rule 3 in the module docstring).
            "density_percent": round(100 * bearing / duration) if duration else 0,
            "claim_count": claim_count,
            "claims_per_minute": round(claim_count / (duration / 60), 2) if duration else 0.0,
            "any_estimated_timestamps": estimated_by_video.get(vid, False),
            "segments": [{"start_seconds": round(s, 1), "end_seconds": round(e, 1)}
                         for s, e in segments],
        })
    return out


def compute_density_for_workspace(workspace_id: str) -> list[dict]:
    from core.config import WORKSPACES_DIR
    base = Path(WORKSPACES_DIR) / workspace_id

    def load(name):
        path = base / f"{name}.json"
        if not path.exists():
            raise SystemExit(f"missing {path}. Run: python3 cli.py add <url> {workspace_id}")
        return json.loads(path.read_text())

    rows = compute_density(load("videos"), load("chunks"), load("claims"))
    (base / "density.json").write_text(json.dumps(rows, indent=2))
    return rows


def render_density(rows: list[dict]) -> str:
    """Plain text. Phrasing is load-bearing: 'at least' is rule 1, not politeness.

    Leads with claims-per-minute, NOT the percentage. See the saturation note below: on
    real corpora density_percent sits at 87-100% for everything and tells you nothing.
    Showing it first would imply a discrimination the number does not have.
    """
    from retrieval.clips import format_duration

    if not rows:
        return "No videos in this workspace yet."

    lines = []
    for r in sorted(rows, key=lambda x: -x["claims_per_minute"]):
        mark = "~" if r["any_estimated_timestamps"] else ""
        lines.append(f'{r["channel"]} — {r["video_title"][:62]}')
        lines.append(
            f'  {r["claims_per_minute"]} checkable claims/min '
            f'({r["claim_count"]} claims over {format_duration(r["duration_seconds"])}) '
            f'— at least {mark}{format_duration(r["claim_bearing_seconds"])} is claim-bearing')
        lines.append("")

    lines.append("Claim density, not quality: a good explainer or a worked example")
    lines.append("legitimately yields few atomic claims. Extraction recall is imperfect,")
    lines.append("so these are floors — there may be more, never less.")
    lines.append("")
    lines.append("CAVEAT, measured: the claim-bearing PERCENTAGE saturates. Across 7 videos")
    lines.append("from 6 creators it ranged 87-100%, because chunks are ~180 words and")
    lines.append("almost every chunk yields a claim — so it measures chunk size, not")
    lines.append("substance. Treat this as a rough diagnostic, not a way to rank videos.")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test-union":
        # Overlap is the whole reason this module exists; chunks overlap by design.
        assert merge_intervals([]) == []
        assert merge_intervals([(0, 10)]) == [(0, 10)]
        assert merge_intervals([(0, 10), (5, 15)]) == [(0, 15)], "overlap must coalesce"
        assert merge_intervals([(5, 15), (0, 10)]) == [(0, 15)], "order must not matter"
        assert merge_intervals([(0, 10), (10, 20)]) == [(0, 20)], "touching spans merge"
        assert merge_intervals([(0, 10), (20, 30)]) == [(0, 10), (20, 30)], "gaps stay gaps"
        assert merge_intervals([(0, 100), (10, 20)]) == [(0, 100)], "nesting collapses"
        assert union_seconds([(0, 10), (5, 15)]) == 15.0, "naive sum would say 20"
        print("interval union OK (overlap, order, touching, gaps, nesting)")
        sys.exit(0)

    workspace_id = sys.argv[1] if len(sys.argv) > 1 else "rag_research"
    print(render_density(compute_density_for_workspace(workspace_id)))
