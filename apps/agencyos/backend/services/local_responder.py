"""
AgencyOS Local Responder

Handles LOCAL_FAST lane requests with quick, guardrailed responses.
Uses the local model tier (Ollama/Gemma) with strict timeout and token limits.

Flow:
1. Check if suggested_response from intent classifier is available (high confidence)
2. If yes, validate and return it
3. If no, generate fresh response with timeout guardrails
4. Apply post-generation safety checks
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

from apps.agencyos.backend.services.model_router import ModelRouter
from apps.agencyos.backend.services.lane_router import Lane, RoutingDecision

logger = logging.getLogger("agencyos.local_responder")


@dataclass(slots=True)
class LocalResponse:
    """Result from local fast lane processing."""

    content: str
    success: bool
    source: str  # 'suggested', 'generated', 'timeout_fallback', 'error'
    response_time_ms: float
    tokens_used: int
    escalated: bool = False
    escalation_reason: Optional[str] = None


class LocalResponder:
    """
    Generates fast local responses for simple queries.

    Features:
    - Uses suggested response when available (high confidence)
    - Strict timeout enforcement (default 2s)
    - Token limits for response brevity
    - Safety checks before returning
    """

    def __init__(self) -> None:
        """Initialize responder with model router."""
        self.model_router = ModelRouter()
        self._system_prompt_template = (
            "You are a helpful assistant for {department} department. "
            "Provide brief, direct answers. Keep responses under 2-3 sentences. "
            "If you cannot answer definitively, say so clearly. "
            "Do not make up information or guess at data you don't have."
        )
        logger.info("LocalResponder initialized")

    async def respond(
        self,
        message: str,
        routing_decision: RoutingDecision,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> LocalResponse:
        """
        Generate a local fast response.

        Args:
            message: The user's message
            routing_decision: The routing decision from LaneRouter
            conversation_history: Optional conversation context

        Returns:
            LocalResponse with content and metadata
        """
        if routing_decision.lane != Lane.LOCAL_FAST:
            return LocalResponse(
                content="",
                success=False,
                source="error",
                response_time_ms=0.0,
                tokens_used=0,
                escalated=True,
                escalation_reason="wrong_lane",
            )

        start_time = time.perf_counter()
        metadata = routing_decision.metadata
        timeout_seconds = metadata.get("timeout_seconds", 2.0)
        max_tokens = metadata.get("max_tokens", 256)

        # Check for high-confidence suggested response
        suggested = metadata.get("suggested_response")
        if suggested and self._validate_suggested_response(suggested):
            response_time_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "Using suggested response",
                extra={
                    "intent": routing_decision.intent_result.intent,
                    "confidence": routing_decision.intent_result.confidence,
                },
            )
            return LocalResponse(
                content=suggested,
                success=True,
                source="suggested",
                response_time_ms=response_time_ms,
                tokens_used=self._estimate_tokens(suggested),
            )

        # Generate fresh response with timeout
        try:
            response = await asyncio.wait_for(
                self._generate_response(
                    message=message,
                    department=routing_decision.intent_result.department,
                    conversation_history=conversation_history,
                    max_tokens=max_tokens,
                ),
                timeout=timeout_seconds,
            )

            response_time_ms = (time.perf_counter() - start_time) * 1000

            # Validate generated response
            if not self._validate_response(response):
                return LocalResponse(
                    content="",
                    success=False,
                    source="error",
                    response_time_ms=response_time_ms,
                    tokens_used=0,
                    escalated=True,
                    escalation_reason="response_validation_failed",
                )

            return LocalResponse(
                content=response,
                success=True,
                source="generated",
                response_time_ms=response_time_ms,
                tokens_used=self._estimate_tokens(response),
            )

        except asyncio.TimeoutError:
            response_time_ms = (time.perf_counter() - start_time) * 1000
            logger.warning(
                f"Local response timed out after {timeout_seconds}s",
                extra={"department": routing_decision.intent_result.department},
            )
            return LocalResponse(
                content="",
                success=False,
                source="timeout_fallback",
                response_time_ms=response_time_ms,
                tokens_used=0,
                escalated=True,
                escalation_reason=f"timeout_after_{timeout_seconds}s",
            )

        except Exception as e:
            response_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Local response generation failed: {e}")
            return LocalResponse(
                content="",
                success=False,
                source="error",
                response_time_ms=response_time_ms,
                tokens_used=0,
                escalated=True,
                escalation_reason=str(e),
            )

    async def _generate_response(
        self,
        message: str,
        department: str,
        conversation_history: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> str:
        """Generate a response using the local model tier."""
        system_prompt = self._system_prompt_template.format(department=department)

        # Build messages
        messages: list[dict[str, str]] = []
        for turn in (conversation_history or [])[-4:]:  # Keep context short
            role = str(turn.get("role", "")).strip().lower()
            content = str(turn.get("content", "")).strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": message})

        # Call local tier model
        result = await self.model_router.generate(
            tier="local",
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )

        content = str((result or {}).get("content", "")).strip()
        return content

    def _validate_suggested_response(self, response: str) -> bool:
        """Validate a suggested response before using it."""
        if not response or len(response.strip()) < 2:
            return False

        # Check for obvious error patterns
        error_patterns = [
            "error",
            "failed",
            "cannot process",
            "unable to",
            "i don't know",
            "i'm not sure",
        ]
        lower_response = response.lower()
        for pattern in error_patterns:
            if pattern in lower_response and len(response) < 50:
                return False

        return True

    def _validate_response(self, response: str) -> bool:
        """Validate a generated response before returning."""
        if not response or len(response.strip()) < 2:
            return False

        # Check for model error indicators
        if response.startswith("Error:") or "error" in response.lower()[:20]:
            return False

        return True

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars per token average)."""
        return max(1, len(text) // 4)


# Module-level singleton
local_responder = LocalResponder()
