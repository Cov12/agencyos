"""
AgencyOS Proposal Routes (Approval Inbox)

The heart of Delegated Mode — manage action proposals.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

from ..models.proposal import (
    ActionProposal,
    ProposalCreate,
    ProposalReview,
    ProposalStatus,
)
from ..services.orchestrator import Orchestrator

router = APIRouter(prefix="/api/agencyos/proposals", tags=["agencyos-proposals"])

# In-memory store for MVP (replace with DB)
_proposals: dict[str, ActionProposal] = {}

_orchestrator = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator


@router.get("/")
async def list_proposals(
    org_id: str,
    status: Optional[str] = None,
    department_id: Optional[str] = None,
):
    """
    List proposals (approval inbox).
    Filter by status and/or department.
    """
    results = [p for p in _proposals.values() if p.org_id == org_id]

    if status:
        results = [p for p in results if p.status == status]
    if department_id:
        results = [p for p in results if p.department_id == department_id]

    return {
        "proposals": [p.model_dump() for p in results],
        "total": len(results),
    }


@router.get("/{proposal_id}")
async def get_proposal(proposal_id: str, org_id: str):
    """Get a specific proposal."""
    proposal = _proposals.get(proposal_id)
    if not proposal or proposal.org_id != org_id:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposal.model_dump()


@router.post("/")
async def create_proposal(
    org_id: str,
    data: ProposalCreate,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """Create a new action proposal (called by AI, not directly by users)."""
    proposal = await orchestrator.create_proposal(org_id=org_id, proposal_data=data)
    _proposals[proposal.id] = proposal
    return proposal.model_dump()


@router.post("/{proposal_id}/review")
async def review_proposal(
    proposal_id: str,
    org_id: str,
    review: ProposalReview,
    user_id: str,  # TODO: Get from auth
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """Approve or reject a proposal."""
    proposal = _proposals.get(proposal_id)
    if not proposal or proposal.org_id != org_id:
        raise HTTPException(status_code=404, detail="Proposal not found")

    if proposal.status != ProposalStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Proposal is already {proposal.status}",
        )

    # TODO: Check user has approver role for this department

    proposal.status = review.status
    proposal.reviewed_by = user_id
    proposal.review_note = review.review_note

    # If approved, execute
    if review.status == ProposalStatus.APPROVED:
        result = await orchestrator.execute_proposal(proposal)
        proposal.execution_result = result

    return proposal.model_dump()


@router.get("/stats/summary")
async def proposal_stats(org_id: str):
    """Get proposal statistics for the org."""
    org_proposals = [p for p in _proposals.values() if p.org_id == org_id]
    return {
        "total": len(org_proposals),
        "pending": sum(1 for p in org_proposals if p.status == ProposalStatus.PENDING),
        "approved": sum(1 for p in org_proposals if p.status == ProposalStatus.APPROVED),
        "rejected": sum(1 for p in org_proposals if p.status == ProposalStatus.REJECTED),
        "executed": sum(1 for p in org_proposals if p.status == ProposalStatus.EXECUTED),
    }
