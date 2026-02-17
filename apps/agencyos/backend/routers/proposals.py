"""
AgencyOS Proposal Routes (Approval Inbox)

The heart of Delegated Mode — manage action proposals.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from open_webui.internal.db import get_session
from ..services.proposals import ProposalsService

router = APIRouter(prefix="/api/agencyos/proposals", tags=["agencyos-proposals"])


class CreateProposalRequest(BaseModel):
    department_id: str
    title: str
    description: str
    action_type: str
    action_payload: dict = {}
    risk_level: str = "low"
    risk_reasoning: str = ""
    chat_id: Optional[str] = None


class ReviewProposalRequest(BaseModel):
    status: str  # "approved" or "rejected"
    review_note: str = ""


@router.get("/")
async def list_proposals(
    org_id: str,
    status: Optional[str] = None,
    department_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_session),
):
    """List proposals (approval inbox). Filter by status and/or department."""
    proposals = ProposalsService.list_proposals(
        db, org_id=org_id, status=status,
        department_id=department_id, limit=limit, offset=offset,
    )
    return {
        "proposals": [
            {
                "id": p.id,
                "title": p.title,
                "description": p.description,
                "action_type": p.action_type,
                "risk_level": p.risk_level,
                "status": p.status,
                "department_id": p.department_id,
                "created_by_ai": p.created_by_ai,
                "reviewed_by": p.reviewed_by,
                "created_at": p.created_at,
            }
            for p in proposals
        ],
        "total": len(proposals),
    }


@router.get("/stats")
async def proposal_stats(
    org_id: str,
    db: Session = Depends(get_session),
):
    """Get proposal statistics for the org."""
    return ProposalsService.get_stats(db, org_id)


@router.get("/{proposal_id}")
async def get_proposal(
    proposal_id: str,
    org_id: str,
    db: Session = Depends(get_session),
):
    """Get a specific proposal."""
    proposal = ProposalsService.get_proposal(db, proposal_id, org_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return {
        "id": proposal.id,
        "title": proposal.title,
        "description": proposal.description,
        "action_type": proposal.action_type,
        "action_payload": proposal.action_payload,
        "risk_level": proposal.risk_level,
        "risk_reasoning": proposal.risk_reasoning,
        "status": proposal.status,
        "department_id": proposal.department_id,
        "chat_id": proposal.chat_id,
        "created_by_ai": proposal.created_by_ai,
        "reviewed_by": proposal.reviewed_by,
        "review_note": proposal.review_note,
        "execution_result": proposal.execution_result,
        "created_at": proposal.created_at,
        "updated_at": proposal.updated_at,
    }


@router.post("/")
async def create_proposal(
    org_id: str,
    data: CreateProposalRequest,
    db: Session = Depends(get_session),
):
    """Create a new action proposal (called by AI during chat)."""
    proposal = ProposalsService.create_proposal(
        db, org_id=org_id,
        department_id=data.department_id,
        title=data.title,
        description=data.description,
        action_type=data.action_type,
        action_payload=data.action_payload,
        risk_level=data.risk_level,
        risk_reasoning=data.risk_reasoning,
        chat_id=data.chat_id,
    )
    return {"id": proposal.id, "title": proposal.title, "status": proposal.status}


@router.post("/{proposal_id}/review")
async def review_proposal(
    proposal_id: str,
    org_id: str,
    data: ReviewProposalRequest,
    user_id: str,  # TODO: Extract from auth token
    db: Session = Depends(get_session),
):
    """Approve or reject a proposal."""
    if data.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Status must be 'approved' or 'rejected'")

    proposal = ProposalsService.review_proposal(
        db, proposal_id=proposal_id, org_id=org_id,
        reviewed_by=user_id, status=data.status,
        review_note=data.review_note,
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found or not pending")

    # If approved, execute the action
    if proposal.status == "approved":
        # TODO: Route to appropriate tool/integration based on action_type
        # For now, just mark as executed
        proposal = ProposalsService.mark_executed(db, proposal_id, org_id, {"note": "execution pending integration"})

    return {"id": proposal.id, "status": proposal.status}
