"""Per-company Cortex assistant resolution — the bridge must not send a hardcoded
agent id (it 404s for any company but WBIT). It resolves a cached per-org agent, else
the WBIT pin for the default company, else provisions one via ensure-agent and caches it;
and re-provisions + retries once on a bridge 404.
"""

import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from open_webui.internal.db import Base
from apps.agencyos.backend.models.db import AgencyOSOrganization
from apps.agencyos.backend.services import cortex_bridge

ORG = "org-internal-x"
CUID = "cmorgxxxxxxxxxxxxxxxxxxxx"


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


def _async(value):
    async def _fn(*a, **k):
        return value
    return _fn


def test_resolve_uses_cached_agent(db, monkeypatch):
    db.query(AgencyOSOrganization).filter_by(id=ORG).update({"cortex_agent_id": "cached-agent"})
    db.commit()
    calls = []
    async def _ensure(cid):
        calls.append(cid)
        return "new-agent"
    monkeypatch.setattr(cortex_bridge, "_ensure_company_agent", _ensure)
    agent = asyncio.run(cortex_bridge._resolve_agent_id(db, ORG, "some-company"))
    assert agent == "cached-agent"
    assert calls == []  # cached → no provisioning call


def test_resolve_default_company_uses_wbit_pin(db, monkeypatch):
    monkeypatch.setenv("WBIT_AGENT_ID", "wbit-agent-14d3")
    monkeypatch.setattr(cortex_bridge, "_default_company_id", lambda: "wbit-company")
    calls = []
    async def _ensure(cid):
        calls.append(cid)
        return "x"
    monkeypatch.setattr(cortex_bridge, "_ensure_company_agent", _ensure)
    agent = asyncio.run(cortex_bridge._resolve_agent_id(db, ORG, "wbit-company"))
    assert agent == "wbit-agent-14d3"
    assert calls == []  # pinned → no provisioning call


def test_resolve_provisions_and_caches(db, monkeypatch):
    monkeypatch.delenv("WBIT_AGENT_ID", raising=False)
    monkeypatch.setattr(cortex_bridge, "_default_company_id", lambda: "wbit-company")
    monkeypatch.setattr(cortex_bridge, "_provision_agent", _async(("provisioned-agent", False)))
    agent = asyncio.run(cortex_bridge._resolve_agent_id(db, ORG, "some-other-company"))
    assert agent == "provisioned-agent"
    row = db.query(AgencyOSOrganization).filter_by(id=ORG).first()
    assert row.cortex_agent_id == "provisioned-agent"  # cached for next time


def test_handle_chat_reprovisions_and_retries_on_404(db, monkeypatch):
    calls = {"send": 0, "ensure": 0}

    async def _send(**kw):
        calls["send"] += 1
        if calls["send"] == 1:
            return {"ok": False, "error": "bridge returned 404", "status_code": 404}
        return {"ok": True, "response": "the launch is Q4", "sessionId": "s1"}

    async def _ensure(cid):
        calls["ensure"] += 1
        return "reprovisioned-agent"

    monkeypatch.setattr(cortex_bridge, "_send", _send)
    monkeypatch.setattr(cortex_bridge, "_ensure_company_agent", _ensure)
    monkeypatch.setattr(cortex_bridge, "_resolve_company_for_chat", lambda db, org: "company-x")
    monkeypatch.setattr(cortex_bridge, "_resolve_agent_id", _async("stale-agent"))
    monkeypatch.setattr(cortex_bridge, "_load_session_id", lambda db, cid: None)
    monkeypatch.setattr(cortex_bridge, "_save_session_id", lambda *a, **k: None)

    result = asyncio.run(cortex_bridge.handle_chat("hi", ORG, chat_id="c1", db=db))
    assert result["status"] == "ok"
    assert result["content"] == "the launch is Q4"
    assert calls["send"] == 2   # retried after 404
    assert calls["ensure"] == 1  # re-provisioned once


def test_ensure_agent_url_is_core_route(monkeypatch):
    monkeypatch.setattr(
        cortex_bridge, "_bridge_url",
        lambda: "https://cortex.example/api/plugins/pid/api/chat",
    )
    monkeypatch.delenv("CORTEX_ENSURE_AGENT_URL", raising=False)
    assert cortex_bridge._ensure_agent_url() == "https://cortex.example/api/bridge/ensure-agent"


def test_ensure_agent_url_env_override(monkeypatch):
    monkeypatch.setenv("CORTEX_ENSURE_AGENT_URL", "https://x.example/ensure")
    assert cortex_bridge._ensure_agent_url() == "https://x.example/ensure"


# --- WorkPipe link for AgencyOS-created companies ------------------------------------
# Portal doesn't offer Cortex to customer orgs, so ensure-agent is how their company gets
# linked to its WorkPipe business. The org's own company is the one its CUID resolves to.

def _org_company():
    return cortex_bridge._resolve_company_id(CUID)


def _recording_provision(results):
    """A fake _provision_agent returning `results` in order and recording each call."""
    calls = []

    async def _fn(company_id, link_fields=None):
        calls.append((company_id, dict(link_fields or {})))
        return results[min(len(calls), len(results)) - 1]

    return _fn, calls


def _linked_flag(db):
    db.expire_all()
    row = db.query(AgencyOSOrganization).filter_by(id=ORG).first()
    return (row.settings or {}).get("cortexWorkpipeLinked")


