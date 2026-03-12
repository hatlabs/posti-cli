"""Shipping methods — hardcoded list (no Posti API endpoint exists)."""

SHIPPING_METHODS = [
    {
        "code": "2103",
        "name": "Postipaketti",
        "deliveryType": "pickup",
        "description": "Pickup from Posti service point",
    },
    {
        "code": "2351",
        "name": "Pickup Parcel / Posti Parcel Connect",
        "deliveryType": "pickup",
        "description": "International pickup parcel",
    },
    {
        "code": "2331",
        "name": "Posti Parcel Baltic",
        "deliveryType": "pickup",
        "description": "Baltic countries pickup parcel",
    },
    {
        "code": "2352",
        "name": "Posti Home Parcel",
        "deliveryType": "home",
        "description": "Home delivery parcel",
    },
    {
        "code": "2015",
        "name": "Posti Priority",
        "deliveryType": "home",
        "description": "Priority home delivery",
    },
    {
        "code": "2017",
        "name": "Posti Express (EMS)",
        "deliveryType": "home",
        "description": "Express home delivery",
    },
]


def list_methods() -> list[dict]:
    """Return all available Posti shipping methods."""
    return SHIPPING_METHODS
