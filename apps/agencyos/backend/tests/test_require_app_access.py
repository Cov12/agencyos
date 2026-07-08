"""Unit tests for the require_app_access FastAPI dep factory."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from apps.agencyos.backend.middleware.deps import require_app_access
from apps.agencyos.backend.middleware.jwt_auth import PortalAuthContext


def _make_request(portal_auth):
    """Build a minimal Request-like object exposing .state, .headers, .cookies.

    headers/cookies are empty so _resolve_owui_user_id (#45) finds no OWUI token and
    returns None -> the portal_auth-None tests exercise the dev-flag / deny path.
    """
    return SimpleNamespace(
        state=SimpleNamespace(portal_auth=portal_auth),
        headers={},
        cookies={},
    )


class TestRequireAppAccess:
    def test_grants_access_when_app_in_app_access(self, monkeypatch):
        monkeypatch.delenv("AGENCYOS_DEV_ALLOW_HEADER_AUTH", raising=False)
        dep = require_app_access("CORTEX")
        ctx = PortalAuthContext(
            user_id="u-1",
            org_id="o-1",
            app_access=["CORTEX"],
        )

        # Should not raise.
        assert dep(_make_request(ctx)) is None

    def test_denies_when_app_missing(self, monkeypatch):
        monkeypatch.delenv("AGENCYOS_DEV_ALLOW_HEADER_AUTH", raising=False)
        dep = require_app_access("CORTEX")
        ctx = PortalAuthContext(
            user_id="u-1",
            org_id="o-1",
            app_access=["WORKPIPE"],
        )

        with pytest.raises(HTTPException) as exc:
            dep(_make_request(ctx))
        assert exc.value.status_code == 403
        assert "CORTEX" in exc.value.detail

    def test_denies_when_portal_auth_none_default(self, monkeypatch):
        """No portal_auth + no dev env var = 403."""
        monkeypatch.delenv("AGENCYOS_DEV_ALLOW_HEADER_AUTH", raising=False)
        dep = require_app_access("CORTEX")

        with pytest.raises(HTTPException) as exc:
            dep(_make_request(None))
        assert exc.value.status_code == 403

    def test_allows_when_portal_auth_none_with_dev_env_var(self, monkeypatch):
        """No portal_auth + AGENCYOS_DEV_ALLOW_HEADER_AUTH=1 = allow through."""
        monkeypatch.setenv("AGENCYOS_DEV_ALLOW_HEADER_AUTH", "1")
        dep = require_app_access("CORTEX")

        # Should not raise.
        assert dep(_make_request(None)) is None

    def test_dev_env_var_must_be_exactly_1(self, monkeypatch):
        """Truthy strings other than literal "1" do NOT trip the escape hatch."""
        monkeypatch.setenv("AGENCYOS_DEV_ALLOW_HEADER_AUTH", "true")
        dep = require_app_access("CORTEX")

        with pytest.raises(HTTPException) as exc:
            dep(_make_request(None))
        assert exc.value.status_code == 403

    def test_dev_env_var_does_not_bypass_explicit_missing_app(self, monkeypatch):
        """If portal_auth is present but lacks the app, env var does NOT bypass."""
        monkeypatch.setenv("AGENCYOS_DEV_ALLOW_HEADER_AUTH", "1")
        dep = require_app_access("CORTEX")
        ctx = PortalAuthContext(
            user_id="u-1",
            org_id="o-1",
            app_access=[],
        )

        with pytest.raises(HTTPException) as exc:
            dep(_make_request(ctx))
        assert exc.value.status_code == 403
