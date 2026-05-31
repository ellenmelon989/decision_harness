"""Request dependencies: authenticated user + resource-ownership guards.

Auth posture (default-deny once configured):
  • A presented Bearer token is ALWAYS cryptographically verified against the
    Supabase project's published JWKS (asymmetric ES256/RS256 signing keys). We
    never decode a token we can't verify — if Supabase isn't configured, a
    presented token is rejected.
  • A missing token is accepted as the demo user ONLY in local dev
    (`dev_unauthenticated` True AND auth not configured). The moment Supabase is
    configured (`auth_enabled`), a valid token is required.

Ownership guards return 404 (not 403) so we don't leak the existence of resources.
"""
from functools import lru_cache
from typing import Optional

import jwt  # PyJWT
from fastapi import Header, HTTPException, Request
from jwt import PyJWKClient

from ..config import get_settings

DEMO_USER_ID = "00000000-0000-0000-0000-000000000000"

# Supabase signs user access tokens with asymmetric keys published via JWKS.
_ALGORITHMS = ["ES256", "RS256"]


@lru_cache(maxsize=8)
def _jwk_client(jwks_url: str) -> PyJWKClient:
    # PyJWKClient caches fetched signing keys internally (default ~5-min lifespan),
    # so reusing one instance per URL avoids refetching the JWKS on every request.
    return PyJWKClient(jwks_url)


def _verify_token(token: str, jwks_url: str) -> dict:
    signing_key = _jwk_client(jwks_url).get_signing_key_from_jwt(token)
    return jwt.decode(token, signing_key.key, algorithms=_ALGORITHMS,
                      audience="authenticated")


def _subject_from_token(token: str) -> str:
    """Verify a presented token against the project JWKS and return its subject."""
    s = get_settings()
    if not s.auth_enabled:
        # No project to verify against — refuse rather than trust blindly.
        raise HTTPException(status_code=401, detail="token verification not configured")
    try:
        claims = _verify_token(token, s.jwks_url)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"invalid token: {exc}") from exc
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="token missing subject")
    return sub


def _resolve_user(token: Optional[str]) -> str:
    """Shared policy: a presented token is always verified; a missing one is the
    demo user only in local dev (auth not configured), else 401."""
    if token:
        return _subject_from_token(token)
    if get_settings().dev_unauthenticated and not get_settings().auth_enabled:
        return DEMO_USER_ID
    raise HTTPException(status_code=401, detail="authentication required")


def get_current_user(authorization: Optional[str] = Header(default=None)) -> str:
    token = authorization.removeprefix("Bearer ").strip() if authorization else None
    return _resolve_user(token)


def get_current_user_sse(request: Request) -> str:
    """Auth for the SSE stream: EventSource can't set headers, so the access token
    arrives as the `?access_token=` query param. Verified identically."""
    return _resolve_user(request.query_params.get("access_token"))


def require_org_access(repo, org_id: str, user: str):
    """Return the org iff `user` owns it, else 404."""
    org = repo.get_org(org_id)
    if not org or org.owner_id != user:
        raise HTTPException(status_code=404, detail="org not found")
    return org


def require_session_access(repo, session_id: str, user: str):
    """Return the session iff `user` owns its org, else 404."""
    sess = repo.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    org = repo.get_org(sess.org_id)
    if not org or org.owner_id != user:
        raise HTTPException(status_code=404, detail="session not found")
    return sess
