"""Shipment operations."""

import base64
import os

from posti_cli.core.client_v2 import PostiV2Client


def create_shipment(client: PostiV2Client, data: dict) -> list:
    """Create a shipment (POST /v2/shipping/order?returnFile=true).

    Defaults valuePerParcel to false in each parcel if not set,
    since the API requires it but the default is almost always false.
    """
    shipment = data.get("shipment", {})
    for parcel in shipment.get("parcels", []):
        parcel.setdefault("valuePerParcel", False)

    return client._request(
        "/v2/shipping/order",
        method="POST",
        data=data,
        params={"returnFile": "true"},
    )


def save_pdfs(response: list, output_dir: str) -> list[str]:
    """Decode and save base64-encoded PDFs from the response.

    Supports both v2 format (prints/data) and v1 format (pdfs/pdf).
    Returns list of saved file paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    saved = []

    for i, shipment in enumerate(response):
        parcels = shipment.get("parcels", [])
        tracking = parcels[0].get("parcelNo", "") if parcels else ""
        if not tracking:
            tracking = f"shipment_{i}"

        # v2 format: "prints" array with "data" field
        # v1 format: "pdfs" array with "pdf" field
        print_items = shipment.get("prints", shipment.get("pdfs", []))
        for item in print_items:
            pdf_data = item.get("data", item.get("pdf"))
            if not pdf_data:
                continue

            pdf_type = item.get("pdf_type", "unknown")
            filename = f"{tracking}_{pdf_type}.pdf"
            filepath = os.path.join(output_dir, filename)

            if isinstance(pdf_data, str):
                pdf_bytes = base64.b64decode(pdf_data)
            else:
                pdf_bytes = pdf_data

            with open(filepath, "wb") as f:
                f.write(pdf_bytes)

            saved.append(filepath)

    return saved
