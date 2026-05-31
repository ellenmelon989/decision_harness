"""Auth verification: Supabase ES256 access tokens validated against the project JWKS.

These tests mint real ES256 tokens against an in-memory EC keypair and stub the
JWKS client so verification runs the production code path without network access.
"""
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException

from backend.api import deps


@pytest.fixture
def ec_private_key():
    return ec.generate_private_key(ec.SECP256R1())


def _mint(priv, sub="user-123", aud="authenticated", **extra):
    payload = {"sub": sub, "aud": aud, **extra}
    return jwt.encode(payload, priv, algorithm="ES256")


@pytest.fixture
def auth_on(monkeypatch, ec_private_key):
    """Enable auth and point JWKS verification at our in-memory EC public key."""
    pub = ec_private_key.public_key()

    class _Settings:
        auth_enabled = True
        dev_unauthenticated = True
        jwks_url = "https://example.test/auth/v1/.well-known/jwks.json"

    monkeypatch.setattr(deps, "get_settings", lambda: _Settings())

    class _StubKey:
        key = pub

    class _StubClient:
        def get_signing_key_from_jwt(self, token):
            return _StubKey()

    monkeypatch.setattr(deps, "_jwk_client", lambda url: _StubClient())
    return ec_private_key


def test_valid_es256_token_returns_subject(auth_on):
    token = _mint(auth_on, sub="abc")
    assert deps.get_current_user(f"Bearer {token}") == "abc"


def test_tampered_token_rejected(auth_on):
    token = _mint(auth_on)
    bad = token[:-3] + ("aaa" if not token.endswith("aaa") else "bbb")
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(f"Bearer {bad}")
    assert e.value.status_code == 401


def test_wrong_audience_rejected(auth_on):
    token = _mint(auth_on, aud="not-authenticated")
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(f"Bearer {token}")
    assert e.value.status_code == 401


def test_token_without_subject_rejected(auth_on):
    token = jwt.encode({"aud": "authenticated"}, auth_on, algorithm="ES256")
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(f"Bearer {token}")
    assert e.value.status_code == 401


def test_missing_token_when_auth_enabled_is_401(auth_on):
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(None)
    assert e.value.status_code == 401


# --- SSE stream auth (token via ?access_token= query param) ---

class _Req:
    """Minimal stand-in for starlette Request: only query_params is read."""
    def __init__(self, access_token=None):
        self.query_params = {"access_token": access_token} if access_token else {}


def test_sse_valid_query_token_returns_subject(auth_on):
    token = _mint(auth_on, sub="streamer")
    assert deps.get_current_user_sse(_Req(token)) == "streamer"


def test_sse_missing_query_token_is_401(auth_on):
    with pytest.raises(HTTPException) as e:
        deps.get_current_user_sse(_Req(None))
    assert e.value.status_code == 401


def test_sse_invalid_query_token_is_401(auth_on):
    token = _mint(auth_on)
    bad = token[:-3] + ("aaa" if not token.endswith("aaa") else "bbb")
    with pytest.raises(HTTPException) as e:
        deps.get_current_user_sse(_Req(bad))
    assert e.value.status_code == 401
