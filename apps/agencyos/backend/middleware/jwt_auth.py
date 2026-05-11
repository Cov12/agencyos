"""
AgencyOS JWT Authentication Middleware

Validates Portal-issued JWTs on /api/agencyos routes.
Extracts org_id, user_id, role, and department_memberships from token.

Phase 2A: Replaces X-Org-Id header approach from Phase 1.
Falls back to Phase 1 behavior (X-Org-Id header) if no JWT present,
allowing gradual migration.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import jwt as pyjwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("agencyos.middleware.jwt_auth")

# JWT secret shared with WBIT Portal
JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"


class PortalAuthContext:
    """Parsed auth context from Portal JWT."""

    def __init__(
        self,
        user_id: str,
        org_id: str,
        role: str = "member",
        department_memberships: list[str] | None = None,
        email: Optional[str] = None,
    ):
        self.user_id = user_id
        self.org_id = org_id
        self.role = role
        self.department_memberships = department_memberships or []
        self.email = email

    def has_department_access(self, dept_id: str) -> bool:
        """Check if user has access to a specific department."""
        if self.role in ("owner", "admin"):
            return True
        return dept_id in self.department_memberships


def decode_portal_jwt(token: str) -> Optional[PortalAuthContext]:
    """Decode and validate a Portal JWT. Returns None on failure."""
    if not JWT_SECRET:
        logger.warning("JWT_SECRET not configured — cannot validate Portal tokens")
        return None

    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return PortalAuthContext(
            user_id=payload.get("user_id", payload.get("sub", "")),
            org_id=payload.get("org_id", ""),
            role=payload.get("role", "member"),
            department_memberships=payload.get("department_memberships", []),
            email=payload.get("email"),
        )
    except pyjwt.ExpiredSignatureError:
        logger.warning("Portal JWT expired")
        return None
    except pyjwt.InvalidTokenError as e:
        logger.warning("Invalid Portal JWT: %s", e)
        return None


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    Validates Portal JWTs on AgencyOS API routes.

    Priority:
    1. Authorization: Bearer <jwt> header (Portal token)
    2. X-Org-Id header (Phase 1 fallback, for OpenWebUI-internal requests)
    3. org_id query param (Phase 1 fallback)

    Sets request.state:
    - portal_auth: PortalAuthContext (if JWT valid) or None
    - org_id: str (from JWT or fallback)
    - user_id: str (from JWT or OpenWebUI session)
    """

    async def dispatch(self, request: Request, call_next):
        # Skip non-AgencyOS routes
        if not request.url.path.startswith("/api/agencyos"):
            return await call_next(request)

        # Skip health endpoint
        if request.url.path == "/api/agencyos/health":
            return await call_next(request)

        portal_auth = None
        org_id = None

        # Try Portal JWT first
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            # Don't try to decode OpenWebUI tokens as Portal JWTs
            # Portal JWTs are shorter and have specific claims
            if JWT_SECRET and len(token) < 500:
                portal_auth = decode_portal_jwt(token)

        if portal_auth:
            org_id = portal_auth.org_id
            request.state.portal_auth = portal_auth
            request.state.org_id = org_id
            request.state.user_id = portal_auth.user_id
            logger.info(
                "Portal JWT auth: user=%s org=%s role=%s",
                portal_auth.user_id,
                portal_auth.org_id,
                portal_auth.role,
            )
        else:
            # Phase 1 fallback: X-Org-Id header or query param
            org_id = (
                request.headers.get("X-Org-Id")
                or request.query_params.get("org_id")
            )
            request.state.portal_auth = None
            request.state.org_id = org_id or None
            # user_id from OpenWebUI session (set by upstream middleware)
            request.state.user_id = getattr(request.state, "user_id", None)

        response = await call_next(request)
        return response
