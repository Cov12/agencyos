"""
AgencyOS SQLAlchemy Database Models

These tables are added to OpenWebUI's existing database.
All tables prefixed with 'agencyos_' to avoid conflicts.
Uses OpenWebUI's Base, SessionLocal, and migration infrastructure.
"""

import time
import uuid
import logging
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import Session

from open_webui.internal.db import Base, JSONField, get_db

log = logging.getLogger("agencyos.db")


def generate_id() -> str:
    return str(uuid.uuid4())


def now_ms() -> int:
    return int(time.time() * 1000)


####################
# Organization
####################

class AgencyOSOrganization(Base):
    """Multi-tenant organization — one per customer."""
    __tablename__ = "agencyos_organization"

    id = Column(String, primary_key=True, default=generate_id)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)  # orgslug for routing
    workpipe_account_id = Column(String, nullable=True)  # Link to WorkPipe
    plan = Column(String, default="starter")  # starter | growth | enterprise
    settings = Column(JSON, server_default="{}")

    created_at = Column(BigInteger, default=now_ms)
    updated_at = Column(BigInteger, default=now_ms)

    __table_args__ = (
        Index("agencyos_org_slug_idx", "slug"),
    )


####################
# Organization Member
####################

class AgencyOSMember(Base):
    """Maps users to organizations with roles."""
    __tablename__ = "agencyos_member"

    id = Column(String, primary_key=True, default=generate_id)
    org_id = Column(String, ForeignKey("agencyos_organization.id"), nullable=False)
    user_id = Column(String, nullable=False)  # References OpenWebUI user
    role = Column(String, default="member")  # executive | department_head | manager | member
    department_ids = Column(JSON, server_default="[]")  # Which depts they belong to

    created_at = Column(BigInteger, default=now_ms)

    __table_args__ = (
        Index("agencyos_member_org_idx", "org_id"),
        Index("agencyos_member_user_idx", "user_id"),
    )


####################
# Department
####################

class AgencyOSDepartment(Base):
    """A department within an organization."""
    __tablename__ = "agencyos_department"

    id = Column(String, primary_key=True, default=generate_id)
    org_id = Column(String, ForeignKey("agencyos_organization.id"), nullable=False)
    slug = Column(String, nullable=False)  # sales_admin, customer, back_office
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    model_tier = Column(String, default="mid")  # premium | mid | local
    knowledge_scope = Column(String, default="")  # RAG namespace
    capabilities = Column(JSON, server_default="[]")
    workpipe_modules = Column(JSON, server_default="[]")
    system_prompt = Column(Text, default="")
    is_active = Column(Boolean, default=True)

    created_at = Column(BigInteger, default=now_ms)
    updated_at = Column(BigInteger, default=now_ms)

    __table_args__ = (
        Index("agencyos_dept_org_idx", "org_id"),
        Index("agencyos_dept_slug_idx", "org_id", "slug"),
    )


####################
# Department Knowledge (RAG)
####################

class AgencyOSKnowledge(Base):
    """Knowledge base entry scoped to a department for RAG retrieval."""
    __tablename__ = "agencyos_knowledge"

    id = Column(String, primary_key=True, default=generate_id)
    department_id = Column(String, ForeignKey("agencyos_department.id"), nullable=False)
    org_id = Column(String, ForeignKey("agencyos_organization.id"), nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, server_default="{}")
    # pgvector embedding added later when vector extension is enabled

    created_at = Column(BigInteger, default=now_ms)
    updated_at = Column(BigInteger, default=now_ms)

    __table_args__ = (
        Index("agencyos_knowledge_dept_idx", "department_id"),
        Index("agencyos_knowledge_org_idx", "org_id"),
    )


####################
# Action Proposal (Delegated Mode)
####################

class AgencyOSProposal(Base):
    """AI-generated action requiring human approval before execution."""
    __tablename__ = "agencyos_proposal"

    id = Column(String, primary_key=True, default=generate_id)
    org_id = Column(String, ForeignKey("agencyos_organization.id"), nullable=False)
    department_id = Column(String, ForeignKey("agencyos_department.id"), nullable=False)
    chat_id = Column(String, nullable=True)  # OpenWebUI conversation ID

    # What the AI wants to do
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    action_type = Column(String, nullable=False)  # send_email, update_contact, etc.
    action_payload = Column(JSON, server_default="{}")

    # Risk assessment
    risk_level = Column(String, default="low")  # low | medium | high | critical
    risk_reasoning = Column(Text, default="")

    # Status tracking
    status = Column(String, default="pending")  # pending | approved | rejected | executed | failed | expired
    created_by_ai = Column(String, default="")  # Which model/dept generated this
    reviewed_by = Column(String, nullable=True)  # User ID of approver
    review_note = Column(Text, default="")
    executed_at = Column(BigInteger, nullable=True)
    execution_result = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(BigInteger, default=now_ms)
    updated_at = Column(BigInteger, default=now_ms)
    expires_at = Column(BigInteger, nullable=True)

    __table_args__ = (
        Index("agencyos_proposal_org_idx", "org_id"),
        Index("agencyos_proposal_dept_idx", "department_id"),
        Index("agencyos_proposal_status_idx", "org_id", "status"),
    )


####################
# Audit Log
####################

class AgencyOSAuditLog(Base):
    """Audit trail for all AgencyOS actions — proposals, approvals, executions."""
    __tablename__ = "agencyos_audit_log"

    id = Column(String, primary_key=True, default=generate_id)
    org_id = Column(String, ForeignKey("agencyos_organization.id"), nullable=False)
    event_type = Column(String, nullable=False)  # proposal_created, proposal_approved, action_executed, etc.
    actor_id = Column(String, nullable=True)  # User or AI that triggered the event
    actor_type = Column(String, default="user")  # user | ai
    department_id = Column(String, nullable=True)
    proposal_id = Column(String, nullable=True)
    details = Column(JSON, server_default="{}")

    created_at = Column(BigInteger, default=now_ms)

    __table_args__ = (
        Index("agencyos_audit_org_idx", "org_id"),
        Index("agencyos_audit_type_idx", "org_id", "event_type"),
    )
