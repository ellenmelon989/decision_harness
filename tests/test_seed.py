"""Per-user auto-seed of the Judge Panel is idempotent (spec: ensure-seed)."""
from backend.api import orgs as orgs_mod
from backend.db.repository import InMemoryRepository


def test_ensure_seed_is_idempotent_per_user(monkeypatch):
    repo = InMemoryRepository()
    monkeypatch.setattr(orgs_mod, "get_repo", lambda: repo)

    first = orgs_mod.ensure_seed(user="user-1")
    assert len(first) == 1
    assert first[0].owner_id == "user-1"

    # Second call for the same user must NOT create a duplicate org.
    again = orgs_mod.ensure_seed(user="user-1")
    assert len(again) == 1
    assert again[0].id == first[0].id


def test_ensure_seed_is_per_user(monkeypatch):
    repo = InMemoryRepository()
    monkeypatch.setattr(orgs_mod, "get_repo", lambda: repo)

    orgs_mod.ensure_seed(user="user-1")
    other = orgs_mod.ensure_seed(user="user-2")

    assert len(other) == 1
    assert other[0].owner_id == "user-2"
    # user-1 still owns exactly one org of their own.
    assert len(repo.list_orgs("user-1")) == 1
