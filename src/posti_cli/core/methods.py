"""Shipping methods — hardcoded list (no Posti API endpoint exists)."""

SHIPPING_METHODS = [
    {
        "code": "PO2103",
        "name": "Postipaketti",
        "deliveryType": "pickup",
        "description": "Pickup from Posti service point",
    },
    {
        "code": "PO2351",
        "name": "Pickup Parcel / Posti Parcel Connect",
        "deliveryType": "pickup",
        "description": "International pickup parcel",
    },
    {
        "code": "PO2331",
        "name": "Posti Parcel Baltic",
        "deliveryType": "pickup",
        "description": "Baltic countries pickup parcel",
    },
    {
        "code": "PO2352",
        "name": "Posti Home Parcel",
        "deliveryType": "home",
        "description": "Home delivery parcel",
    },
    {
        "code": "PO2015",
        "name": "Posti Priority",
        "deliveryType": "home",
        "description": "Priority home delivery",
    },
    {
        "code": "PO2017",
        "name": "Posti Express (EMS)",
        "deliveryType": "home",
        "description": "Express home delivery",
    },
]


def list_methods() -> list[dict]:
    """Return all available Posti shipping methods."""
    return SHIPPING_METHODS
