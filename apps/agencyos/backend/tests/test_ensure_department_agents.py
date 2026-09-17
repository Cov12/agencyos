"""Specialist-agent provisioning forwarder — cortex_bridge.ensure_department_agents (P2a).

Onboarding P2a asks Cortex to provision one specialist agent per canonical role. The
contract this file pins:
  - URL is derived from the bridge ORIGIN (like ensure-agent / contexta-seed), env-overridable;
  - the shared x-wbit-bridge-secret authenticates it, and companyId resolves exactly as
    chat resolves it;
  - UNLIKE seeding, failure is MEANINGFUL: it is reported as {ok: False, error, status},
    never swallowed into a success — but it still never RAISES into the request path;
  - Cortex's own 4xx message survives, so the route can relay the offending role.
"""

import asyncio

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from open_webui.internal.db import Base
from apps.agencyos.backend.models.db import AgencyOSOrganization
from apps.agencyos.backend.services import cortex_bridge

ORG = "org-internal-agents"
CUID = "cmorgagentsxxxxxxxxxxxxxx"
SECRET = "agents-secret"
ROLES = ["sales", "marketing"]
AGENTS = [
    {"role": "sales", "agentId": "agent-sales", "created": True},
    {"role": "marketing", "agentId": "agent-marketing", "created": False},
]


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(AgencyOSOrganization(id=ORG, name="X", slug="x", portal_org_id=CUID))
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


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
    return fake


# --- URL resolution ----------------------------------------------------------

def test_url_is_core_route_derived_from_bridge_origin(monkeypatch):
    monkeypatch.setattr(
        cortex_bridge, "_bridge_url",
        lambda: "https://cortex.example/api/plugins/pid/api/chat",
    )
    monkeypatch.delenv("CORTEX_ENSURE_DEPT_AGENTS_URL", raising=False)
    assert (
        cortex_bridge._ensure_department_agents_url()
        == "https://cortex.example/api/bridge/ensure-department-agents"
    )


def test_url_env_override(monkeypatch):
    monkeypatch.setenv("CORTEX_ENSURE_DEPT_AGENTS_URL", "https://x.example/agents")
    assert cortex_bridge._ensure_department_agents_url() == "https://x.example/agents"


# --- happy path --------------------------------------------------------------

def test_posts_company_roles_and_secret(db, monkeypatch):
    fake = _patch(monkeypatch, _FakeClient(_FakeResponse(200, {"agents": AGENTS})))

    result = asyncio.run(cortex_bridge.ensure_department_agents(db, ORG, ROLES))

    assert result == {"ok": True, "agents": AGENTS}
    call = fake.calls[0]
    assert call["url"] == cortex_bridge._ensure_department_agents_url()
    assert call["url"].endswith("/api/bridge/ensure-department-agents")
    assert call["headers"]["x-wbit-bridge-secret"] == SECRET
    # companyId resolved the SAME way chat resolves it (portal id -> UUIDv5).
    assert call["json"]["companyId"] == cortex_bridge._resolve_company_id(CUID)
    assert call["json"]["roles"] == ROLES


def test_accepts_201(db, monkeypatch):
    _patch(monkeypatch, _FakeClient(_FakeResponse(201, {"agents": []})))
    assert asyncio.run(cortex_bridge.ensure_department_agents(db, ORG, ROLES)) == {
        "ok": True,
        "agents": [],
    }


def test_falls_back_to_default_company_without_db(monkeypatch):
    fake = _patch(monkeypatch, _FakeClient(_FakeResponse(200, {"agents": AGENTS})))

    assert asyncio.run(cortex_bridge.ensure_department_agents(None, None, ROLES))["ok"] is True
    assert fake.calls[0]["json"]["companyId"] == cortex_bridge._default_company_id()


# --- failures are reported, never swallowed ----------------------------------

def test_relays_cortex_4xx_message_and_status(db, monkeypatch):
    """Cortex rejects unknown roles / ceo / default with a 400 naming the role; the
    message and status must survive so the route can relay them."""
    fake = _patch(
        monkeypatch,
        _FakeClient(_FakeResponse(400, {"error": "unknown role: wizard"})),
    )

    result = asyncio.run(cortex_bridge.ensure_department_agents(db, ORG, ["wizard"]))

    assert result == {"ok": False, "error": "unknown role: wizard", "status": 400}
    assert fake.calls[0]["json"]["roles"] == ["wizard"]


def test_falls_back_to_a_generic_message_when_the_error_body_is_bare(db, monkeypatch):
    _patch(monkeypatch, _FakeClient(_FakeResponse(400, {})))
    result = asyncio.run(cortex_bridge.ensure_department_agents(db, ORG, ROLES))
    assert result["ok"] is False
    assert "400" in result["error"]
    assert result["status"] == 400


def test_without_secret_is_a_noop_failure(db, monkeypatch):
    fake = _FakeClient(_FakeResponse(200, {"agents": AGENTS}))
    monkeypatch.delenv("WBIT_BRIDGE_SECRET", raising=False)
    monkeypatch.setattr(cortex_bridge.httpx, "AsyncClient", lambda **kw: fake)

    result = asyncio.run(cortex_bridge.ensure_department_agents(db, ORG, ROLES))

    assert result["ok"] is False
    assert result["status"] is None
    assert fake.calls == []  # never left the process


def test_with_no_roles_is_a_noop_failure(db, monkeypatch):
    fake = _patch(monkeypatch, _FakeClient(_FakeResponse(200, {"agents": AGENTS})))
    assert asyncio.run(cortex_bridge.ensure_department_agents(db, ORG, []))["ok"] is False
    assert fake.calls == []


@pytest.mark.parametrize(
    # Factories, not instances: a parametrize list is built once at collection time, so
    # sharing _FakeClient objects would share their mutable `calls` across tests.
    "make_fake, expected_status",
    [
        (lambda: _FakeClient(_FakeResponse(500, {"error": "kaboom"})), 500),
        (lambda: _FakeClient(exc=httpx.TimeoutException("slow")), None),
        (lambda: _FakeClient(exc=httpx.RequestError("no route")), None),
        (lambda: _FakeClient(exc=RuntimeError("unexpected")), None),
        (lambda: _FakeClient(_FakeResponse(200, raise_json=True)), 200),
        (lambda: _FakeClient(_FakeResponse(200, {"ok": True})), 200),
        (lambda: _FakeClient(_FakeResponse(200, ["not", "a", "dict"])), 200),
    ],
    ids=["500", "timeout", "transport", "unexpected", "non-json", "no-agents-key", "non-dict-body"],
)
def test_degrades_to_ok_false_without_raising(db, monkeypatch, make_fake, expected_status):
    _patch(monkeypatch, make_fake())

    result = asyncio.run(cortex_bridge.ensure_department_agents(db, ORG, ROLES))

    assert result["ok"] is False
    assert result["error"]
    assert result["status"] == expected_status
