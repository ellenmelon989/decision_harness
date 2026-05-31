from fastapi import APIRouter, Depends, HTTPException

from ..db.repository import get_repo
from ..db.seed import seed_judge_panel
from ..engine.org_builder import generate_org_agents
from ..schemas import Agent, AgentCreate, CreateOrgRequest, GenerateOrgRequest, Org
from .deps import get_current_user, require_org_access

router = APIRouter(prefix="/orgs", tags=["orgs"])


@router.get("", response_model=list[Org])
def list_orgs(user: str = Depends(get_current_user)):
    return get_repo().list_orgs(user)


@router.post("/ensure-seed", response_model=list[Org])
def ensure_seed(user: str = Depends(get_current_user)):
    """Idempotent first-login bootstrap: if the user owns no orgs, seed a personal
    Judge Panel (owned by their auth.uid()), then return all their orgs. Safe to
    call on every login."""
    repo = get_repo()
    orgs = repo.list_orgs(user)
    if not orgs:
        seed_judge_panel(repo, user)
        orgs = repo.list_orgs(user)
    return orgs


@router.post("", response_model=Org)
def create_org(body: CreateOrgRequest, user: str = Depends(get_current_user)):
    return get_repo().create_org(user, body.name, body.description, body.preset)


@router.post("/generate", response_model=Org)
async def generate_org(body: GenerateOrgRequest, user: str = Depends(get_current_user)):
    """Synthesize a full panel of agents from a prompt and persist it."""
    repo = get_repo()
    spec = await generate_org_agents(body.prompt)
    org = repo.create_org(user, name=spec["org_name"],
                          description=spec.get("description"), preset="generated")
    for ac in spec["agents"]:
        repo.create_agent(org.id, ac)
    return org


@router.get("/{org_id}/agents", response_model=list[Agent])
def list_org_agents(org_id: str, user: str = Depends(get_current_user)):
    repo = get_repo()
    require_org_access(repo, org_id, user)
    return repo.list_agents(org_id)


@router.post("/{org_id}/agents", response_model=Agent)
def create_org_agent(org_id: str, body: AgentCreate, user: str = Depends(get_current_user)):
    repo = get_repo()
    require_org_access(repo, org_id, user)
    return repo.create_agent(org_id, body)
