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
    ) -> AgencyOSOrganization:
        org = AgencyOSOrganization(
            id=generate_id(),
            name=name,
            slug=slug,
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
    def get_org_by_id(db: Session, org_id: str) -> Optional[AgencyOSOrganization]:
        return db.query(AgencyOSOrganization).filter_by(id=org_id).first()

    @staticmethod
    def get_org_by_slug(db: Session, slug: str) -> Optional[AgencyOSOrganization]:
        return db.query(AgencyOSOrganization).filter_by(slug=slug).first()

    @staticmethod
    def list_orgs(db: Session) -> list[AgencyOSOrganization]:
        return db.query(AgencyOSOrganization).order_by(AgencyOSOrganization.created_at.desc()).all()

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
