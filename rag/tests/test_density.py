"""
Tests for claim density — offline, no network, no models.

  python3 -m pytest rag/tests/test_density.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from knowledge.density import (
    compute_density,
    merge_intervals,
    render_density,
    union_seconds,
)


# ─── INTERVAL UNION — chunks overlap by design, so this is correctness-critical ─

def test_empty_union():
    assert merge_intervals([]) == []


def test_overlapping_spans_coalesce():
    assert merge_intervals([(0, 10), (5, 15)]) == [(0, 15)]


def test_input_order_does_not_matter():
    assert merge_intervals([(5, 15), (0, 10)]) == [(0, 15)]


def test_touching_spans_merge_because_a_chunk_boundary_is_not_a_gap():
    assert merge_intervals([(0, 10), (10, 20)]) == [(0, 20)]


def test_gaps_are_preserved():
    assert merge_intervals([(0, 10), (20, 30)]) == [(0, 10), (20, 30)]


def test_nested_span_collapses_into_its_container():
    assert merge_intervals([(0, 100), (10, 20)]) == [(0, 100)]


def test_union_does_not_double_count_overlap():
    """The bug this module exists to avoid: naive summation would report 20."""
    assert union_seconds([(0, 10), (5, 15)]) == 15.0


def test_reversed_bounds_are_normalized():
    assert merge_intervals([(10, 0)]) == [(0, 10)]


# ─── DENSITY ──────────────────────────────────────────────────────────────────

VIDEOS = [{"video_id": "v1", "title": "T1", "channel": "@A",
           "upload_date": "20260411", "duration_seconds": 600}]

CHUNKS = [
    {"chunk_id": "v1_c1", "video_id": "v1", "start_seconds": 0.0,
     "end_seconds": 60.0, "is_estimated": False},
    {"chunk_id": "v1_c2", "video_id": "v1", "start_seconds": 50.0,
     "end_seconds": 110.0, "is_estimated": True},
    {"chunk_id": "v1_c3", "video_id": "v1", "start_seconds": 500.0,
     "end_seconds": 530.0, "is_estimated": False},
]


def _claim(cid, chunk_ids):
    return {"claim_id": cid, "video_id": "v1",
            "evidence": [{"chunk_id": c, "evidence_text": "x"} for c in chunk_ids]}


def test_density_uses_the_union_not_the_sum():
    """c1 and c2 overlap by 10s: union is 110, naive sum would be 120."""
    rows = compute_density(VIDEOS, CHUNKS, [_claim("a", ["v1_c1"]), _claim("b", ["v1_c2"])])
    assert rows[0]["claim_bearing_seconds"] == 110


def test_density_percent_is_a_whole_number():
    rows = compute_density(VIDEOS, CHUNKS, [_claim("a", ["v1_c1"])])
    assert rows[0]["density_percent"] == 10
    assert isinstance(rows[0]["density_percent"], int)


def test_disjoint_segments_are_reported_separately():
    rows = compute_density(VIDEOS, CHUNKS, [_claim("a", ["v1_c1"]), _claim("b", ["v1_c3"])])
    assert rows[0]["segments"] == [
        {"start_seconds": 0.0, "end_seconds": 60.0},
        {"start_seconds": 500.0, "end_seconds": 530.0},
    ]


def test_one_chunk_contributes_its_span_only_once_even_with_many_claims():
    """Two claims from the same chunk must not double its runtime contribution."""
    rows = compute_density(VIDEOS, CHUNKS, [_claim("a", ["v1_c1"]), _claim("b", ["v1_c1"])])
    assert rows[0]["claim_bearing_seconds"] == 60
    assert rows[0]["claim_count"] == 2


def test_unverifiable_evidence_earns_no_runtime():
    """An evidence chunk_id that is not a real chunk contributes nothing."""
    rows = compute_density(VIDEOS, CHUNKS, [_claim("a", ["ghost_c9"])])
    assert rows[0]["claim_bearing_seconds"] == 0
    assert rows[0]["claim_count"] == 0


def test_video_with_no_claims_reports_zero_not_an_error():
    rows = compute_density(VIDEOS, CHUNKS, [])
    assert rows[0]["density_percent"] == 0
    assert rows[0]["segments"] == []


def test_zero_duration_does_not_divide_by_zero():
    videos = [{"video_id": "v1", "duration_seconds": 0}]
    rows = compute_density(videos, CHUNKS, [_claim("a", ["v1_c1"])])
    assert rows[0]["density_percent"] == 0
    assert rows[0]["claims_per_minute"] == 0.0


def test_estimated_timestamps_are_flagged():
    rows = compute_density(VIDEOS, CHUNKS, [_claim("a", ["v1_c2"])])
    assert rows[0]["any_estimated_timestamps"] is True


def test_exact_timestamps_are_not_flagged():
    rows = compute_density(VIDEOS, CHUNKS, [_claim("a", ["v1_c1"])])
    assert rows[0]["any_estimated_timestamps"] is False


# ─── RENDERER — the phrasing is a correctness requirement, not style ────────────

def test_render_says_at_least_never_only():
    """Extraction recall is imperfect, so the number is a floor. 'Only' would be a lie."""
    out = render_density(compute_density(VIDEOS, CHUNKS, [_claim("a", ["v1_c1"])]))
    assert "at least" in out
    assert "only " not in out.lower()


def test_render_leads_with_claims_per_minute_not_the_saturated_percentage():
    """Measured on 7 real videos, the percentage sat at 87-100% and ranked nothing.

    Leading with it would imply a discrimination the number does not have.
    """
    out = render_density(compute_density(VIDEOS, CHUNKS, [_claim("a", ["v1_c1"])]))
    first_data_line = out.split("\n")[1]
    assert "claims/min" in first_data_line
    assert "%" not in first_data_line


def test_render_discloses_the_saturation_caveat():
    out = render_density(compute_density(VIDEOS, CHUNKS, [_claim("a", ["v1_c1"])])).lower()
    assert "saturates" in out


def test_render_disclaims_that_this_is_not_a_quality_score():
    out = render_density(compute_density(VIDEOS, CHUNKS, [_claim("a", ["v1_c1"])]))
    assert "not quality" in out.lower()


def test_render_handles_an_empty_workspace():
    assert "no videos" in render_density([]).lower()
