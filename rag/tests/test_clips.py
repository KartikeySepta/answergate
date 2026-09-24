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


# ─── ORCHESTRATION ────────────────────────────────────────────────────────────

from retrieval.clips import find_clips

# rerank_score is present because real retrieval always supplies it (reranker.py:48) and
# because it is the PRIMARY sort key — fixtures without it would let the is_estimated
# tie-break silently reorder results and hide a ranking bug.
RETRIEVED = [
    {"chunk_id": "v1_c1", "video_id": "v1", "video_title": "T1", "channel": "@A",
     "start_seconds": 1170.0, "end_seconds": 1218.0, "is_estimated": True,
     "rerank_score": 0.91,
     "text": "Water retention from creatine is intramuscular, not subcutaneous."},
    {"chunk_id": "v2_c1", "video_id": "v2", "video_title": "T2", "channel": "@B",
     "start_seconds": 482.0, "end_seconds": 554.0, "is_estimated": False,
     "rerank_score": 0.80,
     "text": "Creatine makes you look puffy and bloated all over."},
    {"chunk_id": "v3_c1", "video_id": "v3", "video_title": "T3", "channel": "@C",
     "start_seconds": 10.0, "end_seconds": 70.0, "is_estimated": False,
     "rerank_score": 0.42,
     "text": "I keep my creatine tub next to the blender."},
]

ALL_VIDEOS = [
    {"video_id": "v1", "duration_seconds": 1440},
    {"video_id": "v2", "duration_seconds": 600},
    {"video_id": "v3", "duration_seconds": 900},
    {"video_id": "v4", "duration_seconds": 1200},
]


def _fake_generate(gate_reply, conflict_reply='{"conflicts": []}'):
    """Returns a generate_fn that answers the gate call first, then the conflict call."""
    calls = []

    def generate_fn(prompt, task=None):
        calls.append(task)
        return gate_reply if len(calls) == 1 else conflict_reply

    generate_fn.calls = calls
    return generate_fn


GATE_TWO_ANSWERS = json.dumps({"verdicts": [
    {"chunk_id": "v1_c1", "verdict": "answers", "span": "intramuscular, not subcutaneous"},
    {"chunk_id": "v2_c1", "verdict": "answers", "span": "puffy and bloated all over"},
    {"chunk_id": "v3_c1", "verdict": "mentions", "span": ""},
]})


def _run(gate_reply, conflict_reply='{"conflicts": []}'):
    return find_clips(
        "does creatine cause bloating?", "fitness",
        retrieve_fn=lambda q, w: RETRIEVED,
        generate_fn=_fake_generate(gate_reply, conflict_reply),
        load_videos_fn=lambda w: ALL_VIDEOS,
    )


def test_only_answering_chunks_become_clips():
    result = _run(GATE_TWO_ANSWERS)
    assert [c["chunk_id"] for c in result["clips"]] == ["v1_c1", "v2_c1"]


def test_clips_are_ranked_from_one():
    result = _run(GATE_TWO_ANSWERS)
    assert [c["rank"] for c in result["clips"]] == [1, 2]


def test_clip_carries_a_watch_url_seeking_early():
    result = _run(GATE_TWO_ANSWERS)
    assert result["clips"][0]["watch_url"] == "https://youtu.be/v1?t=1167"


def test_relevance_outranks_timestamp_quality():
    """is_estimated is a TIE-BREAK, never a primary sort.

    v1_c1 has estimated timestamps but a higher rerank_score than v2_c1. It must still
    rank first — demoting a more relevant clip because its timestamp is approximate would
    make the tool worse at its actual job.
    """
    result = _run(GATE_TWO_ANSWERS)
    assert result["clips"][0]["chunk_id"] == "v1_c1"
    assert result["clips"][0]["is_estimated"] is True


