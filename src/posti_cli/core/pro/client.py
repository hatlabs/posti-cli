"""GraphQL client for Posti Pro API (graphql.posti.fi)."""

import json
import urllib.error
import urllib.request

from posti_cli.core.client import PostiAPIError
from posti_cli.core.pro.auth import ProAuth

GRAPHQL_URL = "https://graphql.posti.fi/graphql"


class ProClient:
    """HTTP client for Posti Pro GraphQL API."""

    def __init__(self, auth: ProAuth, url: str = GRAPHQL_URL):
        self.auth = auth
        self.url = url

    def execute(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query and return the response."""
        return self._execute_with_retry(query, variables or {})

    def _execute_with_retry(self, query: str, variables: dict) -> dict:
        """Execute query, retrying once on auth failure."""
        try:
            return self._do_request(query, variables)
        except PostiAPIError as e:
            if e.status_code in (401, 403):
                self.auth.authenticate()
                return self._do_request(query, variables)
            raise

    def _do_request(self, query: str, variables: dict) -> dict:
        """Send a single GraphQL request."""
        body = json.dumps({
            "query": query,
            "variables": variables,
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "posti-cli/1.1",
            **self.auth.get_headers(),
        }

        req = urllib.request.Request(
            self.url, data=body, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                err_body = str(e)
            raise PostiAPIError(
                f"GraphQL request failed (HTTP {e.code}): {err_body[:500]}",
                status_code=e.code,
            ) from e
        except urllib.error.URLError as e:
            raise PostiAPIError(f"Connection error: {e.reason}") from e

        # Check for GraphQL-level errors
        if isinstance(result, dict) and result.get("errors"):
            errors = result["errors"]
            msg = errors[0].get("message", "Unknown GraphQL error")
            error_type = errors[0].get("errorType", "")
            status = 401 if error_type in ("Unauthorized",) else None
            raise PostiAPIError(
                f"GraphQL error: {msg}",
                status_code=status,
            )

        return result
