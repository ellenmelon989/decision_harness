from fastapi import APIRouter, Depends, HTTPException

from ..db.repository import get_repo
from ..schemas import Agent, AgentCreate, CreateOrgRequest, GenerateOrgRequest, Org
from .deps import get_current_user, require_org_access

router = APIRouter(prefix="/orgs", tags=["orgs"])


@router.get("", response_model=list[Org])
def list_orgs(user: str = Depends(get_current_user)):
    return get_repo().list_orgs(user)


@router.post("", response_model=Org)
def create_org(body: CreateOrgRequest, user: str = Depends(get_current_user)):
    return get_repo().create_org(user, body.name, body.description, body.preset)


@router.post("/generate", response_model=Org)
async def generate_org(body: GenerateOrgRequest, user: str = Depends(get_current_user)):
    from ..engine.org_builder import generate_org_agents
    name, description, agents = await generate_org_agents(body.prompt)
    repo = get_repo()
    org = repo.create_org(user, name=name, description=description, preset="generated")
    for agent in agents:
        repo.create_agent(org.id, agent)
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
