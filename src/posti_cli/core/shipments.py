"""Shipment operations."""

import base64
import os

from posti_cli.core.client import PostiClient


def create_shipment(client: PostiClient, data: dict) -> list:
    """Create a shipment (POST /v1/shipping/order?returnFile=true)."""
    return client._request(
        "/v1/shipping/order",
        method="POST",
        data=data,
        params={"returnFile": "true"},
    )


def save_pdfs(response: list, output_dir: str) -> list[str]:
    """Decode and save base64-encoded PDFs from the response.

    Returns list of saved file paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    saved = []

    for shipment in response:
        tracking = ""
        parcels = shipment.get("parcels", [])
        if parcels:
            tracking = parcels[0].get("parcelNo", "unknown")

        for pdf_item in shipment.get("pdfs", []):
            pdf_data = pdf_item.get("pdf")
            if not pdf_data:
                continue

            pdf_type = pdf_item.get("pdf_type", "unknown")
            filename = f"{tracking}_{pdf_type}.pdf"
            filepath = os.path.join(output_dir, filename)

            # pdf_data may be base64-encoded string
            if isinstance(pdf_data, str):
                pdf_bytes = base64.b64decode(pdf_data)
            else:
                pdf_bytes = pdf_data

            with open(filepath, "wb") as f:
                f.write(pdf_bytes)

            saved.append(filepath)

    return saved
