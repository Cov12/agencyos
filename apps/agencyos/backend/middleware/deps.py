"""Request-scope dependencies for AgencyOS routers."""

import logging
import os

import jwt as pyjwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .tenant import get_tenant_session
from ..services.organizations import OrganizationsService

logger = logging.getLogger(__name__)

_OWUI_JWT_ALGORITHM = "HS256"


def _owui_session_secret() -> str:
    """The secret the OWUI app signs its session tokens with (WEBUI_SECRET_KEY).

    Prod requests to AgencyOS carry an OWUI SESSION token (payload {"id": user.id},
    signed WEBUI_SECRET_KEY) — NOT a Portal JWT — so to recover the caller's identity
    we must verify that token with the SAME secret create_token uses
    (open_webui.utils.auth.SESSION_SECRET == WEBUI_SECRET_KEY, auth.py:51,203).

    Resolved lazily and defensively: importing open_webui.utils.auth at module load
    would drag in the full backend dep tree and break the AgencyOS unit-test env
    (apps/agencyos/conftest.py stubs only open_webui.internal.db). We therefore mirror
    env.py's exact resolution off os.environ, which the running app has already
    populated (env.py runs load_dotenv at import), and which tests control directly.
    """
    return (
        os.environ.get("WEBUI_SECRET_KEY")
        or os.environ.get("WEBUI_JWT_SECRET_KEY")
        or "t0p-s3cr3t"
    )


def _resolve_owui_user_id(request: Request):
    """Recover the OWUI user.id from the request's OWUI session token.

    Mirrors open_webui.utils.auth.get_current_user token extraction (bearer header,
    else the `token` cookie) but WITHOUT a hard dependency: get_verified_user/
    get_current_user raise 401 on a missing/invalid token, which would pre-empt the
    escape-hatch / rollout-grace behavior below (we need to fall through to the flag,
    not 401). So we decode softly and return None when no valid OWUI token is present.

    Returns the OWUI user.id (str) or None.
    """
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer ") :].strip()
    if not token:
        token = request.cookies.get("token")
    if not token:
        return None

    try:
        data = pyjwt.decode(
            token, _owui_session_secret(), algorithms=[_OWUI_JWT_ALGORITHM]
        )
    except Exception:
        # Not a valid OWUI session token (e.g. it's a Portal JWT, or expired/forged).
        return None

    if isinstance(data, dict):
        return data.get("id")
    return None


def _escape_hatch_enabled() -> bool:
    return os.environ.get("AGENCYOS_DEV_ALLOW_HEADER_AUTH") == "1"


def require_app_access(required_app: str):
    """
    FastAPI dep factory. 403s unless the caller is entitled to `required_app`.

    Three identity paths (issue #45):

    1. LEGACY Portal-JWT path (request.state.portal_auth present): unchanged —
       the JWT's app_access claim decides (portal_auth.has_app_access), for
       back-compat with the direct Portal-JWT callers.

    2. OWUI-session path (portal_auth None, an OWUI user resolves): the session
       token carries no app_access claim, so entitlement is read from the DB —
       the requested org's cached AgencyOSOrganization.app_access column (written
       at portal-exchange). A user with >=1 membership row is enforced against it;
       a user with NO membership rows falls to the rollout-grace escape hatch.

    3. Neither identity resolves: 403 unless the AGENCYOS_DEV_ALLOW_HEADER_AUTH=1
       escape hatch is set (dev/test / rollout grace — NEVER a prod default).
    """

    def _dep(request: Request, db: Session = Depends(get_tenant_session)):
        portal_auth = getattr(request.state, "portal_auth", None)

        # 1. LEGACY Portal-JWT path — unchanged.
        if portal_auth is not None:
            if not portal_auth.has_app_access(required_app):
                logger.info(
                    "require_app_access[%s] denied for user=%s org=%s",
                    required_app, portal_auth.user_id, portal_auth.org_id,
                )
                raise HTTPException(
                    status_code=403, detail=f"App access denied: {required_app}"
                )
            return

        owui_user_id = _resolve_owui_user_id(request)

        # 3. No identity at all.
        if not owui_user_id:
            if _escape_hatch_enabled():
                logger.warning(
                    "require_app_access[%s]: no portal_auth and no OWUI user; allowing "
                    "via AGENCYOS_DEV_ALLOW_HEADER_AUTH escape hatch",
                    required_app,
                )
                return
            logger.info(
                "require_app_access[%s] denied: unauthenticated (no portal_auth, no OWUI user)",
                required_app,
            )
            raise HTTPException(
                status_code=403, detail=f"App access denied: {required_app}"
            )

        # 2. OWUI-session path.
        members = OrganizationsService.get_user_orgs(db, owui_user_id)
        if not members:
            # Un-provisioned user — rollout grace (or fail-closed with the flag off).
            if _escape_hatch_enabled():
                logger.warning(
                    "require_app_access[%s]: OWUI user=%s has no membership; allowing via "
                    "AGENCYOS_DEV_ALLOW_HEADER_AUTH rollout grace",
                    required_app, owui_user_id,
                )
                return
            logger.info(
                "require_app_access[%s] denied: OWUI user=%s has no membership",
                required_app, owui_user_id,
            )
            raise HTTPException(
                status_code=403, detail=f"App access denied: {required_app}"
            )

        # Member: read the requested org's cached app_access. (require_org_access,
        # composed alongside, enforces that the requested org is one of the caller's.)
        requested_org_id = (
            request.query_params.get("org_id")
            or request.path_params.get("org_id")
        )
        org = (
            OrganizationsService.get_org_by_id(db, requested_org_id)
            if requested_org_id
            else None
        )
        org_app_access = list(getattr(org, "app_access", None) or []) if org else []
        if required_app not in org_app_access:
            logger.info(
                "require_app_access[%s] denied for OWUI user=%s org=%s (org apps=%s)",
                required_app, owui_user_id, requested_org_id, org_app_access,
            )
            raise HTTPException(
                status_code=403, detail=f"App access denied: {required_app}"
            )
        return

    return _dep


