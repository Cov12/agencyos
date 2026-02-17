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
from .middleware.tenant import TenantMiddleware

logger = logging.getLogger("agencyos")


def mount_agencyos(app: FastAPI) -> None:
    """
    Mount all AgencyOS routes and middleware onto the OpenWebUI FastAPI app.
    
    Usage in OpenWebUI's main.py:
        from apps.agencyos.backend.mount import mount_agencyos
        mount_agencyos(app)
    """
    # Add tenant isolation middleware
    app.add_middleware(TenantMiddleware)

    # Mount API routers
    app.include_router(organizations_router)
    app.include_router(departments_router)
    app.include_router(proposals_router)

    # Health check
    @app.get("/api/agencyos/health")
    async def agencyos_health():
        return {
            "status": "ok",
            "service": "agencyos",
            "version": "0.1.0",
        }

    logger.info("AgencyOS mounted successfully — 3 routers, tenant middleware active")
