import uuid as _uuid

import pytest
from unittest.mock import AsyncMock, MagicMock

from apps.agencyos.backend.services import cortex_bridge


class _FakeResponse:
    def __init__(self, status_code, payload=None, raise_json=False):
        self.status_code = status_code
        self._payload = payload or {}
        self._raise_json = raise_json

    def json(self):
        if self._raise_json:
            raise ValueError("no json")
        return self._payload


class _FakeClient:
    """Stands in for httpx.AsyncClient(...) used as an async context manager."""

    def __init__(self, resp=None, exc=None):
        self._resp = resp
        self._exc = exc
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        if self._exc:
            raise self._exc
        return self._resp


def _patch_client(monkeypatch, fake):
    monkeypatch.setattr(cortex_bridge.httpx, "AsyncClient", lambda **kw: fake)


def test_is_enabled(monkeypatch):
    monkeypatch.delenv("WBIT_BRIDGE_ENABLED", raising=False)
    assert cortex_bridge.is_enabled() is False
    for v in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("WBIT_BRIDGE_ENABLED", v)
        assert cortex_bridge.is_enabled() is True
    monkeypatch.setenv("WBIT_BRIDGE_ENABLED", "false")
    assert cortex_bridge.is_enabled() is False


@pytest.mark.asyncio
async def test_send_missing_config(monkeypatch):
    monkeypatch.delenv("WBIT_BRIDGE_SECRET", raising=False)
    out = await cortex_bridge._send("hi", "co", "ag", None)
    assert out["ok"] is False and "SECRET" in out["error"]

    monkeypatch.setenv("WBIT_BRIDGE_SECRET", "s")
    out = await cortex_bridge._send("hi", "", "ag", None)
    assert out["ok"] is False and "COMPANY" in out["error"]


@pytest.mark.asyncio
async def test_send_success_threads_session_and_secret(monkeypatch):
    monkeypatch.setenv("WBIT_BRIDGE_SECRET", "secret")
    fake = _FakeClient(
        _FakeResponse(201, {"response": "hello", "sessionId": "s1", "runId": "r1", "created": True})
    )
    _patch_client(monkeypatch, fake)

    out = await cortex_bridge._send("hi", "co1", "ag1", "prev-session")
    assert out == {
        "ok": True,
        "response": "hello",
        "sessionId": "s1",
        "runId": "r1",
        "created": True,
    }
    body = fake.calls[0]["json"]
    assert body == {
        "companyId": "co1",
        "agentId": "ag1",
        "prompt": "hi",
        "sessionId": "prev-session",
    }
    assert fake.calls[0]["headers"]["x-wbit-bridge-secret"] == "secret"


@pytest.mark.asyncio
async def test_send_omits_session_when_none(monkeypatch):
    monkeypatch.setenv("WBIT_BRIDGE_SECRET", "secret")
    fake = _FakeClient(_FakeResponse(201, {"response": "x", "sessionId": "s"}))
    _patch_client(monkeypatch, fake)
    await cortex_bridge._send("hi", "co", "ag", None)
    assert "sessionId" not in fake.calls[0]["json"]


@pytest.mark.asyncio
async def test_send_non_2xx(monkeypatch):
    monkeypatch.setenv("WBIT_BRIDGE_SECRET", "secret")
    _patch_client(monkeypatch, _FakeClient(_FakeResponse(502, {})))
    out = await cortex_bridge._send("hi", "co", "ag", None)
    assert out["ok"] is False and out["status_code"] == 502


@pytest.mark.asyncio
async def test_send_timeout(monkeypatch):
    monkeypatch.setenv("WBIT_BRIDGE_SECRET", "secret")
    _patch_client(monkeypatch, _FakeClient(exc=cortex_bridge.httpx.TimeoutException("t")))
    out = await cortex_bridge._send("hi", "co", "ag", None)
    assert out["ok"] is False and "timed out" in out["error"]


@pytest.mark.asyncio
async def test_handle_chat_success_shapes_and_saves_session(monkeypatch):
    monkeypatch.setattr(cortex_bridge, "_load_session_id", lambda db, chat_id: None)
    saved = {}
    monkeypatch.setattr(
        cortex_bridge,
        "_save_session_id",
        lambda db, chat_id, org_id, sid: saved.update(
            {"chat_id": chat_id, "org_id": org_id, "sid": sid}
        ),
    )
    monkeypatch.setattr(
        cortex_bridge,
        "_send",
        AsyncMock(return_value={"ok": True, "response": "hi there", "sessionId": "new-sess"}),
    )

    out = await cortex_bridge.handle_chat(
        "build me X", org_id="org1", chat_id="chat1", db=object(), department_slug="sales"
    )
    assert out["status"] == "ok"
    assert out["content"] == "hi there"
    assert out["model"] == "cortex/wbit-assistant"
    assert out["department"] == "sales"
    assert out["proposals"] == [] and out["usage"] == {}
    assert saved == {"chat_id": "chat1", "org_id": "org1", "sid": "new-sess"}