def require_org_access(
    request: Request,
    db: Session = Depends(get_tenant_session),
):
    """
    FastAPI dependency that binds the requested internal org_id to the caller's real
    identity (issue #41 IDOR fix, extended to the OWUI-session path in issue #45).

    The tenant-scoped handlers all trust an `org_id` (the AgencyOS-INTERNAL row id)
    that arrives as a query param (departments/proposals/cortex-approvals/...) or a
    path param (`/orgs/{org_id}/...`) and filter their queries on it. Nothing else
    proves the requested org BELONGS to the caller. This dep closes that hole. It must
    be composed ALONGSIDE get_tenant_session + require_app_access, not as a replacement.

    Three identity paths:

    1. LEGACY Portal-JWT path (request.state.portal_auth present): unchanged — the JWT's
       org_id claim is the Portal CUID; require row.portal_org_id == portal_auth.org_id.
       Fail-closed: a missing org_id, an unknown org, or an org owned by a different
       Portal CUID all 403.

    2. OWUI-session path (portal_auth None, an OWUI user resolves): load the user's
       AgencyOSMember org_ids.
         - If the user HAS >=1 membership row: the requested internal org_id MUST be one
           of them, else 403. (This is the real IDOR enforcement on the prod OWUI path.)
         - If the user has NO membership rows: rollout grace — allow iff
           AGENCYOS_DEV_ALLOW_HEADER_AUTH=1 (log a warning), else 403.

    3. Neither identity resolves: 403 unless the escape hatch is set.
    """
    portal_auth = getattr(request.state, "portal_auth", None)
    # Match how handlers receive the internal org id: query param first (departments,
    # proposals, cortex-approvals, employee-tabs, dashboard/*), else the path param
    # (/orgs/{org_id}/...).
    requested_org_id = (
        request.query_params.get("org_id")
        or request.path_params.get("org_id")
    )

    # 1. LEGACY Portal-JWT path — unchanged.
    if portal_auth is not None:
        if not requested_org_id:
            logger.info(
                "require_org_access denied: no org_id on request for user=%s portal_org=%s",
                portal_auth.user_id, portal_auth.org_id,
            )
            raise HTTPException(
                status_code=403, detail="Org access denied: missing org_id"
            )
        org = OrganizationsService.get_org_by_id(db, requested_org_id)
        if org is None or org.portal_org_id != portal_auth.org_id:
            logger.info(
                "require_org_access denied: user=%s portal_org=%s requested internal org=%s "
                "(owner_portal_org=%s)",
                portal_auth.user_id, portal_auth.org_id, requested_org_id,
                getattr(org, "portal_org_id", None),
            )
            raise HTTPException(status_code=403, detail="Org access denied")
        return

    owui_user_id = _resolve_owui_user_id(request)

    # 3. No identity at all.
    if not owui_user_id:
        if _escape_hatch_enabled():
            logger.warning(
                "require_org_access: no portal_auth and no OWUI user; allowing via "
                "AGENCYOS_DEV_ALLOW_HEADER_AUTH escape hatch (org_id=%s)",
                requested_org_id,
            )
            return
        logger.info(
            "require_org_access denied: unauthenticated (no portal_auth, no OWUI user)"
        )
        raise HTTPException(status_code=403, detail="Org access denied")

    # 2. OWUI-session path.
    member_org_ids = {
        m.org_id for m in OrganizationsService.get_user_orgs(db, owui_user_id)
    }
    if member_org_ids:
        # Real IDOR enforcement: the requested org must be one the caller belongs to.
        if requested_org_id and requested_org_id in member_org_ids:
            return
        logger.info(
            "require_org_access denied: OWUI user=%s requested org=%s not in member orgs %s",
            owui_user_id, requested_org_id, member_org_ids,
        )
        raise HTTPException(status_code=403, detail="Org access denied")

    # No membership rows — rollout grace (or fail-closed with the flag off).
    if _escape_hatch_enabled():
        logger.warning(
            "require_org_access: OWUI user=%s has no membership; allowing via "
            "AGENCYOS_DEV_ALLOW_HEADER_AUTH rollout grace (org_id=%s)",
            owui_user_id, requested_org_id,
        )
        return
    logger.info(
        "require_org_access denied: OWUI user=%s has no membership", owui_user_id
    )
    raise HTTPException(status_code=403, detail="Org access denied")
