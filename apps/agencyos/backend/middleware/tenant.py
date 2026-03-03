"""
AgencyOS Tenant Middleware & Dependencies

Two-layer tenant isolation:
1. TenantMiddleware — extracts org_id from JWT/header, sets request.state.org_id
2. get_tenant_session() — FastAPI dependency that creates a DB session with RLS context

The RLS variable (app.current_org_id) must be set on the SAME session
used by the route handler. SET LOCAL scopes to the current transaction,
so we wrap it in a dependency that yields a properly-configured session.
"""

import logging
from typing import Generator, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi import Depends, Request as FastAPIRequest

from open_webui.internal.db import get_session

logger = logging.getLogger("agencyos.middleware.tenant")


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Extracts org_id from the request and sets request.state.org_id.

    Priority (set by JWTAuthMiddleware which runs first):
    1. request.state.org_id from Portal JWT
    2. X-Org-Id header (Phase 1 fallback)
    3. org_id query param (Phase 1 fallback)

    Does NOT set RLS directly — that's handled by get_tenant_session().
    """

    async def dispatch(self, request: Request, call_next):
        # Skip non-AgencyOS routes
        if not request.url.path.startswith("/api/agencyos"):
            return await call_next(request)

        # JWTAuthMiddleware may have already set org_id from JWT
        existing_org_id = getattr(request.state, "org_id", None)

        if not existing_org_id:
            # Phase 1 fallback: header or query param
            org_id = (
                request.headers.get("X-Org-Id")
                or request.query_params.get("org_id")
            )
            request.state.org_id = org_id or None

        response = await call_next(request)
        return response


def get_tenant_session(
    request: FastAPIRequest,
    db: Session = Depends(get_session),
) -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a DB session with RLS context set.

    Usage in route handlers:
        @router.get("/")
        async def my_route(db: Session = Depends(get_tenant_session)):
            # db already has app.current_org_id set for RLS
            ...

    The SET LOCAL persists for the duration of the current transaction,
    which matches the route handler's lifecycle.
    """
    org_id: Optional[str] = getattr(request.state, "org_id", None)

    if org_id:
        try:
            db.execute(
                text("SET LOCAL app.current_org_id = :org_id"),
                {"org_id": org_id},
            )
            logger.debug("RLS context set on session: org_id=%s", org_id)
        except Exception as e:
            logger.warning("Failed to set RLS context: %s", e)

    try:
        yield db
    finally:
        # Session cleanup handled by get_session's own lifecycle
        pass


def get_org_id(request: FastAPIRequest) -> Optional[str]:
    """
    Simple dependency to extract org_id from request state.
    Use when you need org_id but not a full tenant session.
    """
    return getattr(request.state, "org_id", None)
