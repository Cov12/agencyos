"""Phase 1.4 GATE 1 — the backend spine for first-sub-account onboarding.

Three defects this pins, all on the Portal -> AgencyOS return hop:

  B1  An empty sub-account mirror was AMBIGUOUS. services/subaccount_sync.py collapsed
      `_fetch_subaccounts() is None` (Portal unreachable) and `== []` (Portal says: zero
      sub-accounts) into one `if not items: return 0`. Both render as an empty list, so an
      onboarding nudge built on that list would fire during a Portal outage and tell an
      existing customer they have no sub-accounts. Fixed by stamping an org-level
      last-successful-sync marker in AgencyOSOrganization.settings (a JSON column — no
      migration) on the non-None branch only, and surfacing it as syncedAt/syncOk.

  B2  The 900s per-org back-off (maybe_sync) is wrong for exactly one moment: the user
      returning from Portal having JUST created a sub-account. Throttled, they land on a
      mirror that does not contain it. Fixed by force_sync(), reached when the callback
      carries ?subAccountCreated=1.

  B3  The callback hardcoded its redirect to /agencyos/, so the CTA could not send the
      user back to the view they left. Fixed by ?next=<relative path>, behind an
      open-redirect guard — this endpoint is a public, redirect-by-design entry point, so
      an unvalidated destination here is a phishing hop off a genuine Portal login.

Style follows the existing suites: in-memory SQLite off the conftest-stubbed declarative
Base, Portal HTTP mocked at _fetch_subaccounts, and the REAL callback coroutine driven
directly (see test_callback_provisioning.py) rather than a re-implementation of it.
"""

import asyncio
import sys
import types

import jwt as pyjwt
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from open_webui.internal.db import Base
from apps.agencyos.backend.models.db import AgencyOSOrganization, AgencyOSSubAccount, now_ms
from apps.agencyos.backend.services.organizations import OrganizationsService
from apps.agencyos.backend.services import subaccount_sync


_PORTAL_CUID = "cmonboardorgaaaa0000bbbb"
_SA1 = "clsubacctonboard0001aaaa"
_SA2 = "clsubacctonboard0002bbbb"
_TOKEN = "portal.jwt.token"
_UID = "owui-user-onboarding"
_ORG_ID = "org-onboarding-1"


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(autouse=True)
def _reset_throttle():
    # The back-off map is module state; clear it around every test.
    subaccount_sync._last_attempt_ms.clear()
    yield
    subaccount_sync._last_attempt_ms.clear()


def _org(db):
    return OrganizationsService.create_org(
        db, name="Acme", slug="acme", portal_org_id=_PORTAL_CUID
    )


def _rows(db, org_id):
    return db.query(AgencyOSSubAccount).filter(AgencyOSSubAccount.org_id == org_id).all()


# ============================================================ B3: open-redirect guard

def _guard(value):
    from apps.agencyos.backend.routers.auth_callback import _safe_return_path

    return _safe_return_path(value)


def _default():
    from apps.agencyos.backend.routers.auth_callback import DEFAULT_RETURN_PATH

    return DEFAULT_RETURN_PATH


def test_safe_return_path_allows_same_origin_relative_paths(_owui_callback_stubs):
    assert _guard("/agencyos/x") == "/agencyos/x"
    assert _guard("/agencyos/") == "/agencyos/"
    # Query + fragment survive — the CTA carries ?newSubAccountId=... back to the frontend.
    assert _guard("/agencyos/?newSubAccountId=clsub123#top") == "/agencyos/?newSubAccountId=clsub123#top"
    # Surrounding whitespace is trimmed, not rejected.
    assert _guard("  /agencyos/x  ") == "/agencyos/x"


@pytest.mark.parametrize(
    "hostile",
    [
        "//evil.com",                 # protocol-relative == absolute, foreign origin
        "///evil.com",
        "https://evil",               # absolute URL
        "http://evil.com/agencyos/",
        "/\\evil.com",                # browsers fold backslash to '/', giving host evil.com
        "\\\\evil.com",
        "/agencyos/\\..\\evil",       # backslash anywhere is refused
        "javascript:alert(1)",        # scheme, not a path
        "JavaScript:alert(1)",
        "data:text/html,<script>1</script>",
        "agencyos/x",                 # relative, no leading slash
        "",                           # empty
        "   ",                        # whitespace-only
        None,                         # param absent
        "/agencyos/\r\nSet-Cookie: a=b",   # header splitting
        "/agencyos/\nLocation: //evil",
        "/agencyos/\tx",              # control chars are refused outright
        "/" + "a" * 4096,             # absurd length
    ],
)
def test_safe_return_path_rejects_hostile_values(hostile, _owui_callback_stubs):
    assert _guard(hostile) == _default() == "/agencyos/"


