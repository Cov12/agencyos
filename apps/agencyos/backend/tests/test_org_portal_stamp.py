"""#66 Stage 2 — auto-populate agencyos_organization.portal_org_id.

Covers:
  * Approach A: create_org stamps the Portal CUID at provisioning (and leaves it
    NULL when unknown).
  * Second-org resolution: a newly provisioned org with its own Portal CUID
    resolves via cortex_bridge to its OWN uuid5 company — NOT the WBIT default …c0de.
  * Approach B: the idempotent reconcile stamps NULL rows, never overwrites a
    non-null value, and leaves the 'default' (WBIT-pinned) org untouched; plus the
    get_tenant_session hook mapping (Portal CUID from the JWT, internal org id from
    the `org_id` query param).

Runs against an in-memory SQLite DB built from the (conftest-stubbed) declarative
Base — see apps/agencyos/conftest.py.
"""

import types
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from open_webui.internal.db import Base
from apps.agencyos.backend.models.db import AgencyOSOrganization
from apps.agencyos.backend.services import cortex_bridge
from apps.agencyos.backend.services.organizations import OrganizationsService
from apps.agencyos.backend.middleware.tenant import get_tenant_session


# Locked namespace outputs (mirrors test_cortex_bridge).
_WBIT_CUID = "cmpswvysr000029jthi4waszr"
_C0DE = "00000000-0000-4000-a000-00000000c0de"
# A DISTINCT second Portal org (a CUID, not a UUID → routed through uuid5).
_SECOND_CUID = "clsecondorg0000abcd1234wxyz"


