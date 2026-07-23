"""
AgencyOS Portal Auth Callback Router

Handles the /agencyos/auth/callback endpoint that receives Portal JWTs
and exchanges them for OpenWebUI session tokens.
"""

import datetime
import logging
import os
import time
import uuid

import jwt as pyjwt
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from open_webui.internal.db import get_session
from open_webui.models.users import Users
from open_webui.models.auths import Auths
from open_webui.utils.auth import get_password_hash, create_token
from open_webui.utils.groups import apply_default_group_assignment
from open_webui.utils.misc import parse_duration
from open_webui.env import (
    WEBUI_AUTH_COOKIE_SAME_SITE,
    WEBUI_AUTH_COOKIE_SECURE,
)

logger = logging.getLogger("agencyos.auth_callback")

router = APIRouter(prefix="/agencyos/auth", tags=["agencyos-auth"])


@router.get("/callback")
async def portal_auth_callback(
    request: Request,
    token: str = None,
):
    """
    Handle Portal SSO callback.

    Flow:
    1. Portal redirects here with ?token=<portal_jwt>
    2. Validate the Portal JWT
    3. Find or create OpenWebUI user
    4. Create OpenWebUI session and set cookie
    5. Redirect to /agencyos/
    """
    logger.info(f"[AuthCallback] Hit /agencyos/auth/callback, token present: {bool(token)}")

    if not token:
        logger.warning("Auth callback called without token")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing token parameter",
        )

    # Get the shared JWT secret
    jwt_secret = os.environ.get("JWT_SECRET", "")
    if not jwt_secret:
        logger.error("JWT_SECRET not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration",
        )

    # Validate Portal JWT
    try:
        payload = pyjwt.decode(token, jwt_secret, algorithms=["HS256"])
    except pyjwt.ExpiredSignatureError:
        logger.warning("Portal JWT expired")
        # Redirect to portal sign-in
        portal_url = os.environ.get("PORTAL_URL", "https://portal.wbit.app")
        return RedirectResponse(
            url=f"{portal_url}/sign-in?redirect_url={request.url}",
            status_code=307,
        )
    except pyjwt.InvalidTokenError as e:
        logger.warning(f"Invalid Portal JWT: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    # Extract user info
    email = payload.get("email", "").lower()
    name = payload.get("name", "")
    portal_user_id = payload.get("sub", "")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token missing email",
        )

    if not name:
        name = email.split("@")[0]

    logger.info(f"Portal auth callback: email={email}, name={name}, sub={portal_user_id}")

    # Get database session
    db: Session = next(get_session())

    try:
        # Find or create user
        user = Users.get_user_by_email(email, db=db)

        if not user:
            logger.info(f"Creating new OWUI user from portal: {email}")
            role = "admin" if not Users.has_users(db=db) else "user"

            user = Auths.insert_new_auth(
                email=email,
                password=get_password_hash(str(uuid.uuid4())),
                name=name,
                profile_image_url="/user.png",
                role=role,
                db=db,
            )

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user",
                )

            # Apply default group assignment
            apply_default_group_assignment(
                request.app.state.config.DEFAULT_GROUP_ID,
                user.id,
                db=db,
            )
            logger.info(f"Created OWUI user {user.id}")
        else:
            # Update name if changed
            if user.name != name:
                Users.update_user_by_id(user.id, {"name": name}, db=db)

        # Persist AgencyOS org membership + per-org app_access from the validated
        # Portal JWT, keyed on the OWUI user.id (agencyos#50). portal_auth_callback is the
        # single AgencyOS login path, so this is the sole provisioning entry point.
        # Defensive: the helper never raises (logs + rolls back), so login is never broken.
        from ..services.organizations import OrganizationsService

        OrganizationsService.provision_from_portal(db, user.id, payload)

        # Mirror the org's Portal sub-account roster locally (agencyos#67). This is the ONE
        # place in prod that holds the raw Portal JWT (`token`) needed to pull Portal's
        # GET /api/subaccounts — the request path only ever sees the OWUI session token, so
        # the old get_tenant_session hook never fired in prod and the mirror stayed empty
        # (dashboard showed 0 sub-accounts). maybe_sync is throttled per-org and never
        # raises, so an unreachable Portal just leaves the mirror as-is, never breaks login.
        try:
            portal_cuid = payload.get("org_id")
            if portal_cuid:
                org = OrganizationsService.get_org_by_portal_id(db, portal_cuid)
                if org is not None:
                    from ..services.subaccount_sync import maybe_sync

                    maybe_sync(db, org.id, portal_cuid, token)
        except Exception as e:
            logger.warning(f"AgencyOS sub-account sync at login failed (non-fatal): {e}")

        # Create OWUI session token
        expires_delta = parse_duration(request.app.state.config.JWT_EXPIRES_IN)
        expires_at = None
        if expires_delta:
            expires_at = int(time.time()) + int(expires_delta.total_seconds())

        owui_token = create_token(
            data={"id": user.id},
            expires_delta=expires_delta,
        )

        # Create redirect response
        response = RedirectResponse(url="/agencyos/", status_code=303)

        # Set cookie with path="/" so it's available on all paths
        # This is critical because the callback is at /agencyos/auth/callback
        # but the UI is at /agencyos/
        datetime_expires_at = (
            datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
            if expires_at
            else None
        )
        response.set_cookie(
            key="token",
            value=owui_token,
            expires=datetime_expires_at,
            httponly=False,  # Required for frontend JavaScript to read the token
            samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
            secure=WEBUI_AUTH_COOKIE_SECURE,
            path="/",  # Critical: make cookie available on all paths
        )

        logger.info(f"Portal auth success: user={user.id}, token set with path=/, redirecting to /agencyos/")
        return response

    finally:
        db.close()
