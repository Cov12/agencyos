"""
Sales & Admin Department Engine

Provides CRM-aware intelligence for the Sales & Admin department:
- Lead scoring and prioritization
- Pipeline analysis and deal risk detection
- Follow-up email generation
- Contact enrichment context

This engine enhances the orchestrator's department prompt with real CRM data
and structured analysis, producing actionable proposals.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

from ..crm_adapter import CRMAdapter, CRMStats, CRMPipeline, CRMTicket, CRMContact

logger = logging.getLogger("agencyos.engines.sales_admin")


@dataclass
class LeadScore:
    contact_id: str
    contact_name: str
    score: int  # 0-100
    signals: list[str]
    recommended_action: str


@dataclass
class DealRisk:
    ticket_id: str
    deal_name: str
    risk_level: str  # low, medium, high, critical
    risk_factors: list[str]
    suggested_action: str


class SalesAdminEngine:
    """
    Sales & Admin department intelligence layer.

    Sits between the orchestrator and the CRM adapter, providing
    department-specific analysis and recommendations.
    """

    def __init__(self, crm: CRMAdapter):
        self.crm = crm

    # ── Pipeline Analysis ──────────────────────────────────────────────

    async def get_pipeline_summary(self, sub_account_id: str) -> dict[str, Any]:
        """
        Generate a comprehensive pipeline summary with deal distribution,
        total value, and risk indicators.
        """
        pipelines = await self.crm.get_pipelines(sub_account_id)

        summaries = []
        total_value = 0.0
        total_deals = 0
        at_risk_deals = []

        for pipeline in pipelines:
            tickets = await self.crm.get_tickets(pipeline.id)
            pipeline_value = sum(t.value for t in tickets)
            total_value += pipeline_value
            total_deals += len(tickets)

            # Group by lane
            lane_distribution: dict[str, list[CRMTicket]] = {}
            for ticket in tickets:
                lane_name = ticket.lane_name or ticket.lane_id
                lane_distribution.setdefault(lane_name, []).append(ticket)

            # Detect stale deals (no tags, low value, or stuck in early lanes)
            for ticket in tickets:
                risk = self._assess_deal_risk(ticket, pipeline)
                if risk.risk_level in ("high", "critical"):
                    at_risk_deals.append(risk)

            summaries.append({
                "pipeline_id": pipeline.id,
                "pipeline_name": pipeline.name,
                "total_deals": len(tickets),
                "total_value": pipeline_value,
                "lanes": {
                    name: {
                        "count": len(deals),
                        "value": sum(d.value for d in deals),
                    }
                    for name, deals in lane_distribution.items()
                },
            })

        return {
            "pipelines": summaries,
            "total_value": total_value,
            "total_deals": total_deals,
            "at_risk_deals": [
                {
                    "deal": r.deal_name,
                    "risk_level": r.risk_level,
                    "factors": r.risk_factors,
                    "suggested_action": r.suggested_action,
                }
                for r in at_risk_deals
            ],
        }

    # ── Lead Scoring ───────────────────────────────────────────────────

    async def score_leads(
        self, sub_account_id: str, limit: int = 20
    ) -> list[LeadScore]:
        """
        Score contacts by engagement signals.

        Scoring factors (heuristic — future: ML model):
        - Has email: +20
        - Has phone: +15
        - Has company: +15
        - Has associated deals: +25
        - Deal value > 0: +15
        - Multiple deals: +10
        """
        result = await self.crm.get_contacts(sub_account_id, limit=limit)
        pipelines = await self.crm.get_pipelines(sub_account_id)

        # Build contact→deals map
        contact_deals: dict[str, list[CRMTicket]] = {}
        for pipeline in pipelines:
            tickets = await self.crm.get_tickets(pipeline.id)
            for ticket in tickets:
                if ticket.customer_id:
                    contact_deals.setdefault(ticket.customer_id, []).append(ticket)

        scores = []
        for contact in result.items:
            score = 0
            signals = []

            if contact.email:
                score += 20
                signals.append("has_email")
            if contact.phone:
                score += 15
                signals.append("has_phone")
            if contact.company_name:
                score += 15
                signals.append("has_company")

            deals = contact_deals.get(contact.id, [])
            if deals:
                score += 25
                signals.append(f"{len(deals)}_deals")
                total_deal_value = sum(d.value for d in deals)
                if total_deal_value > 0:
                    score += 15
                    signals.append(f"deal_value_{total_deal_value:.0f}")
                if len(deals) > 1:
                    score += 10
                    signals.append("multi_deal")

            # Determine recommended action
            if score >= 70:
                action = "high_priority_follow_up"
            elif score >= 40:
                action = "nurture_sequence"
            elif score >= 20:
                action = "qualify_further"
            else:
                action = "enrich_data"

            scores.append(LeadScore(
                contact_id=contact.id,
                contact_name=contact.name,
                score=min(100, score),
                signals=signals,
                recommended_action=action,
            ))

        # Sort by score descending
        scores.sort(key=lambda s: s.score, reverse=True)
        return scores

    # ── Deal Risk Detection ────────────────────────────────────────────

    def _assess_deal_risk(self, ticket: CRMTicket, pipeline: CRMPipeline) -> DealRisk:
        """
        Assess risk level for a single deal/ticket.

        Risk factors:
        - No assigned user → medium risk
        - No customer linked → medium risk
        - Zero value → low risk (might be intentional)
        - No tags → low risk (poor categorization)
        - No description → low risk
        """
        risk_factors = []
        risk_score = 0

        if not ticket.assigned_user_id:
            risk_factors.append("unassigned")
            risk_score += 2

        if not ticket.customer_id:
            risk_factors.append("no_customer_linked")
            risk_score += 2

        if ticket.value == 0:
            risk_factors.append("zero_value")
            risk_score += 1

        if not ticket.tags:
            risk_factors.append("no_tags")
            risk_score += 1

        if not ticket.description:
            risk_factors.append("no_description")
            risk_score += 1

        # Determine risk level
        if risk_score >= 4:
            risk_level = "high"
        elif risk_score >= 2:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Suggest action based on risk
        if "unassigned" in risk_factors:
            suggested = "Assign a team member to this deal"
        elif "no_customer_linked" in risk_factors:
            suggested = "Link a contact to this deal"
        elif risk_score >= 2:
            suggested = "Review and update deal details"
        else:
            suggested = "No action needed"

        return DealRisk(
            ticket_id=ticket.id,
            deal_name=ticket.name,
            risk_level=risk_level,
            risk_factors=risk_factors,
            suggested_action=suggested,
        )

    # ── Follow-up Generation Context ───────────────────────────────────

    async def get_follow_up_context(
        self, sub_account_id: str, contact_id: str
    ) -> dict[str, Any]:
        """
        Gather context for generating a follow-up email/message.
        Returns contact details + associated deals for the AI to draft from.
        """
        # Get contact details
        contacts = await self.crm.get_contacts(sub_account_id, limit=1)
        contact = None
        for c in contacts.items:
            if c.id == contact_id:
                contact = c
                break

        # Get associated deals
        pipelines = await self.crm.get_pipelines(sub_account_id)
        associated_deals = []
        for pipeline in pipelines:
            tickets = await self.crm.get_tickets(pipeline.id)
            for ticket in tickets:
                if ticket.customer_id == contact_id:
                    associated_deals.append({
                        "deal_name": ticket.name,
                        "value": ticket.value,
                        "lane": ticket.lane_name or ticket.lane_id,
                        "tags": ticket.tags,
                        "description": ticket.description,
                    })

        return {
            "contact": {
                "id": contact.id if contact else contact_id,
                "name": contact.name if contact else "Unknown",
                "email": contact.email if contact else None,
                "phone": contact.phone if contact else None,
                "company": contact.company_name if contact else None,
            },
            "deals": associated_deals,
            "deal_count": len(associated_deals),
            "total_deal_value": sum(d["value"] for d in associated_deals),
        }

    # ── Dashboard Stats Enhancement ────────────────────────────────────

    async def get_enhanced_stats(self, sub_account_id: str) -> dict[str, Any]:
        """
        Get CRM stats enhanced with sales-specific insights.
        """
        stats = await self.crm.get_stats(sub_account_id)
        leads = await self.score_leads(sub_account_id, limit=10)
        pipeline_summary = await self.get_pipeline_summary(sub_account_id)

        high_priority = [l for l in leads if l.score >= 70]
        at_risk = pipeline_summary.get("at_risk_deals", [])

        return {
            "crm_stats": {
                "contacts_total": stats.contacts_total,
                "contacts_recent": stats.contacts_recent,
                "tickets_total": stats.tickets_total,
                "tickets_value": stats.tickets_value,
                "pipelines_count": stats.pipelines_count,
            },
            "sales_insights": {
                "high_priority_leads": len(high_priority),
                "top_leads": [
                    {"name": l.contact_name, "score": l.score, "action": l.recommended_action}
                    for l in high_priority[:5]
                ],
                "at_risk_deals": len(at_risk),
                "total_pipeline_value": pipeline_summary["total_value"],
            },
        }

    # ── Format for AI Prompt Injection ─────────────────────────────────

    async def build_crm_context(self, sub_account_id: str) -> str:
        """
        Build a formatted CRM context string for injection into
        the department's system prompt.
        """
        try:
            stats = await self.crm.get_stats(sub_account_id)
            leads = await self.score_leads(sub_account_id, limit=5)
            pipeline_summary = await self.get_pipeline_summary(sub_account_id)

            sections = []

            # Overview
            sections.append(
                f"## CRM Overview\n"
                f"- Total contacts: {stats.contacts_total} ({stats.contacts_recent} recent)\n"
                f"- Total deals: {stats.tickets_total}\n"
                f"- Pipeline value: ${stats.tickets_value:,.2f}\n"
                f"- Pipelines: {stats.pipelines_count}"
            )

            # Top leads
            if leads:
                lead_lines = []
                for l in leads[:5]:
                    lead_lines.append(
                        f"  - {l.contact_name} (score: {l.score}) → {l.recommended_action}"
                    )
                sections.append("## Top Leads\n" + "\n".join(lead_lines))

            # At-risk deals
            at_risk = pipeline_summary.get("at_risk_deals", [])
            if at_risk:
                risk_lines = []
                for r in at_risk[:5]:
                    risk_lines.append(
                        f"  - {r['deal']} [{r['risk_level']}]: {', '.join(r['factors'])}"
                    )
                sections.append("## At-Risk Deals\n" + "\n".join(risk_lines))

            return "\n\n".join(sections)

        except Exception as e:
            logger.warning("Failed to build CRM context: %s", e)
            return "## CRM Data\nUnable to load CRM data at this time."