def test_estimated_loses_only_on_an_exact_score_tie():
    tied = [
        {**RETRIEVED[0], "rerank_score": 0.80},   # estimated, tied score
        {**RETRIEVED[1], "rerank_score": 0.80},   # exact, tied score
    ]
    gate = json.dumps({"verdicts": [
        {"chunk_id": "v1_c1", "verdict": "answers", "span": "intramuscular, not subcutaneous"},
        {"chunk_id": "v2_c1", "verdict": "answers", "span": "puffy and bloated all over"},
    ]})
    result = find_clips(
        "q", "fitness",
        retrieve_fn=lambda q, w: tied,
        generate_fn=_fake_generate(gate),
        load_videos_fn=lambda w: ALL_VIDEOS,
    )
    assert result["clips"][0]["chunk_id"] == "v2_c1", "exact timestamps win an exact tie"


def test_mentioned_but_not_answering_video_counts_as_skipped():
    result = _run(GATE_TWO_ANSWERS)
    # v3 only mentions; v4 never retrieved. Both are skippable.
    assert result["skipped"]["video_count"] == 2
    assert sorted(result["skipped"]["video_ids"]) == ["v3", "v4"]
    assert result["skipped"]["total_seconds"] == 2100


def test_uses_two_llm_calls_when_there_are_multiple_clips():
    result = _run(GATE_TWO_ANSWERS)
    assert result["llm_calls"] == 2


def test_skips_the_conflict_call_with_fewer_than_two_clips():
    gate = json.dumps({"verdicts": [
        {"chunk_id": "v1_c1", "verdict": "answers", "span": "intramuscular, not subcutaneous"},
        {"chunk_id": "v2_c1", "verdict": "mentions", "span": ""},
        {"chunk_id": "v3_c1", "verdict": "unrelated", "span": ""},
    ]})
    result = _run(gate)
    assert len(result["clips"]) == 1
    assert result["llm_calls"] == 1


def test_conflicts_are_recorded_on_both_clips():
    result = _run(GATE_TWO_ANSWERS, '{"conflicts": [[1, 2]]}')
    assert result["clips"][0]["conflicts_with"] == [2]
    assert result["clips"][1]["conflicts_with"] == [1]


def test_no_clips_when_nothing_answers():
    gate = json.dumps({"verdicts": [
        {"chunk_id": c["chunk_id"], "verdict": "mentions", "span": ""} for c in RETRIEVED
    ]})
    result = _run(gate)
    assert result["clips"] == []
    assert result["skipped"]["video_count"] == 4


def test_gate_infra_failure_is_reported_not_silently_empty():
    def exploding_generate(prompt, task=None):
        raise RuntimeError("all providers exhausted")

    result = find_clips(
        "q", "fitness",
        retrieve_fn=lambda q, w: RETRIEVED,
        generate_fn=exploding_generate,
        load_videos_fn=lambda w: ALL_VIDEOS,
    )
    assert result["clips"] == []
    assert result["errors"], "an infra failure must be surfaced, not look like 'nothing answers'"


def test_conflict_failure_does_not_discard_the_clips():
    def generate_fn(prompt, task=None):
        if "CONTRADICT" in prompt.upper():
            raise RuntimeError("rate limited")
        return GATE_TWO_ANSWERS

    result = find_clips(
        "q", "fitness",
        retrieve_fn=lambda q, w: RETRIEVED,
        generate_fn=generate_fn,
        load_videos_fn=lambda w: ALL_VIDEOS,
    )
    assert len(result["clips"]) == 2
    assert result["errors"]


def test_respects_the_clip_cap():
    from core.config import CLIP_MAX_RETURNED
    many = [
        {"chunk_id": f"v{i}_c1", "video_id": f"v{i}", "video_title": "T", "channel": "@X",
         "start_seconds": 10.0, "end_seconds": 70.0, "is_estimated": False,
         "rerank_score": 1.0 - (i / 100.0),
         "text": f"answer number {i} here"}
        for i in range(CLIP_MAX_RETURNED + 3)
    ]
    gate = json.dumps({"verdicts": [
        {"chunk_id": c["chunk_id"], "verdict": "answers", "span": c["text"]} for c in many
    ]})
    result = find_clips(
        "q", "fitness",
        retrieve_fn=lambda q, w: many,
        generate_fn=_fake_generate(gate),
        load_videos_fn=lambda w: ALL_VIDEOS,
    )
    assert len(result["clips"]) == CLIP_MAX_RETURNED


