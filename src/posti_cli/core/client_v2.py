"""HTTP client for Posti 2025-04 API (OAuth 2.0 authenticated)."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from posti_cli.core.client import PostiAPIError, extract_error_detail
from posti_cli.core.oauth import OAuthToken, make_oauth_token

DEFAULT_BASE_URL = "https://gateway.posti.fi/2025-04"


@dataclass
class PostiV2Client:
    """HTTP client for Posti 2025-04 API."""

    url: str
    oauth: OAuthToken

    def _request(
        self,
        path: str,
        method: str = "GET",
        data: dict | list | None = None,
        params: dict | None = None,
        headers_extra: dict | None = None,
    ) -> dict | list:
        """Make an authenticated request to Posti 2025-04 API."""
        url = f"{self.url}{path}"
        if params:
            qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
            url = f"{url}?{qs}"

        body = json.dumps(data).encode("utf-8") if data is not None else None
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "posti-cli/1.1",
            "Authorization": f"Bearer {self.oauth.access_token}",
        }
        if headers_extra:
            headers.update(headers_extra)

        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = extract_error_detail(e)
            raise PostiAPIError(detail, status_code=e.code) from e
        except urllib.error.URLError as e:
            raise PostiAPIError(f"Connection error: {e.reason}") from e

        # Check for error response patterns
        if isinstance(result, dict):
            # 2025-04 API pattern: {"errorCode": ..., "message": ...}
            if "errorCode" in result:
                msg = result.get("message", result.get("errorCode", "Unknown error"))
                raise PostiAPIError(f"API error: {msg}", status_code=200)
            # Shipping API pattern: {"errors": [...]}
            if "errors" in result:
                raise PostiAPIError(
                    f"API error: {json.dumps(result['errors'])}",
                    status_code=200,
                )

        return result


def make_v2_client(
    url: str | None = None,
    oauth_client_id: str | None = None,
    oauth_client_secret: str | None = None,
) -> PostiV2Client:
    """Create a PostiV2Client from explicit args or environment variables."""
    url = url or os.environ.get("POSTI_V2_URL", DEFAULT_BASE_URL)
    url = url.rstrip("/")

    oauth = make_oauth_token(
        client_id=oauth_client_id,
        client_secret=oauth_client_secret,
    )

    return PostiV2Client(url=url, oauth=oauth)
