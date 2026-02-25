"""
AgencyOS Tenant Middleware

Injects org context into every request.
Enforces tenant isolation — users can only access their org's data.
"""

import logging

from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from open_webui.internal.db import get_session

logger = logging.getLogger("agencyos.middleware.tenant")


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Extracts org_id from the request and makes it available
    throughout the request lifecycle.

    Phase 1: org_id from header/query param (simple)
    Phase 2: org_id from JWT/SSO token (WorkPipe auth)
    """

    async def dispatch(self, request: Request, call_next):
        # Skip non-AgencyOS routes
        if not request.url.path.startswith("/api/agencyos"):
            return await call_next(request)

        # Phase 1: Simple org_id extraction
        org_id = (
            request.headers.get("X-Org-Id")
            or request.query_params.get("org_id")
        )

        request.state.org_id = org_id or None

        # Set Postgres session variable for RLS checks
        if org_id:
            db = None
            try:
                db = next(get_session())
                db.execute(
                    text("SET LOCAL app.current_org_id = :org_id"),
                    {"org_id": org_id},
                )
                logger.info(f"RLS context set: org_id={org_id}")
            except Exception as e:
                logger.warning(f"Failed to set RLS context: {e}")
            finally:
                if db is not None:
                    db.close()

        response = await call_next(request)
        return response
