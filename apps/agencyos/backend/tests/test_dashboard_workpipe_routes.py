import time

import jwt as pyjwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from open_webui.internal.db import Base
from apps.agencyos.backend.middleware import jwt_auth
from apps.agencyos.backend.middleware.jwt_auth import JWTAuthMiddleware
from apps.agencyos.backend.middleware.tenant import get_tenant_session
from apps.agencyos.backend.models.db import AgencyOSOrganization
from apps.agencyos.backend.routers import dashboard_workpipe
from apps.agencyos.backend.services import workpipe_dashboard


TEST_JWT_SECRET = "test-workpipe-dashboard-secret"
TEST_ORG_ID = "org-dashboard-1"
TEST_WORKPIPE_BUSINESS_ID = "portal-biz-cuid-123"
TEST_WORKPIPE_SUBACCOUNT_ID = "subaccount-bound-456"


class _FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, headers=None, params=None):
        self.calls.append({"url": url, "headers": headers or {}, "params": params or {}})
        return self.response


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        session.add(
            AgencyOSOrganization(
                id=TEST_ORG_ID,
                name="Acme",
                slug="acme",
                plan="starter",
                portal_org_id=TEST_WORKPIPE_BUSINESS_ID,
                workpipe_account_id=TEST_WORKPIPE_SUBACCOUNT_ID,
            )
        )
        session.commit()
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def app(db_session, monkeypatch):
    monkeypatch.setattr(jwt_auth, "JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setattr(workpipe_dashboard, "JWT_SECRET", TEST_JWT_SECRET)

    app = FastAPI()
    app.add_middleware(JWTAuthMiddleware)
    app.dependency_overrides[get_tenant_session] = lambda: db_session
    app.include_router(dashboard_workpipe.router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


def _mint_portal_token(app_access):
    now = int(time.time())
    payload = {
        "sub": "user-77",
        "user_id": "user-77",
        "org_id": "portal-org-cuid",
        "role": "owner",
        "email": "cov@example.com",
        "app_access": app_access,
        "iat": now,
        "exp": now + 600,
    }
    return pyjwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def _patch_httpx(monkeypatch, fake_client):
    monkeypatch.setattr(workpipe_dashboard.httpx, "AsyncClient", lambda **kwargs: fake_client)


def test_stats_route_mints_workpipe_jwt_and_threads_subaccount(client, monkeypatch):
    fake = _FakeClient(
        _FakeResponse(
            200,
            {
                "contacts": {"total": 14, "recentCount": 3},
                "tickets": {"total": 9, "totalValue": 12500, "byLane": {"lane-1": 4}},
                "pipelines": {"count": 2},
            },
        )
    )
    _patch_httpx(monkeypatch, fake)

    token = _mint_portal_token(["AGENCYOS", "WORKPIPE"])
    response = client.get(
        "/api/agencyos/dashboard/workpipe/stats",
        params={"org_id": TEST_ORG_ID, "subAccountId": "sub-42"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "data": {
            "contacts": {"total": 14, "recentCount": 3},
            "tickets": {"total": 9, "totalValue": 12500.0, "byLane": {"lane-1": 4}},
            "pipelines": {"count": 2},
        }
    }

    call = fake.calls[0]
    assert call["url"] == "https://workpipe-stg.onrender.com/api/internal/stats"
    assert call["params"] == {"subAccountId": "sub-42"}

    bearer = call["headers"]["Authorization"].split(" ", 1)[1]
    workpipe_token = pyjwt.decode(bearer, TEST_JWT_SECRET, algorithms=["HS256"])
    assert workpipe_token["org_id"] == TEST_WORKPIPE_BUSINESS_ID
    assert workpipe_token["org_id"] != TEST_WORKPIPE_SUBACCOUNT_ID
    assert workpipe_token["user_id"] == "user-77"
    assert workpipe_token["sub"] == "user-77"


def test_contacts_route_omits_subaccount_for_business_scope(client, monkeypatch):
    fake = _FakeClient(
        _FakeResponse(
            200,
            {
                "contacts": [
                    {"id": "c1", "name": "Alice", "email": "alice@example.com"},
                    {"id": "c2", "name": "Bob", "email": "bob@example.com"},
                ],
                "total": 8,
            },
        )
    )
    _patch_httpx(monkeypatch, fake)

    token = _mint_portal_token(["AGENCYOS", "WORKPIPE"])
    response = client.get(
        "/api/agencyos/dashboard/workpipe/contacts",
        params={"org_id": TEST_ORG_ID, "limit": 6},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["total"] == 8
    assert fake.calls[0]["params"] == {"limit": 6, "offset": 0}


def test_pipelines_route_requires_workpipe_app_access(client, monkeypatch):
    fake = _FakeClient(_FakeResponse(200, {"pipelines": []}))
    _patch_httpx(monkeypatch, fake)

    token = _mint_portal_token(["AGENCYOS"])
    response = client.get(
        "/api/agencyos/dashboard/workpipe/pipelines",
        params={"org_id": TEST_ORG_ID},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403, response.text
    assert not fake.calls


def test_stats_route_returns_409_when_org_is_not_linked_to_workpipe(client, db_session, monkeypatch):
    db_session.query(AgencyOSOrganization).filter_by(id=TEST_ORG_ID).update({"portal_org_id": None})
    db_session.commit()

    fake = _FakeClient(_FakeResponse(200, {"contacts": {}, "tickets": {}, "pipelines": {}}))
    _patch_httpx(monkeypatch, fake)

    token = _mint_portal_token(["AGENCYOS", "WORKPIPE"])
    response = client.get(
        "/api/agencyos/dashboard/workpipe/stats",
        params={"org_id": TEST_ORG_ID},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409, response.text
    assert "not linked to WorkPipe" in response.text
    assert not fake.calls
