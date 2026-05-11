from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from apps.agencyos.backend.services.intent_classifier import IntentClassifier, IntentResult
from apps.agencyos.backend.services.voice_session import VoiceSessionManager


class TestVoiceSessionManager:
    @pytest.mark.asyncio
    async def test_create_session(self) -> None:
        manager = VoiceSessionManager()

        session = await manager.create_session(
            org_id="org_acme",
            user_id="user_123",
            department_slug="sales",
        )

        assert UUID(session.session_id)
        assert session.org_id == "org_acme"
        assert session.user_id == "user_123"
        assert session.department_slug == "sales"
        assert session.is_active is True
        assert session.escalation_count == 0
        assert session.total_turns == 0
        assert session.conversation_history == []
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.last_activity, datetime)

    @pytest.mark.asyncio
    async def test_add_turn(self) -> None:
        manager = VoiceSessionManager()
        session = await manager.create_session("org_acme", "user_123")

        await manager.add_turn(session.session_id, "user", "Hi there")
        await manager.add_turn(session.session_id, "assistant", "Hello! How can I help?")

        updated = await manager.get_session(session.session_id)
        assert updated is not None
        assert len(updated.conversation_history) == 2
        assert updated.total_turns == 2
        assert updated.conversation_history[0]["content"] == "Hi there"
        assert updated.conversation_history[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_add_turn_caps_history_at_20(self) -> None:
        manager = VoiceSessionManager()
        session = await manager.create_session("org_acme", "user_123")

        for i in range(25):
            await manager.add_turn(session.session_id, "user", f"turn {i}")

        updated = await manager.get_session(session.session_id)
        assert updated is not None
        assert len(updated.conversation_history) == 20
        assert updated.total_turns == 25
        assert updated.conversation_history[0]["content"] == "turn 5"
        assert updated.conversation_history[-1]["content"] == "turn 24"

    @pytest.mark.asyncio
    async def test_record_escalation(self) -> None:
        manager = VoiceSessionManager()
        session = await manager.create_session("org_acme", "user_123")

        await manager.record_escalation(session.session_id)
        await manager.record_escalation(session.session_id)

        updated = await manager.get_session(session.session_id)
        assert updated is not None
        assert updated.escalation_count == 2

    @pytest.mark.asyncio
    async def test_end_session(self) -> None:
        manager = VoiceSessionManager()
        session = await manager.create_session("org_acme", "user_123")
        await manager.add_turn(session.session_id, "user", "Need help with a quote")
        await manager.add_turn(session.session_id, "assistant", "I can help with that")
        await manager.record_escalation(session.session_id)

        stats = await manager.end_session(session.session_id)
        updated = await manager.get_session(session.session_id)

        assert stats is not None
        assert stats["duration_seconds"] >= 0
        assert stats["total_turns"] == 2
        assert stats["escalation_count"] == 1
        assert updated is not None
        assert updated.is_active is False

    @pytest.mark.asyncio
    async def test_cleanup_stale(self) -> None:
        manager = VoiceSessionManager()
        session = await manager.create_session("org_acme", "user_123")
        await manager.end_session(session.session_id)

        stale = await manager.get_session(session.session_id)
        assert stale is not None
        stale.last_activity = datetime.now(timezone.utc) - timedelta(minutes=60)

        removed = await manager.cleanup_stale(max_age_minutes=30)
        missing = await manager.get_session(session.session_id)

        assert removed == 1
        assert missing is None

    @pytest.mark.asyncio
    async def test_get_active_sessions(self) -> None:
        manager = VoiceSessionManager()
        s1 = await manager.create_session("org_acme", "user_1")
        s2 = await manager.create_session("org_beta", "user_2")
        s3 = await manager.create_session("org_acme", "user_3")
        await manager.end_session(s2.session_id)

        all_active = await manager.get_active_sessions()
        acme_active = await manager.get_active_sessions(org_id="org_acme")

        assert {s.session_id for s in all_active} == {s1.session_id, s3.session_id}
        assert {s.session_id for s in acme_active} == {s1.session_id, s3.session_id}

    @pytest.mark.asyncio
    async def test_get_stats(self) -> None:
        manager = VoiceSessionManager()
        s1 = await manager.create_session("org_acme", "user_1")
        s2 = await manager.create_session("org_acme", "user_2")
        s3 = await manager.create_session("org_beta", "user_3")

        await manager.add_turn(s1.session_id, "user", "hello")
        await manager.add_turn(s1.session_id, "assistant", "hi")
        await manager.add_turn(s2.session_id, "user", "quote status")
        await manager.end_session(s3.session_id)

        stats = await manager.get_stats()

        assert stats["total_active"] == 2
        assert stats["by_org"] == {"org_acme": 2}
        assert stats["avg_turns_per_session"] == 1.5


class TestIntentClassifier:
    def test_parse_classification_valid_json(self) -> None:
        classifier = IntentClassifier()
        raw = (
            '{"intent":"lead_query","complexity":2,"needs_tool":true,'
            '"department":"sales","can_handle_locally":true,'
            '"suggested_response":"Checking your leads now.",'
            '"confidence":0.88,"escalation_reason":null}'
        )

        result = classifier._parse_classification(raw)

        assert isinstance(result, IntentResult)
        assert result.intent == "lead_query"
        assert result.complexity == 2
        assert result.needs_tool is True
        assert result.department == "sales"
        assert result.can_handle_locally is True
        assert result.suggested_response == "Checking your leads now."
        assert result.confidence == pytest.approx(0.88)
        assert result.escalation_reason is None

    def test_parse_classification_fenced_json(self) -> None:
        classifier = IntentClassifier()
        raw = """Here is the result:\n```json
{"intent":"greeting","complexity":1,"needs_tool":false,"department":"chief","can_handle_locally":true,"suggested_response":"Hey there!","confidence":0.95,"escalation_reason":null}
```"""

        result = classifier._parse_classification(raw)

        assert result.intent == "greeting"
        assert result.complexity == 1
        assert result.department == "chief"
        assert result.can_handle_locally is True
        assert result.suggested_response == "Hey there!"

    @pytest.mark.asyncio
    async def test_parse_classification_malformed(self) -> None:
        classifier = IntentClassifier()
        classifier.model_router = MagicMock()
        classifier.model_router.generate = AsyncMock(return_value={"content": "totally not json"})

        result = await classifier.classify(
            message="Can you create a strategic expansion plan?",
            department_slug="chief",
        )

        assert isinstance(result, IntentResult)
        assert result.complexity == 3
        assert result.can_handle_locally is False
        assert result.escalation_reason == "classification_failure"

    @pytest.mark.asyncio
    async def test_classify_mocked(self) -> None:
        classifier = IntentClassifier()
        canned = {
            "content": (
                '{"intent":"ticket_status","complexity":2,"needs_tool":true,'
                '"department":"support","can_handle_locally":true,'
                '"suggested_response":"I can check that for you.",'
                '"confidence":0.91,"escalation_reason":null}'
            )
        }

        with patch.object(classifier.model_router, "generate", new=AsyncMock(return_value=canned)) as mock_generate:
            result = await classifier.classify(
                message="What is the status of ticket #4821?",
                department_slug="support",
                conversation_history=[
                    {"role": "user", "content": "Hi"},
                    {"role": "assistant", "content": "Hello!"},
                ],
            )

        assert isinstance(result, IntentResult)
        assert result.intent == "ticket_status"
        assert result.department == "support"
        assert result.complexity == 2
        assert result.can_handle_locally is True
        assert result.escalation_reason is None
        assert result.suggested_response == "I can check that for you."
        mock_generate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_batch_classify(self) -> None:
        classifier = IntentClassifier()

        responses = [
            {
                "content": '{"intent":"greeting","complexity":1,"needs_tool":false,"department":"sales","can_handle_locally":true,"suggested_response":"Hi!","confidence":0.8,"escalation_reason":null}'
            },
            {
                "content": '{"intent":"proposal_request","complexity":4,"needs_tool":false,"department":"sales","can_handle_locally":false,"suggested_response":null,"confidence":0.86,"escalation_reason":"Needs deeper synthesis"}'
            },
        ]

        with patch.object(classifier.model_router, "generate", new=AsyncMock(side_effect=responses)):
            result = await classifier.batch_classify(
                messages=["Hey there", "Draft an enterprise proposal for Q3"],
                department_slug="sales",
            )

        assert len(result) == 2
        assert all(isinstance(item, IntentResult) for item in result)
        assert result[0].intent == "greeting"
        assert result[0].can_handle_locally is True
        assert result[1].intent == "proposal_request"
        assert result[1].complexity == 4
        assert result[1].can_handle_locally is False
