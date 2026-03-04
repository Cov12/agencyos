import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from apps.agencyos.backend.services.crm_adapter import (
    CRMContact,
    CRMListResult,
    CRMPipeline,
    CRMStats,
    CRMTicket,
)
from apps.agencyos.backend.services.engines.back_office import BackOfficeEngine
from apps.agencyos.backend.services.engines.customer import CustomerEngine
from apps.agencyos.backend.services.engines.sales_admin import SalesAdminEngine


@pytest.fixture
def fake_crm():
    crm = AsyncMock()
    crm.get_contacts = AsyncMock()
    crm.get_pipelines = AsyncMock()
    crm.get_tickets = AsyncMock()
    crm.get_stats = AsyncMock()
    return crm


class TestSalesAdminEngine:
    @pytest.mark.asyncio
    async def test_high_value_lead_with_complete_data_scores_above_70(self, fake_crm):
        engine = SalesAdminEngine(fake_crm)

        contact = CRMContact(
            id="c-1",
            name="Alice Morgan",
            email="alice@acme.com",
            phone="+1-555-0101",
            company_name="Acme Logistics",
        )
        pipeline = CRMPipeline(id="p-1", name="Main Pipeline")
        deal = CRMTicket(
            id="t-1",
            name="Enterprise Expansion",
            lane_id="negotiation",
            value=25000,
            customer_id="c-1",
            assigned_user_id="u-1",
            tags=["hot"],
            description="Qualified and budget-approved",
        )

        fake_crm.get_contacts.return_value = CRMListResult(items=[contact], total=1)
        fake_crm.get_pipelines.return_value = [pipeline]
        fake_crm.get_tickets.return_value = [deal]

        scores = await engine.score_leads("sub-1")

        assert scores
        assert scores[0].score > 70
        assert scores[0].recommended_action == "high_priority_follow_up"

    @pytest.mark.asyncio
    async def test_low_value_lead_with_missing_fields_scores_below_30(self, fake_crm):
        engine = SalesAdminEngine(fake_crm)

        contact = CRMContact(id="c-2", name="No Data Lead")
        pipeline = CRMPipeline(id="p-1", name="Main Pipeline")

        fake_crm.get_contacts.return_value = CRMListResult(items=[contact], total=1)
        fake_crm.get_pipelines.return_value = [pipeline]
        fake_crm.get_tickets.return_value = []

        scores = await engine.score_leads("sub-1")

        assert scores[0].score < 30
        assert scores[0].recommended_action == "enrich_data"

    @pytest.mark.asyncio
    async def test_pipeline_with_stalled_deals_identifies_bottleneck_like_risk(self, fake_crm):
        engine = SalesAdminEngine(fake_crm)

        pipeline = CRMPipeline(id="p-1", name="Sales Pipeline")
        stalled = CRMTicket(
            id="t-stalled",
            name="Stalled Deal",
            lane_id="qualified",
            lane_name="Qualified",
            value=0,
            assigned_user_id=None,
            customer_id=None,
            tags=[],
            description=None,
        )

        fake_crm.get_pipelines.return_value = [pipeline]
        fake_crm.get_tickets.return_value = [stalled]

        summary = await engine.get_pipeline_summary("sub-1")

        assert summary["total_deals"] == 1
        assert summary["at_risk_deals"], "Expected stalled deal to be flagged as at-risk"
        risk = summary["at_risk_deals"][0]
        assert risk["risk_level"] in {"high", "critical"}
        assert "unassigned" in risk["factors"]

    def test_deal_with_no_recent_activity_proxy_is_high_risk(self, fake_crm):
        engine = SalesAdminEngine(fake_crm)
        pipeline = CRMPipeline(id="p-1", name="Sales Pipeline")
        inactive_deal = CRMTicket(
            id="t-2",
            name="Dormant Opportunity",
            lane_id="prospect",
            value=0,
            assigned_user_id=None,
            customer_id=None,
            tags=[],
            description=None,
        )

        risk = engine._assess_deal_risk(inactive_deal, pipeline)

        assert risk.risk_level == "high"
        assert "unassigned" in risk.risk_factors
        assert "no_customer_linked" in risk.risk_factors


