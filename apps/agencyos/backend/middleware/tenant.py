"""
AgencyOS Tenant Middleware & Dependencies

Tenant isolation layers:
1. PRIMARY (always on): the application layer — require_org_access (middleware/deps.py)
   binds the requested org_id to the caller's real membership, and every tenant-scoped
   query filters by that org_id. This is what actually enforces isolation in prod.
2. SECONDARY (Postgres only): Postgres RLS policies (migrations/001_rls_policies.sql)
   keyed on the app.current_org_id session variable that get_tenant_session sets.
   AgencyOS prod runs on SQLite, which has no RLS, so this layer is dormant there —
   get_tenant_session sets the variable only when the bound engine is Postgres.

TenantMiddleware extracts org_id from the JWT/header onto request.state.org_id;
get_tenant_session yields the DB session, setting the RLS context on Postgres. SET LOCAL
scopes to the current transaction, matching the route handler's lifecycle.
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

            # A1 (#27): mirror the org's Portal sub-account roster locally. Same hook
            # as the #66 stamp above — it is the ONE place with (a) the Portal CUID,
            # (b) the AgencyOS-internal org id (the `org_id` query param), (c) the raw
            # Portal JWT (stashed by JWTAuthMiddleware), and (d) a live db session.
            # maybe_sync is throttled per-org and never raises, so an unreachable
            # Portal just leaves the mirror as-is (business-scope-only), never a 500.
            portal_token = getattr(request.state, "portal_token", None)
            if portal_token:
                from ..services.subaccount_sync import maybe_sync

                maybe_sync(db, internal_org_id, portal_cuid, portal_token)

    # RLS is a Postgres-only SECOND layer (migrations/001_rls_policies.sql). AgencyOS prod
    # runs on SQLite, which has no RLS — `SET LOCAL` there raises a syntax error on EVERY
    # tenant request (previously caught + logged, i.e. per-request warning spam plus a
    # false impression of DB-level isolation). The PRIMARY, always-on guard is the
    # application layer: require_org_access (middleware/deps.py) binds the requested org_id
    # to the caller's membership and every tenant-scoped query filters by that org_id. So
    # only set the RLS context when the bound engine is Postgres, where a policy can
    # actually consult it; on SQLite this is a clean no-op.
    if org_id and db.get_bind().dialect.name == "postgresql":
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
