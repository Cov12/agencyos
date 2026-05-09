"""
AgencyOS Portal Auth Callback Router

Handles the /agencyos/auth/callback endpoint that receives Portal JWTs
and exchanges them for OpenWebUI session tokens.
"""

import logging
import os
import uuid

import jwt as pyjwt
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from open_webui.internal.db import get_session
from open_webui.models.users import Users
from open_webui.models.auths import Auths
from open_webui.utils.auth import get_password_hash
from open_webui.routers.auths import create_session_response

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
            logger.info(f"Created OWUI user {user.id}")
        else:
            # Update name if changed
            if user.name != name:
                Users.update_user_by_id(user.id, {"name": name}, db=db)

        # Create session response with cookie
        response = RedirectResponse(url="/agencyos/", status_code=303)

        # Create session and set cookie
        session_data = create_session_response(
            request=request,
            user=user,
            db=db,
            response=response,
            set_cookie=True,
        )

        logger.info(f"Portal auth success: user={user.id}, redirecting to /agencyos/")
        return response

    finally:
        db.close()
