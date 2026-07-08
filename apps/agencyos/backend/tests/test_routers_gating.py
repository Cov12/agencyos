"""HTTP-layer entitlement gating tests.

Complements `test_require_app_access.py`: that file calls `_dep(request)`
on the dependency function directly. This file mounts the actual routers
in a FastAPI app, drives them via TestClient, and asserts the gate behaves
correctly through the full dependency chain + HTTP layer.

Coverage:
  - Default deny: no Portal JWT, no env var → 403 on both CORTEX-gated
    routers (cortex-approvals, employee-tabs).
  - Dev escape hatch: AGENCYOS_DEV_ALLOW_HEADER_AUTH=1 opens the gate and
    emits the documented WARNING log line. Env var must be exactly "1".
  - Portal JWT path: HS256 tokens minted with the test secret are decoded
    by JWTAuthMiddleware; the CORTEX entitlement is gated purely on the
    JWT's app_access claim. Covers happy path + expired + bad-signature +
    malformed + empty-claim cases.
  - Security invariant: dev escape hatch must NOT bypass an explicit JWT
    denial (JWT present but missing CORTEX → 403 even with env var set).
  - Regression: ungated routers (proposals/) are unaffected — confirms
    the gate is router-scoped, not a JWT-middleware side effect.
"""
import logging
import time

import jwt as pyjwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.agencyos.backend.middleware.tenant import get_tenant_session
from apps.agencyos.backend.models.db import Base


TEST_JWT_SECRET = "test-secret-for-pr6-router-smoke-tests"


@pytest.fixture
def db_session():
    # The gates now resolve get_tenant_session (require_app_access / require_org_access
    # read AgencyOSMember + the org's app_access on the OWUI path -- #45). Provide an
    # in-memory DB so dependency resolution doesn't 500 before the gate logic runs.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    # Seed the org the Portal-JWT tests reference (org_id="test-org"); require_org_access
    # (#41, legacy path) needs a row whose portal_org_id matches the JWT's org_id claim.
    from apps.agencyos.backend.models.db import AgencyOSOrganization
    session.add(AgencyOSOrganization(
        id="test-org", name="Test Org", slug="test-org", plan="starter",
        portal_org_id="test-org",
    ))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def app(db_session):
    """Two CORTEX-gated routers, no JWT middleware. Tier 2/3 use this."""
    from apps.agencyos.backend.routers import cortex_approvals, employee_tabs

    a = FastAPI()
    a.include_router(cortex_approvals.router)
    a.include_router(employee_tabs.router)
    a.dependency_overrides[get_tenant_session] = lambda: db_session
    return a


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def app_with_jwt(monkeypatch, db_session):
    """Two CORTEX-gated routers + the un-gated proposals router + JWTAuthMiddleware.

    Tier 4 uses this for the JWT path. Tier 5 reuses it to prove proposals/
    is NOT 403'd when a token lacks CORTEX — i.e. the gate is router-scoped,
    not a global JWT-side-effect.

    Patches module-level JWT_SECRET (read at import time) to a known value.
    """
    from apps.agencyos.backend.middleware import jwt_auth
    from apps.agencyos.backend.middleware.jwt_auth import JWTAuthMiddleware
    from apps.agencyos.backend.routers import cortex_approvals, employee_tabs, proposals

    monkeypatch.setattr(jwt_auth, "JWT_SECRET", TEST_JWT_SECRET)
    a = FastAPI()
    a.add_middleware(JWTAuthMiddleware)
    a.include_router(cortex_approvals.router)
    a.include_router(employee_tabs.router)
    a.include_router(proposals.router)
    a.dependency_overrides[get_tenant_session] = lambda: db_session
    return a


@pytest.fixture
def jwt_client(app_with_jwt):
    return TestClient(app_with_jwt, raise_server_exceptions=False)


def _mint_token(app_access, *, secret=TEST_JWT_SECRET, expired=False, extra=None):
    now = int(time.time())
    payload = {
        "sub": "test-user",
        "org_id": "test-org",
        "role": "member",
        "app_access": app_access,
        "iat": now - (3600 if expired else 0),
        "exp": now - (1800 if expired else -600),
    }
    if extra:
        payload.update(extra)
    return pyjwt.encode(payload, secret, algorithm="HS256")


# ─────────────────────────────────────────────────────────────────────────
# Tier 2 — default-deny path
# ─────────────────────────────────────────────────────────────────────────
class TestDefaultDeny:
    def test_cortex_approvals_returns_403_when_no_portal_auth_and_no_env_var(
        self, client, monkeypatch
    ):
        monkeypatch.delenv("AGENCYOS_DEV_ALLOW_HEADER_AUTH", raising=False)
        r = client.get(
            "/api/agencyos/cortex-approvals/",
            headers={"X-Org-Id": "any-org"},
            params={"org_id": "any-org"},
        )
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"
        assert "App access denied" in r.text
        assert "CORTEX" in r.text

    def test_employee_tabs_returns_403_when_no_portal_auth_and_no_env_var(
        self, client, monkeypatch
    ):
        monkeypatch.delenv("AGENCYOS_DEV_ALLOW_HEADER_AUTH", raising=False)
        r = client.get(
            "/api/agencyos/employee-tabs/",
            headers={"X-Org-Id": "any-org"},
            params={"org_id": "any-org"},
        )
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"
        assert "App access denied" in r.text
        assert "CORTEX" in r.text


