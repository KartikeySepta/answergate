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
