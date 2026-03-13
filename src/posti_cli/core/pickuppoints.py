"""Pickup point operations for Posti 2025-04 API."""

from posti_cli.core.client_v2 import PostiV2Client


def search_pickuppoints(
    client: PostiV2Client,
    data: dict,
    language: str | None = None,
) -> dict:
    """Search pickup points (POST /pickuppoints)."""
    headers = {}
    if language:
        headers["Accept-Language"] = language
    return client._request(
        "/pickuppoints",
        method="POST",
        data=data,
        headers_extra=headers or None,
    )


def list_pickuppoints(
    client: PostiV2Client,
    country: str,
    language: str | None = None,
) -> dict:
    """List all pickup points for a country (GET /pickuppoints/{country})."""
    headers = {}
    if language:
        headers["Accept-Language"] = language
    return client._request(
        f"/pickuppoints/{country}",
        method="GET",
        headers_extra=headers or None,
    )


def get_pickuppoint(
    client: PostiV2Client,
    country: str,
    point_id: str,
    language: str | None = None,
) -> dict:
    """Get a single pickup point (GET /pickuppoints/{country}/{id})."""
    headers = {}
    if language:
        headers["Accept-Language"] = language
    return client._request(
        f"/pickuppoints/{country}/{point_id}",
        method="GET",
        headers_extra=headers or None,
    )
