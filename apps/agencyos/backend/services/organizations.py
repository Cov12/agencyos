"""
AgencyOS Organization CRUD Service
"""

import time
import logging
from typing import Optional

from sqlalchemy.orm import Session

from ..models.db import (
    AgencyOSOrganization,
    AgencyOSMember,
    AgencyOSDepartment,
    generate_id,
    now_ms,
)

log = logging.getLogger("agencyos.services.organizations")


class OrganizationsService:
    """CRUD operations for organizations and members."""

    @staticmethod
    def create_org(
        db: Session,
        name: str,
        slug: str,
        workpipe_account_id: Optional[str] = None,
        plan: str = "starter",
        portal_org_id: Optional[str] = None,
    ) -> AgencyOSOrganization:
        # #66 Stage 2 (Approach A): when this org is provisioned from a Portal-authed
        # request, portal_org_id carries the Portal org CUID so the bridge later derives
        # this org's OWN per-org Cortex company (cortex_bridge._resolve_company_id).
        # Left NULL when unknown -> the bridge falls back to the WBIT_COMPANY_ID pin.
        org = AgencyOSOrganization(
            id=generate_id(),
            name=name,
            slug=slug,
            portal_org_id=portal_org_id or None,
            workpipe_account_id=workpipe_account_id,
            plan=plan,
            created_at=now_ms(),
            updated_at=now_ms(),
        )
        db.add(org)
        db.commit()
        db.refresh(org)
        log.info(f"Created org: {org.name} ({org.slug})")
        return org

    @staticmethod
    def stamp_portal_org_id(
        db: Session, internal_org_id: str, portal_org_id: str
    ) -> bool:
        """#66 Stage 2 (Approach B): idempotent backfill of portal_org_id for org rows
        that predate Stage-2 provisioning.

        Stamps the Portal org CUID onto the row whose AgencyOS-INTERNAL id ==
        internal_org_id, but ONLY when:
          - the row exists,
          - its portal_org_id is currently NULL (never overwrite -> idempotent), and
          - it is not the WBIT-pinned 'default' org (left untouched by design; it is
            backfilled by migration 002 and pinned to …c0de via PORTAL_COMPANY_OVERRIDES).

        Returns True iff a row was stamped. Defensive by contract: this runs in the
        request path (see middleware.tenant.get_tenant_session), so it MUST NOT raise —
        it rolls back and swallows on any failure, mirroring
        cortex_bridge._portal_org_id_for."""
        if not internal_org_id or not portal_org_id:
            return False
        try:
            row = (
                db.query(AgencyOSOrganization)
                .filter(AgencyOSOrganization.id == internal_org_id)
                .one_or_none()
            )
            if row is None or row.portal_org_id is not None or row.slug == "default":
                return False
            row.portal_org_id = portal_org_id
            row.updated_at = now_ms()
            db.commit()
            log.info(
                f"Stamped portal_org_id on org {internal_org_id} ({row.slug})"
            )
            return True
        except Exception as e:  # never let a reconcile break the request
            log.warning(
                f"stamp_portal_org_id failed for org {internal_org_id}: {e}"
            )
            try:
                db.rollback()
            except Exception:
                pass
            return False

    @staticmethod
    def get_org_by_id(db: Session, org_id: str) -> Optional[AgencyOSOrganization]:
        return db.query(AgencyOSOrganization).filter_by(id=org_id).first()

    @staticmethod
    def get_org_by_slug(db: Session, slug: str) -> Optional[AgencyOSOrganization]:
        return db.query(AgencyOSOrganization).filter_by(slug=slug).first()

    @staticmethod
    def list_orgs(db: Session) -> list[AgencyOSOrganization]:
        return db.query(AgencyOSOrganization).order_by(AgencyOSOrganization.created_at.desc()).all()

    @staticmethod
    def list_orgs_for_portal(
        db: Session, portal_org_id: str
    ) -> list[AgencyOSOrganization]:
        """#35 (GA-safety): list ONLY the org(s) owned by the caller's Portal org.

        RLS is a no-op on SQLite, so cross-tenant isolation rests on explicit
        filters. The bare list endpoint previously returned EVERY org (name/slug/
        plan) to any authenticated caller — a cross-tenant enumeration leak, and the
        frontend's resolveOrganization() fallback would then pick orgs[0], which
        could belong to a DIFFERENT tenant. On the Portal-authed path the JWT's
        org_id claim is the Portal CUID, stored here as AgencyOSOrganization
        .portal_org_id, so we scope by it. Returns [] for an unknown/blank CUID
        (fail-closed to no data, never another tenant's rows)."""
        if not portal_org_id:
            return []
        return (
            db.query(AgencyOSOrganization)
            .filter(AgencyOSOrganization.portal_org_id == portal_org_id)
            .order_by(AgencyOSOrganization.created_at.desc())
            .all()
        )

    @staticmethod
    def add_member(
        db: Session,
        org_id: str,
        user_id: str,
        role: str = "member",
        department_ids: list[str] = None,
    ) -> AgencyOSMember:
        member = AgencyOSMember(
            id=generate_id(),
            org_id=org_id,
            user_id=user_id,
            role=role,
            department_ids=department_ids or [],
            created_at=now_ms(),
        )
        db.add(member)
        db.commit()
        db.refresh(member)
        log.info(f"Added member {user_id} to org {org_id} as {role}")
        return member

    @staticmethod
    def get_member(db: Session, org_id: str, user_id: str) -> Optional[AgencyOSMember]:
        return db.query(AgencyOSMember).filter_by(org_id=org_id, user_id=user_id).first()

    @staticmethod
    def list_members(db: Session, org_id: str) -> list[AgencyOSMember]:
        return db.query(AgencyOSMember).filter_by(org_id=org_id).all()

    @staticmethod
    def get_user_orgs(db: Session, user_id: str) -> list[AgencyOSMember]:
        """Get all orgs a user belongs to."""
        return db.query(AgencyOSMember).filter_by(user_id=user_id).all()

    @staticmethod
    def setup_default_departments(db: Session, org_id: str) -> list[AgencyOSDepartment]:
        """Create the 3 MVP departments for a new org."""
        defaults = [
            {
                "slug": "sales_admin",
                "name": "Sales & Admin",
                "description": "Lead prioritization, follow-up generation, pipeline summaries, deal risk detection",
                "model_tier": "mid",
                "knowledge_scope": "sales",
                "capabilities": ["lead_prioritization", "follow_up_generation", "pipeline_summaries", "deal_risk_detection"],
                "workpipe_modules": ["contacts", "pipelines", "deals"],
            },
            {
                "slug": "customer",
                "name": "Customer",
                "description": "Ticket triage, suggested replies, escalation detection, sentiment summaries",
                "model_tier": "mid",
                "knowledge_scope": "customer",
                "capabilities": ["ticket_triage", "suggested_replies", "escalation_detection", "sentiment_summaries"],
                "workpipe_modules": ["tickets", "contacts"],
            },
            {
                "slug": "back_office",
                "name": "Back Office",
                "description": "Invoice follow-up, operational tasks, financial summaries, internal checklists",
                "model_tier": "mid",
                "knowledge_scope": "operations",
                "capabilities": ["invoice_follow_up", "operational_automation", "financial_summaries", "checklist_automation"],
                "workpipe_modules": ["invoices", "tasks"],
            },
        ]

        departments = []
        for dept_data in defaults:
            dept = AgencyOSDepartment(
                id=generate_id(),
                org_id=org_id,
                created_at=now_ms(),
                updated_at=now_ms(),
                **dept_data,
            )
            db.add(dept)
            departments.append(dept)

        db.commit()
        for dept in departments:
            db.refresh(dept)

        log.info(f"Created {len(departments)} default departments for org {org_id}")
        return departments
