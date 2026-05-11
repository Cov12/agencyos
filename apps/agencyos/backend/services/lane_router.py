"""
AgencyOS Lane Router

Routes requests to the appropriate processing lane:
- LOCAL_FAST: Simple questions (complexity 1-2), handled locally with 2s timeout
- CORTEX_SYNC: Tool-based or moderate complexity, Cortex handles synchronously
- CORTEX_ASYNC: Complex/long-running work, Cortex handles asynchronously with polling

Uses IntentClassifier for routing decisions with feature flag controls.
"""

from __future__ import annotations

import logging
import time
import yaml
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from apps.agencyos.backend.services.intent_classifier import (
    IntentClassifier,
    IntentResult,
)

logger = logging.getLogger("agencyos.lane_router")

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


class Lane(str, Enum):
    """Processing lanes for request routing."""

    LOCAL_FAST = "LOCAL_FAST"
    CORTEX_SYNC = "CORTEX_SYNC"
    CORTEX_ASYNC = "CORTEX_ASYNC"
    FALLBACK = "FALLBACK"


@dataclass(slots=True)
class RoutingDecision:
    """Result of routing a request to a processing lane."""

    lane: Lane
    intent_result: IntentResult
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)
    routing_time_ms: float = 0.0


@dataclass(slots=True)
class FeatureFlags:
    """Feature flags for lane routing."""

    # Local fast lane
    local_fast_enabled: bool = True
    local_fast_timeout_seconds: float = 2.0
    local_fast_confidence_threshold: float = 0.7

    # Cortex routing
    cortex_routing_enabled: bool = False
    cortex_sync_timeout_seconds: float = 30.0
    cortex_async_threshold_seconds: float = 60.0

    # Guardrails
    max_local_response_tokens: int = 256
    always_escalate_intents: list[str] = field(default_factory=list)
    restricted_departments: list[str] = field(default_factory=list)

    # Observability
    log_routing_decisions: bool = True
    include_timing_metrics: bool = True
    trace_sample_rate: float = 0.1


