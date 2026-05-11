"""
AgencyOS Cortex Approvals Service

Manages the local read model for Cortex approvals.
Syncs from Cortex and provides fast local queries for the approval inbox UI.
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..models.db import (
    AgencyOSCortexApproval,
    AgencyOSAuditLog,
    generate_id,
    now_ms,
)
from .cortex_adapter import CortexAdapter, CortexError, get_cortex_adapter
from .cortex_types import ApprovalSyncEvent, ApprovalStatus, ApprovalType

log = logging.getLogger("agencyos.services.cortex_approvals")


class CortexApprovalsService:
    """
    Service for managing Cortex approval read model.

    Provides:
    - Sync from Cortex to local DB
    - Local CRUD for fast UI queries
    - Proxy approve/reject to Cortex with local update
    """

    def __init__(self, cortex_adapter: Optional[CortexAdapter] = None):
        """Initialize with optional custom Cortex adapter."""
        self.cortex = cortex_adapter or get_cortex_adapter()

    # ========================================================================
    # Sync Operations
    # ========================================================================

    async def sync_approvals(
        self,
        db: Session,
        org_id: str,
        cortex_company_id: str,
    ) -> dict:
        """
        Sync approvals from Cortex to local read model.

        Args:
            db: Database session
            org_id: AgencyOS organization ID
            cortex_company_id: Cortex company ID to sync from

        Returns:
            Sync statistics (created, updated, unchanged)
        """
        stats = {"created": 0, "updated": 0, "unchanged": 0, "errors": 0}

        try:
            events = await self.cortex.sync_approvals(cortex_company_id)
        except CortexError as e:
            log.error(f"Failed to sync approvals from Cortex: {e}")
            stats["errors"] = 1
            return stats

        for event in events:
            try:
                existing = db.query(AgencyOSCortexApproval).filter_by(id=event.approval_id).first()

                if existing:
                    # Update if changed
                    if self._approval_changed(existing, event):
                        self._update_approval(existing, event)
                        stats["updated"] += 1
                    else:
                        stats["unchanged"] += 1
                else:
                    # Create new
                    approval = self._create_approval_from_event(org_id, cortex_company_id, event)
                    db.add(approval)
                    stats["created"] += 1

            except Exception as e:
                log.error(f"Failed to sync approval {event.approval_id}: {e}")
                stats["errors"] += 1

        db.commit()
        log.info(
            f"Sync complete: {stats['created']} created, {stats['updated']} updated, "
            f"{stats['unchanged']} unchanged, {stats['errors']} errors"
        )
        return stats

    def _approval_changed(
        self,
        existing: AgencyOSCortexApproval,
        event: ApprovalSyncEvent,
    ) -> bool:
        """Check if approval has changed since last sync."""
        event_updated_ms = int(event.updated_at.timestamp() * 1000)
        return existing.cortex_updated_at != event_updated_ms

    def _create_approval_from_event(
        self,
        org_id: str,
        cortex_company_id: str,
        event: ApprovalSyncEvent,
    ) -> AgencyOSCortexApproval:
        """Create a new approval record from sync event."""
        return AgencyOSCortexApproval(
            id=event.approval_id,
            org_id=org_id,
            cortex_company_id=cortex_company_id,
            approval_type=event.type.value,
            status=event.status.value,
            payload=event.payload,
            requested_by_agent_id=event.requested_by_agent_id,
            requested_by_agent_name=event.requested_by_agent_name,
            cortex_created_at=int(event.created_at.timestamp() * 1000),
            cortex_updated_at=int(event.updated_at.timestamp() * 1000),
            synced_at=now_ms(),
        )

    def _update_approval(
        self,
        existing: AgencyOSCortexApproval,
        event: ApprovalSyncEvent,
    ) -> None:
        """Update existing approval from sync event."""
        existing.status = event.status.value
        existing.payload = event.payload
        existing.cortex_updated_at = int(event.updated_at.timestamp() * 1000)
        existing.synced_at = now_ms()

    # ========================================================================
    # Query Operations
    # ========================================================================

    @staticmethod
    def list_approvals(
        db: Session,
        org_id: str,
        status: Optional[str] = None,
        approval_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AgencyOSCortexApproval]:
        """List approvals from local read model."""
        query = db.query(AgencyOSCortexApproval).filter_by(org_id=org_id)

        if status:
            query = query.filter_by(status=status)
        if approval_type:
            query = query.filter_by(approval_type=approval_type)

        return (
            query.order_by(AgencyOSCortexApproval.cortex_created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_approval(
        db: Session,
        approval_id: str,
        org_id: str,
    ) -> Optional[AgencyOSCortexApproval]:
        """Get a single approval by ID."""
        return db.query(AgencyOSCortexApproval).filter_by(
            id=approval_id,
            org_id=org_id,
        ).first()

    @staticmethod
    def get_stats(db: Session, org_id: str) -> dict:
        """Get approval statistics for the org."""
        approvals = db.query(AgencyOSCortexApproval).filter_by(org_id=org_id).all()
        return {
            "total": len(approvals),
            "pending": sum(1 for a in approvals if a.status == "pending"),
            "approved": sum(1 for a in approvals if a.status == "approved"),
            "rejected": sum(1 for a in approvals if a.status == "rejected"),
            "revision_requested": sum(1 for a in approvals if a.status == "revision_requested"),
            "hire_agent": sum(1 for a in approvals if a.approval_type == "hire_agent"),
        }

    @staticmethod
    def get_pending_count(db: Session, org_id: str) -> int:
        """Get count of pending approvals (for badge display)."""
        return db.query(AgencyOSCortexApproval).filter_by(
            org_id=org_id,
            status="pending",
        ).count()

    # ========================================================================
    # Action Operations (Proxy to Cortex)
    # ========================================================================

    async def approve(
        self,
        db: Session,
        approval_id: str,
        org_id: str,
        user_id: str,
        decision_note: Optional[str] = None,
    ) -> Optional[AgencyOSCortexApproval]:
        """
        Approve a Cortex approval.

        Proxies to Cortex API and updates local read model.
        """
        local = self.get_approval(db, approval_id, org_id)
        if not local:
            return None

        if local.status != "pending":
            log.warning(f"Approval {approval_id} is already {local.status}")
            return None

        try:
            # Proxy to Cortex
            result = await self.cortex.approve_approval(approval_id, decision_note)

            # Update local read model
            local.status = result.status.value
            local.decision_note = decision_note
            local.decided_by_user_id = user_id
            local.decided_at = now_ms()
            local.synced_at = now_ms()

            # Audit log
            audit = AgencyOSAuditLog(
                id=generate_id(),
                org_id=org_id,
                event_type="cortex_approval_approved",
                actor_id=user_id,
                actor_type="user",
                details={
                    "approval_id": approval_id,
                    "approval_type": local.approval_type,
                    "decision_note": decision_note,
                },
                created_at=now_ms(),
            )
            db.add(audit)
            db.commit()
            db.refresh(local)

            log.info(f"Approval {approval_id} approved by {user_id}")
            return local

        except CortexError as e:
            log.error(f"Failed to approve in Cortex: {e}")
            raise

    async def reject(
        self,
        db: Session,
        approval_id: str,
        org_id: str,
        user_id: str,
        decision_note: Optional[str] = None,
    ) -> Optional[AgencyOSCortexApproval]:
        """
        Reject a Cortex approval.

        Proxies to Cortex API and updates local read model.
        """
        local = self.get_approval(db, approval_id, org_id)
        if not local:
            return None

        if local.status != "pending":
            log.warning(f"Approval {approval_id} is already {local.status}")
            return None

        try:
            # Proxy to Cortex
            result = await self.cortex.reject_approval(approval_id, decision_note)

            # Update local read model
            local.status = result.status.value
            local.decision_note = decision_note
            local.decided_by_user_id = user_id
            local.decided_at = now_ms()
            local.synced_at = now_ms()

            # Audit log
            audit = AgencyOSAuditLog(
                id=generate_id(),
                org_id=org_id,
                event_type="cortex_approval_rejected",
                actor_id=user_id,
                actor_type="user",
                details={
                    "approval_id": approval_id,
                    "approval_type": local.approval_type,
                    "decision_note": decision_note,
                },
                created_at=now_ms(),
            )
            db.add(audit)
            db.commit()
            db.refresh(local)

            log.info(f"Approval {approval_id} rejected by {user_id}")
            return local

        except CortexError as e:
            log.error(f"Failed to reject in Cortex: {e}")
            raise
