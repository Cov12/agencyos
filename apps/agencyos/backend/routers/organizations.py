"""
AgencyOS Organization Routes

Multi-tenant org management — CRUD for orgs and members.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from ..middleware.tenant import get_tenant_session
from ..models.db import AgencyOSSubAccount
from ..services.organizations import OrganizationsService
from ..services.subaccount_sync import (
    AGENCYOS_SUBACCOUNT_COOKIE,
    BUSINESS_SCOPE_SENTINEL,
    list_active_subaccounts,
    resolve_active_subaccount_id,
)

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


@router.get("/")
async def list_organizations(
    request: Request,
    db: Session = Depends(get_tenant_session),
):
    """List organizations for user org resolution.

    #35 (GA-safety): on the Portal-authed path this is scoped to the caller's own
    Portal org (portal_auth.org_id == AgencyOSOrganization.portal_org_id) so it can
    no longer enumerate every tenant's orgs. The unauthenticated dev/OWUI-internal
    fallback (no portal_auth — e.g. the X-Org-Id header path, which is gated to
    non-prod by require_app_access elsewhere) keeps the legacy list-all behavior so
    single-tenant/dev flows are unaffected.
    """
    portal_auth = getattr(request.state, "portal_auth", None)
    portal_cuid = getattr(portal_auth, "org_id", None) if portal_auth else None
    if portal_cuid:
        orgs = OrganizationsService.list_orgs_for_portal(db, portal_cuid)
    else:
        orgs = OrganizationsService.list_orgs(db)
    return [
        {"id": o.id, "name": o.name, "slug": o.slug, "plan": o.plan}
        for o in orgs
    ]


@router.post("/")
async def create_organization(
    data: CreateOrgRequest,
    request: Request,
    db: Session = Depends(get_tenant_session),
):
    """Create a new organization with default departments."""
    existing = OrganizationsService.get_org_by_slug(db, data.slug)
    if existing:
        raise HTTPException(status_code=409, detail="Organization slug already exists")

    # #66 Stage 2 (Approach A): if this create is Portal-authed, stamp the new org with
    # the Portal org CUID (the JWT's org_id claim, surfaced on request.state.portal_auth
    # by JWTAuthMiddleware) so it resolves to its OWN per-org Cortex company. Guarded
    # defensively — a missing/empty portal_auth must never block org creation.
    portal_auth = getattr(request.state, "portal_auth", None)
    portal_org_id = getattr(portal_auth, "org_id", None) if portal_auth else None

    org = OrganizationsService.create_org(
        db, name=data.name, slug=data.slug,
        workpipe_account_id=data.workpipe_account_id, plan=data.plan,
        portal_org_id=portal_org_id or None,
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
    db: Session = Depends(get_tenant_session),
):
    """Get organization details."""
    org = OrganizationsService.get_org_by_id(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {"id": org.id, "name": org.name, "slug": org.slug, "plan": org.plan, "settings": org.settings}


@router.get("/{org_id}/subaccounts")
async def list_org_subaccounts(
    org_id: str,
    request: Request,
    db: Session = Depends(get_tenant_session),
):
    """List ACTIVE mirrored sub-accounts plus the current chat scope selection."""
    org = OrganizationsService.get_org_by_id(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    active_subaccount_id = resolve_active_subaccount_id(
        db, org_id, request.cookies.get(AGENCYOS_SUBACCOUNT_COOKIE)
    )
    subaccounts = list_active_subaccounts(db, org_id)
    return {
        "subAccounts": [
            {
                "id": s.id,
                "name": s.name,
                "slug": s.slug,
                "status": s.status,
            }
            for s in subaccounts
        ],
        "activeSubAccountId": active_subaccount_id,
    }


@router.post("/{org_id}/subaccounts/select")
async def select_org_subaccount(
    org_id: str,
    request: Request,
    db: Session = Depends(get_tenant_session),
):
    """Persist the active AgencyOS chat scope in an httpOnly cookie."""
    org = OrganizationsService.get_org_by_id(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    try:
        body = await request.json()
    except Exception:
        body = {}

    candidate = body.get("subAccountId") if isinstance(body, dict) else None
    sub_account_id = candidate.strip() if isinstance(candidate, str) else None

    cookie_value = BUSINESS_SCOPE_SENTINEL
    selected: str | None = None
    if sub_account_id:
        subaccount = (
            db.query(AgencyOSSubAccount)
            .filter(AgencyOSSubAccount.org_id == org_id)
            .filter(AgencyOSSubAccount.id == sub_account_id)
            .first()
        )
        if not subaccount or (subaccount.status or "").lower() != "active":
            raise HTTPException(status_code=404, detail="Sub-account not found in this organization")
        cookie_value = str(subaccount.id)
        selected = str(subaccount.id)

    response = JSONResponse({"selected": selected})
    response.set_cookie(
        key=AGENCYOS_SUBACCOUNT_COOKIE,
        value=cookie_value,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        max_age=60 * 60 * 24 * 365,
        path="/",
    )
    return response


@router.get("/{org_id}/members")
async def list_members(
    org_id: str,
    db: Session = Depends(get_tenant_session),
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
    db: Session = Depends(get_tenant_session),
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
