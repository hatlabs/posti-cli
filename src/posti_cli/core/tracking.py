"""Public shipment tracking via the consumer GraphQL API (graphql.posti.fi).

This is the unauthenticated, recipient-facing tracking that powers
www.posti.fi/en/tracking. Unlike the Pro API (core/pro), it needs no login:
an anonymous token is minted on demand from auth-service.posti.fi. It is the
only Posti source that returns measured weight/dimensions for *inbound*
parcels (which never appear in the Pro corporate feed).

Query captured from live www.posti.fi traffic 2026-06-23.
"""

import json
import urllib.error
import urllib.request

from posti_cli.core.client import PostiAPIError

ANONYMOUS_TOKEN_URL = "https://auth-service.posti.fi/api/v1/anonymous_token"
GRAPHQL_URL = "https://graphql.posti.fi/graphql"

# Minimal field set — only what tracking and customs clearance need. The live
# site requests far more (pickup point, payments, call-to-action); partial
# selection is always valid in GraphQL, so the smaller query is less brittle.
SEARCH_SHIPMENTS_QUERY = """
query SearchShipments(
  $page: Int!
  $pageSize: Int!
  $type: ConsumerSearchTypeFilter!
  $searchTerms: [String!]!
  $locale: String
) {
  consumerSearchShipments(
    page: $page
    pageSize: $pageSize
    type: $type
    searchTerms: $searchTerms
    locale: $locale
  ) {
    totalHits
    hits {
      displayId
      displayName
      shipmentType
      status {
        main
        subStatus
      }
      measurements {
        size
        weight { unit value }
        height { unit value }
        width { unit value }
        length { unit value }
        volume { unit value }
        packageQuantity { unit value }
      }
      events {
        city
        eventDescription
        timestamp
      }
    }
  }
}
""".strip()


class TrackingClient:
    """GraphQL client for the consumer tracking API with anonymous auth.

    Tokens are minted lazily and refreshed once on a 401/403, mirroring the
    Pro client's retry shape so the rest of the code is identical in spirit.
    """

    def __init__(self, token_url: str = ANONYMOUS_TOKEN_URL,
                 graphql_url: str = GRAPHQL_URL):
        self.token_url = token_url
        self.graphql_url = graphql_url
        self._authorization: str | None = None
        self._posti_token: str | None = None

    def authenticate(self) -> None:
        """Mint a fresh anonymous token pair.

        The endpoint takes a bare POST (no body, no content-type — adding one
        would trip a CORS preflight in a browser; harmless here but kept bare
        to match the captured request). It returns an ``id_token`` plus a list
        of ``role_tokens``; the consumer GraphQL API wants the anonymous role
        token in ``Authorization`` and the id token in ``X-Posti-Token``.
        """
        req = urllib.request.Request(self.token_url, data=b"", method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise PostiAPIError(
                f"Anonymous token request failed (HTTP {e.code})",
                status_code=e.code,
            ) from e
        except urllib.error.URLError as e:
            raise PostiAPIError(f"Connection error: {e.reason}") from e

        id_token = data.get("id_token")
        role_tokens = data.get("role_tokens") or []
        role = next(
            (r for r in role_tokens if r.get("type") == "anonymous"),
            role_tokens[0] if role_tokens else None,
        )
        if not id_token or not role or not role.get("token"):
            raise PostiAPIError("Anonymous token response missing tokens")

        self._posti_token = id_token
        self._authorization = role["token"]

    def execute(self, query: str, variables: dict | None = None) -> dict:
        """Run a GraphQL query, minting/refreshing the anonymous token."""
        if self._authorization is None:
            self.authenticate()
        try:
            return self._do_request(query, variables or {})
        except PostiAPIError as e:
            if e.status_code in (401, 403):
                self.authenticate()
                return self._do_request(query, variables or {})
            raise

    def _do_request(self, query: str, variables: dict) -> dict:
        body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "User-Agent": "posti-cli/1.1",
            "Authorization": self._authorization,
            "X-Posti-Token": f"Bearer {self._posti_token}",
        }
        req = urllib.request.Request(
            self.graphql_url, data=body, headers=headers, method="POST"
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

        if isinstance(result, dict) and result.get("errors"):
            errors = result["errors"]
            msg = errors[0].get("message", "Unknown GraphQL error")
            error_type = errors[0].get("errorType", "")
            status = 401 if error_type == "Unauthorized" else None
            raise PostiAPIError(f"GraphQL error: {msg}", status_code=status)

        return result


def track_shipment(client: TrackingClient, tracking_number: str,
                   locale: str = "en") -> dict:
    """Look up a public shipment by tracking number.

    Returns the first hit (measurements, status, events). Raises if no
    shipment matches the tracking number.
    """
    variables = {
        "page": 1,
        "pageSize": 20,
        "type": "PUBLIC_SHIPMENTS",
        "searchTerms": [tracking_number],
        "locale": locale,
    }
    result = client.execute(SEARCH_SHIPMENTS_QUERY, variables)
    search = result["data"]["consumerSearchShipments"]
    hits = search.get("hits") or []
    if not hits:
        raise PostiAPIError(f"No shipment found for tracking number: {tracking_number}")
    return hits[0]
