"""OAuth 2.0 client_credentials token handling for Posti 2025-04 API."""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from posti_cli.core.client import PostiAPIError

TOKEN_URL = "https://gateway-auth.posti.fi/api/v1/token"


class OAuthToken:
    """Manages OAuth 2.0 token acquisition and caching."""

    def __init__(self, client_id: str, client_secret: str, token_url: str = TOKEN_URL):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self._access_token: str | None = None
        self._expires_at: float = 0

    @property
    def access_token(self) -> str:
        """Return a valid access token, refreshing if needed."""
        if self._access_token and time.time() < self._expires_at:
            return self._access_token
        self._fetch_token()
        return self._access_token

    def _fetch_token(self) -> None:
        """Fetch a new token using client_credentials grant."""
        body = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        req = urllib.request.Request(
            self.token_url, data=body, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                err_body = str(e)
            raise PostiAPIError(
                f"OAuth token request failed: HTTP {e.code}: {err_body[:500]}",
                status_code=e.code,
            ) from e
        except urllib.error.URLError as e:
            raise PostiAPIError(f"OAuth connection error: {e.reason}") from e

        self._access_token = data["access_token"]
        # Refresh 60 seconds before actual expiry
        expires_in = data.get("expires_in", 3600)
        self._expires_at = time.time() + expires_in - 60


def make_oauth_token(
    client_id: str | None = None,
    client_secret: str | None = None,
) -> OAuthToken:
    """Create an OAuthToken from explicit args or environment variables."""
    client_id = client_id or os.environ.get("POSTI_OAUTH_CLIENT_ID")
    client_secret = client_secret or os.environ.get("POSTI_OAUTH_CLIENT_SECRET")

    if not client_id:
        raise PostiAPIError(
            "POSTI_OAUTH_CLIENT_ID not set. Provide --oauth-client-id or set the env var."
        )
    if not client_secret:
        raise PostiAPIError(
            "POSTI_OAUTH_CLIENT_SECRET not set. Provide --oauth-client-secret or set the env var."
        )

    return OAuthToken(client_id=client_id, client_secret=client_secret)
