"""Prove persistence: round-trip every SupabaseRepository method against the real
Postgres DB (no LLM calls), then clean up.

    python -m backend.db.verify
"""
from ..api.deps import DEMO_USER_ID
from ..config import get_settings
from ..schemas import (
    AgentCreate,
    EventType,
    Position,
    SessionStatus,
    Stance,
    Verdict,
)
from .repository import SupabaseRepository, get_repo


def main() -> None:
    s = get_settings()
    repo = get_repo()
    print(f"repo={type(repo).__name__}  supabase_enabled={s.supabase_enabled}")
    if not isinstance(repo, SupabaseRepository):
        raise SystemExit("Not using Supabase — check backend/.env (SUPABASE_URL/SERVICE_KEY).")

    org = repo.create_org(DEMO_USER_ID, "Verify Org", "temporary", "test")
    try:
        agent = repo.create_agent(org.id, AgentCreate(
            name="Verifier", role="tester", system_prompt="p", weight=1.0))
        sess = repo.create_session(org.id, "Does persistence work?", rounds=1,
                                   created_by=DEMO_USER_ID)
        repo.append_event(sess.id, 0, EventType.position,
                          {"stance": "YES", "score": 7, "confidence": 0.8, "rationale": "ok"},
                          agent_id=agent.id)
        repo.save_position(sess.id, 0, agent.id,
                           Position(stance=Stance.YES, score=7, confidence=0.8, rationale="ok"))
        repo.update_session(sess.id, status=SessionStatus.done,
                            final_verdict=Verdict(decision=Stance.YES, weighted_score=7.0,
                                                  confidence=0.8))

        # read back through every list/get path
        assert len(repo.list_orgs(DEMO_USER_ID)) >= 1
        assert len(repo.list_agents(org.id)) == 1
        assert len(repo.list_events(sess.id)) == 1
        assert len(repo.list_positions(sess.id)) == 1
        s2 = repo.get_session(sess.id)
        assert s2.status == SessionStatus.done and s2.final_verdict.decision == Stance.YES
        print("✓ create/list/get/update all round-trip through Postgres")
    finally:
        repo.c.table("orgs").delete().eq("id", org.id).execute()  # cascade cleans children
        print("✓ cleaned up verify org")


if __name__ == "__main__":
    main()
