"""
AgencyOS Employee Tabs Service

Manages dynamic employee chat tabs driven by Cortex agent status.
Persists tab visibility and conversation history across sessions.

Flow:
1. Sync: Fetch active agents from Cortex, create/update local tab state
2. Interact: User sends message to agent, update conversation history
3. Toggle: User hides/shows tab, persist visibility
4. Pin: User pins tab for quick access
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from ..models.db import (
    AgencyOSEmployeeTab,
    AgencyOSAuditLog,
    generate_id,
    now_ms,
)
from .cortex_adapter import CortexAdapter, CortexError, get_cortex_adapter
from .cortex_types import AgentStatus, EmployeeTabState

log = logging.getLogger("agencyos.services.employee_tabs")


class EmployeeTabsService:
    """
    Service for managing dynamic employee chat tabs.

    Provides:
    - Sync tabs from Cortex agent list
    - Persist conversation history
    - Toggle visibility and pin state
    - Retrieve tabs for UI rendering
    """

    def __init__(self, cortex_adapter: Optional[CortexAdapter] = None):
        """Initialize with optional custom Cortex adapter."""
        self.cortex = cortex_adapter or get_cortex_adapter()

    # ========================================================================
    # Sync Operations
    # ========================================================================

    async def sync_tabs(
        self,
        db: Session,
        org_id: str,
        user_id: str,
        cortex_company_id: str,
    ) -> dict:
        """
        Sync employee tabs from Cortex agent list.

        Creates new tabs for agents not yet tracked.
        Updates status for existing tabs.
        Does NOT delete tabs (preserves history).

        Args:
            db: Database session
            org_id: AgencyOS organization ID
            user_id: OpenWebUI user ID
            cortex_company_id: Cortex company ID

        Returns:
            Sync statistics
        """
        stats = {"created": 0, "updated": 0, "unchanged": 0, "errors": 0}

        try:
            agents = await self.cortex.list_agents(cortex_company_id)
        except CortexError as e:
            log.error(f"Failed to fetch agents from Cortex: {e}")
            stats["errors"] = 1
            return stats

        for agent in agents:
            # Only sync active agents
            if agent.status not in (AgentStatus.ACTIVE, AgentStatus.PENDING_APPROVAL):
                continue

            try:
                existing = db.query(AgencyOSEmployeeTab).filter_by(
                    org_id=org_id,
                    user_id=user_id,
                    agent_id=agent.id,
                ).first()

                if existing:
                    # Update if agent info changed
                    if self._tab_needs_update(existing, agent):
                        existing.agent_name = agent.name
                        existing.agent_icon = agent.icon
                        existing.department = agent.role
                        existing.updated_at = now_ms()
                        stats["updated"] += 1
                    else:
                        stats["unchanged"] += 1
                else:
                    # Create new tab
                    tab = AgencyOSEmployeeTab(
                        id=generate_id(),
                        org_id=org_id,
                        user_id=user_id,
                        agent_id=agent.id,
                        agent_name=agent.name,
                        agent_icon=agent.icon,
                        department=agent.role,
                        is_visible=True,
                        is_pinned=False,
                        sort_order=now_ms(),
                        conversation_history=[],
                        created_at=now_ms(),
                        updated_at=now_ms(),
                    )
                    db.add(tab)
                    stats["created"] += 1

            except Exception as e:
                log.error(f"Failed to sync tab for agent {agent.id}: {e}")
                stats["errors"] += 1

        db.commit()
        log.info(
            f"Tab sync complete: {stats['created']} created, {stats['updated']} updated"
        )
        return stats

    def _tab_needs_update(self, tab: AgencyOSEmployeeTab, agent) -> bool:
        """Check if tab needs updating based on agent changes."""
        return (
            tab.agent_name != agent.name
            or tab.agent_icon != agent.icon
            or tab.department != agent.role
        )

    # ========================================================================
    # Query Operations
    # ========================================================================

    @staticmethod
    def list_tabs(
        db: Session,
        org_id: str,
        user_id: str,
        visible_only: bool = True,
    ) -> list[AgencyOSEmployeeTab]:
        """
        List employee tabs for a user.

        Args:
            db: Database session
            org_id: AgencyOS organization ID
            user_id: OpenWebUI user ID
            visible_only: If True, only return visible tabs

        Returns:
            List of tabs sorted by pinned status and sort_order
        """
        query = db.query(AgencyOSEmployeeTab).filter_by(
            org_id=org_id,
            user_id=user_id,
        )

        if visible_only:
            query = query.filter_by(is_visible=True)

        return query.order_by(
            AgencyOSEmployeeTab.is_pinned.desc(),
            AgencyOSEmployeeTab.sort_order.asc(),
        ).all()

    @staticmethod
    def get_tab(
        db: Session,
        tab_id: str,
        org_id: str,
        user_id: str,
    ) -> Optional[AgencyOSEmployeeTab]:
        """Get a single tab by ID."""
        return db.query(AgencyOSEmployeeTab).filter_by(
            id=tab_id,
            org_id=org_id,
            user_id=user_id,
        ).first()

    @staticmethod
    def get_tab_by_agent(
        db: Session,
        agent_id: str,
        org_id: str,
        user_id: str,
    ) -> Optional[AgencyOSEmployeeTab]:
        """Get a tab by agent ID."""
        return db.query(AgencyOSEmployeeTab).filter_by(
            agent_id=agent_id,
            org_id=org_id,
            user_id=user_id,
        ).first()

    # ========================================================================
    # Tab State Operations
    # ========================================================================

    @staticmethod
    def toggle_visibility(
        db: Session,
        tab_id: str,
        org_id: str,
        user_id: str,
        is_visible: bool,
    ) -> Optional[AgencyOSEmployeeTab]:
        """Toggle tab visibility."""
        tab = db.query(AgencyOSEmployeeTab).filter_by(
            id=tab_id,
            org_id=org_id,
            user_id=user_id,
        ).first()

        if not tab:
            return None

        tab.is_visible = is_visible
        tab.updated_at = now_ms()
        db.commit()
        db.refresh(tab)

        log.info(f"Tab {tab_id} visibility set to {is_visible}")
        return tab

    @staticmethod
    def toggle_pin(
        db: Session,
        tab_id: str,
        org_id: str,
        user_id: str,
        is_pinned: bool,
    ) -> Optional[AgencyOSEmployeeTab]:
        """Toggle tab pin state."""
        tab = db.query(AgencyOSEmployeeTab).filter_by(
            id=tab_id,
            org_id=org_id,
            user_id=user_id,
        ).first()

        if not tab:
            return None

        tab.is_pinned = is_pinned
        tab.updated_at = now_ms()
        db.commit()
        db.refresh(tab)

        log.info(f"Tab {tab_id} pin state set to {is_pinned}")
        return tab

    @staticmethod
    def update_sort_order(
        db: Session,
        tab_id: str,
        org_id: str,
        user_id: str,
        sort_order: int,
    ) -> Optional[AgencyOSEmployeeTab]:
        """Update tab sort order."""
        tab = db.query(AgencyOSEmployeeTab).filter_by(
            id=tab_id,
            org_id=org_id,
            user_id=user_id,
        ).first()

        if not tab:
            return None

        tab.sort_order = sort_order
        tab.updated_at = now_ms()
        db.commit()
        db.refresh(tab)
        return tab

    # ========================================================================
    # Conversation Operations
    # ========================================================================

    @staticmethod
    def add_message(
        db: Session,
        tab_id: str,
        org_id: str,
        user_id: str,
        role: str,
        content: str,
    ) -> Optional[AgencyOSEmployeeTab]:
        """
        Add a message to the tab's conversation history.

        Args:
            db: Database session
            tab_id: Tab ID
            org_id: AgencyOS organization ID
            user_id: OpenWebUI user ID
            role: Message role ('user' or 'assistant')
            content: Message content

        Returns:
            Updated tab or None if not found
        """
        tab = db.query(AgencyOSEmployeeTab).filter_by(
            id=tab_id,
            org_id=org_id,
            user_id=user_id,
        ).first()

        if not tab:
            return None

        # Get existing history or initialize
        history = tab.conversation_history or []

        # Add new message
        history.append({
            "role": role,
            "content": content,
            "timestamp": now_ms(),
        })

        # Keep last 100 messages
        if len(history) > 100:
            history = history[-100:]

        tab.conversation_history = history
        tab.last_interaction_at = now_ms()
        tab.updated_at = now_ms()

        db.commit()
        db.refresh(tab)
        return tab

    @staticmethod
    def clear_history(
        db: Session,
        tab_id: str,
        org_id: str,
        user_id: str,
    ) -> Optional[AgencyOSEmployeeTab]:
        """Clear conversation history for a tab."""
        tab = db.query(AgencyOSEmployeeTab).filter_by(
            id=tab_id,
            org_id=org_id,
            user_id=user_id,
        ).first()

        if not tab:
            return None

        tab.conversation_history = []
        tab.updated_at = now_ms()
        db.commit()
        db.refresh(tab)

        log.info(f"Tab {tab_id} history cleared")
        return tab

    # ========================================================================
    # DTO Conversion
    # ========================================================================

    @staticmethod
    def to_state(tab: AgencyOSEmployeeTab) -> EmployeeTabState:
        """Convert database model to EmployeeTabState DTO."""
        from datetime import datetime

        return EmployeeTabState(
            agent_id=tab.agent_id,
            agent_name=tab.agent_name,
            agent_icon=tab.agent_icon,
            department=tab.department,
            status=AgentStatus.ACTIVE,  # Assume active if in tabs
            is_visible=tab.is_visible,
            has_pending_approval=False,  # Could be enriched from Cortex
            last_interaction_at=(
                datetime.fromtimestamp(tab.last_interaction_at / 1000)
                if tab.last_interaction_at
                else None
            ),
            conversation_history=[
                {"role": m.get("role", ""), "content": m.get("content", "")}
                for m in (tab.conversation_history or [])
            ],
        )