def test_link_fields_only_for_the_orgs_own_company(db, monkeypatch):
    monkeypatch.delenv("PORTAL_COMPANY_OVERRIDES", raising=False)
    assert cortex_bridge._org_link_fields(db, ORG, _org_company()) == {
        "portalOrgId": CUID,
        "orgName": "X",
    }
    # A company the CUID doesn't resolve to (e.g. the default fallback) never claims a link.
    assert cortex_bridge._org_link_fields(db, ORG, "some-other-company") == {}
    assert cortex_bridge._org_link_fields(db, "unknown-org", _org_company()) == {}


def test_resolve_sends_link_fields_and_records_confirmation(db, monkeypatch):
    monkeypatch.delenv("PORTAL_COMPANY_OVERRIDES", raising=False)
    fake, calls = _recording_provision([("agent-1", True)])
    monkeypatch.setattr(cortex_bridge, "_provision_agent", fake)

    agent = asyncio.run(cortex_bridge._resolve_agent_id(db, ORG, _org_company()))

    assert agent == "agent-1"
    assert calls == [(_org_company(), {"portalOrgId": CUID, "orgName": "X"})]
    assert _linked_flag(db) is True


def test_cached_but_unlinked_org_calls_ensure_agent_once(db, monkeypatch):
    # The Antillies case: an assistant is cached, but the company was never linked.
    monkeypatch.delenv("PORTAL_COMPANY_OVERRIDES", raising=False)
    db.query(AgencyOSOrganization).filter_by(id=ORG).update({"cortex_agent_id": "cached-agent"})
    db.commit()
    fake, calls = _recording_provision([("cached-agent", True)])
    monkeypatch.setattr(cortex_bridge, "_provision_agent", fake)

    first = asyncio.run(cortex_bridge._resolve_agent_id(db, ORG, _org_company()))
    second = asyncio.run(cortex_bridge._resolve_agent_id(db, ORG, _org_company()))

    assert first == second == "cached-agent"
    assert len(calls) == 1  # confirmed after the first call → cached from then on


def test_unconfirmed_link_is_retried_not_assumed(db, monkeypatch):
    # A Cortex that predates the link (or failed to write it) returns no workpipeLinked:true.
    monkeypatch.delenv("PORTAL_COMPANY_OVERRIDES", raising=False)
    db.query(AgencyOSOrganization).filter_by(id=ORG).update({"cortex_agent_id": "cached-agent"})
    db.commit()
    fake, calls = _recording_provision([("cached-agent", False)])
    monkeypatch.setattr(cortex_bridge, "_provision_agent", fake)

    asyncio.run(cortex_bridge._resolve_agent_id(db, ORG, _org_company()))
    asyncio.run(cortex_bridge._resolve_agent_id(db, ORG, _org_company()))

    assert len(calls) == 2
    assert not _linked_flag(db)


def test_cortex_down_keeps_the_cached_agent(db, monkeypatch):
    monkeypatch.delenv("PORTAL_COMPANY_OVERRIDES", raising=False)
    db.query(AgencyOSOrganization).filter_by(id=ORG).update({"cortex_agent_id": "cached-agent"})
    db.commit()
    monkeypatch.setattr(cortex_bridge, "_provision_agent", _async((None, False)))

    assert asyncio.run(cortex_bridge._resolve_agent_id(db, ORG, _org_company())) == "cached-agent"


def test_default_company_never_sends_link_fields(db, monkeypatch):
    # The WBIT pin path is unchanged: no link fields, no extra call.
    monkeypatch.setenv("WBIT_AGENT_ID", "wbit-agent-14d3")
    monkeypatch.setattr(cortex_bridge, "_default_company_id", lambda: _org_company())
    fake, calls = _recording_provision([("x", True)])
    monkeypatch.setattr(cortex_bridge, "_provision_agent", fake)

    assert asyncio.run(cortex_bridge._resolve_agent_id(db, ORG, _org_company())) == "wbit-agent-14d3"
    assert calls == []


class _FakeResp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, resp, sink):
        self._resp = resp
        self._sink = sink

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, json=None, headers=None):
        self._sink.append({"url": url, "json": json})
        return self._resp


def test_provision_agent_posts_fields_and_reads_link_status(monkeypatch):
    sent = []
    monkeypatch.setattr(cortex_bridge, "_bridge_secret", lambda: "s3cret")
    monkeypatch.setattr(
        cortex_bridge.httpx,
        "AsyncClient",
        lambda **kw: _FakeClient(_FakeResp(200, {"agentId": "a1", "workpipeLinked": True}), sent),
    )
    result = asyncio.run(cortex_bridge._provision_agent("c1", {"portalOrgId": CUID, "orgName": "X"}))
    assert result == ("a1", True)
    assert sent[0]["json"] == {"companyId": "c1", "portalOrgId": CUID, "orgName": "X"}

    # An older Cortex answers without workpipeLinked → not linked.
    sent.clear()
    monkeypatch.setattr(
        cortex_bridge.httpx,
        "AsyncClient",
        lambda **kw: _FakeClient(_FakeResp(200, {"agentId": "a1"}), sent),
    )
    assert asyncio.run(cortex_bridge._provision_agent("c1")) == ("a1", False)
    assert sent[0]["json"] == {"companyId": "c1"}

