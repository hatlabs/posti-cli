"""Posti OmaPosti Pro HTTP API client."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


class PostiAPIError(Exception):
    """Raised when the Posti API returns an error."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def extract_error_detail(error: Exception) -> str:
    """Extract human-readable error from Posti API error responses."""
    if isinstance(error, urllib.error.HTTPError):
        try:
            body = error.read().decode("utf-8", errors="replace")
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return f"HTTP {error.code}: {body[:500] if 'body' in dir() else str(error)}"

        if isinstance(data, dict):
            if data.get("errors"):
                return json.dumps(data["errors"])
            if data.get("message"):
                return str(data["message"])

        return f"HTTP {error.code}: {body[:500]}"

    return str(error)


@dataclass
class PostiClient:
    """HTTP client for Posti OmaPosti Pro API."""

    url: str
    api_key: str
    customer_number: str

    def _request(
        self,
        path: str,
        method: str = "GET",
        data: dict | list | None = None,
        params: dict | None = None,
    ) -> dict | list:
        """Make an HTTP request to Posti and return parsed JSON.

        Posti API returns HTTP 200 with "errors" key on failure,
        so we check for that explicitly.
        """
        url = f"{self.url}{path}"
        if params:
            qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
            url = f"{url}?{qs}"

        body = json.dumps(data).encode("utf-8") if data is not None else None
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "posti-cli/1.0",
            "Authorization": self.api_key,
        }

        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = extract_error_detail(e)
            raise PostiAPIError(detail, status_code=e.code) from e
        except urllib.error.URLError as e:
            raise PostiAPIError(f"Connection error: {e.reason}") from e

        # Posti returns 200 with "errors" key on failure
        if isinstance(result, dict) and "errors" in result:
            raise PostiAPIError(
                f"API error: {json.dumps(result['errors'])}",
                status_code=200,
            )

        return result


def make_client(
    url: str | None = None,
    api_key: str | None = None,
    customer_number: str | None = None,
) -> PostiClient:
    """Create a PostiClient from explicit args or environment variables."""
    url = url or os.environ.get("POSTI_URL")
    api_key = api_key or os.environ.get("POSTI_API_KEY")
    customer_number = customer_number or os.environ.get("POSTI_CUSTOMER_NUMBER")

    if not url:
        raise PostiAPIError(
            "POSTI_URL not set. Provide --url or set the env var."
        )
    if not api_key:
        raise PostiAPIError(
            "POSTI_API_KEY not set. Provide --api-key or set the env var."
        )
    if not customer_number:
        raise PostiAPIError(
            "POSTI_CUSTOMER_NUMBER not set. Provide --customer-number or set the env var."
        )

    url = url.rstrip("/")

    return PostiClient(url=url, api_key=api_key, customer_number=customer_number)
