"""Posti Pro SSO authentication — OAuth 2.0 authorization code flow.

Authenticates against todentaminen.posti.fi SSO using form-based login,
then exchanges the auth code at auth-service.posti.fi for JWT tokens
used to call the graphql.posti.fi GraphQL API.
"""

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from urllib.parse import urlparse, parse_qs

from posti_cli.core.client import PostiAPIError

LOGIN_URL = "https://auth-service.posti.fi/api/v1/login"
TOKEN_V2_URL = "https://auth-service.posti.fi/api/v1/token_v2"
CLIENT_ID = "5b05bc63-9195-4687-9ac0-df872a6f936e"
TOKEN_EXPIRY_BUFFER = 60
DEFAULT_TOKEN_TTL = 3600


class ProAuth:
    """Manages Posti Pro authentication tokens."""

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self._id_token: str | None = None
        self._role_token: str | None = None
        self._expires_at: float = 0

    def get_headers(self) -> dict[str, str]:
        """Return auth headers for GraphQL requests, authenticating if needed."""
        if not self._id_token or time.time() >= self._expires_at:
            self.authenticate()
        return {
            "Authorization": self._role_token,
            "x-omaposti-token": f"Bearer {self._id_token}",
        }

    def authenticate(self) -> None:
        """Execute the full SSO login + token exchange flow."""
        cookie_jar = CookieJar()
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cookie_jar),
        )

        # Step 1: Initiate login — follow redirects to SSO
        login_params = urllib.parse.urlencode({
            "locale": "fi",
            "redirect_uri": "https://pro.posti.fi/",
        })
        login_req = urllib.request.Request(
            f"{LOGIN_URL}?{login_params}",
            headers={"Accept": "text/html"},
        )
        try:
            resp = opener.open(login_req, timeout=30)
            sso_url = resp.url
        except urllib.error.URLError as e:
            raise PostiAPIError(f"SSO login initiation failed: {e}") from e

        # Step 2: Extract session ID from SSO URL
        session_id = self._extract_session_id(sso_url)
        if not session_id:
            raise PostiAPIError(
                f"Could not extract SSO session ID from URL: {sso_url}"
            )

        # Step 3: Submit credentials
        submit_url = (
            f"https://todentaminen.posti.fi/uas/authn/{session_id}/submit"
            f"?entityID={CLIENT_ID}&locale=fi"
        )
        submit_body = urllib.parse.urlencode({
            "username": self.username,
            "password": self.password,
            "method": "passwordsql",
        }).encode("utf-8")
        submit_req = urllib.request.Request(
            submit_url,
            data=submit_body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            resp = opener.open(submit_req, timeout=30)
            final_url = resp.url
            resp_body = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            raise PostiAPIError(
                f"SSO login failed (HTTP {e.code}). Check credentials."
            ) from e
        except urllib.error.URLError as e:
            raise PostiAPIError(f"SSO login failed: {e}") from e

        # The SSO success page contains a form with the auth code and state
        # as hidden fields (auto-submitted by JavaScript in the browser).
        # Extract the fields and submit to the OIDC callback ourselves.
        code = self._extract_code(final_url)
        if not code:
            sso_code = self._extract_code_from_form(resp_body)
            state = self._extract_form_field(resp_body, "state")
            if not sso_code:
                raise PostiAPIError(
                    "SSO login succeeded but no auth code received. "
                    "Check credentials or account status."
                )

            # Submit SSO form to OIDC callback (GET with query params)
            callback_params = urllib.parse.urlencode({
                "app_id": "oppro-prd",
                "code": sso_code,
                "state": state or "",
            })
            callback_url = (
                f"https://auth-service.posti.fi/api/v1/oidc_callback"
                f"?{callback_params}"
            )
            try:
                resp = opener.open(callback_url, timeout=30)
                code = self._extract_code(resp.url)
            except urllib.error.URLError as e:
                raise PostiAPIError(
                    f"OIDC callback failed: {e}"
                ) from e

        if not code:
            raise PostiAPIError(
                "Auth flow completed but no final code received."
            )

        # Step 4: Exchange code for tokens
        token_body = urllib.parse.urlencode({"code": code}).encode("utf-8")
        token_req = urllib.request.Request(
            TOKEN_V2_URL,
            data=token_body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://pro.posti.fi/",
            },
            method="POST",
        )
        try:
            with opener.open(token_req, timeout=30) as resp:
                token_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                err_body = str(e)
            raise PostiAPIError(
                f"Token exchange failed (HTTP {e.code}): {err_body[:500]}"
            ) from e
        except urllib.error.URLError as e:
            raise PostiAPIError(f"Token exchange failed: {e}") from e

        self._parse_token_response(token_data)

    def _parse_token_response(self, data: dict) -> None:
        """Parse token_v2 response and store tokens."""
        id_token = data.get("id_token")
        if not id_token:
            raise PostiAPIError("Token response missing id_token")

        role_tokens = data.get("role_tokens", [])
        if not role_tokens:
            raise PostiAPIError("No role tokens in response")

        self._id_token = id_token
        self._role_token = role_tokens[0]["token"]
        expires_in = data.get("expires_in", DEFAULT_TOKEN_TTL)
        self._expires_at = time.time() + expires_in - TOKEN_EXPIRY_BUFFER

    @staticmethod
    def _extract_session_id(url: str) -> str | None:
        """Extract SSO session ID from redirect URL query or path."""
        parsed = urlparse(url)
        # Prefer _id query param (path may contain '*' placeholder)
        qs = parse_qs(parsed.query)
        ids = qs.get("_id", [])
        if ids:
            return ids[0]
        # Fallback: extract from path /uas/authn/{session_id}/view
        parts = parsed.path.split("/")
        for i, part in enumerate(parts):
            if part == "authn" and i + 1 < len(parts):
                sid = parts[i + 1]
                if sid != "*":
                    return sid
        return None

    @staticmethod
    def _extract_code(url: str) -> str | None:
        """Extract authorization code from redirect URL."""
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        codes = qs.get("code", [])
        return codes[0] if codes else None

    @staticmethod
    def _extract_code_from_form(html: str) -> str | None:
        """Extract authorization code from SSO success page form.

        The SSO returns a success page with a hidden form that JavaScript
        auto-submits. The code is in a hidden input field.
        """
        return ProAuth._extract_form_field(html, "code")

    @staticmethod
    def _extract_form_field(html: str, field_name: str) -> str | None:
        """Extract a hidden form field value by name."""
        tag_match = re.search(
            rf'<input[^>]*name="{field_name}"[^>]*/?>',
            html,
        )
        if not tag_match:
            return None
        value_match = re.search(r'value="([^"]+)"', tag_match.group(0))
        return value_match.group(1) if value_match else None


def make_pro_auth(
    username: str | None = None,
    password: str | None = None,
) -> ProAuth:
    """Create ProAuth from explicit args or environment variables."""
    username = username or os.environ.get("POSTI_PRO_USERNAME")
    password = password or os.environ.get("POSTI_PRO_PASSWORD")

    if not username:
        raise PostiAPIError(
            "POSTI_PRO_USERNAME not set. Set the environment variable."
        )
    if not password:
        raise PostiAPIError(
            "POSTI_PRO_PASSWORD not set. Set the environment variable."
        )

    return ProAuth(username=username, password=password)