# ─── RENDERER ─────────────────────────────────────────────────────────────────

from retrieval.clips import render_clips

RESULT = {
    "question": "does creatine cause bloating?",
    "workspace_id": "fitness",
    "provider": "gemini",
    "clips": [
        {"rank": 1, "chunk_id": "v1_c1", "video_id": "v1", "video_title": "T1",
         "channel": "@A", "start_seconds": 1170.0, "end_seconds": 1218.0,
         "is_estimated": True, "span": "intramuscular, not subcutaneous",
         "watch_url": "https://youtu.be/v1?t=1167", "conflicts_with": [2]},
        {"rank": 2, "chunk_id": "v2_c1", "video_id": "v2", "video_title": "T2",
         "channel": "@B", "start_seconds": 482.0, "end_seconds": 554.0,
         "is_estimated": False, "span": "puffy and bloated all over",
         "watch_url": "https://youtu.be/v2?t=479", "conflicts_with": [1]},
    ],
    "skipped": {"video_count": 9, "total_seconds": 13860, "video_ids": []},
    "llm_calls": 2, "rejections": [], "errors": [],
}


def test_render_shows_channel_and_span():
    out = render_clips(RESULT)
    assert "@A" in out
    assert "intramuscular, not subcutaneous" in out


def test_render_shows_the_watch_url():
    assert "https://youtu.be/v1?t=1167" in render_clips(RESULT)


def test_render_marks_estimated_timestamps_with_a_tilde():
    assert "~19:30" in render_clips(RESULT)


def test_render_does_not_mark_exact_timestamps():
    out = render_clips(RESULT)
    assert "~8:02" not in out
    assert "8:02" in out


def test_render_flags_conflicts():
    assert "CONFLICTS" in render_clips(RESULT).upper()


def test_render_reports_time_saved():
    out = render_clips(RESULT)
    assert "9" in out
    assert "3h 51m" in out


def test_render_says_so_when_nothing_answers():
    empty = {**RESULT, "clips": []}
    assert "no clip" in render_clips(empty).lower()


def test_render_surfaces_errors_distinctly_from_no_answers():
    failed = {**RESULT, "clips": [], "errors": ["answer gate failed: boom"]}
    out = render_clips(failed).lower()
    assert "error" in out or "failed" in out


# ─── REGRESSION GUARDS (defects found reviewing the first implementation) ──────

def test_duplicate_verdict_for_same_chunk_keeps_the_first_and_rejects_the_rest():
    """A model returning one chunk twice with conflicting verdicts is not deciding.

    Keeping both let the later verdict silently overwrite the earlier one via span_by_id.
    """
    chunks = [{"chunk_id": "c1", "video_id": "v", "text": "alpha beta gamma"}]
    raw = json.dumps({"verdicts": [
        {"chunk_id": "c1", "verdict": "answers", "span": "alpha beta"},
        {"chunk_id": "c1", "verdict": "unrelated", "span": ""},
    ]})
    verdicts, rejections = parse_answer_gate_response(raw, chunks)
    assert len(verdicts) == 1
    assert verdicts[0]["verdict"] == "answers"
    assert any("duplicate" in r["reason"] for r in rejections)


def test_clip_with_missing_timestamps_does_not_crash_the_renderer():
    """format_timestamp does int(seconds); a None start_seconds used to raise TypeError."""
    result = find_clips(
        "q", "fitness",
        retrieve_fn=lambda q, w: [
            {"chunk_id": "c1", "video_id": "v1", "video_title": "T", "channel": "@A",
             "rerank_score": 0.9, "text": "alpha beta gamma"}],   # no start/end at all
        generate_fn=_fake_generate(json.dumps({"verdicts": [
            {"chunk_id": "c1", "verdict": "answers", "span": "alpha beta"}]})),
        load_videos_fn=lambda w: [{"video_id": "v1", "duration_seconds": 60}],
    )
    assert result["clips"][0]["start_seconds"] == 0.0
    render_clips(result)   # must not raise