class TestCustomerEngine:
    @pytest.mark.asyncio
    async def test_urgent_keyword_tag_in_ticket_sets_urgent_priority(self, fake_crm):
        engine = CustomerEngine(fake_crm)

        pipeline = CRMPipeline(id="p-1", name="Support")
        urgent_ticket = CRMTicket(
            id="ct-1",
            name="Production outage",
            lane_id="new",
            value=400,
            tags=["urgent", "bug"],
            assigned_user_id="agent-1",
            description="Checkout is failing for all users",
        )

        fake_crm.get_pipelines.return_value = [pipeline]
        fake_crm.get_tickets.return_value = [urgent_ticket]

        triage = await engine.triage_tickets("sub-1")

        assert triage["tickets"][0]["priority"] == "urgent"
        assert "urgent_tag" in triage["tickets"][0]["signals"]

    def test_multiple_angry_messages_proxy_triggers_escalation_tag_rule(self, fake_crm):
        engine = CustomerEngine(fake_crm)

        escalated_ticket = CRMTicket(
            id="ct-2",
            name="Customer threatening cancellation",
            lane_id="open",
            value=1200,
            tags=["escalated", "billing"],
            assigned_user_id="agent-2",
            description="Customer upset after repeated failed invoices",
        )

        flag = engine._check_escalation(escalated_ticket)

        assert flag is not None
        assert flag.severity == "critical"
        assert "escalation" in flag.reason.lower()

    @pytest.mark.asyncio
    async def test_vip_customer_ticket_gets_elevated_priority(self, fake_crm):
        engine = CustomerEngine(fake_crm)

        pipeline = CRMPipeline(id="p-1", name="Support")
        vip_ticket = CRMTicket(
            id="ct-3",
            name="API integration issue",
            lane_id="triage",
            value=5000,
            tags=["integration"],
            assigned_user_id="agent-7",
            description="Enterprise account blocked on launch",
        )

        fake_crm.get_pipelines.return_value = [pipeline]
        fake_crm.get_tickets.return_value = [vip_ticket]

        triage = await engine.triage_tickets("sub-1")

        assert triage["tickets"][0]["priority"] in {"high", "urgent"}
        assert "high_value_customer" in triage["tickets"][0]["signals"]

    @pytest.mark.asyncio
    async def test_build_reply_context_contains_ticket_and_customer_history(self, fake_crm):
        engine = CustomerEngine(fake_crm)

        pipeline = CRMPipeline(id="p-1", name="Support")
        target = CRMTicket(
            id="ct-10",
            name="Password reset loop",
            lane_id="open",
            customer_id="cust-1",
            value=150,
            tags=["login"],
            description="Reset email keeps expiring",
        )
        previous = CRMTicket(
            id="ct-11",
            name="2FA issue",
            lane_id="closed",
            customer_id="cust-1",
            value=200,
            tags=["security"],
            description="Resolved last week",
        )

        fake_crm.get_pipelines.return_value = [pipeline]
        fake_crm.get_tickets.return_value = [target, previous]
        fake_crm.get_contacts.return_value = CRMListResult(
            items=[CRMContact(id="cust-1", name="VIP Client", email="vip@client.com", company_name="VIP Co")],
            total=1,
        )

        context = await engine.get_reply_context("sub-1", "ct-10")

        assert context["ticket"]["id"] == "ct-10"
        assert context["customer"]["name"] == "VIP Client"
        assert context["customer_history"]["total_tickets"] == 2


class TestBackOfficeEngine:
    @pytest.mark.asyncio
    async def test_healthy_metrics_produce_health_score_above_80(self, fake_crm):
        engine = BackOfficeEngine(fake_crm)

        fake_crm.get_stats.return_value = CRMStats(
            contacts_total=200,
            contacts_recent=45,
            tickets_total=30,
            tickets_value=180000,
            tickets_by_lane={"Qualified": 10, "Won": 8, "Proposal": 12},
            pipelines_count=2,
        )
        fake_crm.get_pipelines.return_value = [CRMPipeline(id="p-1", name="Main")]
        fake_crm.get_tickets.return_value = [
            CRMTicket(
                id="t-1",
                name="Deal A",
                lane_id="proposal",
                value=20000,
                assigned_user_id="u-1",
                tags=["priority"],
                description="Detailed next steps",
            )
        ]

        health = await engine.get_operational_health("sub-1")

        assert health["health_score"] > 80

    @pytest.mark.asyncio
    async def test_revenue_declining_proxy_flagged_in_financial_summary(self, fake_crm):
        engine = BackOfficeEngine(fake_crm)

        fake_crm.get_stats.return_value = CRMStats(
            contacts_total=120,
            contacts_recent=0,
            tickets_total=12,
            tickets_value=0,
            tickets_by_lane={"Open": 12},
            pipelines_count=1,
        )
        fake_crm.get_pipelines.return_value = [CRMPipeline(id="p-1", name="Main")]

        summary = await engine.get_financial_summary("sub-1")
        descriptions = [a["description"].lower() for a in summary["alerts"]]

        assert any("zero value" in d for d in descriptions)

    @pytest.mark.asyncio
    async def test_high_ticket_backlog_proxy_results_in_low_ops_health(self, fake_crm):
        engine = BackOfficeEngine(fake_crm)

        fake_crm.get_stats.return_value = CRMStats(
            contacts_total=80,
            contacts_recent=0,
            tickets_total=50,
            tickets_value=0,
            tickets_by_lane={"Backlog": 50},
            pipelines_count=1,
        )
        fake_crm.get_pipelines.return_value = [CRMPipeline(id="p-1", name="Operations")]
        fake_crm.get_tickets.return_value = [
            CRMTicket(
                id=f"t-{i}",
                name=f"Backlog #{i}",
                lane_id="backlog",
                value=0,
                assigned_user_id=None,
                tags=[],
                description=None,
            )
            for i in range(1, 6)
        ]

        health = await engine.get_operational_health("sub-1")

        assert health["health_score"] < 80
        assert health["pipelines"][0]["unassigned"] >= 1