def test_safe_return_path_rejects_non_string_input(_owui_callback_stubs):
    """The endpoint's default is a fastapi Query object when the coroutine is called
    directly (as the callback suites do), so the guard must not assume `str | None`."""
    from fastapi import Query

    assert _guard(Query(default=None, alias="next")) == "/agencyos/"
    assert _guard(12345) == "/agencyos/"


def test_percent_encoded_slashes_stay_in_the_path(_owui_callback_stubs):
    """The guard must NOT url-decode first: '%2f%2f' is a literal path segment per
    RFC 3986 and no browser re-reads it as a host, but decoding would turn it into the
    '//evil.com' form we reject — i.e. decoding creates the bypass it looks like it
    prevents. Kept as an explicit decision, not an accident."""
    assert _guard("/%2f%2fevil.com") == "/%2f%2fevil.com"


# ==================================================== B1: zero vs sync-failed, at source

def test_fetch_failure_records_no_sync_marker(db, monkeypatch):
    org = _org(db)
    monkeypatch.setattr(subaccount_sync, "_fetch_subaccounts", lambda token: None)

    assert subaccount_sync.sync_org_subaccounts(db, org.id, _PORTAL_CUID, _TOKEN) == 0
    assert _rows(db, org.id) == []

    synced_at, sync_ok = subaccount_sync.get_sync_status(db, org.id)
    assert synced_at is None
    assert sync_ok is False  # unknown, NOT "zero sub-accounts"
    db.refresh(org)
    assert subaccount_sync.SUBACCOUNTS_SYNCED_AT_KEY not in (org.settings or {})


def test_valid_empty_list_stamps_sync_marker(db, monkeypatch):
    """The genuine zero-sub-account org — the ONLY state the onboarding nudge may fire on."""
    org = _org(db)
    monkeypatch.setattr(subaccount_sync, "_fetch_subaccounts", lambda token: [])

    assert subaccount_sync.sync_org_subaccounts(db, org.id, _PORTAL_CUID, _TOKEN) == 0
    assert _rows(db, org.id) == []

    synced_at, sync_ok = subaccount_sync.get_sync_status(db, org.id)
    assert sync_ok is True
    assert isinstance(synced_at, str) and synced_at.endswith("Z")


def test_successful_pull_stamps_sync_marker(db, monkeypatch):
    org = _org(db)
    monkeypatch.setattr(
        subaccount_sync,
        "_fetch_subaccounts",
        lambda token: [{"id": _SA1, "name": "Northwind", "status": "active"}],
    )

    assert subaccount_sync.sync_org_subaccounts(db, org.id, _PORTAL_CUID, _TOKEN) == 1
    synced_at, sync_ok = subaccount_sync.get_sync_status(db, org.id)
    assert sync_ok is True and synced_at


def test_sync_marker_preserves_other_settings_keys(db, monkeypatch):
    """settings is a shared JSON blob; stamping must merge, never clobber."""
    org = _org(db)
    org.settings = {"theme": "dark"}
    db.commit()

    monkeypatch.setattr(subaccount_sync, "_fetch_subaccounts", lambda token: [])
    subaccount_sync.sync_org_subaccounts(db, org.id, _PORTAL_CUID, _TOKEN)

    db.refresh(org)
    assert org.settings["theme"] == "dark"
    assert org.settings[subaccount_sync.SUBACCOUNTS_SYNCED_AT_KEY]


def test_later_failure_keeps_last_known_good_marker(db, monkeypatch):
    """syncOk is last-known-good, not liveness: once a pull has succeeded, a subsequent
    outage must not flip the org back to 'unknown' and re-arm the nudge."""
    org = _org(db)
    monkeypatch.setattr(
        subaccount_sync,
        "_fetch_subaccounts",
        lambda token: [{"id": _SA1, "name": "Northwind", "status": "active"}],
    )
    subaccount_sync.sync_org_subaccounts(db, org.id, _PORTAL_CUID, _TOKEN)
    first_stamp, ok = subaccount_sync.get_sync_status(db, org.id)
    assert ok is True

    monkeypatch.setattr(subaccount_sync, "_fetch_subaccounts", lambda token: None)
    subaccount_sync.sync_org_subaccounts(db, org.id, _PORTAL_CUID, _TOKEN)

    assert subaccount_sync.get_sync_status(db, org.id) == (first_stamp, True)


