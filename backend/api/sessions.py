import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from ..db.repository import get_repo
from ..engine import stream
from ..engine.debate import run_debate
from ..engine.orchestrator import build_influence_graph
from ..schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    InfluenceGraph,
    RerunRequest,
    SessionDetail,
    SessionStatus,
)
from .deps import (get_current_user, get_current_user_sse, require_org_access,
                   require_session_access)

router = APIRouter(prefix="/sessions", tags=["sessions"])


async def _run_debate(session_id: str) -> None:
    """Background task: run the debate, persisting + streaming as it goes."""
    repo = get_repo()
    sess = repo.get_session(session_id)
    agents = repo.list_agents(sess.org_id)
    try:
        await run_debate(sess, agents, repo)
    except Exception as exc:  # surface to the stream, mark errored
        repo.update_session(session_id, status=SessionStatus.error)
        stream.publish(session_id, {"type": "error", "content": {"error": str(exc)}})
        stream.close(session_id)


@router.post("", response_model=CreateSessionResponse)
async def create_session(body: CreateSessionRequest, user: str = Depends(get_current_user)):
    repo = get_repo()
    require_org_access(repo, body.org_id, user)
    if not repo.list_agents(body.org_id):
        raise HTTPException(400, "org has no agents")
    sess = repo.create_session(body.org_id, body.question, body.context, body.rounds,
                               created_by=user)
    asyncio.create_task(_run_debate(sess.id))
    return CreateSessionResponse(session_id=sess.id)


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session_id: str, user: str = Depends(get_current_user)):
    repo = get_repo()
    sess = require_session_access(repo, session_id, user)
    return SessionDetail(session=sess, events=repo.list_events(session_id),
                         positions=repo.list_positions(session_id),
                         verdict=sess.final_verdict)


@router.get("/{session_id}/stream")
async def stream_session(session_id: str, request: Request,
                         user: str = Depends(get_current_user_sse)):
    repo = get_repo()
    require_session_access(repo, session_id, user)
    q = stream.subscribe(session_id)

    async def gen():
        try:
            # Replay history for late subscribers, then go live.
            for ev in repo.list_events(session_id):
                yield {"event": ev.type.value, "data": json.dumps(ev.model_dump(mode="json"))}
            if repo.get_session(session_id).status in (SessionStatus.done, SessionStatus.error):
                yield {"event": "done", "data": "{}"}
                return
            while True:
                if await request.is_disconnected():
                    break
                item = await q.get()
                if item is None:
                    yield {"event": "done", "data": "{}"}
                    break
                yield {"event": item.get("type", "message"), "data": json.dumps(item)}
        finally:
            stream.unsubscribe(session_id, q)

    return EventSourceResponse(gen())


@router.post("/{session_id}/rerun", response_model=CreateSessionResponse)
async def rerun(session_id: str, body: RerunRequest, user: str = Depends(get_current_user)):
    repo = get_repo()
    parent = require_session_access(repo, session_id, user)
    child = repo.create_session(parent.org_id, parent.question,
                                context=body.context or parent.context, rounds=parent.rounds,
                                created_by=user, parent_session=parent.id,
                                weights_override=body.weights_override)
    asyncio.create_task(_run_debate(child.id))
    return CreateSessionResponse(session_id=child.id)


@router.get("/{session_id}/influence", response_model=InfluenceGraph)
def influence(session_id: str, user: str = Depends(get_current_user)):
    repo = get_repo()
    sess = require_session_access(repo, session_id, user)
    agents = repo.list_agents(sess.org_id)
    weights = sess.weights_override or {a.id: a.weight for a in agents}
    return build_influence_graph(agents, repo.list_events(session_id), weights)
