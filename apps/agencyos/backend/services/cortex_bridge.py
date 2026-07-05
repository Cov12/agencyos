"""
AgencyOS -> Cortex WBIT bridge caller (thin transport).

When enabled, this forwards a user's chat turn to the Cortex WBIT Assistant via
the bridge plugin's block-and-return endpoint and returns the assistant's reply.
It bypasses the legacy lane_router / intent_classifier / model_router stack
entirely (Option B) -- AgencyOS is just a transport; Cortex is the brain.

Multi-turn continuity: the bridge returns a `sessionId`. We persist it per OWUI
`chat_id` (agencyos_cortex_session) and replay it on later turns so Hermes keeps
the same conversation. Turn 1 has no sessionId -> bridge creates one; turns 2+
send it back -> bridge reuses it.
"""

import logging
import os
import re
import uuid
from typing import Optional

import httpx
from sqlalchemy.orm import Session

logger = logging.getLogger("agencyos.cortex_bridge")

# Per-org company resolution. These MUST stay in lockstep with Cortex's
# resolvePortalCompany (wbit-cortex: server/src/routes/portal-callback.ts) so both
# services derive the SAME company UUID for a given Portal org id. The namespace and
# the PORTAL_COMPANY_OVERRIDES format are identical on both sides; Python's stdlib
# uuid.uuid5 is RFC-4122 v5 (SHA-1) and matches Cortex's inline implementation exactly
# (verified). NEVER change the namespace — it would remap every org's company.
_PORTAL_ORG_UUID_NAMESPACE = uuid.UUID("1d3a9b6e-0c4f-4a2d-9e7b-5f8c2a1e6d40")
_DEFAULT_PORTAL_COMPANY_ID = "00000000-0000-4000-a000-00000000c0de"
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)

# Points at the installed WBIT bridge plugin on Cortex prod; override per-env.
_DEFAULT_BRIDGE_URL = (
    "https://cortex-prod-we61.onrender.com"
    "/api/plugins/bad9f2f7-f128-4d36-808e-1bf6f05e5150/api/chat"
)
_DEFAULT_AGENT_ID = "14d3caab-5d9f-4bec-881b-c5691f8d6ed9"
# The bridge blocks up to 120s (WBIT_BRIDGE_RUN_TIMEOUT_MS); give the client headroom.
_DEFAULT_TIMEOUT_S = 125.0

_ERROR_REPLY = (
    "Sorry — I'm having trouble reaching the team right now. "
    "Please try again in a moment."
)


# --- config (env) ------------------------------------------------------------

