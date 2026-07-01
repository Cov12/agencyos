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

    # #66 Stage 2 (Approach B): idempotent backfill of portal_org_id for org rows that
    # predate Stage-2 provisioning. Hook point = this dependency because it is the ONE
    # place that already has BOTH (a) the parsed Portal auth (the Portal CUID) and (b) a
    # live db session, and it runs on every tenant-scoped route.
    #
    # Mapping (verified against the codebase, NOT guessed): on a Portal-authed request
    # the JWT's org_id claim is the Portal CUID (JWTAuthMiddleware puts it on
    # request.state.portal_auth.org_id AND request.state.org_id), while the AgencyOS-
    # INTERNAL org id travels as the `org_id` QUERY PARAM — the same value the chat path
    # (cortex_bridge._resolve_company_for_chat) and employee_tabs use to scope data to a
    # row (AgencyOSOrganization.id == org_id). So we map CUID -> row via that query param,
    # NOT via request.state.org_id (which is the CUID on the JWT path, never the row id).
    #
    # Runs BEFORE the SET LOCAL below: the stamp commits, and SET LOCAL is transaction-
    # scoped, so doing it first keeps the RLS setting fresh for the handler's queries.
    # stamp_portal_org_id never raises (it rolls back + swallows), so a reconcile failure
    # cannot 500 a normal request.
    portal_auth = getattr(request.state, "portal_auth", None)
    portal_cuid = getattr(portal_auth, "org_id", None) if portal_auth else None
    if portal_cuid:
        from ..services.organizations import OrganizationsService

        internal_org_id = request.query_params.get("org_id")
        if internal_org_id:
            OrganizationsService.stamp_portal_org_id(db, internal_org_id, portal_cuid)

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
