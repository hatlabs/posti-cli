"""Posti API shared error types and helpers."""

import json
import urllib.error


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