def test_get_sync_status_degrades_on_missing_inputs(db):
    assert subaccount_sync.get_sync_status(None, _ORG_ID) == (None, False)
    assert subaccount_sync.get_sync_status(db, None) == (None, False)
    assert subaccount_sync.get_sync_status(db, "no-such-org") == (None, False)


# ================================================ B2: force_sync bypasses the back-off

def test_force_sync_bypasses_the_throttle(db, monkeypatch):
    org = _org(db)
    calls = {"n": 0}

    def _fetch(token):
        calls["n"] += 1
        return [{"id": _SA1, "name": "Northwind", "status": "active"}]

    monkeypatch.setattr(subaccount_sync, "_fetch_subaccounts", _fetch)

    subaccount_sync.maybe_sync(db, org.id, _PORTAL_CUID, _TOKEN)
    subaccount_sync.maybe_sync(db, org.id, _PORTAL_CUID, _TOKEN)
    assert calls["n"] == 1, "second maybe_sync must be throttled (baseline)"

    # Same org, same TTL window — force_sync pulls anyway.
    assert subaccount_sync.force_sync(db, org.id, _PORTAL_CUID, _TOKEN) == 1
    assert calls["n"] == 2


def test_force_sync_restarts_the_back_off_window(db, monkeypatch):
    """A forced pull still records the attempt, so it doesn't leave a stale timestamp
    that would let the very next request pull again."""
    org = _org(db)
    calls = {"n": 0}

    def _fetch(token):
        calls["n"] += 1
        return []

    monkeypatch.setattr(subaccount_sync, "_fetch_subaccounts", _fetch)

    subaccount_sync.force_sync(db, org.id, _PORTAL_CUID, _TOKEN)
    subaccount_sync.maybe_sync(db, org.id, _PORTAL_CUID, _TOKEN)
    assert calls["n"] == 1


def test_force_sync_degrades_on_missing_inputs(db):
    org = _org(db)
    assert subaccount_sync.force_sync(None, org.id, _PORTAL_CUID, _TOKEN) == 0
    assert subaccount_sync.force_sync(db, None, _PORTAL_CUID, _TOKEN) == 0
    assert subaccount_sync.force_sync(db, org.id, _PORTAL_CUID, None) == 0


# ======================================================= the REAL callback return hop

@pytest.fixture
def _owui_callback_stubs():
    """auth_callback.py imports open_webui submodules the unit-test conftest doesn't stub.
    Install ONLY the ones that aren't already importable, so a full-deps env still
    exercises the real modules — same approach as test_callback_provisioning.py, repeated
    here because apps/agencyos/backend/tests is not an importable package (no __init__)."""

    def _importable(name):
        try:
            __import__(name)
            return True
        except Exception:
            return False

    sys.modules.setdefault("open_webui", types.ModuleType("open_webui"))
    for pkg in ("open_webui.models", "open_webui.utils"):
        sys.modules.setdefault(pkg, types.ModuleType(pkg))

    if not _importable("open_webui.models.users"):
        m = types.ModuleType("open_webui.models.users")

        class Users:
            @staticmethod
            def get_user_by_email(email, db=None):
                return None

            @staticmethod
            def has_users(db=None):
                return True

            @staticmethod
            def update_user_by_id(uid, data, db=None):
                return None

        m.Users = Users
        sys.modules["open_webui.models.users"] = m

    if not _importable("open_webui.models.auths"):
        m = types.ModuleType("open_webui.models.auths")

        class Auths:
            @staticmethod
            def insert_new_auth(**kwargs):
                return None

        m.Auths = Auths
        sys.modules["open_webui.models.auths"] = m

    if not _importable("open_webui.utils.auth"):
        m = types.ModuleType("open_webui.utils.auth")
        m.get_password_hash = lambda pw: "hash"
        m.create_token = lambda **kwargs: "tok"
        sys.modules["open_webui.utils.auth"] = m

    if not _importable("open_webui.utils.groups"):
        m = types.ModuleType("open_webui.utils.groups")
        m.apply_default_group_assignment = lambda *a, **k: None
        sys.modules["open_webui.utils.groups"] = m

    if not _importable("open_webui.utils.misc"):
        m = types.ModuleType("open_webui.utils.misc")
        m.parse_duration = lambda v: None
        sys.modules["open_webui.utils.misc"] = m

    if not _importable("open_webui.env"):
        m = types.ModuleType("open_webui.env")
        m.WEBUI_AUTH_COOKIE_SAME_SITE = "lax"
        m.WEBUI_AUTH_COOKIE_SECURE = False
        sys.modules["open_webui.env"] = m

    return True


