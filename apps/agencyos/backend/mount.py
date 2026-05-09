"""
AgencyOS Mount Point

This is the single integration point with OpenWebUI's FastAPI app.
Import and call `mount_agencyos(app)` from OpenWebUI's main.py.

This is the ONLY file that touches OpenWebUI internals.
Everything else lives in the agencyos wrapper layer.
"""

import logging
from fastapi import FastAPI

from .routers.departments import router as departments_router
from .routers.proposals import router as proposals_router
from .routers.organizations import router as organizations_router
from .routers.workpipe import router as workpipe_router
from .routers.email_ingest import router as email_router
from .routers.voice import router as voice_router
from .routers.auth_callback import router as auth_callback_router
from .middleware.tenant import TenantMiddleware
from .middleware.jwt_auth import JWTAuthMiddleware
from .middleware.rate_limiter import RateLimiterMiddleware
from .middleware.error_handler import ErrorHandlerMiddleware
from .middleware.auth_redirect import AuthRedirectMiddleware

logger = logging.getLogger("agencyos")


def mount_agencyos(app: FastAPI) -> None:
    """
    Mount all AgencyOS routes and middleware onto the OpenWebUI FastAPI app.
    
    Usage in OpenWebUI's main.py:
        from apps.agencyos.backend.mount import mount_agencyos
        mount_agencyos(app)
    """
    # Add middleware (order: outermost runs first)
    # Error handler → Rate limiter → Auth redirect → JWT auth → Tenant context
    app.add_middleware(TenantMiddleware)
    app.add_middleware(JWTAuthMiddleware)
    app.add_middleware(AuthRedirectMiddleware)
    app.add_middleware(RateLimiterMiddleware, rpm=100)
    app.add_middleware(ErrorHandlerMiddleware)

    # Mount API routers
    app.include_router(auth_callback_router)  # Portal SSO callback
    app.include_router(organizations_router)
    app.include_router(departments_router)
    app.include_router(proposals_router)
    app.include_router(workpipe_router)
    app.include_router(email_router)
    app.include_router(voice_router)

    # Health check
    @app.get("/api/agencyos/health")
    async def agencyos_health():
        return {
            "status": "ok",
            "service": "agencyos",
            "version": "0.3.0",
        }

    # Ensure AgencyOS tables exist (create if missing)
    try:
        from open_webui.internal.db import engine, Base
        from .models.db import (
            AgencyOSOrganization,
            AgencyOSMember,
            AgencyOSDepartment,
            AgencyOSKnowledge,
            AgencyOSProposal,
            AgencyOSAuditLog,
        )
        # Create only agencyos_ tables, don't touch OpenWebUI tables
        agencyos_tables = [
            AgencyOSOrganization.__table__,
            AgencyOSMember.__table__,
            AgencyOSDepartment.__table__,
            AgencyOSKnowledge.__table__,
            AgencyOSProposal.__table__,
            AgencyOSAuditLog.__table__,
        ]
        Base.metadata.create_all(bind=engine, tables=agencyos_tables)
        logger.info("AgencyOS database tables verified/created")
    except Exception as e:
        logger.warning(f"AgencyOS table creation skipped: {e}")

    logger.info("AgencyOS mounted — 6 routers, 5 middleware layers (error/rate/auth-redirect/jwt/tenant)")
