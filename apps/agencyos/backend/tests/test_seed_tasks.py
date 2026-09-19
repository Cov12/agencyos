"""Seed-tasks forwarder — cortex_bridge.seed_tasks (onboarding P4b).

The contract this file pins:
  - URL is derived from the bridge ORIGIN (like ensure-department-agents / role-map),
    env-overridable with CORTEX_SEED_TASKS_URL;
  - the shared x-wbit-bridge-secret authenticates it; the body is {companyId, tasks} with
    companyId resolved the same way chat resolves it;
  - a 200 with an issues list is {ok: True, issues}; everything else is
    {ok: False, error, status} — and it never RAISES into the request path.
"""

import asyncio

import httpx
import pytest

from apps.agencyos.backend.services import cortex_bridge

SECRET = "seed-tasks-secret"
COMPANY_ID = "company-uuid-1"
TASKS = [{"title": "Call Bob", "priority": "high"}, {"title": "Plan the launch"}]
ISSUES = [
    {"id": "iss-1", "identifier": "ACM-1", "title": "Call Bob"},
    {"id": "iss-2", "identifier": "ACM-2", "title": "Plan the launch"},
]


class _FakeResponse:
    def __init__(self, status_code, payload=None, raise_json=False):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self._raise_json = raise_json
        self.text = ""

    def json(self):
        if self._raise_json:
            raise ValueError("not json")
        return self._payload


class _FakeClient:
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "json": json or {}, "headers": headers or {}})
        if self.exc:
            raise self.exc
        return self.response


def _patch(monkeypatch, fake):
    monkeypatch.setenv("WBIT_BRIDGE_SECRET", SECRET)
    monkeypatch.setattr(cortex_bridge.httpx, "AsyncClient", lambda **kw: fake)
    monkeypatch.setattr(cortex_bridge, "_resolve_company_for_chat", lambda db, oid: COMPANY_ID)
    return fake


# --- URL resolution ----------------------------------------------------------

def test_url_is_core_route_derived_from_bridge_origin(monkeypatch):
    monkeypatch.setattr(
        cortex_bridge, "_bridge_url",
        lambda: "https://cortex.example/api/plugins/pid/api/chat",
    )
    monkeypatch.delenv("CORTEX_SEED_TASKS_URL", raising=False)
    assert cortex_bridge._seed_tasks_url() == "https://cortex.example/api/bridge/seed-tasks"


def test_url_env_override(monkeypatch):
    monkeypatch.setenv("CORTEX_SEED_TASKS_URL", "https://x.example/seed-tasks")
    assert cortex_bridge._seed_tasks_url() == "https://x.example/seed-tasks"


# --- happy path --------------------------------------------------------------

def test_posts_company_tasks_and_secret(monkeypatch):
    fake = _patch(monkeypatch, _FakeClient(_FakeResponse(200, {"issues": ISSUES})))

    result = asyncio.run(cortex_bridge.seed_tasks(None, "org-1", TASKS))

    assert result == {"ok": True, "issues": ISSUES}
    call = fake.calls[0]
    assert call["url"] == cortex_bridge._seed_tasks_url()
    assert call["headers"]["x-wbit-bridge-secret"] == SECRET
    assert call["json"] == {"companyId": COMPANY_ID, "tasks": TASKS}


# --- failures ----------------------------------------------------------------

def test_without_secret_is_a_noop_failure(monkeypatch):
    fake = _FakeClient(_FakeResponse(200, {"issues": ISSUES}))
    monkeypatch.delenv("WBIT_BRIDGE_SECRET", raising=False)
    monkeypatch.setattr(cortex_bridge.httpx, "AsyncClient", lambda **kw: fake)

    result = asyncio.run(cortex_bridge.seed_tasks(None, None, TASKS))
    assert result["ok"] is False and result["status"] is None
    assert fake.calls == []


def test_no_tasks_is_a_noop_failure(monkeypatch):
    fake = _patch(monkeypatch, _FakeClient(_FakeResponse(200, {"issues": []})))
    assert asyncio.run(cortex_bridge.seed_tasks(None, None, []))["ok"] is False
    assert fake.calls == []


def test_cortex_400_carries_its_message_and_status(monkeypatch):
    _patch(monkeypatch, _FakeClient(_FakeResponse(400, {"error": "title required"})))
    assert asyncio.run(cortex_bridge.seed_tasks(None, None, TASKS)) == {
        "ok": False, "error": "title required", "status": 400,
    }


@pytest.mark.parametrize(
    "make_fake, status",
    [
        (lambda: _FakeClient(_FakeResponse(500, {"error": "kaboom"})), 500),
        (lambda: _FakeClient(_FakeResponse(401, {})), 401),
        (lambda: _FakeClient(exc=httpx.TimeoutException("slow")), None),
        (lambda: _FakeClient(exc=httpx.RequestError("no route")), None),
        (lambda: _FakeClient(exc=RuntimeError("unexpected")), None),
        (lambda: _FakeClient(_FakeResponse(200, raise_json=True)), 200),
        (lambda: _FakeClient(_FakeResponse(200, {"ok": True})), 200),
        (lambda: _FakeClient(_FakeResponse(200, ["not", "a", "dict"])), 200),
    ],
    ids=["500", "401", "timeout", "transport", "unexpected", "non-json", "no-issues", "non-dict"],
)
def test_degrades_to_ok_false_without_raising(monkeypatch, make_fake, status):
    _patch(monkeypatch, make_fake())

    result = asyncio.run(cortex_bridge.seed_tasks(None, None, TASKS))

    assert result["ok"] is False
    assert result["error"]
    assert result["status"] == status