class LaneRouter:
    """
    Routes incoming requests to the appropriate processing lane.

    Routing logic:
    1. Check feature flags - if local_fast disabled, use Cortex/fallback
    2. Classify intent using IntentClassifier
    3. Check guardrails (restricted intents, departments)
    4. Route based on complexity and tool needs:
       - complexity 1-2, no restricted intent → LOCAL_FAST
       - needs_tool or complexity 3 → CORTEX_SYNC
       - complexity 4-5 or estimated long duration → CORTEX_ASYNC
    """

    def __init__(self) -> None:
        """Initialize router with classifier and feature flags."""
        self.classifier = IntentClassifier()
        self.flags = self._load_feature_flags()
        logger.info(
            "LaneRouter initialized",
            extra={
                "local_fast_enabled": self.flags.local_fast_enabled,
                "cortex_routing_enabled": self.flags.cortex_routing_enabled,
            },
        )

    def _load_feature_flags(self) -> FeatureFlags:
        """Load feature flags from config file."""
        config_path = CONFIG_DIR / "feature_flags.yaml"
        if not config_path.exists():
            logger.warning("No feature_flags.yaml found, using defaults")
            return FeatureFlags()

        try:
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}

            routing = config.get("routing", {})
            guardrails = config.get("guardrails", {})
            observability = config.get("observability", {})

            return FeatureFlags(
                local_fast_enabled=routing.get("local_fast_enabled", True),
                local_fast_timeout_seconds=routing.get("local_fast_timeout_seconds", 2.0),
                local_fast_confidence_threshold=routing.get(
                    "local_fast_confidence_threshold", 0.7
                ),
                cortex_routing_enabled=routing.get("cortex_routing_enabled", False),
                cortex_sync_timeout_seconds=routing.get("cortex_sync_timeout_seconds", 30.0),
                cortex_async_threshold_seconds=routing.get(
                    "cortex_async_threshold_seconds", 60.0
                ),
                max_local_response_tokens=guardrails.get("max_local_response_tokens", 256),
                always_escalate_intents=guardrails.get("always_escalate_intents", []),
                restricted_departments=guardrails.get("restricted_departments", []),
                log_routing_decisions=observability.get("log_routing_decisions", True),
                include_timing_metrics=observability.get("include_timing_metrics", True),
                trace_sample_rate=observability.get("trace_sample_rate", 0.1),
            )
        except Exception as e:
            logger.error(f"Failed to load feature flags: {e}")
            return FeatureFlags()

    def reload_flags(self) -> None:
        """Reload feature flags from config (for runtime updates)."""
        self.flags = self._load_feature_flags()
        logger.info("Feature flags reloaded")

    async def route(
        self,
        message: str,
        department_slug: str,
        conversation_history: list[dict[str, Any]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        """
        Route a message to the appropriate processing lane.

        Args:
            message: The user's message to route
            department_slug: The department context (e.g., 'sales', 'support')
            conversation_history: Optional conversation context
            context: Optional additional context (org_id, user_id, etc.)

        Returns:
            RoutingDecision with lane, intent result, and metadata
        """
        start_time = time.perf_counter()
        context = context or {}

        # Step 1: Classify intent
        intent_result = await self.classifier.classify(
            message=message,
            department_slug=department_slug,
            conversation_history=conversation_history,
        )

        # Step 2: Apply routing logic
        decision = self._apply_routing_logic(intent_result, department_slug, context)

        # Add timing
        routing_time_ms = (time.perf_counter() - start_time) * 1000
        decision.routing_time_ms = routing_time_ms

        # Log decision if enabled
        if self.flags.log_routing_decisions:
            self._log_decision(decision, message, department_slug)

        return decision

    def _apply_routing_logic(
        self,
        intent_result: IntentResult,
        department_slug: str,
        context: dict[str, Any],
    ) -> RoutingDecision:
        """Apply routing rules to determine the appropriate lane."""

        # Check if local fast is disabled globally
        if not self.flags.local_fast_enabled:
            return self._route_to_cortex_or_fallback(
                intent_result, "local_fast_disabled"
            )

        # Check restricted departments
        if department_slug in self.flags.restricted_departments:
            return self._route_to_cortex_or_fallback(
                intent_result, f"department_{department_slug}_restricted"
            )

        # Check always-escalate intents
        if intent_result.intent in self.flags.always_escalate_intents:
            return self._route_to_cortex_or_fallback(
                intent_result, f"intent_{intent_result.intent}_requires_escalation"
            )

        # Check if can handle locally (complexity 1-2)
        if intent_result.can_handle_locally:
            # Verify confidence threshold
            if intent_result.confidence >= self.flags.local_fast_confidence_threshold:
                return RoutingDecision(
                    lane=Lane.LOCAL_FAST,
                    intent_result=intent_result,
                    reason="complexity_1_2_high_confidence",
                    metadata={
                        "suggested_response": intent_result.suggested_response,
                        "timeout_seconds": self.flags.local_fast_timeout_seconds,
                        "max_tokens": self.flags.max_local_response_tokens,
                    },
                )
            else:
                # Low confidence, still try local but without suggested response
                return RoutingDecision(
                    lane=Lane.LOCAL_FAST,
                    intent_result=intent_result,
                    reason="complexity_1_2_low_confidence_generate",
                    metadata={
                        "suggested_response": None,  # Generate fresh
                        "timeout_seconds": self.flags.local_fast_timeout_seconds,
                        "max_tokens": self.flags.max_local_response_tokens,
                    },
                )

        # Needs tool or complexity 3 → Cortex sync
        if intent_result.needs_tool or intent_result.complexity == 3:
            return self._route_to_cortex_or_fallback(
                intent_result,
                "needs_tool" if intent_result.needs_tool else "complexity_3_moderate",
                prefer_sync=True,
            )

        # Complexity 4-5 → Cortex async
        if intent_result.complexity >= 4:
            return self._route_to_cortex_or_fallback(
                intent_result,
                f"complexity_{intent_result.complexity}_high",
                prefer_sync=False,
            )

        # Default: route to Cortex sync (shouldn't reach here normally)
        return self._route_to_cortex_or_fallback(intent_result, "default_escalation")

    def _route_to_cortex_or_fallback(
        self,
        intent_result: IntentResult,
        reason: str,
        prefer_sync: bool = True,
    ) -> RoutingDecision:
        """Route to Cortex if enabled, otherwise fallback."""
        if not self.flags.cortex_routing_enabled:
            return RoutingDecision(
                lane=Lane.FALLBACK,
                intent_result=intent_result,
                reason=f"{reason}_cortex_disabled",
                metadata={
                    "fallback_reason": "cortex_routing_not_enabled",
                    "escalation_reason": intent_result.escalation_reason,
                },
            )

        lane = Lane.CORTEX_SYNC if prefer_sync else Lane.CORTEX_ASYNC
        timeout = (
            self.flags.cortex_sync_timeout_seconds
            if prefer_sync
            else self.flags.cortex_async_threshold_seconds
        )

        return RoutingDecision(
            lane=lane,
            intent_result=intent_result,
            reason=reason,
            metadata={
                "timeout_seconds": timeout,
                "escalation_reason": intent_result.escalation_reason,
            },
        )

    def _log_decision(
        self,
        decision: RoutingDecision,
        message: str,
        department_slug: str,
    ) -> None:
        """Log routing decision for observability."""
        log_data = {
            "lane": decision.lane.value,
            "reason": decision.reason,
            "intent": decision.intent_result.intent,
            "complexity": decision.intent_result.complexity,
            "department": department_slug,
            "needs_tool": decision.intent_result.needs_tool,
            "confidence": decision.intent_result.confidence,
        }

        if self.flags.include_timing_metrics:
            log_data["routing_time_ms"] = round(decision.routing_time_ms, 2)

        # Truncate message for logging
        log_data["message_preview"] = message[:50] + "..." if len(message) > 50 else message

        logger.info(
            f"Routing decision: {decision.lane.value}",
            extra=log_data,
        )


# Module-level singleton
lane_router = LaneRouter()