def is_enabled() -> bool:
    """Route chat through the Cortex bridge instead of the legacy local stack."""
    return os.environ.get("WBIT_BRIDGE_ENABLED", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _bridge_url() -> str:
    return os.environ.get("CORTEX_BRIDGE_URL", _DEFAULT_BRIDGE_URL)


def _history_url() -> str:
    """The bridge's /history verb is a sibling of /chat on the same plugin base,
    so we derive it from _bridge_url() by swapping the trailing /chat segment for
    /history. This keeps one env override (CORTEX_BRIDGE_URL) driving both verbs —
    no second URL to configure or drift."""
    base = _bridge_url()
    if base.endswith("/chat"):
        return base[: -len("/chat")] + "/history"
    return base.rstrip("/") + "/history"


def _bridge_secret() -> str:
    return os.environ.get("WBIT_BRIDGE_SECRET", "")


def _agent_id() -> str:
    return os.environ.get("WBIT_AGENT_ID", _DEFAULT_AGENT_ID)


def _default_company_id() -> str:
    """Company used when an org has no stored Portal id. WBIT_COMPANY_ID (if set)
    stays the back-compat pin; otherwise the shared default company (…c0de)."""
    return os.environ.get("WBIT_COMPANY_ID", "").strip() or _DEFAULT_PORTAL_COMPANY_ID


def _is_uuid(value: str) -> bool:
    return bool(_UUID_RE.match(value))


def _company_overrides() -> dict:
    """Parse PORTAL_COMPANY_OVERRIDES ("<orgId>=<companyUuid>,...") — same env and
    format Cortex reads, so a Portal org pinned to an existing company (e.g. WBIT ->
    …c0de) resolves identically on both sides. Split on the FIRST '=' only."""
    raw = os.environ.get("PORTAL_COMPANY_OVERRIDES", "")
    out: dict = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        idx = pair.find("=")
        if idx <= 0:
            continue
        key = pair[:idx].strip()
        val = pair[idx + 1 :].strip()
        if key and _is_uuid(val):
            out[key] = val
    return out


def _resolve_company_id(portal_org_id: Optional[str]) -> str:
    """Map a Portal org id (CUID) to its Cortex company UUID. MUST match Cortex's
    resolvePortalCompany:
      - no id            -> default company (WBIT_COMPANY_ID env or …c0de)
      - override match    -> pinned company UUID
      - already a UUID    -> used as-is
      - a CUID (today)    -> deterministic UUIDv5 (shared namespace)
    """
    oid = (portal_org_id or "").strip()
    if not oid:
        return _default_company_id()
    override = _company_overrides().get(oid)
    if override:
        return override
    if _is_uuid(oid):
        return oid
    return str(uuid.uuid5(_PORTAL_ORG_UUID_NAMESPACE, oid))


def _portal_org_id_for(
    db: Optional[Session], internal_org_id: Optional[str]
) -> Optional[str]:
    """Look up the stored Portal org id (CUID) for an AgencyOS-internal org id.
    Returns None if db/id missing, org unknown, or column unset — caller then falls
    back to the default company. Never raises into the chat path."""
    if db is None or not internal_org_id:
        return None
    try:
        from ..models.db import AgencyOSOrganization

        row = (
            db.query(AgencyOSOrganization)
            .filter(AgencyOSOrganization.id == internal_org_id)
            .one_or_none()
        )
        return (row.portal_org_id or None) if row else None
    except Exception as e:  # never let company resolution break a chat
        logger.warning(
            f"cortex_bridge: portal_org_id lookup failed for org {internal_org_id}: {e}"
        )
        # If the SELECT aborted the transaction (e.g. code deployed before the
        # 002 migration adds the column), roll back so the later session-save in
        # this same request isn't poisoned. Falls back to the pin regardless.
        try:
            db.rollback()
        except Exception:
            pass
        return None


def _subaccount_id_for(
    db: Optional[Session], internal_org_id: Optional[str]
) -> Optional[str]:
    """The org's bound WorkPipe sub-account id, used to partition the WBIT
    assistant's long-term memory per sub-account (Cortex composes the Hermes
    session key as companyId:subAccountId). This is the SAME sub-account whose CRM
    data the agent operates on (see services/crm_adapter + workpipe), so memory
    and operational scope stay aligned. None (no binding / unknown org) →
    company/business scope, unchanged. Never raises into the chat path."""
    if db is None or not internal_org_id:
        return None
    try:
        from ..models.db import AgencyOSOrganization

        row = (
            db.query(AgencyOSOrganization)
            .filter(AgencyOSOrganization.id == internal_org_id)
            .one_or_none()
        )
        return (row.workpipe_account_id or None) if row else None
    except Exception as e:  # never let memory scoping break a chat
        logger.warning(
            f"cortex_bridge: subaccount lookup failed for org {internal_org_id}: {e}"
        )
        try:
            db.rollback()
        except Exception:
            pass
        return None


def _resolve_company_for_chat(
    db: Optional[Session], internal_org_id: Optional[str]
) -> str:
    """Resolve the Cortex company UUID for one chat turn.

    A chat request carries the AgencyOS-INTERNAL org id (the query param / OWUI
    session org), NOT the Portal CUID — so we look up the org's stored Portal id and
    run THAT through the shared resolver, yielding the same UUID Cortex provisioned
    for the Portal org. An org with no stored Portal id (or an unknown org) falls
    back to the WBIT_COMPANY_ID pin, preserving pre-#66 behavior. This is the fix
    for the first #66 attempt, which mis-resolved the internal id directly."""
    portal_org_id = _portal_org_id_for(db, internal_org_id)
    if portal_org_id:
        return _resolve_company_id(portal_org_id)
    return _default_company_id()


def _timeout_s() -> float:
    try:
        return float(os.environ.get("CORTEX_BRIDGE_TIMEOUT_S", _DEFAULT_TIMEOUT_S))
    except ValueError:
        return _DEFAULT_TIMEOUT_S


# --- session threading (chat_id -> cortex sessionId) -------------------------

def _load_session_id(db: Optional[Session], chat_id: Optional[str]) -> Optional[str]:
    if db is None or not chat_id:
        return None
    try:
        from ..models.db import AgencyOSCortexSession

        row = (
            db.query(AgencyOSCortexSession)
            .filter(AgencyOSCortexSession.chat_id == chat_id)
            .one_or_none()
        )
        return row.cortex_session_id if row else None
    except Exception as e:  # never let session lookup break a chat
        logger.warning(f"cortex_bridge: load session failed for chat {chat_id}: {e}")
        return None


def _save_session_id(
    db: Optional[Session],
    chat_id: Optional[str],
    org_id: Optional[str],
    session_id: Optional[str],
) -> None:
    if db is None or not chat_id or not session_id:
        return
    try:
        from ..models.db import AgencyOSCortexSession, now_ms

        row = (
            db.query(AgencyOSCortexSession)
            .filter(AgencyOSCortexSession.chat_id == chat_id)
            .one_or_none()
        )
        if row is None:
            db.add(
                AgencyOSCortexSession(
                    chat_id=chat_id,
                    org_id=org_id,
                    cortex_session_id=session_id,
                )
            )
        else:
            row.cortex_session_id = session_id
            row.updated_at = now_ms()
        db.commit()
    except Exception as e:  # persistence is best-effort; degrade to fresh session
        logger.warning(f"cortex_bridge: save session failed for chat {chat_id}: {e}")
        try:
            db.rollback()
        except Exception:
            pass


# --- HTTP call ---------------------------------------------------------------

async def _send(
    prompt: str,
    company_id: str,
    agent_id: str,
    session_id: Optional[str],
    sub_account_id: Optional[str] = None,
) -> dict:
    secret = _bridge_secret()
    if not secret:
        return {"ok": False, "error": "WBIT_BRIDGE_SECRET not configured"}
    if not company_id:
        return {"ok": False, "error": "WBIT_COMPANY_ID not configured"}

    body = {"companyId": company_id, "agentId": agent_id, "prompt": prompt}
    if session_id:
        body["sessionId"] = session_id
    # Partition the assistant's long-term memory per sub-account: Cortex composes
    # the Hermes session key as companyId:subAccountId. Omitted when unset →
    # company-level (business) scope, unchanged.
    if sub_account_id:
        body["subAccountId"] = sub_account_id

    headers = {"Content-Type": "application/json", "x-wbit-bridge-secret": secret}

    try:
        async with httpx.AsyncClient(timeout=_timeout_s()) as client:
            resp = await client.post(_bridge_url(), json=body, headers=headers)
    except httpx.TimeoutException:
        return {"ok": False, "error": "bridge request timed out"}
    except httpx.RequestError as e:
        return {"ok": False, "error": f"bridge request error: {e}"}

    if resp.status_code not in (200, 201):
        return {
            "ok": False,
            "error": f"bridge returned {resp.status_code}",
            "status_code": resp.status_code,
        }

    try:
        data = resp.json()
    except ValueError:
        return {"ok": False, "error": "bridge returned non-JSON body"}

    return {
        "ok": True,
        "response": data.get("response") or "",
        "sessionId": data.get("sessionId"),
        "runId": data.get("runId"),
        "created": data.get("created", False),
    }


# --- high-level entry --------------------------------------------------------

async def handle_chat(
    message: str,
    org_id: str,
    chat_id: Optional[str] = None,
    db: Optional[Session] = None,
    department_slug: Optional[str] = None,
    sub_account_id: Optional[str] = None,
) -> dict:
    """
    Forward one chat turn to the WBIT Assistant and return a result dict in the
    same shape the orchestrator's local path returns, so the frontend renders it
    unchanged.
    """
    session_id = _load_session_id(db, chat_id)
    result = await _send(
        prompt=message,
        company_id=_resolve_company_for_chat(db, org_id),
        agent_id=_agent_id(),
        session_id=session_id,
        sub_account_id=sub_account_id,
    )

    if not result.get("ok"):
        logger.warning(f"cortex_bridge: chat failed: {result.get('error')}")
        return _shape(department_slug, _ERROR_REPLY, status="error")

    new_session_id = result.get("sessionId")
    if new_session_id and new_session_id != session_id:
        _save_session_id(db, chat_id, org_id, new_session_id)

    return _shape(department_slug, result.get("response", ""), status="ok")


def _shape(department_slug: Optional[str], content: str, status: str) -> dict:
    return {
        "department": department_slug,
        "model_tier": "cortex_bridge",
        "model": "cortex/wbit-assistant",
        "content": content,
        "proposals": [],
        "usage": {},
        "status": status,
    }


# --- read: recent run history (Dashboard D4b) --------------------------------

async def fetch_history(
    db: Optional[Session],
    org_id: Optional[str],
    sub_account_id: Optional[str] = None,
    limit: int = 20,
) -> list:
    """Fetch recent Cortex runs for one org's company (and optional sub-account)
    scope, for the read-only dashboard. Resolves companyId the SAME way chat does
    (_resolve_company_for_chat), then POSTs to the bridge's /history verb with the
    shared x-wbit-bridge-secret.

    Defensive by design — this feeds a widget, never a mutation: it NEVER raises
    into the request. Missing secret, timeout, transport error, non-2xx, or a
    non-JSON/malformed body all degrade to [] (mirrors _send / _subaccount_id_for).
    subAccountId is omitted when None → company/business scope, matching /chat.
    """
    secret = _bridge_secret()
    if not secret:
        logger.warning("cortex_bridge: history skipped — WBIT_BRIDGE_SECRET not configured")
        return []

    company_id = _resolve_company_for_chat(db, org_id)
    if not company_id:
        return []

    body: dict = {"companyId": company_id, "limit": limit}
    if sub_account_id:
        body["subAccountId"] = sub_account_id

    headers = {"Content-Type": "application/json", "x-wbit-bridge-secret": secret}

    try:
        async with httpx.AsyncClient(timeout=_timeout_s()) as client:
            resp = await client.post(_history_url(), json=body, headers=headers)
    except httpx.TimeoutException:
        logger.warning("cortex_bridge: history request timed out")
        return []
    except httpx.RequestError as e:
        logger.warning(f"cortex_bridge: history request error: {e}")
        return []

    if resp.status_code not in (200, 201):
        logger.warning(f"cortex_bridge: history returned {resp.status_code}")
        return []

    try:
        data = resp.json()
    except ValueError:
        logger.warning("cortex_bridge: history returned non-JSON body")
        return []

    runs = data.get("runs") if isinstance(data, dict) else None
    return runs if isinstance(runs, list) else []
