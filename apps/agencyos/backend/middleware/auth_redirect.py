"""AgencyOS UI authentication redirect middleware.

Redirects unauthenticated AgencyOS UI requests to the WBIT Portal sign-in page.
API routes remain handled by JWTAuthMiddleware.
"""

from __future__ import annotations

import logging
import os
from typing import Iterable
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

import jwt as pyjwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

logger = logging.getLogger("agencyos.auth_redirect")

JWT_ALGORITHM = "HS256"


class AuthRedirectMiddleware(BaseHTTPMiddleware):
    """Redirect unauthenticated AgencyOS UI traffic to Portal authentication."""

    def __init__(
        self,
        app,
        portal_url: str = "https://portal.wbit.app",
        cookie_name: str = "agencyos_token",
        cookie_max_age: int = 86400,
        excluded_paths: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.portal_url = portal_url.rstrip("/")
        self.cookie_name = cookie_name
        self.cookie_max_age = cookie_max_age
        self.excluded_paths = excluded_paths or ["/agencyos/auth/callback"]

    async def dispatch(self, request: Request, call_next) -> Response:
        """Validate UI auth token or redirect to Portal sign-in."""
        if not self._should_handle_request(request):
            return await call_next(request)

        query_token = request.query_params.get("token")
        if query_token:
            if self._is_valid_jwt(query_token):
                response = RedirectResponse(
                    url=self._url_without_token(request),
                    status_code=303,
                )
                response.set_cookie(
                    key=self.cookie_name,
                    value=query_token,
                    max_age=self.cookie_max_age,
                    httponly=True,
                    secure=True,
                    samesite="lax",
                    path="/",
                )
                return response
            logger.warning("Invalid token provided via query param on path=%s", request.url.path)

        auth_token = self._get_bearer_token(request)
        if auth_token and self._is_valid_jwt(auth_token):
            return await call_next(request)

        cookie_token = request.cookies.get(self.cookie_name)
        if cookie_token and self._is_valid_jwt(cookie_token):
            return await call_next(request)

        return RedirectResponse(
            url=self._build_portal_signin_url(request),
            status_code=307,
        )

    def _should_handle_request(self, request: Request) -> bool:
        """Return True only for AgencyOS UI HTTP routes needing auth redirect."""
        path = request.url.path

        if request.method.upper() == "OPTIONS":
            return False

        # BaseHTTPMiddleware handles HTTP requests; keep explicit check for upgrades.
        if request.headers.get("upgrade", "").lower() == "websocket":
            return False

        if not path.startswith("/agencyos/"):
            return False

        # Explicitly keep API paths out of this middleware.
        if path.startswith("/api/agencyos/"):
            return False

        if path in self.excluded_paths:
            return False

        if path.endswith("/health") or path == "/health":
            return False

        if self._is_static_path(path):
            return False

        return True

    @staticmethod
    def _is_static_path(path: str) -> bool:
        """Best-effort static-asset path detection for UI resources."""
        static_prefixes: Iterable[str] = (
            "/agencyos/static/",
            "/agencyos/assets/",
            "/static/",
            "/assets/",
        )
        if any(path.startswith(prefix) for prefix in static_prefixes):
            return True

        static_files = {
            "/favicon.ico",
            "/robots.txt",
            "/manifest.json",
            "/agencyos/favicon.ico",
        }
        return path in static_files

    def _is_valid_jwt(self, token: str) -> bool:
        """Validate JWT with HS256 using shared AgencyOS secret."""
        secret = os.environ.get("AGENCYOS_JWT_SECRET") or os.environ.get("JWT_SECRET", "")
        if not secret:
            logger.warning("AGENCYOS_JWT_SECRET/JWT_SECRET not configured")
            return False

        try:
            pyjwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
            return True
        except pyjwt.ExpiredSignatureError:
            logger.info("JWT expired during UI auth redirect validation")
            return False
        except pyjwt.InvalidTokenError as exc:
            logger.info("Invalid JWT during UI auth redirect validation: %s", exc)
            return False

    @staticmethod
    def _get_bearer_token(request: Request) -> str | None:
        """Extract bearer token from Authorization header if present."""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()
        return None

    @staticmethod
    def _url_without_token(request: Request) -> str:
        """Return current URL without the token query parameter."""
        split = urlsplit(str(request.url))
        kept_params = [(k, v) for k, v in parse_qsl(split.query, keep_blank_values=True) if k != "token"]
        new_query = urlencode(kept_params, doseq=True)
        return urlunsplit((split.scheme, split.netloc, split.path, new_query, split.fragment))

    def _build_portal_signin_url(self, request: Request) -> str:
        """Build Portal sign-in URL with callback to the current page."""
        current_url = str(request.url)
        query = urlencode({"redirect_url": current_url})
        return f"{self.portal_url}/auth/sign-in?{query}"
