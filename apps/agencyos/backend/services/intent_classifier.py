"""Standalone intent classification service for AgencyOS voice mode."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from apps.agencyos.backend.services.model_router import ModelRouter

logger = logging.getLogger("agencyos.intent_classifier")


@dataclass(slots=True)
class IntentResult:
    """Structured intent classification output."""

    intent: str
    complexity: int
    needs_tool: bool
    department: str
    can_handle_locally: bool
    suggested_response: Optional[str]
    confidence: float
    escalation_reason: Optional[str]


class IntentClassifier:
    """Classifies user requests for local handling vs model escalation."""

    def __init__(self) -> None:
        """Initialize classifier state and prompt template."""
        self.model_router = ModelRouter()
        self._prompt_template = (
            "You are an intent classifier for AgencyOS. "
            "Analyze the latest user message (and optional conversation context).\n\n"
            "Department context:\n"
            "- Department slug: {department_slug}\n"
            "- Interpret intent using department-aware language.\n"
            "  * If department is sales-related, prioritize terms like: lead, pipeline, deal, quote, prospect, follow-up.\n"
            "  * If department is customer support-related, prioritize terms like: ticket, bug, issue, outage, refund, SLA, troubleshooting.\n"
            "  * Otherwise, infer from the department slug and message semantics.\n\n"
            "Complexity guide:\n"
            "1 = greeting, tiny chit-chat, basic confirmation\n"
            "2 = simple lookup or straightforward factual request\n"
            "3 = analysis, comparison, or multi-step reasoning\n"
            "4 = proposal drafting, synthesis, or nuanced recommendation\n"
            "5 = strategic planning, executive-level reasoning, or broad cross-domain coordination\n\n"
            "Rules:\n"
            "- can_handle_locally MUST be true only for complexity 1-2.\n"
            "- For complexity 3+, set can_handle_locally=false and provide escalation_reason.\n"
            "- needs_tool=true if CRM, ticketing, calendar, or external system data/actions are required.\n"
            "- Keep intent concise, lowercase snake_case where possible (e.g., greeting, lead_query, ticket_status).\n"
            "- Confidence must be a float between 0.0 and 1.0.\n"
            "- suggested_response should be provided only when can_handle_locally=true.\n\n"
            "Return ONLY valid JSON with this exact schema:\n"
            "{\n"
            "  \"intent\": \"string\",\n"
            "  \"complexity\": 1,\n"
            "  \"needs_tool\": false,\n"
            "  \"department\": \"{department_slug}\",\n"
            "  \"can_handle_locally\": true,\n"
            "  \"suggested_response\": \"string or null\",\n"
            "  \"confidence\": 0.0,\n"
            "  \"escalation_reason\": \"string or null\"\n"
            "}"
        )

    async def classify(
        self,
        message: str,
        department_slug: str,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> IntentResult:
        """Classify a single message using the local-tier model (Gemma)."""
        system_prompt = self._build_classification_prompt(department_slug)

        messages: list[dict[str, str]] = []
        for turn in (conversation_history or [])[-6:]:
            role = str(turn.get("role", "")).strip().lower()
            content = str(turn.get("content", "")).strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": message})

        try:
            result = await self.model_router.generate(
                tier="local",
                messages=messages,
                system_prompt=system_prompt,
            )
            raw = str((result or {}).get("content", ""))
            parsed = self._parse_classification(raw)

            if parsed.department != department_slug:
                parsed.department = department_slug

            if parsed.complexity <= 2:
                parsed.can_handle_locally = True
                parsed.escalation_reason = None
            else:
                parsed.can_handle_locally = False
                if not parsed.escalation_reason:
                    parsed.escalation_reason = (
                        "Requires deeper reasoning than local complexity threshold."
                    )

            if not parsed.can_handle_locally:
                parsed.suggested_response = None

            return parsed
        except Exception as exc:
            logger.warning(
                "Intent classification failed; falling back to escalation path",
                extra={"department": department_slug, "error": str(exc)},
            )
            return self._fallback_result(department_slug, "classification_failure")

    async def batch_classify(
        self,
        messages: list[str],
        department_slug: str,
    ) -> list[IntentResult]:
        """Classify a batch of messages, preserving input order."""
        results: list[IntentResult] = []
        for msg in messages:
            results.append(
                await self.classify(
                    message=msg,
                    department_slug=department_slug,
                    conversation_history=None,
                )
            )
        return results

    def _build_classification_prompt(self, department_slug: str) -> str:
        """Build the classification system prompt with department context."""
        return self._prompt_template.format(department_slug=department_slug)

    def _parse_classification(self, raw: str) -> IntentResult:
        """Parse classifier JSON from plain output, fenced blocks, or mixed text."""
        text = (raw or "").strip()
        if not text:
            raise ValueError("Empty classification output")

        candidates: list[str] = [text]
        candidates.extend(
            re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
        )

        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            candidates.append(text[first_brace : last_brace + 1])

        for candidate in candidates:
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return self._intent_result_from_dict(data)
            except (json.JSONDecodeError, TypeError, ValueError):
                continue

        raise ValueError("No valid JSON classification object found")

    def _intent_result_from_dict(self, data: dict[str, Any]) -> IntentResult:
        """Coerce parsed JSON dict into a validated IntentResult."""
        intent = str(data.get("intent", "unknown")).strip() or "unknown"

        try:
            complexity = int(data.get("complexity", 3))
        except (TypeError, ValueError):
            complexity = 3
        complexity = max(1, min(5, complexity))

        needs_tool = bool(data.get("needs_tool", False))
        department = str(data.get("department", "")).strip() or "unknown"

        can_handle_locally_raw = data.get("can_handle_locally")
        if can_handle_locally_raw is None:
            can_handle_locally = complexity <= 2
        else:
            can_handle_locally = bool(can_handle_locally_raw)

        suggested_response_raw = data.get("suggested_response")
        suggested_response = (
            str(suggested_response_raw).strip()
            if suggested_response_raw not in (None, "")
            else None
        )

        confidence_raw = data.get("confidence", 0.5)
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        escalation_reason_raw = data.get("escalation_reason")
        escalation_reason = (
            str(escalation_reason_raw).strip()
            if escalation_reason_raw not in (None, "")
            else None
        )

        return IntentResult(
            intent=intent,
            complexity=complexity,
            needs_tool=needs_tool,
            department=department,
            can_handle_locally=can_handle_locally,
            suggested_response=suggested_response,
            confidence=confidence,
            escalation_reason=escalation_reason,
        )

    def _fallback_result(self, department_slug: str, reason: str) -> IntentResult:
        """Build conservative fallback classification when parsing/modeling fails."""
        return IntentResult(
            intent="unknown",
            complexity=3,
            needs_tool=False,
            department=department_slug,
            can_handle_locally=False,
            suggested_response=None,
            confidence=0.0,
            escalation_reason=reason,
        )


intent_classifier = IntentClassifier()