def test_gate_failure_does_not_claim_videos_are_skippable():
    """"4h you can skip" after a rate limit is worse than no answer at all.

    The skip report asserts "these videos contain nothing that answers you." If the gate
    never ran, that has not been checked and must not be claimed.
    """
    result = find_clips(
        "q", "fitness",
        retrieve_fn=lambda q, w: RETRIEVED,
        generate_fn=lambda p, task=None: (_ for _ in ()).throw(RuntimeError("rate limited")),
        load_videos_fn=lambda w: ALL_VIDEOS,
    )
    assert result["gate_ran"] is False
    assert result["skipped"]["video_count"] == 0
    assert result["skipped"]["total_seconds"] == 0
    assert result["errors"]


def test_conflict_failure_still_allows_the_skip_report():
    """Only a failed GATE invalidates the skip report; a failed conflict check does not."""
    def generate_fn(prompt, task=None):
        if "CONTRADICT" in prompt.upper():
            raise RuntimeError("rate limited")
        return GATE_TWO_ANSWERS

    result = find_clips(
        "q", "fitness",
        retrieve_fn=lambda q, w: RETRIEVED,
        generate_fn=generate_fn,
        load_videos_fn=lambda w: ALL_VIDEOS,
    )
    assert result["gate_ran"] is True
    assert result["skipped"]["video_count"] == 2
    assert result["errors"]


def test_renderer_omits_the_skip_line_when_the_gate_failed():
    result = find_clips(
        "q", "fitness",
        retrieve_fn=lambda q, w: RETRIEVED,
        generate_fn=lambda p, task=None: (_ for _ in ()).throw(RuntimeError("boom")),
        load_videos_fn=lambda w: ALL_VIDEOS,
    )
    out = render_clips(result)
    assert "you can skip" not in out
    assert "ERRORS" in out


def test_renderer_distinguishes_could_not_check_from_found_nothing():
    """These are different facts. Reporting the second as the first destroys trust."""
    checked = {**RESULT, "clips": [], "errors": [], "gate_ran": True}
    not_checked = {**RESULT, "clips": [], "errors": ["gate failed: boom"], "gate_ran": False}

    assert "no clip in this workspace answers" in render_clips(checked).lower()
    out = render_clips(not_checked).lower()
    assert "could not determine" in out
    assert "no clip in this workspace answers" not in out


# ─── OVERLAP DEDUPE ───────────────────────────────────────────────────────────

OVERLAPPING = [
    {"chunk_id": "v1_c1", "video_id": "v1", "video_title": "T", "channel": "@A",
     "start_seconds": 240.0, "end_seconds": 310.0, "is_estimated": True, "rerank_score": 0.90,
     "text": "MCP is an abstraction above APIs. APIs still exist. MCP makes them friendly."},
    {"chunk_id": "v1_c2", "video_id": "v1", "video_title": "T", "channel": "@A",
     "start_seconds": 300.0, "end_seconds": 370.0, "is_estimated": True, "rerank_score": 0.85,
     "text": "APIs still exist. MCP makes them friendly. Take a practical example."},
    {"chunk_id": "v2_c1", "video_id": "v2", "video_title": "T2", "channel": "@B",
     "start_seconds": 380.0, "end_seconds": 450.0, "is_estimated": False, "rerank_score": 0.80,
     "text": "Your APIs don't go anywhere. An API is a point-to-point connection."},
]


