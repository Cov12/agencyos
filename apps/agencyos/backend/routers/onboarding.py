"""
AgencyOS Onboarding Routes (P1 — capture + seed + completion)

The "warm assistant day one" slice: capture the org's onboarding context once, seed it
into Contexta (mem0) through the Cortex bridge so the assistant already knows the
business on the first turn, and record completion server-side.

Completion used to live in an ephemeral frontend store (onboardingComplete), so it was
lost on reload and never shared across devices. It now lives in
AgencyOSOrganization.settings["onboarding"] — a JSON column that already exists
(models/db.py), so this ships with NO migration.

SCOPE (P1): org-level only. The question set is small and FIXED — no LLM here (the
assisted path is P3) and no agent provisioning (P2). Seeding is best-effort: completion
is committed even when the seed call fails, and the response reports `seeded` so a
later drop can retry.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..middleware.tenant import get_tenant_session
from ..middleware.deps import require_org_access
from ..models.db import AgencyOSOrganization, now_ms
from ..services import cortex_bridge

logger = logging.getLogger("agencyos.onboarding")

router = APIRouter(prefix="/api/agencyos/orgs", tags=["agencyos-onboarding"])

# Key inside AgencyOSOrganization.settings holding completion state. Deliberately a
# JSON-column key, not a new column (same call as subaccount_sync's synced-at marker).
ONBOARDING_KEY = "onboarding"
# Bump when the captured question set changes, so a later version can re-ask/re-seed.
ONBOARDING_VERSION = 1

# Key holding the raw captured answers, kept so seeding can be retried later without
# re-interviewing the user (P1 never retries; it just records enough to make that easy).
ONBOARDING_PROFILE_KEY = "onboardingProfile"

# The FIXED P1 question set: answer key -> the fact label seeded into Contexta. Order is
# the seeding order, so the memory reads top-down like a briefing. Adding a question means
# adding one row here and one field in the wizard — nothing else.
FACT_LABELS: list[tuple[str, str]] = [
    ("orgName", "Business name"),
    ("industry", "Industry"),
    ("whatBusinessDoes", "What the business does"),
    ("customers", "Who the customers are"),
    ("primaryGoal", "Primary goal right now"),
    ("dayToDay", "Main day-to-day work"),
]

# Org profile fields worth mirroring to the top level of settings (read by other
# surfaces); everything else stays inside ONBOARDING_PROFILE_KEY.
PROFILE_FIELDS = ("industry",)

# Defensive cap on one answer, so a pasted essay can't bloat the settings JSON or the
# seeded memory. Answers are user free text.
_MAX_ANSWER_CHARS = 2000


class OnboardingRequest(BaseModel):
    answers: dict = {}
    # OPTIONAL and unwired in P1: the org-level flow never sends it, so seeding lands at
    # company/business scope (Hermes stores it under companyId:_business). Accepted now so
    # per-sub-account seeding is a later drop-in with no contract change.
    subAccountId: Optional[str] = None


def _clean_answer(value) -> Optional[str]:
    """Normalize one raw answer to a concise string, or None if it carries no signal.
    Non-string scalars are stringified (a select may send a number/bool); dicts/lists are
    dropped — P1 captures free text and selects only."""
    if value is None or isinstance(value, (dict, list)):
        return None
    text = value.strip() if isinstance(value, str) else str(value).strip()
    if not text:
        return None
    return text[:_MAX_ANSWER_CHARS]


def _build_facts(answers: dict) -> list[str]:
    """Turn the captured answers into one concise fact string per meaningful answer
    ("Industry: SaaS"), in FACT_LABELS order. Empty/blank/unknown keys are skipped, so a
    user who answers two of six questions seeds exactly two facts."""
    if not isinstance(answers, dict):
        return []
    facts: list[str] = []
    for key, label in FACT_LABELS:
        text = _clean_answer(answers.get(key))
        if text:
            facts.append(f"{label}: {text}")
    return facts


def _captured_profile(answers: dict) -> dict:
    """The cleaned subset of answers we persist — only the known P1 keys, so an arbitrary
    client payload can't write unbounded junk into org.settings."""
    if not isinstance(answers, dict):
        return {}
    out: dict = {}
    for key, _label in FACT_LABELS:
        text = _clean_answer(answers.get(key))
        if text:
            out[key] = text
    return out


def _get_org(db: Session, org_id: str) -> AgencyOSOrganization:
    org = (
        db.query(AgencyOSOrganization)
        .filter(AgencyOSOrganization.id == org_id)
        .one_or_none()
    )
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


def _onboarding_state(org: AgencyOSOrganization) -> dict:
    """Read completion state out of settings, defaulting to not-completed. Tolerates a
    NULL/non-dict settings column and a legacy non-dict onboarding value."""
    settings = org.settings if isinstance(org.settings, dict) else {}
    state = settings.get(ONBOARDING_KEY)
    if not isinstance(state, dict):
        return {"completed": False, "completedAt": None, "version": ONBOARDING_VERSION}
    return {
        "completed": bool(state.get("completed", False)),
        "completedAt": state.get("completedAt"),
        "version": state.get("version", ONBOARDING_VERSION),
    }


@router.get("/{org_id}/onboarding", dependencies=[Depends(require_org_access)])
async def get_onboarding(
    org_id: str,
    db: Session = Depends(get_tenant_session),
):
    """Whether this org has finished onboarding — the gate the LockScreen reads instead
    of the old ephemeral client store."""
    return _onboarding_state(_get_org(db, org_id))


@router.post("/{org_id}/onboarding", dependencies=[Depends(require_org_access)])
async def complete_onboarding(
    org_id: str,
    data: OnboardingRequest,
    db: Session = Depends(get_tenant_session),
):
    """Capture the onboarding answers, seed them into Contexta, and mark onboarding done.

    Ordering matters: we seed BEFORE committing completion so `seeded` reflects this
    request's real outcome, but completion is committed either way — a Cortex outage must
    not trap a paying customer in the wizard. `seeded: false` is the retry signal.
    """
    org = _get_org(db, org_id)

    facts = _build_facts(data.answers)
    profile = _captured_profile(data.answers)

    sub_account_id = (data.subAccountId or "").strip() or None

    # Best-effort by contract: seed_contexta swallows every failure into {ok: False}.
    seed_result = await cortex_bridge.seed_contexta(
        db, org_id, facts, sub_account_id=sub_account_id
    )
    seeded = bool(seed_result.get("ok"))
    if not seeded:
        logger.warning(
            "onboarding: contexta seed failed for org %s (%s facts): %s",
            org_id, len(facts), seed_result.get("error"),
        )

    # The JSON column is not mutation-tracked — assign a NEW dict, never mutate in place,
    # or the write is silently dropped. Existing settings keys are preserved.
    current = org.settings if isinstance(org.settings, dict) else {}
    updated = {**current}
    if profile:
        updated[ONBOARDING_PROFILE_KEY] = profile
        for field in PROFILE_FIELDS:
            if profile.get(field):
                updated[field] = profile[field]
    updated[ONBOARDING_KEY] = {
        "completed": True,
        "completedAt": now_ms(),
        "version": ONBOARDING_VERSION,
    }
    org.settings = updated
    org.updated_at = now_ms()
    db.commit()

    return {
        "ok": True,
        "completed": True,
        "seeded": seeded,
        "factCount": len(facts),
    }