# ─────────────────────────────────────────────────────────────────────────
# Tier 3 — dev fallback env var
# ─────────────────────────────────────────────────────────────────────────
class TestDevFallback:
    def test_cortex_approvals_does_NOT_return_403_when_env_var_set(
        self, client, monkeypatch
    ):
        monkeypatch.setenv("AGENCYOS_DEV_ALLOW_HEADER_AUTH", "1")
        r = client.get(
            "/api/agencyos/cortex-approvals/",
            headers={"X-Org-Id": "real-org"},
            params={"org_id": "real-org"},
        )
        # With dev fallback ON, require_app_access lets the request through.
        # The next dependency (get_tenant_session) needs a real DB which we
        # don't have in tests — that yields a non-403 error (DB or service-
        # level), proving the gate has been opened.
        assert r.status_code != 403, (
            f"expected non-403 (gate opened), got 403: {r.text}"
        )

    def test_employee_tabs_does_NOT_return_403_when_env_var_set(
        self, client, monkeypatch
    ):
        monkeypatch.setenv("AGENCYOS_DEV_ALLOW_HEADER_AUTH", "1")
        r = client.get(
            "/api/agencyos/employee-tabs/",
            headers={"X-Org-Id": "real-org"},
            params={"org_id": "real-org"},
        )
        assert r.status_code != 403, (
            f"expected non-403 (gate opened), got 403: {r.text}"
        )

    def test_dev_fallback_emits_warning_log(self, client, monkeypatch, caplog):
        monkeypatch.setenv("AGENCYOS_DEV_ALLOW_HEADER_AUTH", "1")
        caplog.set_level(logging.WARNING, logger="apps.agencyos.backend.middleware.deps")
        # Hit either router; the dep is identical
        client.get(
            "/api/agencyos/cortex-approvals/",
            headers={"X-Org-Id": "real-org"},
            params={"org_id": "real-org"},
        )
        warning_lines = [
            r.getMessage()
            for r in caplog.records
            if r.levelname == "WARNING"
        ]
        # Spec: "WARNING ... require_app_access[CORTEX]: portal_auth missing;
        # allowing via AGENCYOS_DEV_ALLOW_HEADER_AUTH dev escape hatch"
        match = [m for m in warning_lines if "require_app_access" in m and "CORTEX" in m and "AGENCYOS_DEV_ALLOW_HEADER_AUTH" in m]
        assert match, (
            f"expected WARNING line containing 'require_app_access', 'CORTEX', "
            f"and 'AGENCYOS_DEV_ALLOW_HEADER_AUTH'; got: {warning_lines}"
        )
        print("captured WARNING line:", match[0])

    def test_dev_env_var_other_values_do_NOT_open_the_gate(
        self, client, monkeypatch
    ):
        for val in ["true", "TRUE", "0", "yes", ""]:
            monkeypatch.setenv("AGENCYOS_DEV_ALLOW_HEADER_AUTH", val)
            r = client.get(
                "/api/agencyos/cortex-approvals/",
                headers={"X-Org-Id": "any-org"},
                params={"org_id": "any-org"},
            )
            assert r.status_code == 403, (
                f"env var '{val}' should NOT open the gate; got {r.status_code}"
            )


