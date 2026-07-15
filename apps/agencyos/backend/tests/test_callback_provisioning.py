"""Callback-path provisioning tests — agencyos#50.

The deployed AgencyOS login is the server-side route
`apps/agencyos/backend/routers/auth_callback.py::portal_auth_callback`
(GET /agencyos/auth/callback). Historically the Portal->AgencyOS provisioning
(AgencyOSMember + per-org app_access, #45) lived ONLY in a `portal_token_exchange`
endpoint prod never called (it was hit by an unused Svelte page, since removed). So
provisioning never ran in prod: users were created but no
membership / app_access rows, and every OWUI-session auth gate fell through to the
AGENCYOS_DEV_ALLOW_HEADER_AUTH rollout grace.

These tests pin the fix: a shared `OrganizationsService.provision_from_portal` helper,
exercised directly AND invoked from the REAL callback path (portal_auth_callback).
"""

import asyncio
import sys
import types

import jwt as pyjwt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from open_webui.internal.db import Base
from apps.agencyos.backend.models.db import (
    AgencyOSMember,
    AgencyOSOrganization,
)
from apps.agencyos.backend.services.organizations import OrganizationsService

CUID = "cuidprovisionaaaaaaaaaaaa"
UID = "owui-user-provision"


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


def _payload(**over):
    p = {
        "sub": "user_clerk_x",
        "email": "owner@acme.test",
        "name": "Acme Owner",
        "org_id": CUID,
        "org_slug": "acme",
        "org_name": "Acme Inc",
        "role": "OWNER",  # Portal sends UPPERCASE — the helper must lowercase it.
        "app_access": ["AGENCYOS", "DRIVE", "WORKPIPE"],
    }
    p.update(over)
    return p


# ---------------------------------------------------------------- helper unit tests

def test_provision_creates_org_member_and_app_access(db):
    OrganizationsService.provision_from_portal(db, UID, _payload())

    org = OrganizationsService.get_org_by_portal_id(db, CUID)
    assert org is not None and org.portal_org_id == CUID
    assert org.app_access == ["AGENCYOS", "DRIVE", "WORKPIPE"]

    mem = db.query(AgencyOSMember).filter_by(org_id=org.id, user_id=UID).all()
    assert len(mem) == 1
    assert mem[0].role == "owner"  # normalized from "OWNER"


def test_provision_reuses_existing_org(db):
    db.add(
        AgencyOSOrganization(
            id="org-x", name="Acme", slug="acme", portal_org_id=CUID, app_access=[]
        )
    )
    db.commit()

    OrganizationsService.provision_from_portal(db, UID, _payload())

    orgs = db.query(AgencyOSOrganization).filter_by(portal_org_id=CUID).all()
    assert len(orgs) == 1 and orgs[0].id == "org-x"
    assert orgs[0].app_access == ["AGENCYOS", "DRIVE", "WORKPIPE"]


def test_provision_idempotent_updates_role_no_dup(db):
    OrganizationsService.provision_from_portal(db, UID, _payload(role="MEMBER"))
    OrganizationsService.provision_from_portal(db, UID, _payload(role="OWNER"))

    org = OrganizationsService.get_org_by_portal_id(db, CUID)
    mem = db.query(AgencyOSMember).filter_by(org_id=org.id, user_id=UID).all()
    assert len(mem) == 1
    assert mem[0].role == "owner"


def test_provision_skips_without_org_id(db):
    OrganizationsService.provision_from_portal(db, UID, _payload(org_id=None))
    assert db.query(AgencyOSOrganization).count() == 0
    assert db.query(AgencyOSMember).count() == 0


# ------------------------------------------------- the REAL deployed path (the fix)

def _install_owui_stubs_for_callback():
    """auth_callback.py imports several open_webui submodules the unit-test conftest
    doesn't stub (models.users/auths, utils.auth/groups/misc, env). Stub ONLY the ones
    that aren't already importable, so a full-deps env exercises the real modules and a
    min-deps env can still import + run this test (the whole point: test the REAL path).
    The test monkeypatches the behaviors it cares about; these stubs only satisfy import.
    """
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


def test_portal_auth_callback_invokes_provisioning(monkeypatch, db):
    """The bug: portal_auth_callback (the path prod uses) never provisioned. Assert it
    now calls provision_from_portal with the resolved OWUI user.id and decoded claims."""
    _install_owui_stubs_for_callback()
    from apps.agencyos.backend.routers import auth_callback

    monkeypatch.setenv("JWT_SECRET", "test-portal-secret")

    # User resolution isn't the subject — return an existing OWUI user.
    fake_user = types.SimpleNamespace(id=UID, name="Acme Owner")
    monkeypatch.setattr(
        auth_callback.Users,
        "get_user_by_email",
        staticmethod(lambda email, db=None: fake_user),
    )
    monkeypatch.setattr(auth_callback, "create_token", lambda **k: "owui-token")
    monkeypatch.setattr(auth_callback, "parse_duration", lambda v: None)
    # Point the callback's `next(get_session())` at our in-memory session.
    monkeypatch.setattr(auth_callback, "get_session", lambda: iter([db]))

    captured = {}

    def spy(_db, user_id, payload):
        captured["user_id"] = user_id
        captured["payload"] = payload

    monkeypatch.setattr(
        OrganizationsService, "provision_from_portal", staticmethod(spy)
    )

    token = pyjwt.encode(_payload(), "test-portal-secret", algorithm="HS256")
    req = types.SimpleNamespace(
        app=types.SimpleNamespace(
            state=types.SimpleNamespace(
                config=types.SimpleNamespace(
                    DEFAULT_GROUP_ID=None, JWT_EXPIRES_IN="1h"
                )
            )
        ),
        url="http://test/agencyos/auth/callback",
    )

    resp = asyncio.run(auth_callback.portal_auth_callback(request=req, token=token))

    assert resp.status_code == 303
    assert captured.get("user_id") == UID
    assert captured["payload"]["org_id"] == CUID
    assert captured["payload"]["app_access"] == ["AGENCYOS", "DRIVE", "WORKPIPE"]
    assert captured["payload"]["role"] == "OWNER"
