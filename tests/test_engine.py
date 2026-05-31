"""End-to-end engine test in deterministic MOCK mode (no network)."""
import pytest

from backend.db.repository import InMemoryRepository
from backend.db.seed import seed_judge_panel
from backend.engine import agent_runner, orchestrator
from backend.engine.debate import run_debate
from backend.engine.org_builder import _fallback_team
from backend.schemas import EventType, SessionStatus, Stance


@pytest.fixture(autouse=True)
def force_mock(monkeypatch):
    # No LLM backend → agents/orchestrator use deterministic mocks.
    monkeypatch.setattr(agent_runner, "resolve_backend", lambda *_: None)
    monkeypatch.setattr(orchestrator, "resolve_backend", lambda *_: None)


async def test_mock_debate_produces_verdict():
    repo = InMemoryRepository()
    org = seed_judge_panel(repo, "u")
    assert org is not None
    agents = repo.list_agents(org.id)
    assert len(agents) >= 3

    sess = repo.create_session(org.id, "Should this win?", rounds=2)
    verdict = await run_debate(sess, agents, repo)

    assert verdict.decision in set(Stance)
    assert 0.0 <= verdict.weighted_score <= 10.0
    assert 0.0 <= verdict.confidence <= 1.0
    assert len(verdict.influence_ranking) == len(agents)

    events = repo.list_events(sess.id)
    types = {e.type for e in events}
    assert EventType.position in types
    assert EventType.verdict in types
    assert repo.get_session(sess.id).status == SessionStatus.done


def test_org_builder_fallback_team():
    spec = _fallback_team("a biotech seed investment committee")
    assert spec["agents"]
    assert abs(sum(a.weight for a in spec["agents"]) - 1.0) < 0.02  # normalized (3dp rounding)


async def test_veto_agent_caps_a_clean_yes_in_the_verdict():
    from backend.engine.orchestrator import orchestrate_verdict
    from backend.schemas import Agent, Position, Stance

    optimist = Agent(id="opt", org_id="o", name="Optimist", role="r", system_prompt="")
    skeptic = Agent(id="skep", org_id="o", name="Skeptic", role="r", system_prompt="", veto=True)
    positions = {
        "opt": Position(stance=Stance.YES, score=9.0, confidence=0.9, rationale=""),
        "skep": Position(stance=Stance.NO, score=2.0, confidence=0.9, rationale=""),
    }
    weights = {"opt": 0.9, "skep": 0.1}  # weighted score 8.3 → would be a clean YES

    verdict = await orchestrate_verdict([optimist, skeptic], positions, weights, events=[])

    assert verdict.weighted_score >= 7.0          # the raw math says YES
    assert verdict.decision == Stance.CONDITIONAL  # but the unconvinced veto caps it
