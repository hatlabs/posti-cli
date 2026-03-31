"""Shipment list and detail operations via Posti Pro GraphQL API.

Query strings captured from live pro.posti.fi traffic 2026-03-28.
"""

from posti_cli.core.client import PostiAPIError
from posti_cli.core.pro.client import ProClient

SHIPMENT_FEED_QUERY = """
query getShipmentFeedItems(
  $status: [CorporateShipmentFeedStatusInput],
  $sortBy: CorporateShipmentFeedSortBy,
  $sortOrder: ShipmentFeedSortOrder,
  $first: Int!,
  $offset: Int,
  $queryTerm: String,
  $estimatedDeliveryStartDate: AWSDate,
  $estimatedDeliveryEndDate: AWSDate,
  $extra: [CorporateFeedExtraFilter]
) {
  getOPPROCorporateShipmentFeed(
    status: $status
    sortBy: $sortBy
    sortOrder: $sortOrder
    first: $first
    offset: $offset
    queryTerm: $queryTerm
    estimatedDeliveryStartDate: $estimatedDeliveryStartDate
    estimatedDeliveryEndDate: $estimatedDeliveryEndDate
    extra: $extra
  ) {
    totalFound
    moreResults
    items {
      consignmentNumber
      isStarred
      savedDateTime
      updatedDateTime
      product {
        code
        name { fi, en, sv }
      }
      sender { name, country }
      receiver { name, country }
      shipmentType
      status {
        code
        description { lang, value }
      }
      additionalStatus {
        code
        description { lang, value }
      }
      trackingNumbers
      waybillNumber
    }
  }
}
""".strip()

SHIPMENT_DETAIL_QUERY = """
query getOPPROShipmentInfoQuery($trackingId: String) {
  getOPPROShipmentInfoV2(trackingId: $trackingId) {
    consignmentNumber
    trackingNumbers
    waybillNumber
    shipmentType
    createdAt
    modifiedAt
    estimatedDeliveryTime
    deliveryDate { earliest, latest }
    pickupDate { earliest, latest }
    sender {
      account, city, countryCode, email, mobile,
      name, name2, phone, postCode, street, street2
    }
    receiver {
      city, countryCode, email, mobile,
      name, name2, phone, postCode, street, street2
    }
    references {
      invoiceNumber, invoicingCode, orderNumber, postiOrderNumber,
      seller, senderReferenceNumbers, receiverReferenceNumbers, shipmentSeq
    }
    status {
      code
      description { lang, value }
    }
    product {
      code
      localNames { lang, value }
    }
    services {
      code
      localNames { lang, value }
    }
    events {
      city, countryCode, eventCode, role, timeStamp
      eventShortName { lang, value }
      reasonDescription { lang, value }
    }
    height { unit, value }
    length { unit, value }
    width { unit, value }
    weight { unit, value }
    volume { unit, value }
  }
}
""".strip()


def list_shipments(
    client: ProClient,
    *,
    first: int = 50,
    offset: int = 0,
    query_term: str | None = None,
    starred: bool = False,
    sort_by: str = "SHIPMENT_CREATED",
    sort_order: str = "DESC",
) -> dict:
    """List shipments from the feed."""
    variables = {
        "status": [],
        "extra": ["STARRED"] if starred else [],
        "sortBy": sort_by,
        "sortOrder": sort_order,
        "first": first,
        "offset": offset,
        "queryTerm": query_term,
        "estimatedDeliveryStartDate": None,
        "estimatedDeliveryEndDate": None,
    }

    result = client.execute(SHIPMENT_FEED_QUERY, variables)
    data = result.get("data") or {}
    feed = data.get("getOPPROCorporateShipmentFeed")
    if feed is None:
        raise PostiAPIError("Unexpected response: no shipment feed data")
    return feed


def get_shipment(client: ProClient, tracking_id: str) -> dict:
    """Get full shipment detail including dimensions and tracking events."""
    variables = {"trackingId": tracking_id}
    result = client.execute(SHIPMENT_DETAIL_QUERY, variables)
    data = result.get("data") or {}
    items = data.get("getOPPROShipmentInfoV2")
    if not items:
        raise PostiAPIError(f"No shipment found for tracking ID: {tracking_id}")
    return items[0]
