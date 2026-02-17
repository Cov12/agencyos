"""
AgencyOS Organization Routes

Multi-tenant org management — CRUD for orgs and members.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from ..models.organization import (
    Organization,
    OrganizationCreate,
    OrganizationMember,
    OrganizationMemberCreate,
)

router = APIRouter(prefix="/api/agencyos/orgs", tags=["agencyos-organizations"])

# In-memory store for MVP (replace with DB)
_orgs: dict[str, Organization] = {}
_members: dict[str, list[OrganizationMember]] = {}


@router.post("/")
async def create_organization(data: OrganizationCreate):
    """Create a new organization (tenant)."""
    org = Organization(**data.model_dump())
    _orgs[org.id] = org
    _members[org.id] = []
    return org.model_dump()


@router.get("/{org_id}")
async def get_organization(org_id: str):
    """Get organization details."""
    org = _orgs.get(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org.model_dump()


@router.get("/{org_id}/members")
async def list_members(org_id: str):
    """List organization members."""
    if org_id not in _orgs:
        raise HTTPException(status_code=404, detail="Organization not found")
    members = _members.get(org_id, [])
    return {"members": [m.model_dump() for m in members], "total": len(members)}


@router.post("/{org_id}/members")
async def add_member(org_id: str, data: OrganizationMemberCreate):
    """Add a member to an organization."""
    if org_id not in _orgs:
        raise HTTPException(status_code=404, detail="Organization not found")
    member = OrganizationMember(org_id=org_id, **data.model_dump())
    _members.setdefault(org_id, []).append(member)
    return member.model_dump()
