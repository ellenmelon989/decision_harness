"""Pure decision-math tests (no network)."""
from backend.engine.scoring import (
    apply_veto_cap,
    blended_confidence,
    consensus,
    decision_from_score,
    normalized_variance,
    weighted_score,
)
from backend.schemas import Agent, Position, Stance


def _agent(aid: str, *, veto: bool = False) -> Agent:
    return Agent(id=aid, org_id="o", name=aid, role="r", system_prompt="", veto=veto)


def _pos(stance: Stance) -> Position:
    return Position(stance=stance, score=5.0, confidence=0.5, rationale="")


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


# ── veto cap: a structural skeptic can block a clean YES, not force a NO ──

def test_veto_agent_not_convinced_caps_yes_to_conditional():
    agents = [_agent("opt"), _agent("skeptic", veto=True)]
    positions = {"opt": _pos(Stance.YES), "skeptic": _pos(Stance.NO)}
    assert apply_veto_cap(Stance.YES, agents, positions) == Stance.CONDITIONAL


def test_veto_agent_conditional_also_caps_yes():
    agents = [_agent("skeptic", veto=True)]
    positions = {"skeptic": _pos(Stance.CONDITIONAL)}
    assert apply_veto_cap(Stance.YES, agents, positions) == Stance.CONDITIONAL


def test_veto_agent_convinced_does_not_cap():
    agents = [_agent("skeptic", veto=True)]
    positions = {"skeptic": _pos(Stance.YES)}
    assert apply_veto_cap(Stance.YES, agents, positions) == Stance.YES


def test_no_veto_agent_never_caps():
    agents = [_agent("a"), _agent("b")]
    positions = {"a": _pos(Stance.YES), "b": _pos(Stance.NO)}
    assert apply_veto_cap(Stance.YES, agents, positions) == Stance.YES


def test_veto_cannot_force_a_no_down_or_lift_a_no():
    # The cap only ever softens a YES; it never touches NO/CONDITIONAL verdicts.
    agents = [_agent("skeptic", veto=True)]
    positions = {"skeptic": _pos(Stance.NO)}
    assert apply_veto_cap(Stance.NO, agents, positions) == Stance.NO
    assert apply_veto_cap(Stance.CONDITIONAL, agents, positions) == Stance.CONDITIONAL
