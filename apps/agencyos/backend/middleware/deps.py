"""Request-scope dependencies for AgencyOS routers."""

import logging
import os
from fastapi import Depends, HTTPException, Request

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