def _jwt_payload(**over):
    p = {
        "sub": "user_clerk_x",
        "email": "owner@acme.test",
        "name": "Acme Owner",
        "org_id": _PORTAL_CUID,
        "org_slug": "acme",
        "org_name": "Acme Inc",
        "role": "OWNER",
        "app_access": ["AGENCYOS", "DRIVE", "WORKPIPE"],
    }
    p.update(over)
    return p


def _fake_request():
    return types.SimpleNamespace(
        app=types.SimpleNamespace(
            state=types.SimpleNamespace(
                config=types.SimpleNamespace(DEFAULT_GROUP_ID=None, JWT_EXPIRES_IN="1h")
            )
        ),
        url="http://test/agencyos/auth/callback",
    )


@pytest.fixture
def callback(monkeypatch, db, _owui_callback_stubs):
    """The real portal_auth_callback, wired to the in-memory session, with user
    resolution / token minting stubbed (neither is the subject here). Returns a caller
    that takes the callback's query params."""
    from apps.agencyos.backend.routers import auth_callback

    monkeypatch.setenv("JWT_SECRET", "test-portal-secret")
    fake_user = types.SimpleNamespace(id=_UID, name="Acme Owner")
    monkeypatch.setattr(
        auth_callback.Users, "get_user_by_email",
        staticmethod(lambda email, db=None: fake_user),
    )
    monkeypatch.setattr(auth_callback, "create_token", lambda **k: "owui-token")
    monkeypatch.setattr(auth_callback, "parse_duration", lambda v: None)
    monkeypatch.setattr(auth_callback, "get_session", lambda: iter([db]))

    # Provisioning isn't under test; just materialize the org so the sync block resolves it.
    def _provision(_db, uid, payload):
        if db.query(AgencyOSOrganization).filter_by(id=_ORG_ID).one_or_none() is None:
            db.add(
                AgencyOSOrganization(
                    id=_ORG_ID, name="Acme", slug="acme", portal_org_id=_PORTAL_CUID,
                    created_at=now_ms(), updated_at=now_ms(),
                )
            )
            db.commit()

    monkeypatch.setattr(
        OrganizationsService, "provision_from_portal", staticmethod(_provision)
    )

    token = pyjwt.encode(_jwt_payload(), "test-portal-secret", algorithm="HS256")

    def _call(**params):
        return asyncio.run(
            auth_callback.portal_auth_callback(request=_fake_request(), token=token, **params)
        )

    _call.token = token
    return _call


def test_callback_defaults_to_agencyos_root(callback, monkeypatch):
    monkeypatch.setattr(subaccount_sync, "_fetch_subaccounts", lambda token: [])
    resp = callback()
    assert resp.status_code == 303
    assert resp.headers["location"] == "/agencyos/"


def test_callback_honors_a_safe_return_path(callback, monkeypatch):
    monkeypatch.setattr(subaccount_sync, "_fetch_subaccounts", lambda token: [])
    resp = callback(return_path="/agencyos/?newSubAccountId=" + _SA2)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/agencyos/?newSubAccountId=" + _SA2


@pytest.mark.parametrize("hostile", ["//evil.com", "https://evil.com/x", "/\\evil.com", "javascript:alert(1)", ""])
def test_callback_refuses_an_open_redirect(callback, monkeypatch, hostile):
    monkeypatch.setattr(subaccount_sync, "_fetch_subaccounts", lambda token: [])
    resp = callback(return_path=hostile)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/agencyos/"


