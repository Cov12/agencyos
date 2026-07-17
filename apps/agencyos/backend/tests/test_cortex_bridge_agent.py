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
    monkeypatch.setattr(cortex_bridge, "_ensure_company_agent", _async("provisioned-agent"))
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