@pytest.fixture
def db():
    """In-memory SQLite session with the AgencyOS tables created."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    # Pure derivation: no override, default company == …c0de.
    monkeypatch.delenv("PORTAL_COMPANY_OVERRIDES", raising=False)
    monkeypatch.delenv("WBIT_COMPANY_ID", raising=False)


# --- Approach A: stamp at org-create -----------------------------------------

def test_create_org_stamps_portal_org_id_when_provided(db):
    org = OrganizationsService.create_org(
        db, name="Acme", slug="acme", portal_org_id=_SECOND_CUID
    )
    assert org.portal_org_id == _SECOND_CUID
    # Persisted, not just set on the transient instance.
    fetched = OrganizationsService.get_org_by_id(db, org.id)
    assert fetched.portal_org_id == _SECOND_CUID


def test_create_org_leaves_portal_org_id_null_when_absent(db):
    org = OrganizationsService.create_org(db, name="NoPortal", slug="noportal")
    assert org.portal_org_id is None
    # Empty string is normalized to NULL, never stored as "".
    org2 = OrganizationsService.create_org(
        db, name="Empty", slug="empty", portal_org_id=""
    )
    assert org2.portal_org_id is None


# --- Second org resolves to its OWN company (not the WBIT default) ------------

def test_second_org_resolves_to_own_uuid5_not_wbit_default(db):
    """The core issue-#23 assertion: a distinct second org resolves to its own
    per-org uuid5 company, NOT collapsing onto the WBIT default …c0de."""
    # WBIT default org (pinned) + a distinct second org, both provisioned via A.
    OrganizationsService.create_org(
        db, name="My Organization", slug="default", portal_org_id=_WBIT_CUID
    )
    second = OrganizationsService.create_org(
        db, name="Acme", slug="acme", portal_org_id=_SECOND_CUID
    )

    expected = str(
        uuid.uuid5(cortex_bridge._PORTAL_ORG_UUID_NAMESPACE, _SECOND_CUID)
    )
    resolved = cortex_bridge._resolve_company_for_chat(db, second.id)

    assert resolved == expected
    assert resolved != _C0DE  # NOT collapsed onto the WBIT default pin
    # And it is genuinely distinct from the WBIT org's derived company.
    wbit_derived = str(
        uuid.uuid5(cortex_bridge._PORTAL_ORG_UUID_NAMESPACE, _WBIT_CUID)
    )
    assert resolved != wbit_derived


# --- Approach B: idempotent reconcile helper ---------------------------------

def test_stamp_reconcile_stamps_null_row(db):
    org = OrganizationsService.create_org(db, name="Legacy", slug="legacy")
    assert org.portal_org_id is None

    stamped = OrganizationsService.stamp_portal_org_id(db, org.id, _SECOND_CUID)
    assert stamped is True
    assert OrganizationsService.get_org_by_id(db, org.id).portal_org_id == _SECOND_CUID


def test_stamp_reconcile_never_overwrites_non_null(db):
    org = OrganizationsService.create_org(
        db, name="Already", slug="already", portal_org_id=_SECOND_CUID
    )
    # A different CUID must NOT clobber the existing value.
    stamped = OrganizationsService.stamp_portal_org_id(db, org.id, "clOTHERvalue0000zzzz")
    assert stamped is False
    assert OrganizationsService.get_org_by_id(db, org.id).portal_org_id == _SECOND_CUID


def test_stamp_reconcile_leaves_default_org_untouched(db):
    # NULL 'default' row (e.g. migration 002 not yet applied) is still left alone.
    org = OrganizationsService.create_org(db, name="My Organization", slug="default")
    stamped = OrganizationsService.stamp_portal_org_id(db, org.id, _WBIT_CUID)
    assert stamped is False
    assert OrganizationsService.get_org_by_id(db, org.id).portal_org_id is None


def test_stamp_reconcile_unknown_row_is_noop(db):
    assert OrganizationsService.stamp_portal_org_id(db, "does-not-exist", _SECOND_CUID) is False


def test_stamp_reconcile_guards_empty_inputs(db):
    assert OrganizationsService.stamp_portal_org_id(db, "", _SECOND_CUID) is False
    assert OrganizationsService.stamp_portal_org_id(db, "x", "") is False


# --- Approach B: get_tenant_session hook (CUID -> row via query param) --------

class _FakeState:
    def __init__(self, portal_cuid, state_org_id):
        self.portal_auth = types.SimpleNamespace(org_id=portal_cuid) if portal_cuid else None
        self.org_id = state_org_id


class _FakeRequest:
    """Minimal stand-in for the pieces get_tenant_session reads."""

    def __init__(self, portal_cuid=None, query_org_id=None, state_org_id=None):
        self.state = _FakeState(portal_cuid, state_org_id)
        self.query_params = {"org_id": query_org_id} if query_org_id else {}


def _drive(request, db):
    """Run the get_tenant_session generator body (up to yield) and close it."""
    gen = get_tenant_session(request, db)
    next(gen)  # executes the reconcile + SET LOCAL (SET LOCAL no-ops on SQLite)
    gen.close()


def test_tenant_session_stamps_via_query_param_on_portal_request(db):
    """A Portal-authed request (CUID on the JWT, internal id in ?org_id=) stamps
    the matched NULL row."""
    org = OrganizationsService.create_org(db, name="Legacy", slug="legacy")
    # JWT carries the CUID; the frontend passes the INTERNAL org id as ?org_id=.
    req = _FakeRequest(portal_cuid=_SECOND_CUID, query_org_id=org.id)
    _drive(req, db)
    assert OrganizationsService.get_org_by_id(db, org.id).portal_org_id == _SECOND_CUID


def test_tenant_session_no_stamp_without_portal_auth(db):
    """Phase-1 (no Portal JWT) request must not stamp anything."""
    org = OrganizationsService.create_org(db, name="Legacy", slug="legacy")
    req = _FakeRequest(portal_cuid=None, query_org_id=org.id, state_org_id=org.id)
    _drive(req, db)
    assert OrganizationsService.get_org_by_id(db, org.id).portal_org_id is None


def test_tenant_session_no_stamp_without_query_param(db):
    """Portal JWT present but no ?org_id= (can't map CUID -> row) → no stamp."""
    org = OrganizationsService.create_org(db, name="Legacy", slug="legacy")
    req = _FakeRequest(portal_cuid=_SECOND_CUID, query_org_id=None)
    _drive(req, db)
    assert OrganizationsService.get_org_by_id(db, org.id).portal_org_id is None
