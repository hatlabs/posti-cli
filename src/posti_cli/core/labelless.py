"""Labelless sending operations for Posti 2025-04 API."""

from posti_cli.core.client_v2 import PostiV2Client


def create_sending_code(client: PostiV2Client, data: dict) -> dict:
    """Create a sending code (POST /labelless)."""
    return client._request("/labelless", method="POST", data=data)


def get_by_tracking_number(client: PostiV2Client, tracking_number: str) -> dict:
    """Get sending code by tracking number (GET /labelless/{trackingNumber})."""
    return client._request(f"/labelless/{tracking_number}", method="GET")


def get_by_sending_code(client: PostiV2Client, sending_code: str) -> dict:
    """Get shipment by sending code (GET /labelless/shipment/{sendingCode})."""
    return client._request(f"/labelless/shipment/{sending_code}", method="GET")