def test_return_marker_forces_a_resync_through_the_throttle(callback, monkeypatch, db):
    """THE gate-1 behavior: the user just created a sub-account in Portal and is bouncing
    back. maybe_sync would be inside its 900s window (they logged in minutes ago), so the
    new sub-account would be invisible. ?subAccountCreated=1 must pull anyway."""
    fetched = {"n": 0}

    def _fetch(token):
        fetched["n"] += 1
        return [{"id": _SA1, "name": "Northwind", "status": "active"}]

    monkeypatch.setattr(subaccount_sync, "_fetch_subaccounts", _fetch)

    # Ambient login: pulls once, then the org is inside its back-off window.
    callback()
    assert fetched["n"] == 1
    # A second ordinary login is throttled — proving the window is live.
    callback()
    assert fetched["n"] == 1

    # Return-from-create hop: bypasses it.
    resp = callback(subaccount_created="1", return_path="/agencyos/?newSubAccountId=" + _SA1)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/agencyos/?newSubAccountId=" + _SA1
    assert fetched["n"] == 2, "the return marker must bypass the per-org back-off"
    assert {r.id for r in _rows(db, _ORG_ID)} == {_SA1}


def test_return_marker_routes_through_force_sync_not_maybe_sync(callback, monkeypatch):
    seen = []
    monkeypatch.setattr(subaccount_sync, "force_sync",
                        lambda _db, org_id, cuid, tok: seen.append(("force", org_id, cuid, tok)))
    monkeypatch.setattr(subaccount_sync, "maybe_sync",
                        lambda _db, org_id, cuid, tok: seen.append(("maybe", org_id, cuid, tok)))

    callback(subaccount_created="1")
    assert seen == [("force", _ORG_ID, _PORTAL_CUID, callback.token)]  # the RAW Portal JWT

    seen.clear()
    callback()
    assert seen == [("maybe", _ORG_ID, _PORTAL_CUID, callback.token)]


@pytest.mark.parametrize("falsy", ["0", "false", "no", "off", "", "   "])
def test_falsy_marker_keeps_the_throttled_path(callback, monkeypatch, falsy):
    seen = []
    monkeypatch.setattr(subaccount_sync, "force_sync", lambda *a: seen.append("force"))
    monkeypatch.setattr(subaccount_sync, "maybe_sync", lambda *a: seen.append("maybe"))

    callback(subaccount_created=falsy)
    assert seen == ["maybe"]


def test_sync_failure_on_the_return_hop_still_logs_the_user_in(callback, monkeypatch):
    """The force path lives inside the callback's never-raises try: Portal blowing up must
    not cost the user their login."""
    def _boom(token):
        raise RuntimeError("portal exploded")

    monkeypatch.setattr(subaccount_sync, "_fetch_subaccounts", _boom)

    resp = callback(subaccount_created="1", return_path="/agencyos/x")
    assert resp.status_code == 303
    assert resp.headers["location"] == "/agencyos/x"
    assert "token=owui-token" in resp.headers["set-cookie"]


