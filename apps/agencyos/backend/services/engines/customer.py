"""
Customer Department Engine

Provides CRM-aware intelligence for the Customer department:
- Ticket triage and priority classification
- Suggested reply generation context
- Escalation detection
- Sentiment/workload summaries
- SLA tracking context
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from ..crm_adapter import CRMAdapter, CRMTicket

logger = logging.getLogger("agencyos.engines.customer")


@dataclass
class TicketTriage:
    ticket_id: str
    ticket_name: str
    priority: str  # low, normal, high, urgent
    signals: list[str] = field(default_factory=list)
    suggested_action: str = ""


@dataclass
class EscalationFlag:
    ticket_id: str
    ticket_name: str
    reason: str
    severity: str  # warning, critical


class CustomerEngine:
    """
    Customer department intelligence layer.

    Analyzes support tickets, triages priority, detects escalations,
    and provides context for AI-generated replies.
    """

    def __init__(self, crm: CRMAdapter):
        self.crm = crm

    # ── Ticket Triage ──────────────────────────────────────────────────

    async def triage_tickets(self, sub_account_id: str) -> dict[str, Any]:
        """
        Analyze all open tickets and assign priority scores.

        Priority signals:
        - Has "urgent" or "critical" tag → urgent
        - Unassigned → bumps priority
        - High value deal linked → bumps priority
        - No description → needs triage
        """
        pipelines = await self.crm.get_pipelines(sub_account_id)
        all_tickets: list[CRMTicket] = []
        for pipeline in pipelines:
            tickets = await self.crm.get_tickets(pipeline.id)
            all_tickets.extend(tickets)

        triaged = []
        escalations = []

        for ticket in all_tickets:
            triage = self._triage_single(ticket)
            triaged.append(triage)

            # Check for escalation
            esc = self._check_escalation(ticket)
            if esc:
                escalations.append(esc)

        # Sort: urgent first, then high, normal, low
        priority_order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
        triaged.sort(key=lambda t: priority_order.get(t.priority, 2))

        return {
            "tickets": [
                {
                    "ticket_id": t.ticket_id,
                    "name": t.ticket_name,
                    "priority": t.priority,
                    "signals": t.signals,
                    "suggested_action": t.suggested_action,
                }
                for t in triaged
            ],
            "total": len(triaged),
            "by_priority": {
                p: sum(1 for t in triaged if t.priority == p)
                for p in ("urgent", "high", "normal", "low")
            },
            "escalations": [
                {
                    "ticket_id": e.ticket_id,
                    "name": e.ticket_name,
                    "reason": e.reason,
                    "severity": e.severity,
                }
                for e in escalations
            ],
        }

    def _triage_single(self, ticket: CRMTicket) -> TicketTriage:
        """Triage a single ticket."""
        signals = []
        score = 0  # higher = more urgent

        tag_names = [t.lower() for t in ticket.tags]

        # Tag-based signals
        if any(t in tag_names for t in ("urgent", "critical", "emergency")):
            signals.append("urgent_tag")
            score += 4

        if any(t in tag_names for t in ("bug", "broken", "error")):
            signals.append("bug_report")
            score += 2

        if any(t in tag_names for t in ("billing", "payment", "refund")):
            signals.append("billing_issue")
            score += 3

        # Assignment
        if not ticket.assigned_user_id:
            signals.append("unassigned")
            score += 2

        # Value-based
        if ticket.value > 1000:
            signals.append("high_value_customer")
            score += 2
        elif ticket.value > 500:
            signals.append("mid_value_customer")
            score += 1

        # Description quality
        if not ticket.description:
            signals.append("no_description")
            score += 1

        # Determine priority
        if score >= 5:
            priority = "urgent"
        elif score >= 3:
            priority = "high"
        elif score >= 1:
            priority = "normal"
        else:
            priority = "low"

        # Suggested action
        if "unassigned" in signals:
            action = "Assign to a support agent immediately"
        elif priority == "urgent":
            action = "Respond within 1 hour"
        elif "billing_issue" in signals:
            action = "Route to billing team"
        elif "bug_report" in signals:
            action = "Escalate to engineering"
        else:
            action = "Standard response queue"

        return TicketTriage(
            ticket_id=ticket.id,
            ticket_name=ticket.name,
            priority=priority,
            signals=signals,
            suggested_action=action,
        )

    def _check_escalation(self, ticket: CRMTicket) -> Optional[EscalationFlag]:
        """Check if a ticket needs escalation."""
        tag_names = [t.lower() for t in ticket.tags]

        if any(t in tag_names for t in ("escalated", "executive", "legal")):
            return EscalationFlag(
                ticket_id=ticket.id,
                ticket_name=ticket.name,
                reason="Explicitly tagged for escalation",
                severity="critical",
            )

        if not ticket.assigned_user_id and ticket.value > 1000:
            return EscalationFlag(
                ticket_id=ticket.id,
                ticket_name=ticket.name,
                reason="High-value unassigned ticket",
                severity="warning",
            )

        return None

    # ── Reply Context ──────────────────────────────────────────────────

    async def get_reply_context(
        self, sub_account_id: str, ticket_id: str
    ) -> dict[str, Any]:
        """
        Gather context for generating a support reply.
        Returns ticket details + customer info + related tickets.
        """
        pipelines = await self.crm.get_pipelines(sub_account_id)
        target_ticket = None
        customer_tickets = []

        for pipeline in pipelines:
            tickets = await self.crm.get_tickets(pipeline.id)
            for ticket in tickets:
                if ticket.id == ticket_id:
                    target_ticket = ticket
                if target_ticket and ticket.customer_id == target_ticket.customer_id:
                    customer_tickets.append(ticket)

        if not target_ticket:
            return {"error": "Ticket not found"}

        # Get customer details
        customer = None
        if target_ticket.customer_id:
            contacts = await self.crm.get_contacts(sub_account_id, limit=100)
            for c in contacts.items:
                if c.id == target_ticket.customer_id:
                    customer = c
                    break

        return {
            "ticket": {
                "id": target_ticket.id,
                "name": target_ticket.name,
                "description": target_ticket.description,
                "lane": target_ticket.lane_name or target_ticket.lane_id,
                "tags": target_ticket.tags,
                "value": target_ticket.value,
            },
            "customer": {
                "id": customer.id if customer else None,
                "name": customer.name if customer else "Unknown",
                "email": customer.email if customer else None,
                "company": customer.company_name if customer else None,
            } if customer else None,
            "customer_history": {
                "total_tickets": len(customer_tickets),
                "total_value": sum(t.value for t in customer_tickets),
            },
        }

    # ── Workload Summary ───────────────────────────────────────────────

    async def get_workload_summary(self, sub_account_id: str) -> dict[str, Any]:
        """Get support workload overview."""
        stats = await self.crm.get_stats(sub_account_id)
        triage = await self.triage_tickets(sub_account_id)

        return {
            "total_open": triage["total"],
            "by_priority": triage["by_priority"],
            "escalations_count": len(triage["escalations"]),
            "unassigned": sum(
                1 for t in triage["tickets"] if "unassigned" in t["signals"]
            ),
            "contacts_total": stats.contacts_total,
        }

    # ── Format for AI Prompt Injection ─────────────────────────────────

    async def build_crm_context(self, sub_account_id: str) -> str:
        """Build formatted CRM context for Customer dept system prompt."""
        try:
            workload = await self.get_workload_summary(sub_account_id)
            triage = await self.triage_tickets(sub_account_id)

            sections = []

            sections.append(
                f"## Support Overview\n"
                f"- Open tickets: {workload['total_open']}\n"
                f"- Urgent: {workload['by_priority'].get('urgent', 0)}\n"
                f"- High: {workload['by_priority'].get('high', 0)}\n"
                f"- Unassigned: {workload['unassigned']}\n"
                f"- Escalations: {workload['escalations_count']}"
            )

            # Urgent/high priority tickets
            urgent = [t for t in triage["tickets"] if t["priority"] in ("urgent", "high")]
            if urgent:
                lines = []
                for t in urgent[:5]:
                    lines.append(
                        f"  - [{t['priority'].upper()}] {t['name']}: {t['suggested_action']}"
                    )
                sections.append("## Priority Tickets\n" + "\n".join(lines))

            # Escalations
            if triage["escalations"]:
                esc_lines = []
                for e in triage["escalations"]:
                    esc_lines.append(f"  - ⚠️ {e['name']}: {e['reason']}")
                sections.append("## Escalations\n" + "\n".join(esc_lines))

            return "\n\n".join(sections)

        except Exception as e:
            logger.warning("Failed to build Customer CRM context: %s", e)
            return "## Support Data\nUnable to load support data at this time."
