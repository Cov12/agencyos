"""
AgencyOS Organization Routes

Multi-tenant org management — CRUD for orgs and members.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from open_webui.internal.db import get_session
from ..services.organizations import OrganizationsService

router = APIRouter(prefix="/api/agencyos/orgs", tags=["agencyos-organizations"])


class CreateOrgRequest(BaseModel):
    name: str
    slug: str
    workpipe_account_id: Optional[str] = None
    plan: str = "starter"


class AddMemberRequest(BaseModel):
    user_id: str
    role: str = "member"
    department_ids: list[str] = []


@router.post("/")
async def create_organization(
    data: CreateOrgRequest,
    db: Session = Depends(get_session),
):
    """Create a new organization with default departments."""
    existing = OrganizationsService.get_org_by_slug(db, data.slug)
    if existing:
        raise HTTPException(status_code=409, detail="Organization slug already exists")

    org = OrganizationsService.create_org(
        db, name=data.name, slug=data.slug,
        workpipe_account_id=data.workpipe_account_id, plan=data.plan,
    )
    # Auto-create MVP departments
    departments = OrganizationsService.setup_default_departments(db, org.id)

    return {
        "organization": {"id": org.id, "name": org.name, "slug": org.slug, "plan": org.plan},
        "departments": [{"id": d.id, "slug": d.slug, "name": d.name} for d in departments],
    }


@router.get("/{org_id}")
async def get_organization(
    org_id: str,
    db: Session = Depends(get_session),
):
    """Get organization details."""
    org = OrganizationsService.get_org_by_id(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {"id": org.id, "name": org.name, "slug": org.slug, "plan": org.plan, "settings": org.settings}


@router.get("/{org_id}/members")
async def list_members(
    org_id: str,
    db: Session = Depends(get_session),
):
    """List organization members."""
    members = OrganizationsService.list_members(db, org_id)
    return {
        "members": [
            {"id": m.id, "user_id": m.user_id, "role": m.role, "department_ids": m.department_ids}
            for m in members
        ],
        "total": len(members),
    }


@router.post("/{org_id}/members")
async def add_member(
    org_id: str,
    data: AddMemberRequest,
    db: Session = Depends(get_session),
):
    """Add a member to an organization."""
    org = OrganizationsService.get_org_by_id(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    member = OrganizationsService.add_member(
        db, org_id=org_id, user_id=data.user_id,
        role=data.role, department_ids=data.department_ids,
    )
    return {"id": member.id, "user_id": member.user_id, "role": member.role}