def test_overlapping_chunks_do_not_produce_duplicate_clips():
    """Chunks overlap by CHUNK_OVERLAP_WORDS, so one sentence lives in two of them.

    Observed on real data: three of five demo questions returned the identical quote twice.
    """
    gate = json.dumps({"verdicts": [
        {"chunk_id": "v1_c1", "verdict": "answers", "span": "APIs still exist"},
        {"chunk_id": "v1_c2", "verdict": "answers", "span": "APIs still exist"},
        {"chunk_id": "v2_c1", "verdict": "answers", "span": "Your APIs don't go anywhere"},
    ]})
    result = find_clips(
        "does MCP replace APIs?", "w",
        retrieve_fn=lambda q, w: OVERLAPPING,
        generate_fn=_fake_generate(gate),
        load_videos_fn=lambda w: [{"video_id": "v1", "duration_seconds": 600},
                                  {"video_id": "v2", "duration_seconds": 600}],
    )
    spans = [c["span"] for c in result["clips"]]
    assert len(spans) == 2, spans
    assert spans[0] == "APIs still exist"
    assert spans[1] == "Your APIs don't go anywhere"


def test_dedupe_keeps_the_higher_ranked_of_a_duplicate_pair():
    gate = json.dumps({"verdicts": [
        {"chunk_id": "v1_c1", "verdict": "answers", "span": "APIs still exist"},
        {"chunk_id": "v1_c2", "verdict": "answers", "span": "APIs still exist"},
    ]})
    result = find_clips(
        "q", "w",
        retrieve_fn=lambda q, w: OVERLAPPING[:2],
        generate_fn=_fake_generate(gate),
        load_videos_fn=lambda w: [{"video_id": "v1", "duration_seconds": 600}],
    )
    assert len(result["clips"]) == 1
    assert result["clips"][0]["chunk_id"] == "v1_c1"   # rerank_score 0.90 beats 0.85


def test_a_span_contained_in_a_kept_span_is_also_deduped():
    """The overlap often yields one longer and one shorter quote of the same sentence."""
    gate = json.dumps({"verdicts": [
        {"chunk_id": "v1_c1", "verdict": "answers", "span": "APIs still exist. MCP makes them friendly"},
        {"chunk_id": "v1_c2", "verdict": "answers", "span": "APIs still exist"},
    ]})
    result = find_clips(
        "q", "w",
        retrieve_fn=lambda q, w: OVERLAPPING[:2],
        generate_fn=_fake_generate(gate),
        load_videos_fn=lambda w: [{"video_id": "v1", "duration_seconds": 600}],
    )
    assert len(result["clips"]) == 1


def test_dedupe_frees_slots_for_genuinely_different_answers():
    """Dedupe runs before the cap, so duplicates never consume the 5-clip budget."""
    from core.config import CLIP_MAX_RETURNED
    chunks = [{"chunk_id": f"c{i}", "video_id": f"v{i}", "video_title": "T", "channel": "@X",
               "start_seconds": 10.0, "end_seconds": 70.0, "is_estimated": False,
               "rerank_score": 1.0 - i / 100,
               "text": ("same answer here" if i < 4 else f"distinct answer {i}")}
              for i in range(CLIP_MAX_RETURNED + 4)]
    gate = json.dumps({"verdicts": [
        {"chunk_id": c["chunk_id"], "verdict": "answers", "span": c["text"]} for c in chunks]})
    result = find_clips(
        "q", "w",
        retrieve_fn=lambda q, w: chunks,
        generate_fn=_fake_generate(gate),
        load_videos_fn=lambda w: [],
    )
    spans = [c["span"] for c in result["clips"]]
    assert spans.count("same answer here") == 1, spans
    assert len([s for s in spans if s.startswith("distinct")]) == 5 - 1


# ─── SENTENCE-INDEX CONTRACT ──────────────────────────────────────────────────
# Root cause of llama3.2's unparseable replies: the gate asked the model to reproduce
# transcript text inside a JSON string, and transcripts are full of quote characters.
# The model now returns a sentence INDEX and we slice the text ourselves, so escaping
# cannot go wrong and the span is verbatim by construction rather than by validation.

