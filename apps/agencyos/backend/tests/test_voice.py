from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

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
