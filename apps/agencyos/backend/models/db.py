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
    # Portal org id (a CUID) — the cross-system identity the bridge runs through
    # cortex_bridge._resolve_company_id to derive this org's Cortex company UUID, in
    # lockstep with Cortex's resolvePortalCompany. NULL -> bridge falls back to the
    # WBIT_COMPANY_ID pin. Populated by backfill (WBIT) / org provisioning (#66 Stage 2).
    portal_org_id = Column(String, nullable=True)
    workpipe_account_id = Column(String, nullable=True)  # Link to WorkPipe
    plan = Column(String, default="starter")  # starter | growth | enterprise
    settings = Column(JSON, server_default="{}")
    # Per-org Portal app entitlement, cached from the Portal JWT at portal-exchange
    # (routers/auths.py portal_token_exchange). This is what require_app_access reads
    # on the OWUI-session path (middleware/deps.py) — the OWUI session token carries no
    # app_access claim, so the entitlement must live server-side per org. Mirrors why
    # Cortex persists app_access. Added to existing prod rows by migration 005; NULL/[]
    # means "no apps entitled" (fail-closed).
    app_access = Column(JSON, server_default="[]")

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


####################
# Cortex Approval (Read Model)
####################

class AgencyOSCortexApproval(Base):
    """
    Mirrored copy of Cortex approvals for fast local UI rendering.

    This is a read model - the source of truth is in Cortex.
    Synced periodically via the CortexAdapter.sync_approvals() method.
    """
    __tablename__ = "agencyos_cortex_approval"

    id = Column(String, primary_key=True)  # Same ID as Cortex
    org_id = Column(String, ForeignKey("agencyos_organization.id"), nullable=False)
    cortex_company_id = Column(String, nullable=False)  # Cortex company ID

    # Approval info
    approval_type = Column(String, nullable=False)  # hire_agent, custom, etc.
    status = Column(String, nullable=False)  # pending, approved, rejected, revision_requested
    payload = Column(JSON, server_default="{}")

    # Requester info
    requested_by_agent_id = Column(String, nullable=True)
    requested_by_agent_name = Column(String, nullable=True)
    requested_by_user_id = Column(String, nullable=True)

    # Decision info
    decision_note = Column(Text, nullable=True)
    decided_by_user_id = Column(String, nullable=True)
    decided_at = Column(BigInteger, nullable=True)

    # Timestamps (from Cortex)
    cortex_created_at = Column(BigInteger, nullable=False)
    cortex_updated_at = Column(BigInteger, nullable=False)

    # Local sync tracking
    synced_at = Column(BigInteger, default=now_ms)

    __table_args__ = (
        Index("agencyos_cortex_approval_org_idx", "org_id"),
        Index("agencyos_cortex_approval_status_idx", "org_id", "status"),
        Index("agencyos_cortex_approval_type_idx", "org_id", "approval_type"),
    )


####################
# Cortex Employee Tab State
####################

class AgencyOSEmployeeTab(Base):
    """
    Persisted employee tab state for dynamic chat tabs.

    Stores visibility and conversation history for each Cortex agent
    that the user has interacted with.
    """
    __tablename__ = "agencyos_employee_tab"

    id = Column(String, primary_key=True, default=generate_id)
    org_id = Column(String, ForeignKey("agencyos_organization.id"), nullable=False)
    user_id = Column(String, nullable=False)  # OpenWebUI user ID

    # Agent info (from Cortex)
    agent_id = Column(String, nullable=False)
    agent_name = Column(String, nullable=False)
    agent_icon = Column(String, nullable=True)
    department = Column(String, nullable=False)

    # Tab state
    is_visible = Column(Boolean, default=True)
    is_pinned = Column(Boolean, default=False)
    sort_order = Column(BigInteger, default=0)

    # Conversation history (stored locally)
    conversation_history = Column(JSON, server_default="[]")
    last_interaction_at = Column(BigInteger, nullable=True)

    # Timestamps
    created_at = Column(BigInteger, default=now_ms)
    updated_at = Column(BigInteger, default=now_ms)

    __table_args__ = (
        Index("agencyos_employee_tab_org_user_idx", "org_id", "user_id"),
        Index("agencyos_employee_tab_agent_idx", "org_id", "agent_id"),
    )


####################
# Cortex Bridge Session
####################


class AgencyOSCortexSession(Base):
    """Maps an OpenWebUI chat to a persistent Cortex bridge session id, so a
    multi-turn chat threads the same Hermes conversation. Written by the
    cortex_bridge thin-transport path (services/cortex_bridge.py)."""

    __tablename__ = "agencyos_cortex_session"

    chat_id = Column(String, primary_key=True)  # OpenWebUI chat id
    org_id = Column(String, nullable=True)  # AgencyOS org (for scoping / cleanup)
    cortex_session_id = Column(String, nullable=False)

    created_at = Column(BigInteger, default=now_ms)
    updated_at = Column(BigInteger, default=now_ms)


####################
# Sub-Account Mirror (Portal read model)
####################


class AgencyOSSubAccount(Base):
    """Local mirror of an org's Portal sub-accounts (issue #27 / A1).

    Portal is the source of truth for sub-account identity; AgencyOS runs its own
    SQLite (webui.db) and cannot share Portal's Postgres, so it PULLs the list per
    org (services/subaccount_sync.py -> Portal GET /api/subaccounts) and mirrors it
    here. The PK is Portal's SubAccount.id (a CUID) stored VERBATIM — never minted
    locally — so AgencyOS keys the SAME sub-account identity as WorkPipe/Drive/Portal
    (WorkPipe's CRM rows are scoped by this exact `subAccountId`; see services/crm_adapter
    and services/workpipe_dashboard).

    Distinct from AgencyOSOrganization.workpipe_account_id, which pins the ONE
    sub-account a chat's memory/CRM scope binds to; this table is the full roster.

    FK is on org_id -> agencyos_organization.id (the AgencyOS-INTERNAL id), matching
    every other agencyos_* table (member/department/proposal/...), so consumers that
    already hold the internal org id can list an org's sub-accounts directly. The
    owning org's Portal CUID is also stored (portal_org_id) for cross-system tracing.
    """

    __tablename__ = "agencyos_subaccount"

    # Portal SubAccount.id (CUID), stored verbatim. NOT default=generate_id.
    id = Column(String, primary_key=True)
    org_id = Column(
        String, ForeignKey("agencyos_organization.id"), nullable=False
    )  # owning AgencyOS org (internal id)
    portal_org_id = Column(String, nullable=True)  # owning org's Portal CUID

    name = Column(String, nullable=True)
    slug = Column(String, nullable=True)
    status = Column(String, nullable=True)

    created_at = Column(BigInteger, default=now_ms)
    updated_at = Column(BigInteger, default=now_ms)
    synced_at = Column(BigInteger, default=now_ms)  # last time Portal confirmed this row

    __table_args__ = (
        Index("agencyos_subaccount_org_idx", "org_id"),
        Index("agencyos_subaccount_portal_org_idx", "portal_org_id"),
    )
