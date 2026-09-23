"""
Tests for the answer gate — offline, no network, no LLM calls, no model loads.

  python3 -m pytest rag/tests/test_clips.py -v
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from retrieval.clips import (
    GATE_VERDICTS,
    build_answer_gate_prompt,
    normalize_whitespace,
    parse_answer_gate_response,
)

CHUNKS = [
    {"chunk_id": "vid1_c14", "video_id": "vid1", "channel": "@A",
     "text": "Water retention from creatine is intramuscular, not subcutaneous."},
    {"chunk_id": "vid2_c03", "video_id": "vid2", "channel": "@B",
     "text": "I take creatine every morning with my coffee."},
]


def _reply(verdicts):
    return json.dumps({"verdicts": verdicts})


# ─── WHITESPACE NORMALIZATION ─────────────────────────────────────────────────

def test_normalize_whitespace_collapses_runs():
    assert normalize_whitespace("a   b\n\tc") == "a b c"


def test_normalize_whitespace_strips_ends():
    assert normalize_whitespace("  hello  ") == "hello"


# ─── PROMPT ───────────────────────────────────────────────────────────────────

def test_prompt_includes_question_and_every_chunk_id():
    prompt = build_answer_gate_prompt("does creatine cause bloating?", CHUNKS)
    assert "does creatine cause bloating?" in prompt
    assert "vid1_c14" in prompt
    assert "vid2_c03" in prompt


def test_prompt_states_all_three_verdicts():
    prompt = build_answer_gate_prompt("q", CHUNKS)
    for verdict in GATE_VERDICTS:
        assert verdict in prompt


# ─── PARSER: STRUCTURE ────────────────────────────────────────────────────────

def test_parses_a_clean_answers_verdict():
    raw = _reply([{"chunk_id": "vid1_c14", "verdict": "answers",
                   "span": "intramuscular, not subcutaneous"}])
    verdicts, rejections = parse_answer_gate_response(raw, CHUNKS)
    assert rejections == []
    assert len(verdicts) == 1
    assert verdicts[0]["verdict"] == "answers"
    assert verdicts[0]["chunk_id"] == "vid1_c14"


def test_strips_markdown_fences():
    raw = ('```json\n' + _reply([{"chunk_id": "vid2_c03", "verdict": "unrelated",
                                  "span": ""}]) + '\n```')
    verdicts, rejections = parse_answer_gate_response(raw, CHUNKS)
    assert len(verdicts) == 1
    assert verdicts[0]["verdict"] == "unrelated"


def test_unparseable_reply_raises():
    with pytest.raises(ValueError):
        parse_answer_gate_response("this is not json at all", CHUNKS)


# ─── PARSER: HALLUCINATION GUARDS ─────────────────────────────────────────────

def test_invented_chunk_id_is_rejected_not_returned():
    raw = _reply([{"chunk_id": "vid9_c99", "verdict": "answers", "span": "anything"}])
    verdicts, rejections = parse_answer_gate_response(raw, CHUNKS)
    assert verdicts == []
    assert len(rejections) == 1
    assert "vid9_c99" in rejections[0]["reason"]


def test_invalid_verdict_value_is_rejected():
    raw = _reply([{"chunk_id": "vid1_c14", "verdict": "probably", "span": "x"}])
    verdicts, rejections = parse_answer_gate_response(raw, CHUNKS)
    assert verdicts == []
    assert len(rejections) == 1


def test_answers_with_span_not_in_chunk_is_downgraded_to_mentions():
    raw = _reply([{"chunk_id": "vid1_c14", "verdict": "answers",
                   "span": "creatine is completely safe for your kidneys"}])
    verdicts, rejections = parse_answer_gate_response(raw, CHUNKS)
    assert len(verdicts) == 1
    assert verdicts[0]["verdict"] == "mentions"
    assert len(rejections) == 1


def test_span_matching_tolerates_whitespace_differences():
    chunks = [{"chunk_id": "c1", "video_id": "v", "channel": "@A",
               "text": "Water  retention\nis intramuscular."}]
    raw = _reply([{"chunk_id": "c1", "verdict": "answers",
                   "span": "Water retention is intramuscular"}])
    verdicts, rejections = parse_answer_gate_response(raw, chunks)
    assert rejections == []
    assert verdicts[0]["verdict"] == "answers"


def test_answers_with_empty_span_is_downgraded():
    raw = _reply([{"chunk_id": "vid1_c14", "verdict": "answers", "span": ""}])
    verdicts, rejections = parse_answer_gate_response(raw, CHUNKS)
    assert verdicts[0]["verdict"] == "mentions"
    assert len(rejections) == 1


def test_mentions_verdict_does_not_require_a_valid_span():
    raw = _reply([{"chunk_id": "vid2_c03", "verdict": "mentions", "span": ""}])
    verdicts, rejections = parse_answer_gate_response(raw, CHUNKS)
    assert rejections == []
    assert verdicts[0]["verdict"] == "mentions"


# ─── WATCH LINKS ──────────────────────────────────────────────────────────────

from retrieval.clips import build_skip_report, build_watch_url, format_duration


def test_watch_url_starts_three_seconds_early():
    assert build_watch_url("abc123", 1170.0) == "https://youtu.be/abc123?t=1167"


def test_watch_url_truncates_fractional_seconds():
    assert build_watch_url("abc123", 1170.9) == "https://youtu.be/abc123?t=1167"


def test_watch_url_clamps_at_zero_instead_of_going_negative():
    assert build_watch_url("abc123", 1.0) == "https://youtu.be/abc123?t=0"


def test_watch_url_clamps_at_zero_for_a_zero_start():
    assert build_watch_url("abc123", 0.0) == "https://youtu.be/abc123?t=0"


def test_watch_url_lead_is_overridable():
    assert build_watch_url("abc123", 100.0, lead=0) == "https://youtu.be/abc123?t=100"


# ─── SKIP REPORT ──────────────────────────────────────────────────────────────

VIDEOS = [
    {"video_id": "v1", "duration_seconds": 1440},
    {"video_id": "v2", "duration_seconds": 600},
    {"video_id": "v3", "duration_seconds": 900},
]


def test_skip_report_counts_videos_with_no_answering_clip():
    report = build_skip_report(VIDEOS, {"v1"})
    assert report["video_count"] == 2
    assert report["total_seconds"] == 1500
    assert report["video_ids"] == ["v2", "v3"]


def test_skip_report_is_empty_when_every_video_answered():
    report = build_skip_report(VIDEOS, {"v1", "v2", "v3"})
    assert report["video_count"] == 0
    assert report["total_seconds"] == 0
    assert report["video_ids"] == []


def test_skip_report_treats_missing_duration_as_zero():
    videos = [{"video_id": "v1"}, {"video_id": "v2", "duration_seconds": None}]
    report = build_skip_report(videos, set())
    assert report["video_count"] == 2
    assert report["total_seconds"] == 0


def test_format_duration_uses_hours_and_minutes():
    assert format_duration(13860) == "3h 51m"


def test_format_duration_omits_hours_under_one_hour():
    assert format_duration(720) == "12m"


def test_format_duration_handles_zero():
    assert format_duration(0) == "0m"


# ─── CONFLICT DETECTION ───────────────────────────────────────────────────────

from retrieval.clips import build_conflict_prompt, parse_conflict_response

CLIPS = [
    {"chunk_id": "vid1_c14", "channel": "@A", "span": "retention is intramuscular"},
    {"chunk_id": "vid2_c03", "channel": "@B", "span": "it makes you look puffy"},
]


def test_conflict_prompt_numbers_clips_from_one():
    prompt = build_conflict_prompt(CLIPS)
    assert "[1]" in prompt
    assert "[2]" in prompt
    assert "[0]" not in prompt


def test_conflict_prompt_includes_each_span():
    prompt = build_conflict_prompt(CLIPS)
    assert "retention is intramuscular" in prompt
    assert "it makes you look puffy" in prompt


def test_parses_a_conflicting_pair():
    assert parse_conflict_response('{"conflicts": [[1, 2]]}', 2) == [(1, 2)]


def test_parses_an_empty_conflict_list():
    assert parse_conflict_response('{"conflicts": []}', 2) == []


def test_conflict_pairs_are_normalized_to_ascending_order():
    assert parse_conflict_response('{"conflicts": [[2, 1]]}', 2) == [(1, 2)]


def test_duplicate_conflict_pairs_are_deduplicated():
    assert parse_conflict_response('{"conflicts": [[1, 2], [2, 1]]}', 2) == [(1, 2)]


def test_out_of_range_index_is_discarded():
    assert parse_conflict_response('{"conflicts": [[1, 9]]}', 2) == []


def test_zero_index_is_discarded_because_clips_are_one_based():
    assert parse_conflict_response('{"conflicts": [[0, 1]]}', 2) == []


def test_self_pair_is_discarded():
    assert parse_conflict_response('{"conflicts": [[1, 1]]}', 2) == []


def test_malformed_pair_shape_is_discarded():
    assert parse_conflict_response('{"conflicts": [[1], [1, 2, 3], "nope"]}', 3) == []


def test_unparseable_conflict_reply_raises():
    with pytest.raises(ValueError):
        parse_conflict_response("not json", 2)
