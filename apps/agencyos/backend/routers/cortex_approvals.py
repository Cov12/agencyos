"""
AgencyOS Cortex Approvals Routes (Approval Inbox)

API endpoints for managing Cortex approvals through the AgencyOS UI.
Provides fast local queries from the read model and proxies actions to Cortex.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from starlette.requests import Request

from ..middleware.tenant import get_tenant_session
from ..services.cortex_approvals import CortexApprovalsService
from ..services.cortex_adapter import CortexError

router = APIRouter(prefix="/api/agencyos/cortex-approvals", tags=["agencyos-cortex-approvals"])

# Service instance (singleton)
_service: Optional[CortexApprovalsService] = None


def get_service() -> CortexApprovalsService:
    """Get or create the Cortex approvals service."""
    global _service
    if _service is None:
        _service = CortexApprovalsService()
    return _service


class ApprovalDecisionRequest(BaseModel):
    """Request to approve or reject an approval."""
    decision_note: Optional[str] = None


class SyncRequest(BaseModel):
    """Request to sync approvals from Cortex."""
    cortex_company_id: str


# ============================================================================
# List & Query Endpoints
# ============================================================================


@router.get("/")
async def list_approvals(
    org_id: str,
    status: Optional[str] = None,
    approval_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_tenant_session),
):
    """
    List Cortex approvals from local read model.

    Filter by status (pending, approved, rejected) and/or type (hire_agent, custom).
    """
    service = get_service()
    approvals = service.list_approvals(
        db,
        org_id=org_id,
        status=status,
        approval_type=approval_type,
        limit=limit,
        offset=offset,
    )

    return {
        "approvals": [
            {
                "id": a.id,
                "type": a.approval_type,
                "status": a.status,
                "payload": a.payload,
                "requested_by_agent_id": a.requested_by_agent_id,
                "requested_by_agent_name": a.requested_by_agent_name,
                "decision_note": a.decision_note,
                "decided_by_user_id": a.decided_by_user_id,
                "decided_at": a.decided_at,
                "created_at": a.cortex_created_at,
                "updated_at": a.cortex_updated_at,
                "synced_at": a.synced_at,
            }
            for a in approvals
        ],
        "total": len(approvals),
    }


@router.get("/stats")
async def approval_stats(
    org_id: str,
    db: Session = Depends(get_tenant_session),
):
    """Get approval statistics for badge display and dashboard."""
    service = get_service()
    return service.get_stats(db, org_id)


@router.get("/pending-count")
async def pending_count(
    org_id: str,
    db: Session = Depends(get_tenant_session),
):
    """Get count of pending approvals (for notification badge)."""
    service = get_service()
    count = service.get_pending_count(db, org_id)
    return {"count": count}


@router.get("/{approval_id}")
async def get_approval(
    approval_id: str,
    org_id: str,
    db: Session = Depends(get_tenant_session),
):
    """Get a specific approval with full details."""
    service = get_service()
    approval = service.get_approval(db, approval_id, org_id)

    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    return {
        "id": approval.id,
        "type": approval.approval_type,
        "status": approval.status,
        "payload": approval.payload,
        "requested_by_agent_id": approval.requested_by_agent_id,
        "requested_by_agent_name": approval.requested_by_agent_name,
        "requested_by_user_id": approval.requested_by_user_id,
        "decision_note": approval.decision_note,
        "decided_by_user_id": approval.decided_by_user_id,
        "decided_at": approval.decided_at,
        "created_at": approval.cortex_created_at,
        "updated_at": approval.cortex_updated_at,
        "synced_at": approval.synced_at,
    }


# ============================================================================
# Action Endpoints
# ============================================================================


@router.post("/{approval_id}/approve")
async def approve_approval(
    approval_id: str,
    org_id: str,
    data: ApprovalDecisionRequest,
    user_id: str,  # TODO: Extract from auth token
    db: Session = Depends(get_tenant_session),
):
    """
    Approve a Cortex approval.

    Proxies to Cortex API and updates local read model.
    """
    service = get_service()

    try:
        approval = await service.approve(
            db,
            approval_id=approval_id,
            org_id=org_id,
            user_id=user_id,
            decision_note=data.decision_note,
        )

        if not approval:
            raise HTTPException(
                status_code=404,
                detail="Approval not found or already processed",
            )

        return {
            "id": approval.id,
            "status": approval.status,
            "decided_by": user_id,
            "message": "Approval approved successfully",
        }

    except CortexError as e:
        raise HTTPException(
            status_code=e.status_code or 500,
            detail=str(e),
        )


@router.post("/{approval_id}/reject")
async def reject_approval(
    approval_id: str,
    org_id: str,
    data: ApprovalDecisionRequest,
    user_id: str,  # TODO: Extract from auth token
    db: Session = Depends(get_tenant_session),
):
    """
    Reject a Cortex approval.

    Proxies to Cortex API and updates local read model.
    """
    service = get_service()

    try:
        approval = await service.reject(
            db,
            approval_id=approval_id,
            org_id=org_id,
            user_id=user_id,
            decision_note=data.decision_note,
        )

        if not approval:
            raise HTTPException(
                status_code=404,
                detail="Approval not found or already processed",
            )

        return {
            "id": approval.id,
            "status": approval.status,
            "decided_by": user_id,
            "message": "Approval rejected successfully",
        }

    except CortexError as e:
        raise HTTPException(
            status_code=e.status_code or 500,
            detail=str(e),
        )


# ============================================================================
# Sync Endpoints
# ============================================================================


@router.post("/sync")
async def sync_approvals(
    org_id: str,
    data: SyncRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_tenant_session),
):
    """
    Manually trigger a sync of approvals from Cortex.

    This is typically called:
    - On initial page load
    - Periodically in the background
    - When user clicks "refresh"
    """
    service = get_service()

    try:
        stats = await service.sync_approvals(
            db,
            org_id=org_id,
            cortex_company_id=data.cortex_company_id,
        )

        return {
            "success": True,
            "stats": stats,
            "message": f"Synced {stats['created']} new, {stats['updated']} updated",
        }

    except CortexError as e:
        raise HTTPException(
            status_code=e.status_code or 500,
            detail=f"Sync failed: {e}",
        )
