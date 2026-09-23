"""
Tests for the answer-gate scoring harness — offline, no network.

  python3 -m pytest rag/tests/test_evaluate_gate.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.evaluate_gate import score_gate

DATASET = [
    {"question": "q1", "chunk_id": "c1", "label": "answers"},
    {"question": "q1", "chunk_id": "c2", "label": "mentions"},
    {"question": "q1", "chunk_id": "c3", "label": "unrelated"},
    {"question": "q2", "chunk_id": "c4", "label": "answers"},
]


def test_all_correct_scores_one():
    predicted = {("q1", "c1"): "answers", ("q1", "c2"): "mentions",
                 ("q1", "c3"): "unrelated", ("q2", "c4"): "answers"}
    result = score_gate(DATASET, predicted)
    assert result["total"] == 4
    assert result["correct"] == 4
    assert result["accuracy"] == 1.0
    assert result["missing"] == 0


def test_partial_correctness():
    predicted = {("q1", "c1"): "answers", ("q1", "c2"): "answers",
                 ("q1", "c3"): "unrelated", ("q2", "c4"): "mentions"}
    result = score_gate(DATASET, predicted)
    assert result["correct"] == 2
    assert result["accuracy"] == 0.5


def test_missing_prediction_counts_as_wrong_and_is_reported():
    predicted = {("q1", "c1"): "answers"}
    result = score_gate(DATASET, predicted)
    assert result["missing"] == 3
    assert result["correct"] == 1
    assert result["accuracy"] == 0.25


def test_confusion_records_actual_to_predicted():
    predicted = {("q1", "c1"): "mentions", ("q1", "c2"): "mentions",
                 ("q1", "c3"): "unrelated", ("q2", "c4"): "answers"}
    result = score_gate(DATASET, predicted)
    assert result["confusion"][("answers", "mentions")] == 1
    assert result["confusion"][("answers", "answers")] == 1


def test_empty_dataset_does_not_divide_by_zero():
    result = score_gate([], {})
    assert result["total"] == 0
    assert result["accuracy"] == 0.0


def test_missing_is_recorded_in_the_confusion_matrix():
    result = score_gate(DATASET, {})
    assert result["confusion"][("answers", "MISSING")] == 2
    assert result["missing"] == 4