SENT_CHUNKS = [
    {"chunk_id": "c1", "video_id": "v1", "channel": "@A",
     "text": 'APIs still exist. He said "MCP just wraps them" on stage. Nothing is replaced.'},
]


def _sent_reply(items):
    return json.dumps({"verdicts": items})


def test_prompt_numbers_each_sentence():
    prompt = build_answer_gate_prompt("does MCP replace APIs?", SENT_CHUNKS)
    assert "(1)" in prompt and "(2)" in prompt and "(3)" in prompt


def test_sentence_index_resolves_to_text_from_the_chunk():
    raw = _sent_reply([{"chunk_id": "c1", "verdict": "answers", "sentence": 1}])
    verdicts, rejections = parse_answer_gate_response(raw, SENT_CHUNKS)
    assert rejections == []
    assert verdicts[0]["verdict"] == "answers"
    assert verdicts[0]["span"] == "APIs still exist."


def test_span_is_taken_from_the_chunk_even_when_the_model_also_sends_one():
    """The model must never be the source of displayed text."""
    raw = _sent_reply([{"chunk_id": "c1", "verdict": "answers", "sentence": 1,
                        "span": "TEXT THE SOURCE NEVER SAID"}])
    verdicts, _ = parse_answer_gate_response(raw, SENT_CHUNKS)
    assert verdicts[0]["span"] == "APIs still exist."


def test_a_sentence_containing_quotes_survives_intact():
    """This is the whole point: quote chars no longer have to cross the JSON boundary."""
    raw = _sent_reply([{"chunk_id": "c1", "verdict": "answers", "sentence": 2}])
    verdicts, rejections = parse_answer_gate_response(raw, SENT_CHUNKS)
    assert rejections == []
    assert verdicts[0]["span"] == 'He said "MCP just wraps them" on stage.'


def test_out_of_range_sentence_index_is_downgraded():
    raw = _sent_reply([{"chunk_id": "c1", "verdict": "answers", "sentence": 99}])
    verdicts, rejections = parse_answer_gate_response(raw, SENT_CHUNKS)
    assert verdicts[0]["verdict"] == "mentions"
    assert rejections


def test_zero_sentence_index_is_downgraded_because_numbering_starts_at_one():
    raw = _sent_reply([{"chunk_id": "c1", "verdict": "answers", "sentence": 0}])
    verdicts, rejections = parse_answer_gate_response(raw, SENT_CHUNKS)
    assert verdicts[0]["verdict"] == "mentions"


def test_non_integer_sentence_is_downgraded_not_crashed():
    raw = _sent_reply([{"chunk_id": "c1", "verdict": "answers", "sentence": "two"}])
    verdicts, rejections = parse_answer_gate_response(raw, SENT_CHUNKS)
    assert verdicts[0]["verdict"] == "mentions"
    assert rejections


def test_model_that_ignores_the_format_and_sends_a_verbatim_span_still_works():
    """Defense in depth: a stronger model quoting correctly should not be punished."""
    raw = _sent_reply([{"chunk_id": "c1", "verdict": "answers", "span": "APIs still exist"}])
    verdicts, rejections = parse_answer_gate_response(raw, SENT_CHUNKS)
    assert verdicts[0]["verdict"] == "answers"
    assert rejections == []


def test_span_fallback_still_rejects_text_not_in_the_chunk():
    raw = _sent_reply([{"chunk_id": "c1", "verdict": "answers", "span": "totally invented"}])
    verdicts, rejections = parse_answer_gate_response(raw, SENT_CHUNKS)
    assert verdicts[0]["verdict"] == "mentions"
    assert rejections


def test_mentions_needs_no_sentence():
    raw = _sent_reply([{"chunk_id": "c1", "verdict": "mentions"}])
    verdicts, rejections = parse_answer_gate_response(raw, SENT_CHUNKS)
    assert rejections == []
    assert verdicts[0]["verdict"] == "mentions"
