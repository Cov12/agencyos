"""Unit tests for LaneRouter and LocalResponder services."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from apps.agencyos.backend.services.intent_classifier import IntentResult
from apps.agencyos.backend.services.lane_router import (
    Lane,
    LaneRouter,
    RoutingDecision,
    FeatureFlags,
)
from apps.agencyos.backend.services.local_responder import (
    LocalResponder,
    LocalResponse,
)


@pytest.fixture
def mock_intent_classifier():
    """Create a mock IntentClassifier."""
    with patch(
        "apps.agencyos.backend.services.lane_router.IntentClassifier"
    ) as mock_cls:
        mock_instance = MagicMock()
        mock_instance.classify = AsyncMock()
        mock_cls.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def default_flags():
    """Default feature flags for testing."""
    return FeatureFlags(
        local_fast_enabled=True,
        local_fast_timeout_seconds=2.0,
        local_fast_confidence_threshold=0.7,
        cortex_routing_enabled=True,
        cortex_sync_timeout_seconds=30.0,
        cortex_async_threshold_seconds=60.0,
        max_local_response_tokens=256,
        always_escalate_intents=["proposal_create", "payment_process"],
        restricted_departments=["finance"],
        log_routing_decisions=False,
        include_timing_metrics=False,
        trace_sample_rate=0.0,
    )


class TestLaneRouter:
    @pytest.mark.asyncio
    async def test_simple_greeting_routes_to_local_fast(self, mock_intent_classifier):
        """Complexity 1-2 messages should route to LOCAL_FAST."""
        mock_intent_classifier.classify.return_value = IntentResult(
            intent="greeting",
            complexity=1,
            needs_tool=False,
            department="sales",
            can_handle_locally=True,
            suggested_response="Hello! How can I help you today?",
            confidence=0.95,
            escalation_reason=None,
        )

        with patch.object(LaneRouter, "_load_feature_flags") as mock_load:
            mock_load.return_value = FeatureFlags(
                local_fast_enabled=True,
                local_fast_confidence_threshold=0.7,
                cortex_routing_enabled=True,
                log_routing_decisions=False,
            )
            router = LaneRouter()
            router.classifier = mock_intent_classifier

            decision = await router.route("Hello!", "sales")

            assert decision.lane == Lane.LOCAL_FAST
            assert decision.intent_result.intent == "greeting"
            assert decision.metadata.get("suggested_response") == "Hello! How can I help you today?"

    @pytest.mark.asyncio
    async def test_tool_requiring_query_routes_to_cortex_sync(self, mock_intent_classifier):
        """Messages needing tools should route to CORTEX_SYNC."""
        mock_intent_classifier.classify.return_value = IntentResult(
            intent="lead_lookup",
            complexity=2,
            needs_tool=True,
            department="sales",
            can_handle_locally=False,
            suggested_response=None,
            confidence=0.85,
            escalation_reason="Requires CRM data lookup",
        )

        with patch.object(LaneRouter, "_load_feature_flags") as mock_load:
            mock_load.return_value = FeatureFlags(
                local_fast_enabled=True,
                cortex_routing_enabled=True,
                log_routing_decisions=False,
            )
            router = LaneRouter()
            router.classifier = mock_intent_classifier

            decision = await router.route("Show me the top leads", "sales")

            assert decision.lane == Lane.CORTEX_SYNC
            assert "needs_tool" in decision.reason

    @pytest.mark.asyncio
    async def test_high_complexity_routes_to_cortex_async(self, mock_intent_classifier):
        """Complexity 4-5 messages should route to CORTEX_ASYNC."""
        mock_intent_classifier.classify.return_value = IntentResult(
            intent="strategic_analysis",
            complexity=5,
            needs_tool=True,
            department="sales",
            can_handle_locally=False,
            suggested_response=None,
            confidence=0.9,
            escalation_reason="Executive-level analysis required",
        )

        with patch.object(LaneRouter, "_load_feature_flags") as mock_load:
            mock_load.return_value = FeatureFlags(
                local_fast_enabled=True,
                cortex_routing_enabled=True,
                log_routing_decisions=False,
            )
            router = LaneRouter()
            router.classifier = mock_intent_classifier

            decision = await router.route(
                "Create a strategic growth plan for Q3", "sales"
            )

            assert decision.lane == Lane.CORTEX_ASYNC
            assert "complexity_5" in decision.reason

    @pytest.mark.asyncio
    async def test_restricted_intent_always_escalates(self, mock_intent_classifier):
        """Intents in always_escalate_intents should never use LOCAL_FAST."""
        mock_intent_classifier.classify.return_value = IntentResult(
            intent="proposal_create",
            complexity=2,
            needs_tool=False,
            department="sales",
            can_handle_locally=True,
            suggested_response="I can help create a proposal.",
            confidence=0.9,
            escalation_reason=None,
        )

        with patch.object(LaneRouter, "_load_feature_flags") as mock_load:
            mock_load.return_value = FeatureFlags(
                local_fast_enabled=True,
                cortex_routing_enabled=True,
                always_escalate_intents=["proposal_create"],
                log_routing_decisions=False,
            )
            router = LaneRouter()
            router.classifier = mock_intent_classifier

            decision = await router.route("Create a proposal for Acme Corp", "sales")

            assert decision.lane in (Lane.CORTEX_SYNC, Lane.CORTEX_ASYNC)
            assert "proposal_create" in decision.reason

    @pytest.mark.asyncio
    async def test_restricted_department_bypasses_local_fast(self, mock_intent_classifier):
        """Restricted departments should not use LOCAL_FAST."""
        mock_intent_classifier.classify.return_value = IntentResult(
            intent="greeting",
            complexity=1,
            needs_tool=False,
            department="finance",
            can_handle_locally=True,
            suggested_response="Hello!",
            confidence=0.95,
            escalation_reason=None,
        )

        with patch.object(LaneRouter, "_load_feature_flags") as mock_load:
            mock_load.return_value = FeatureFlags(
                local_fast_enabled=True,
                cortex_routing_enabled=True,
                restricted_departments=["finance"],
                log_routing_decisions=False,
            )
            router = LaneRouter()
            router.classifier = mock_intent_classifier

            decision = await router.route("Hello", "finance")

            assert decision.lane in (Lane.CORTEX_SYNC, Lane.CORTEX_ASYNC, Lane.FALLBACK)
            assert "finance" in decision.reason

    @pytest.mark.asyncio
    async def test_local_fast_disabled_routes_to_cortex(self, mock_intent_classifier):
        """When local_fast_enabled=False, all should go to Cortex."""
        mock_intent_classifier.classify.return_value = IntentResult(
            intent="greeting",
            complexity=1,
            needs_tool=False,
            department="sales",
            can_handle_locally=True,
            suggested_response="Hello!",
            confidence=0.95,
            escalation_reason=None,
        )

        with patch.object(LaneRouter, "_load_feature_flags") as mock_load:
            mock_load.return_value = FeatureFlags(
                local_fast_enabled=False,
                cortex_routing_enabled=True,
                log_routing_decisions=False,
            )
            router = LaneRouter()
            router.classifier = mock_intent_classifier

            decision = await router.route("Hello", "sales")

            assert decision.lane in (Lane.CORTEX_SYNC, Lane.CORTEX_ASYNC)
            assert "local_fast_disabled" in decision.reason

    @pytest.mark.asyncio
    async def test_cortex_disabled_falls_back(self, mock_intent_classifier):
        """When cortex_routing_enabled=False and escalation needed, use FALLBACK."""
        mock_intent_classifier.classify.return_value = IntentResult(
            intent="complex_query",
            complexity=4,
            needs_tool=True,
            department="sales",
            can_handle_locally=False,
            suggested_response=None,
            confidence=0.8,
            escalation_reason="Complex analysis required",
        )

        with patch.object(LaneRouter, "_load_feature_flags") as mock_load:
            mock_load.return_value = FeatureFlags(
                local_fast_enabled=True,
                cortex_routing_enabled=False,
                log_routing_decisions=False,
            )
            router = LaneRouter()
            router.classifier = mock_intent_classifier

            decision = await router.route("Analyze market trends", "sales")

            assert decision.lane == Lane.FALLBACK
            assert "cortex_disabled" in decision.reason

    @pytest.mark.asyncio
    async def test_low_confidence_generates_fresh_response(self, mock_intent_classifier):
        """Low confidence should still route LOCAL_FAST but without suggested response."""
        mock_intent_classifier.classify.return_value = IntentResult(
            intent="greeting",
            complexity=1,
            needs_tool=False,
            department="sales",
            can_handle_locally=True,
            suggested_response="Maybe hello?",
            confidence=0.5,
            escalation_reason=None,
        )

        with patch.object(LaneRouter, "_load_feature_flags") as mock_load:
            mock_load.return_value = FeatureFlags(
                local_fast_enabled=True,
                local_fast_confidence_threshold=0.7,
                cortex_routing_enabled=True,
                log_routing_decisions=False,
            )
            router = LaneRouter()
            router.classifier = mock_intent_classifier

            decision = await router.route("Hello", "sales")

            assert decision.lane == Lane.LOCAL_FAST
            assert decision.metadata.get("suggested_response") is None
            assert "low_confidence" in decision.reason


class TestLocalResponder:
    @pytest.mark.asyncio
    async def test_uses_suggested_response_when_valid(self):
        """Should use suggested response from high-confidence classification."""
        decision = RoutingDecision(
            lane=Lane.LOCAL_FAST,
            intent_result=IntentResult(
                intent="greeting",
                complexity=1,
                needs_tool=False,
                department="sales",
                can_handle_locally=True,
                suggested_response="Hello! How can I help?",
                confidence=0.95,
                escalation_reason=None,
            ),
            reason="complexity_1_2_high_confidence",
            metadata={
                "suggested_response": "Hello! How can I help?",
                "timeout_seconds": 2.0,
                "max_tokens": 256,
            },
        )

        with patch.object(LocalResponder, "__init__", lambda x: None):
            responder = LocalResponder()
            responder.model_router = MagicMock()
            responder._system_prompt_template = "You are a helper."

            response = await responder.respond("Hi!", decision)

            assert response.success is True
            assert response.source == "suggested"
            assert response.content == "Hello! How can I help?"
            assert response.escalated is False

    @pytest.mark.asyncio
    async def test_generates_fresh_response_when_no_suggested(self):
        """Should generate fresh response when no suggested response available."""
        decision = RoutingDecision(
            lane=Lane.LOCAL_FAST,
            intent_result=IntentResult(
                intent="greeting",
                complexity=1,
                needs_tool=False,
                department="sales",
                can_handle_locally=True,
                suggested_response=None,
                confidence=0.6,
                escalation_reason=None,
            ),
            reason="complexity_1_2_low_confidence_generate",
            metadata={
                "suggested_response": None,
                "timeout_seconds": 2.0,
                "max_tokens": 256,
            },
        )

        with patch.object(LocalResponder, "__init__", lambda x: None):
            responder = LocalResponder()
            responder.model_router = MagicMock()
            responder.model_router.generate = AsyncMock(
                return_value={"content": "Hi there! What can I do for you?"}
            )
            responder._system_prompt_template = "You are a helper for {department}."

            response = await responder.respond("Hello", decision)

            assert response.success is True
            assert response.source == "generated"
            assert "Hi there" in response.content
            assert response.escalated is False

    @pytest.mark.asyncio
    async def test_rejects_wrong_lane(self):
        """Should reject requests with wrong lane type."""
        decision = RoutingDecision(
            lane=Lane.CORTEX_SYNC,
            intent_result=IntentResult(
                intent="complex",
                complexity=3,
                needs_tool=True,
                department="sales",
                can_handle_locally=False,
                suggested_response=None,
                confidence=0.8,
                escalation_reason="Needs tool",
            ),
            reason="needs_tool",
            metadata={},
        )

        with patch.object(LocalResponder, "__init__", lambda x: None):
            responder = LocalResponder()
            responder.model_router = MagicMock()

            response = await responder.respond("Query", decision)

            assert response.success is False
            assert response.escalated is True
            assert response.escalation_reason == "wrong_lane"

    @pytest.mark.asyncio
    async def test_timeout_triggers_escalation(self):
        """Should escalate on timeout."""
        import asyncio

        decision = RoutingDecision(
            lane=Lane.LOCAL_FAST,
            intent_result=IntentResult(
                intent="greeting",
                complexity=1,
                needs_tool=False,
                department="sales",
                can_handle_locally=True,
                suggested_response=None,
                confidence=0.8,
                escalation_reason=None,
            ),
            reason="complexity_1_2_low_confidence_generate",
            metadata={
                "suggested_response": None,
                "timeout_seconds": 0.01,  # Very short timeout
                "max_tokens": 256,
            },
        )

        async def slow_generate(*args, **kwargs):
            await asyncio.sleep(1.0)
            return {"content": "Too slow"}

        with patch.object(LocalResponder, "__init__", lambda x: None):
            responder = LocalResponder()
            responder.model_router = MagicMock()
            responder.model_router.generate = slow_generate
            responder._system_prompt_template = "You are a helper for {department}."

            response = await responder.respond("Hello", decision)

            assert response.success is False
            assert response.source == "timeout_fallback"
            assert response.escalated is True
            assert "timeout" in response.escalation_reason

    def test_validates_suggested_response(self):
        """Should reject invalid suggested responses."""
        with patch.object(LocalResponder, "__init__", lambda x: None):
            responder = LocalResponder()

            # Empty response
            assert responder._validate_suggested_response("") is False
            assert responder._validate_suggested_response("  ") is False

            # Short error response
            assert responder._validate_suggested_response("error") is False
            assert responder._validate_suggested_response("I don't know") is False

            # Valid responses
            assert responder._validate_suggested_response("Hello! How can I help you?") is True
            assert responder._validate_suggested_response("The meeting is at 3 PM.") is True


class TestFeatureFlags:
    def test_default_values(self):
        """Feature flags should have sensible defaults."""
        flags = FeatureFlags()

        assert flags.local_fast_enabled is True
        assert flags.local_fast_timeout_seconds == 2.0
        assert flags.cortex_routing_enabled is False
        assert flags.max_local_response_tokens == 256

    def test_custom_values(self):
        """Feature flags should accept custom values."""
        flags = FeatureFlags(
            local_fast_enabled=False,
            local_fast_timeout_seconds=5.0,
            always_escalate_intents=["hire", "fire"],
        )

        assert flags.local_fast_enabled is False
        assert flags.local_fast_timeout_seconds == 5.0
        assert "hire" in flags.always_escalate_intents
