"""Delivery estimation for Posti 2025-04 API."""

from posti_cli.core.client_v2 import PostiV2Client


def estimate_delivery(client: PostiV2Client, data: dict) -> dict:
    """Estimate delivery time (POST /estimate)."""
    return client._request("/estimate", method="POST", data=data)
