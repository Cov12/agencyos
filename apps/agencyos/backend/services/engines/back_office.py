"""
Back Office Department Engine

Provides intelligence for internal operations:
- Invoice status tracking and follow-up
- Financial summaries (revenue, outstanding, overdue)
- Operational task management context
- Checklist/process automation context

Note: WorkPipe's invoice system is schema-only (no UI yet).
This engine works with whatever data exists and gracefully
degrades when invoice data is unavailable.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from ..crm_adapter import CRMAdapter, CRMStats

logger = logging.getLogger("agencyos.engines.back_office")


@dataclass
class InvoiceAlert:
    description: str
    severity: str  # info, warning, critical
    action: str


class BackOfficeEngine:
    """
    Back Office department intelligence layer.

    Focuses on financial health, operational efficiency,
    and internal process management.
    """

    def __init__(self, crm: CRMAdapter):
        self.crm = crm

    # ── Financial Overview ─────────────────────────────────────────────

    async def get_financial_summary(self, sub_account_id: str) -> dict[str, Any]:
        """
        Generate financial health summary from CRM data.

        Since invoices are schema-only in WorkPipe, we derive financial
        signals from pipeline data (deal values) as a proxy.
        """
        stats = await self.crm.get_stats(sub_account_id)
        pipelines = await self.crm.get_pipelines(sub_account_id)

        # Analyze deal values across pipelines as financial proxy
        total_pipeline_value = stats.tickets_value
        deals_by_lane = stats.tickets_by_lane

        # Identify won/closed deals vs active
        won_value = 0.0
        active_value = 0.0
        for lane_name, count in deals_by_lane.items():
            lane_lower = lane_name.lower()
            if any(kw in lane_lower for kw in ("won", "closed", "complete", "paid")):
                won_value += count  # This is count, not value — approximation
            else:
                active_value += count

        alerts = self._generate_financial_alerts(stats, pipelines)

        return {
            "total_pipeline_value": total_pipeline_value,
            "total_deals": stats.tickets_total,
            "total_contacts": stats.contacts_total,
            "recent_contacts": stats.contacts_recent,
            "pipelines_count": stats.pipelines_count,
            "deals_by_stage": deals_by_lane,
            "alerts": [
                {"description": a.description, "severity": a.severity, "action": a.action}
                for a in alerts
            ],
        }

    def _generate_financial_alerts(
        self, stats: CRMStats, pipelines: list
    ) -> list[InvoiceAlert]:
        """Generate operational alerts from financial data."""
        alerts = []

        if stats.tickets_total == 0:
            alerts.append(InvoiceAlert(
                description="No deals in pipeline",
                severity="warning",
                action="Review sales pipeline — no active deals found",
            ))

        if stats.contacts_recent == 0:
            alerts.append(InvoiceAlert(
                description="No new contacts in the last 30 days",
                severity="info",
                action="Consider outreach campaign to generate new leads",
            ))

        if stats.tickets_value == 0 and stats.tickets_total > 0:
            alerts.append(InvoiceAlert(
                description="All deals have zero value",
                severity="warning",
                action="Update deal values for accurate pipeline forecasting",
            ))

        return alerts

    # ── Operational Health ─────────────────────────────────────────────

    async def get_operational_health(self, sub_account_id: str) -> dict[str, Any]:
        """
        Assess overall operational health.

        Checks:
        - Pipeline utilization (deals per pipeline)
        - Contact growth (recent vs total)
        - Data quality (deals with missing info)
        """
        stats = await self.crm.get_stats(sub_account_id)
        pipelines = await self.crm.get_pipelines(sub_account_id)

        # Pipeline utilization
        pipeline_health = []
        total_deals = 0
        for pipeline in pipelines:
            tickets = await self.crm.get_tickets(pipeline.id)
            total_deals += len(tickets)

            empty_deals = sum(1 for t in tickets if not t.description and not t.tags)
            unassigned = sum(1 for t in tickets if not t.assigned_user_id)

            pipeline_health.append({
                "name": pipeline.name,
                "total_deals": len(tickets),
                "unassigned": unassigned,
                "incomplete_data": empty_deals,
                "total_value": sum(t.value for t in tickets),
            })

        # Contact growth rate
        growth_rate = (
            (stats.contacts_recent / stats.contacts_total * 100)
            if stats.contacts_total > 0
            else 0
        )

        # Overall score (simple heuristic)
        health_score = 100
        if stats.tickets_total == 0:
            health_score -= 30
        if stats.contacts_recent == 0:
            health_score -= 20
        if stats.tickets_value == 0 and stats.tickets_total > 0:
            health_score -= 15

        return {
            "health_score": max(0, health_score),
            "pipelines": pipeline_health,
            "contact_growth_rate": round(growth_rate, 1),
            "total_deals": total_deals,
            "total_contacts": stats.contacts_total,
        }

    # ── Format for AI Prompt Injection ─────────────────────────────────

    async def build_crm_context(self, sub_account_id: str) -> str:
        """Build formatted CRM context for Back Office dept system prompt."""
        try:
            financial = await self.get_financial_summary(sub_account_id)
            health = await self.get_operational_health(sub_account_id)

            sections = []

            sections.append(
                f"## Financial Overview\n"
                f"- Total pipeline value: ${financial['total_pipeline_value']:,.2f}\n"
                f"- Active deals: {financial['total_deals']}\n"
                f"- Total contacts: {financial['total_contacts']} "
                f"({financial['recent_contacts']} recent)\n"
                f"- Pipelines: {financial['pipelines_count']}"
            )

            # Operational health
            sections.append(
                f"## Operational Health\n"
                f"- Health score: {health['health_score']}/100\n"
                f"- Contact growth: {health['contact_growth_rate']}% (30-day)\n"
                f"- Total deals across pipelines: {health['total_deals']}"
            )

            # Pipeline breakdown
            if health["pipelines"]:
                lines = []
                for p in health["pipelines"]:
                    issues = []
                    if p["unassigned"]:
                        issues.append(f"{p['unassigned']} unassigned")
                    if p["incomplete_data"]:
                        issues.append(f"{p['incomplete_data']} incomplete")
                    issue_str = f" — ⚠️ {', '.join(issues)}" if issues else ""
                    lines.append(
                        f"  - {p['name']}: {p['total_deals']} deals, "
                        f"${p['total_value']:,.2f}{issue_str}"
                    )
                sections.append("## Pipelines\n" + "\n".join(lines))

            # Alerts
            if financial["alerts"]:
                alert_lines = []
                for a in financial["alerts"]:
                    icon = "🔴" if a["severity"] == "critical" else "🟡" if a["severity"] == "warning" else "ℹ️"
                    alert_lines.append(f"  {icon} {a['description']}: {a['action']}")
                sections.append("## Alerts\n" + "\n".join(alert_lines))

            return "\n\n".join(sections)

        except Exception as e:
            logger.warning("Failed to build Back Office CRM context: %s", e)
            return "## Operations Data\nUnable to load operations data at this time."