@pytest.mark.asyncio
async def test_handle_chat_reused_session_not_resaved(monkeypatch):
    monkeypatch.setattr(cortex_bridge, "_load_session_id", lambda db, chat_id: "same")
    save = MagicMock()
    monkeypatch.setattr(cortex_bridge, "_save_session_id", save)
    monkeypatch.setattr(
        cortex_bridge,
        "_send",
        AsyncMock(return_value={"ok": True, "response": "ok", "sessionId": "same"}),
    )
    out = await cortex_bridge.handle_chat("hi", org_id="o", chat_id="c", db=object())
    assert out["status"] == "ok"
    save.assert_not_called()  # unchanged session id -> no rewrite


@pytest.mark.asyncio
async def test_handle_chat_error_returns_friendly_message(monkeypatch):
    monkeypatch.setattr(cortex_bridge, "_load_session_id", lambda db, chat_id: None)
    monkeypatch.setattr(
        cortex_bridge, "_send", AsyncMock(return_value={"ok": False, "error": "boom"})
    )
    out = await cortex_bridge.handle_chat("hi", org_id="o", chat_id="c", db=object())
    assert out["status"] == "error"
    assert "trouble reaching" in out["content"]
    assert out["model"] == "cortex/wbit-assistant"


# --- per-org company resolution (#66) ----------------------------------------

def test_resolve_company_no_org_uses_default(monkeypatch):
    monkeypatch.delenv("WBIT_COMPANY_ID", raising=False)
    monkeypatch.delenv("PORTAL_COMPANY_OVERRIDES", raising=False)
    assert cortex_bridge._resolve_company_id(None) == cortex_bridge._DEFAULT_PORTAL_COMPANY_ID
    assert cortex_bridge._resolve_company_id("") == cortex_bridge._DEFAULT_PORTAL_COMPANY_ID


def test_resolve_company_no_org_honors_wbit_company_id(monkeypatch):
    monkeypatch.delenv("PORTAL_COMPANY_OVERRIDES", raising=False)
    monkeypatch.setenv("WBIT_COMPANY_ID", "11111111-1111-4111-a111-111111111111")
    assert cortex_bridge._resolve_company_id(None) == "11111111-1111-4111-a111-111111111111"


def test_resolve_company_uuid_passthrough(monkeypatch):
    monkeypatch.delenv("PORTAL_COMPANY_OVERRIDES", raising=False)
    u = "22222222-2222-4222-a222-222222222222"
    assert cortex_bridge._resolve_company_id(u) == u


def test_resolve_company_cuid_derives_uuidv5(monkeypatch):
    monkeypatch.delenv("PORTAL_COMPANY_OVERRIDES", raising=False)
    cuid = "clv9k2x7a0001abcd1234efgh"
    expected = str(_uuid.uuid5(cortex_bridge._PORTAL_ORG_UUID_NAMESPACE, cuid))
    assert cortex_bridge._resolve_company_id(cuid) == expected
    assert cortex_bridge._resolve_company_id(cuid) != cortex_bridge._DEFAULT_PORTAL_COMPANY_ID


def test_resolve_company_override_pins_existing_company(monkeypatch):
    wbit_cuid = "cmpswvysr000029jthi4waszr"
    c0de = cortex_bridge._DEFAULT_PORTAL_COMPANY_ID
    monkeypatch.setenv("PORTAL_COMPANY_OVERRIDES", f"{wbit_cuid}={c0de}")
    # Override wins over the would-be derived UUIDv5.
    assert cortex_bridge._resolve_company_id(wbit_cuid) == c0de
    assert cortex_bridge._resolve_company_id(wbit_cuid) != str(
        _uuid.uuid5(cortex_bridge._PORTAL_ORG_UUID_NAMESPACE, wbit_cuid)
    )


def test_resolve_company_override_ignores_non_uuid_value(monkeypatch):
    monkeypatch.setenv("PORTAL_COMPANY_OVERRIDES", "someorg=not-a-uuid")
    # Invalid override value is dropped -> falls through to UUIDv5 derivation.
    assert cortex_bridge._resolve_company_id("someorg") == str(
        _uuid.uuid5(cortex_bridge._PORTAL_ORG_UUID_NAMESPACE, "someorg")
    )


@pytest.mark.asyncio
async def test_handle_chat_sends_resolved_company(monkeypatch):
    monkeypatch.delenv("PORTAL_COMPANY_OVERRIDES", raising=False)
    monkeypatch.setattr(cortex_bridge, "_load_session_id", lambda db, chat_id: None)
    monkeypatch.setattr(cortex_bridge, "_save_session_id", lambda *a, **k: None)
    captured = {}

    async def fake_send(prompt, company_id, agent_id, session_id):
        captured["company_id"] = company_id
        return {"ok": True, "response": "ok", "sessionId": "s"}

    monkeypatch.setattr(cortex_bridge, "_send", fake_send)
    cuid = "clv9k2x7a0002zzzz9999wxyz"
    await cortex_bridge.handle_chat("hi", org_id=cuid, chat_id="c", db=object())
    assert captured["company_id"] == str(
        _uuid.uuid5(cortex_bridge._PORTAL_ORG_UUID_NAMESPACE, cuid)
    )
