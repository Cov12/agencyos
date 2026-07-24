"""
Portal sub-account mirror sync (issue #27 / A1).

Portal is the source of truth for an org's sub-accounts. AgencyOS runs its OWN
SQLite (webui.db) and cannot share Portal's Postgres, so — exactly like WorkPipe
pulls CRM rows — it PULLs the list over HTTP and mirrors it locally into
AgencyOSSubAccount, keyed by Portal's SubAccount.id (a CUID) stored VERBATIM. That
keeps AgencyOS keying the SAME sub-account identity as WorkPipe/Drive/Portal.

Design constraints (mirrors services/cortex_bridge defensive style):
  * NEVER raise into the request path. Any network/HTTP/DB failure -> log + no-op,
    so an unreachable Portal degrades AgencyOS to business-scope-only (empty list),
    never a 500.
  * Ids are Portal's, verbatim. We create-if-missing and update name/slug/status on
    change; we NEVER mint a sub-account id locally.
  * Throttled: the sync hook runs on Portal-authed requests, so we back off per-org
    (in-process TTL) to avoid hammering Portal on every request. See maybe_sync().

Auth + base URL (verified against the codebase, not guessed):
  * PORTAL_URL — the Portal base URL env, default https://portal.wbit.app, the same
    var routers/auth_callback.py + middleware/auth_redirect.py already read.
  * The raw, validated Portal JWT is stashed on request.state.portal_token by
    middleware/jwt_auth.py; we forward it as `Authorization: Bearer <jwt>` so Portal
    authorizes the call as the same user.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger("agencyos.subaccount_sync")

AGENCYOS_SUBACCOUNT_COOKIE = "agencyos_subaccount"
BUSINESS_SCOPE_SENTINEL = "__business__"

_DEFAULT_PORTAL_URL = "https://portal.wbit.app"
_DEFAULT_TIMEOUT_S = 8.0
# Per-org back-off between pulls. One sync every 15 min per org is plenty for a
# roster that changes rarely; overridable per-env.
_DEFAULT_TTL_S = 900.0

# In-process, best-effort throttle: org (internal id) -> last attempt (ms). Not
# shared across workers/restarts by design — the worst case is one redundant pull
# after a restart, which is idempotent and cheap. Avoids a schema column AND a DB
# write on the hot request path (a plain dict lookup instead).
_last_attempt_ms: dict[str, int] = {}


# --- config (env) ------------------------------------------------------------

def _portal_base_url() -> str:
    return os.environ.get("PORTAL_URL", _DEFAULT_PORTAL_URL).rstrip("/")


def _subaccounts_url() -> str:
    return f"{_portal_base_url()}/api/subaccounts"


def _timeout_s() -> float:
    try:
        return float(os.environ.get("SUBACCOUNT_SYNC_TIMEOUT_S", _DEFAULT_TIMEOUT_S))
    except ValueError:
        return _DEFAULT_TIMEOUT_S


def _ttl_ms() -> int:
    try:
        return int(float(os.environ.get("SUBACCOUNT_SYNC_TTL_S", _DEFAULT_TTL_S)) * 1000)
    except ValueError:
        return int(_DEFAULT_TTL_S * 1000)


# --- HTTP fetch --------------------------------------------------------------

def _fetch_subaccounts(token: str) -> Optional[list[dict]]:
    """GET Portal /api/subaccounts as the JWT's user. Returns a list of sub-account
    dicts, or None on ANY failure (missing token, network error, non-2xx, non-JSON,
    unexpected shape). Never raises.

    Portal may return either a bare array or a wrapped envelope
    ({"data": [...]} / {"subAccounts": [...]}); both are accepted."""
    if not token:
        return None
    url = _subaccounts_url()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    try:
        with httpx.Client(timeout=_timeout_s()) as client:
            resp = client.get(url, headers=headers)
    except httpx.HTTPError as e:  # timeout, connect error, etc.
        logger.warning("subaccount_sync: fetch failed (%s): %s", url, e)
        return None

    if resp.status_code not in (200, 201):
        logger.warning(
            "subaccount_sync: Portal returned %s for %s", resp.status_code, url
        )
        return None

    try:
        data = resp.json()
    except ValueError:
        logger.warning("subaccount_sync: Portal returned non-JSON body for %s", url)
        return None

    items = _extract_list(data)
    if items is None:
        logger.warning("subaccount_sync: unexpected Portal payload shape for %s", url)
        return None
    return items


def _extract_list(data) -> Optional[list[dict]]:
    """Normalize Portal's response into a list of dicts. None if it isn't one.

    Portal returns a wrapped envelope, e.g. {"subAccounts": [...]}. Pick the wrapper by
    KEY PRESENCE, not truthiness — an empty list [] is a valid "no sub-accounts" answer and
    must NOT be misread as an absent key (the `x.get(k) or ...` idiom does exactly that,
    since [] is falsy, and mislabels a 0-sub-account org as an 'unexpected payload shape')."""
    if isinstance(data, list):
        candidate = data
    elif isinstance(data, dict):
        candidate = None
        for key in ("data", "subAccounts", "subaccounts"):
            if key in data:
                candidate = data[key]
                break
        if candidate is None:
            # No known wrapper key present: an empty object {} means "no sub-accounts";
            # anything else is an unexpected shape.
            return [] if not data else None
    else:
        return None
    if not isinstance(candidate, list):
        return None
    return [x for x in candidate if isinstance(x, dict)]


# --- upsert ------------------------------------------------------------------

def sync_org_subaccounts(
    db: Optional[Session],
    internal_org_id: Optional[str],
    portal_org_id: Optional[str],
    token: Optional[str],
) -> int:
    """Pull the org's sub-accounts from Portal and upsert them into the mirror.

    Returns the number of sub-accounts upserted (0 on any failure / empty list).
    Ids are stored VERBATIM as Portal's SubAccount.id. Never raises into the
    request path — on error it rolls back and swallows, mirroring cortex_bridge."""
    if db is None or not internal_org_id or not token:
        return 0

    items = _fetch_subaccounts(token)
    if not items:  # None (failure) or [] (no sub-accounts) -> no-op
        return 0

    try:
        from ..models.db import AgencyOSSubAccount, now_ms

        upserted = 0
        for sa in items:
            sid = (sa.get("id") or "").strip()
            if not sid:
                continue  # never mint an id locally; skip malformed entries
            name = sa.get("name")
            slug = sa.get("slug")
            status = sa.get("status")
            ts = now_ms()

            row = (
                db.query(AgencyOSSubAccount)
                .filter(AgencyOSSubAccount.id == sid)
                .one_or_none()
            )
            # Defense-in-depth: never STEAL a sub-account row across Portal orgs. Portal
            # ids are globally unique and each org's sync only fetches its own, so this
            # should never trigger — but if a mismatched (org, token) call ever occurred it
            # must not reassign a row that belongs to a DIFFERENT Portal org. A re-provision
            # under a new AgencyOS internal id keeps the SAME portal_org_id, so that legit
            # case still updates (only a DIFFERENT portal_org_id is refused).
            if (
                row is not None
                and row.portal_org_id
                and portal_org_id
                and row.portal_org_id != portal_org_id
            ):
                logger.warning(
                    "subaccount_sync: sub-account %s already owned by portal_org %s, not %s"
                    " — refusing cross-tenant reassignment",
                    sid, row.portal_org_id, portal_org_id,
                )
                continue
            if row is None:
                db.add(
                    AgencyOSSubAccount(
                        id=sid,  # Portal's id, verbatim
                        org_id=internal_org_id,
                        portal_org_id=portal_org_id,
                        name=name,
                        slug=slug,
                        status=status,
                        created_at=ts,
                        updated_at=ts,
                        synced_at=ts,
                    )
                )
            else:
                changed = (
                    row.name != name
                    or row.slug != slug
                    or row.status != status
                    or row.org_id != internal_org_id
                    or row.portal_org_id != portal_org_id
                )
                row.name = name
                row.slug = slug
                row.status = status
                # Keep the ownership binding fresh (an org re-provisioned under a new
                # internal id would otherwise leave stale rows pointing elsewhere).
                row.org_id = internal_org_id
                row.portal_org_id = portal_org_id
                row.synced_at = ts
                if changed:
                    row.updated_at = ts
            upserted += 1

        db.commit()
        logger.info(
            "subaccount_sync: upserted %d sub-account(s) for org %s",
            upserted,
            internal_org_id,
        )
        return upserted
    except Exception as e:  # never let the mirror break a request
        logger.warning(
            "subaccount_sync: upsert failed for org %s: %s", internal_org_id, e
        )
        try:
            db.rollback()
        except Exception:
            pass
        return 0


# --- throttled request-path entry --------------------------------------------

def maybe_sync(
    db: Optional[Session],
    internal_org_id: Optional[str],
    portal_org_id: Optional[str],
    token: Optional[str],
) -> None:
    """Throttled wrapper called from the request path (middleware.tenant
    get_tenant_session). Backs off per-org so a Portal-authed request stream does
    not pull on every hit. Never raises.

    The attempt timestamp is recorded BEFORE the pull, so a failing/unreachable
    Portal also backs off for the TTL instead of being retried every request —
    exactly the "degrade to business-scope-only" behavior we want."""
    if db is None or not internal_org_id or not token:
        return
    try:
        now = _now_ms()
        last = _last_attempt_ms.get(internal_org_id)
        if last is not None and (now - last) < _ttl_ms():
            return  # throttled
        _last_attempt_ms[internal_org_id] = now
        sync_org_subaccounts(db, internal_org_id, portal_org_id, token)
    except Exception as e:  # belt-and-suspenders: request path must never 500 here
        logger.warning(
            "subaccount_sync: maybe_sync failed for org %s: %s", internal_org_id, e
        )


def _now_ms() -> int:
    from ..models.db import now_ms

    return now_ms()


# --- read helper (AgencyOS as read-only consumer) ----------------------------

def list_subaccounts(db: Optional[Session], internal_org_id: Optional[str]) -> list:
    """List the mirrored sub-accounts for an AgencyOS-internal org id. Returns []
    on missing input or any error — a degraded mirror is business-scope-only, never
    a crash."""
    if db is None or not internal_org_id:
        return []
    try:
        from ..models.db import AgencyOSSubAccount

        return (
            db.query(AgencyOSSubAccount)
            .filter(AgencyOSSubAccount.org_id == internal_org_id)
            .order_by(AgencyOSSubAccount.created_at.asc())
            .all()
        )
    except Exception as e:
        logger.warning(
            "subaccount_sync: list failed for org %s: %s", internal_org_id, e
        )
        try:
            db.rollback()
        except Exception:
            pass
        return []


def list_active_subaccounts(db: Optional[Session], internal_org_id: Optional[str]) -> list:
    """List only ACTIVE mirrored sub-accounts for an org, oldest-first.

    Portal has historically emitted status values with varying case, so ACTIVE is
    treated case-insensitively. Any DB failure degrades to [] instead of raising.
    """
    if db is None or not internal_org_id:
        return []
    try:
        from ..models.db import AgencyOSSubAccount

        return (
            db.query(AgencyOSSubAccount)
            .filter(AgencyOSSubAccount.org_id == internal_org_id)
            .filter(func.lower(func.coalesce(AgencyOSSubAccount.status, "")) == "active")
            .order_by(AgencyOSSubAccount.created_at.asc())
            .all()
        )
    except Exception as e:
        logger.warning(
            "subaccount_sync: active-list failed for org %s: %s", internal_org_id, e
        )
        try:
            db.rollback()
        except Exception:
            pass
        return []


def resolve_active_subaccount_id(
    db: Optional[Session], internal_org_id: Optional[str], cookie_value: Optional[str]
) -> Optional[str]:
    """Resolve the chat's active sub-account from the selector cookie.

    Semantics for AgencyOS chat:
      * missing cookie => business scope (None)
      * BUSINESS sentinel => explicit business scope (None)
      * any id => only honored if it names an ACTIVE mirrored sub-account of this org

    Invalid / stale / cross-org cookie values fail closed to business scope.
    """
    if not cookie_value or cookie_value == BUSINESS_SCOPE_SENTINEL:
        return None
    for row in list_active_subaccounts(db, internal_org_id):
        if row.id == cookie_value:
            return row.id
    return None