# ─────────────────────────────────────────────────────────────────────────
# Tier 4 — Portal JWT path (MOST VALUABLE TEST)
# ─────────────────────────────────────────────────────────────────────────
class TestPortalJwt:
    def test_4_3_token_without_CORTEX_in_app_access_returns_403(
        self, jwt_client, monkeypatch
    ):
        monkeypatch.delenv("AGENCYOS_DEV_ALLOW_HEADER_AUTH", raising=False)
        token = _mint_token(["WORKPIPE", "AGENCYOS", "DRIVE"])
        r = jwt_client.get(
            "/api/agencyos/cortex-approvals/",
            headers={"Authorization": f"Bearer {token}"},
            params={"org_id": "test-org"},
        )
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"
        assert "CORTEX" in r.text

    def test_4_5a_token_with_CORTEX_lets_cortex_approvals_pass_gate(
        self, jwt_client, monkeypatch
    ):
        monkeypatch.delenv("AGENCYOS_DEV_ALLOW_HEADER_AUTH", raising=False)
        token = _mint_token(["AGENCYOS", "CORTEX", "DRIVE", "WORKPIPE"])
        r = jwt_client.get(
            "/api/agencyos/cortex-approvals/",
            headers={"Authorization": f"Bearer {token}"},
            params={"org_id": "test-org"},
        )
        assert r.status_code != 403, f"expected non-403, got {r.status_code}: {r.text}"

    def test_4_5b_token_with_CORTEX_lets_employee_tabs_pass_gate(
        self, jwt_client, monkeypatch
    ):
        monkeypatch.delenv("AGENCYOS_DEV_ALLOW_HEADER_AUTH", raising=False)
        token = _mint_token(["AGENCYOS", "CORTEX", "DRIVE", "WORKPIPE"])
        r = jwt_client.get(
            "/api/agencyos/employee-tabs/",
            headers={"Authorization": f"Bearer {token}"},
            params={"org_id": "test-org"},
        )
        assert r.status_code != 403, f"expected non-403, got {r.status_code}: {r.text}"

    def test_expired_token_returns_403(self, jwt_client, monkeypatch):
        """JWT expired → middleware drops portal_auth → require_app_access denies."""
        monkeypatch.delenv("AGENCYOS_DEV_ALLOW_HEADER_AUTH", raising=False)
        token = _mint_token(["CORTEX"], expired=True)
        r = jwt_client.get(
            "/api/agencyos/cortex-approvals/",
            headers={"Authorization": f"Bearer {token}"},
            params={"org_id": "test-org"},
        )
        assert r.status_code == 403, (
            f"expired token must not bypass the gate; got {r.status_code}"
        )

    def test_bad_signature_returns_403(self, jwt_client, monkeypatch):
        """Signed with wrong secret → middleware rejects → 403."""
        monkeypatch.delenv("AGENCYOS_DEV_ALLOW_HEADER_AUTH", raising=False)
        token = _mint_token(["CORTEX"], secret="not-the-real-secret")
        r = jwt_client.get(
            "/api/agencyos/cortex-approvals/",
            headers={"Authorization": f"Bearer {token}"},
            params={"org_id": "test-org"},
        )
        assert r.status_code == 403

    def test_malformed_token_returns_403(self, jwt_client, monkeypatch):
        monkeypatch.delenv("AGENCYOS_DEV_ALLOW_HEADER_AUTH", raising=False)
        r = jwt_client.get(
            "/api/agencyos/cortex-approvals/",
            headers={"Authorization": "Bearer not-even-a-jwt"},
            params={"org_id": "test-org"},
        )
        assert r.status_code == 403

    def test_token_with_empty_app_access_returns_403(
        self, jwt_client, monkeypatch
    ):
        monkeypatch.delenv("AGENCYOS_DEV_ALLOW_HEADER_AUTH", raising=False)
        token = _mint_token([])
        r = jwt_client.get(
            "/api/agencyos/cortex-approvals/",
            headers={"Authorization": f"Bearer {token}"},
            params={"org_id": "test-org"},
        )
        assert r.status_code == 403

    def test_jwt_path_does_not_consult_env_var(self, jwt_client, monkeypatch):
        """Dev escape hatch must NOT bypass an explicit denial when JWT is present
        but lacks CORTEX. This is the security-critical invariant.
        """
        monkeypatch.setenv("AGENCYOS_DEV_ALLOW_HEADER_AUTH", "1")
        token = _mint_token(["WORKPIPE", "AGENCYOS", "DRIVE"])  # no CORTEX
        r = jwt_client.get(
            "/api/agencyos/cortex-approvals/",
            headers={"Authorization": f"Bearer {token}"},
            params={"org_id": "test-org"},
        )
        assert r.status_code == 403, (
            "Dev escape hatch should NOT bypass JWT-present-but-app-missing case; "
            f"got {r.status_code}"
        )


# ─────────────────────────────────────────────────────────────────────────
# Tier 5 — Regression: non-Cortex routes are NOT gated
# ─────────────────────────────────────────────────────────────────────────
class TestNonCortexRouteRegression:
    def test_proposals_not_403_with_token_lacking_CORTEX(
        self, jwt_client, monkeypatch
    ):
        """Token has NO CORTEX in app_access; proposals/ is untouched by PR #6
        and must still respond non-403. Confirms the gate is router-scoped.
        """
        monkeypatch.delenv("AGENCYOS_DEV_ALLOW_HEADER_AUTH", raising=False)
        token = _mint_token(["WORKPIPE", "AGENCYOS", "DRIVE"])  # no CORTEX
        r = jwt_client.get(
            "/api/agencyos/proposals/",
            headers={"Authorization": f"Bearer {token}"},
            params={"org_id": "test-org"},
        )
        assert r.status_code != 403, (
            f"proposals/ should not be CORTEX-gated; got 403: {r.text[:200]}"
        )
        # Also ensure the body isn't the entitlement-denied phrase, in case some
        # other layer 403's for a different reason.
        assert "App access denied: CORTEX" not in r.text

    def test_proposals_not_403_with_no_auth_at_all(
        self, jwt_client, monkeypatch
    ):
        """Even without any Authorization header, proposals/ is not CORTEX-gated."""
        monkeypatch.delenv("AGENCYOS_DEV_ALLOW_HEADER_AUTH", raising=False)
        r = jwt_client.get(
            "/api/agencyos/proposals/",
            headers={"X-Org-Id": "test-org"},
            params={"org_id": "test-org"},
        )
        # May 4xx/5xx for other reasons (DB, validation) — must not be CORTEX-403
        assert "App access denied: CORTEX" not in r.text, (
            f"proposals/ should not be CORTEX-gated; got {r.status_code}: {r.text[:200]}"
        )
