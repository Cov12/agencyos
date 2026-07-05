"""Dashboard D4b Cortex read routes (recent run/activity, read-only).

Consumes the merged Cortex bridge /history verb via services.cortex_bridge so
the cross-ecosystem dashboard can show recent Cortex runs. GET only — this is a
view surface; it never mutates and never surfaces bridge errors as failures
(the service degrades to [] on any transport/host problem).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..middleware.deps import require_app_access
from ..middleware.tenant import get_tenant_session
from ..services import cortex_bridge

router = APIRouter(
    prefix="/api/agencyos/dashboard/cortex",
    tags=["agencyos-dashboard-cortex"],
    dependencies=[Depends(require_app_access("CORTEX"))],
)


@router.get("/history")
async def get_cortex_history(
    org_id: str,
    sub_account_id: str | None = Query(default=None, alias="subAccountId"),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_tenant_session),
):
    """Recent Cortex runs for the org's company (business scope) or the given
    sub-account. `subAccountId` mirrors the WorkPipe D2 routes' query-param
    convention; `limit` is clamped to [1, 50] here (the bridge host clamps too)."""
    runs = await cortex_bridge.fetch_history(
        db,
        org_id=org_id,
        sub_account_id=sub_account_id,
        limit=limit,
    )
    return {"data": runs}