def test_callback_route_parses_the_query_params_end_to_end(monkeypatch, db, _owui_callback_stubs):
    """Everything above drives the coroutine directly, which would happily accept a
    signature FastAPI rejects (and would never prove the ?next= / ?subAccountCreated=
    ALIASES are what the browser actually sends). Mount the real router and go through
    the HTTP layer once."""
    from apps.agencyos.backend.routers import auth_callback

    monkeypatch.setenv("JWT_SECRET", "test-portal-secret")
    monkeypatch.setattr(
        auth_callback.Users, "get_user_by_email",
        staticmethod(lambda email, db=None: types.SimpleNamespace(id=_UID, name="Acme Owner")),
    )
    monkeypatch.setattr(auth_callback, "create_token", lambda **k: "owui-token")
    monkeypatch.setattr(auth_callback, "parse_duration", lambda v: None)
    monkeypatch.setattr(auth_callback, "get_session", lambda: iter([db]))
    monkeypatch.setattr(
        OrganizationsService, "provision_from_portal", staticmethod(lambda *a: None)
    )

    seen = []
    monkeypatch.setattr(subaccount_sync, "force_sync", lambda *a: seen.append("force"))
    monkeypatch.setattr(subaccount_sync, "maybe_sync", lambda *a: seen.append("maybe"))

    app = FastAPI()
    # The callback reads request.app.state.config (JWT_EXPIRES_IN / DEFAULT_GROUP_ID),
    # which only the real OWUI app populates.
    app.state.config = types.SimpleNamespace(DEFAULT_GROUP_ID=None, JWT_EXPIRES_IN="1h")
    app.include_router(auth_callback.router)
    http = TestClient(app, raise_server_exceptions=False)

    # No token at all -> 400, proving the route is registered with a valid signature.
    assert http.get("/agencyos/auth/callback").status_code == 400

    token = pyjwt.encode(_jwt_payload(), "test-portal-secret", algorithm="HS256")
    resp = http.get(
        "/agencyos/auth/callback",
        params={"token": token, "next": "/agencyos/?newSubAccountId=" + _SA1,
                "subAccountCreated": "1"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/agencyos/?newSubAccountId=" + _SA1
    # No org row exists for this CUID here, so neither sync runs — the point of this test
    # is the param plumbing, which the redirect target proves.
    assert seen == []

    # And the guard is live on the HTTP path too.
    hostile = http.get(
        "/agencyos/auth/callback",
        params={"token": token, "next": "//evil.com"},
        follow_redirects=False,
    )
    assert hostile.headers["location"] == "/agencyos/"


# ============================================ the list response the frontend will read

@pytest.fixture
def app(db):
    from apps.agencyos.backend.middleware.jwt_auth import PortalAuthContext
    from apps.agencyos.backend.middleware.tenant import get_tenant_session
    from apps.agencyos.backend.routers import organizations

    db.add(
        AgencyOSOrganization(
            id=_ORG_ID, name="Acme", slug="acme", plan="starter",
            portal_org_id=_PORTAL_CUID, created_at=now_ms(), updated_at=now_ms(),
        )
    )
    db.commit()

    app = FastAPI()

    @app.middleware("http")
    async def _inject_state(request: Request, call_next):
        request.state.user_id = _UID
        request.state.portal_auth = PortalAuthContext(
            user_id=_UID,
            org_id=_PORTAL_CUID,
            role="owner",
            app_access=["AGENCYOS", "CORTEX", "DRIVE", "WORKPIPE"],
        )
        return await call_next(request)

    app.dependency_overrides[get_tenant_session] = lambda: db
    app.include_router(organizations.router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


def _list_subaccounts(client):
    resp = client.get(f"/api/agencyos/orgs/{_ORG_ID}/subaccounts")
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_list_reports_unknown_sync_before_any_successful_pull(client, db, monkeypatch):
    monkeypatch.setattr(subaccount_sync, "_fetch_subaccounts", lambda token: None)
    subaccount_sync.sync_org_subaccounts(db, _ORG_ID, _PORTAL_CUID, _TOKEN)

    payload = _list_subaccounts(client)
    assert payload["subAccounts"] == []
    assert payload["syncOk"] is False       # => the nudge must NOT fire
    assert payload["syncedAt"] is None


def test_list_reports_known_good_zero(client, db, monkeypatch):
    monkeypatch.setattr(subaccount_sync, "_fetch_subaccounts", lambda token: [])
    subaccount_sync.sync_org_subaccounts(db, _ORG_ID, _PORTAL_CUID, _TOKEN)

    payload = _list_subaccounts(client)
    assert payload["subAccounts"] == []
    assert payload["syncOk"] is True        # => a genuine zero: the nudge may fire
    assert payload["syncedAt"]


def test_list_reports_known_good_with_subaccounts(client, db, monkeypatch):
    monkeypatch.setattr(
        subaccount_sync, "_fetch_subaccounts",
        lambda token: [{"id": _SA1, "name": "Northwind", "slug": "northwind", "status": "active"}],
    )
    subaccount_sync.sync_org_subaccounts(db, _ORG_ID, _PORTAL_CUID, _TOKEN)

    payload = _list_subaccounts(client)
    assert [s["id"] for s in payload["subAccounts"]] == [_SA1]
    assert payload["syncOk"] is True
    assert payload["syncedAt"]


def test_list_emits_configured_public_origin(client, monkeypatch):
    monkeypatch.setenv("AGENCYOS_PUBLIC_ORIGIN", "https://agencyos-ije4.onrender.com/")
    # Trailing slash normalized off so the frontend can concatenate a path directly.
    assert _list_subaccounts(client)["publicOrigin"] == "https://agencyos-ije4.onrender.com"


def test_list_omits_public_origin_when_unset_or_malformed(client, monkeypatch):
    monkeypatch.delenv("AGENCYOS_PUBLIC_ORIGIN", raising=False)
    assert _list_subaccounts(client)["publicOrigin"] is None

    monkeypatch.setenv("AGENCYOS_PUBLIC_ORIGIN", "   ")
    assert _list_subaccounts(client)["publicOrigin"] is None

    # Not an absolute http(s) origin -> None, so the frontend falls back rather than
    # building a returnTo Portal's allowlist will reject.
    monkeypatch.setenv("AGENCYOS_PUBLIC_ORIGIN", "agencyos-ije4.onrender.com")
    assert _list_subaccounts(client)["publicOrigin"] is None
