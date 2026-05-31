"""Pure decision-math tests (no network)."""
from backend.engine.scoring import (
    blended_confidence,
    consensus,
    decision_from_score,
    normalized_variance,
    weighted_score,
)
from backend.schemas import Position, Stance


def test_weighted_score_basic():
    assert weighted_score({"a": 10, "b": 0}, {"a": 3, "b": 1}) == 7.5


def test_weighted_score_zero_weight_is_safe():
    assert weighted_score({"a": 5}, {"a": 0}) == 0.0


def test_decision_thresholds():
    assert decision_from_score(8) == Stance.YES
    assert decision_from_score(7) == Stance.YES
    assert decision_from_score(6) == Stance.CONDITIONAL
    assert decision_from_score(5) == Stance.CONDITIONAL
    assert decision_from_score(4.9) == Stance.NO


def test_consensus_unanimous_vs_split():
    assert consensus([5, 5, 5]) == 1.0
    assert consensus([0, 10]) == 0.0


def test_normalized_variance_bounds():
    assert normalized_variance([5]) == 0.0
    assert normalized_variance([0, 10]) == 1.0
    assert 0.0 <= normalized_variance([3, 5, 7]) <= 1.0


def test_blended_confidence_in_range():
    ps = [Position(stance=Stance.YES, score=7, confidence=0.8, rationale="") for _ in range(3)]
    assert 0.0 <= blended_confidence(ps) <= 1.0
    assert blended_confidence([]) == 0.0
