"""Request-scope dependencies for AgencyOS routers."""

import logging
import os
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .tenant import get_tenant_session
from ..services.organizations import OrganizationsService

logger = logging.getLogger(__name__)


def require_app_access(required_app: str):
    """
    FastAPI dep factory. Returns a callable that 403s if the request's
    PortalAuthContext doesn't grant access to `required_app`.

    Behavior on missing PortalAuthContext (X-Org-Id header fallback path):
      - Default: 403 (deny).
      - If env var AGENCYOS_DEV_ALLOW_HEADER_AUTH=1 is set: allow through
        (dev/test escape hatch — NEVER set in prod).
    """
    def _dep(request: Request):
        portal_auth = getattr(request.state, "portal_auth", None)
        if portal_auth is None:
            if os.environ.get("AGENCYOS_DEV_ALLOW_HEADER_AUTH") == "1":
                logger.warning(
                    "require_app_access[%s]: portal_auth missing; allowing via "
                    "AGENCYOS_DEV_ALLOW_HEADER_AUTH dev escape hatch",
                    required_app,
                )
                return
            logger.info(
                "require_app_access[%s] denied: no portal_auth (X-Org-Id fallback path)",
                required_app,
            )
            raise HTTPException(status_code=403, detail=f"App access denied: {required_app}")
        if not portal_auth.has_app_access(required_app):
            logger.info(
                "require_app_access[%s] denied for user=%s org=%s",
                required_app, portal_auth.user_id, portal_auth.org_id,
            )
            raise HTTPException(status_code=403, detail=f"App access denied: {required_app}")
        return
    return _dep


def require_org_access(
    request: Request,
    db: Session = Depends(get_tenant_session),
):
    """
    FastAPI dependency that binds the requested internal org_id to the caller's
    Portal identity (issue #41 — GA BLOCKER, cross-tenant IDOR).

    The tenant-scoped handlers all trust an `org_id` (the AgencyOS-INTERNAL row id)
    that arrives as a query param (departments/proposals/cortex-approvals/...) or a
    path param (`/orgs/{org_id}/...`) and filter their queries on it. require_app_access
    only proves the JWT grants the *app*; nothing proved the requested org actually
    BELONGS to the caller. So an authenticated user of org A could read org B's rows by
    passing B's internal org_id. This dep closes that hole — it must be composed
    ALONGSIDE get_tenant_session + require_app_access, not as a replacement.

    Ownership check (Portal-authed path): the JWT's org_id claim is the Portal CUID,
    stored on each row as AgencyOSOrganization.portal_org_id (the same identity #35's
    list_orgs_for_portal scopes by). We load the row by its internal id and require
    row.portal_org_id == portal_auth.org_id. Fail-closed: a missing org_id, an unknown
    org, or an org owned by a different Portal CUID all 403.

    Dev/header path (no portal_auth): preserved EXACTLY, gated to non-prod by the same
    AGENCYOS_DEV_ALLOW_HEADER_AUTH=1 escape hatch require_app_access uses. In prod (flag
    off) a request with no portal_auth is already denied here (403), matching the
    require_app_access default-deny — single-tenant/dev/test flows are unaffected.
    """
    portal_auth = getattr(request.state, "portal_auth", None)
    # Match how handlers receive the internal org id: query param first (departments,
    # proposals, cortex-approvals, employee-tabs, dashboard/*), else the path param
    # (/orgs/{org_id}/...).
    requested_org_id = (
        request.query_params.get("org_id")
        or request.path_params.get("org_id")
    )

    if portal_auth is None:
        if os.environ.get("AGENCYOS_DEV_ALLOW_HEADER_AUTH") == "1":
            logger.warning(
                "require_org_access: portal_auth missing; allowing via "
                "AGENCYOS_DEV_ALLOW_HEADER_AUTH dev escape hatch (org_id=%s)",
                requested_org_id,
            )
            return
        logger.info(
            "require_org_access denied: no portal_auth (X-Org-Id fallback path)"
        )
        raise HTTPException(status_code=403, detail="Org access denied")

    if not requested_org_id:
        logger.info(
            "require_org_access denied: no org_id on request for user=%s portal_org=%s",
            portal_auth.user_id, portal_auth.org_id,
        )
        raise HTTPException(status_code=403, detail="Org access denied: missing org_id")

    org = OrganizationsService.get_org_by_id(db, requested_org_id)
    if org is None or org.portal_org_id != portal_auth.org_id:
        logger.info(
            "require_org_access denied: user=%s portal_org=%s requested internal org=%s "
            "(owner_portal_org=%s)",
            portal_auth.user_id, portal_auth.org_id, requested_org_id,
            getattr(org, "portal_org_id", None),
        )
        raise HTTPException(status_code=403, detail="Org access denied")
    return
