from sqlalchemy.orm import Session

from app.keitaro_client import KeitaroAPIError, KeitaroClient
from app.models import CampaignStream, CampaignStreamOffer, CreatedCampaign

ACTIVE_STATUSES = ("active", "pending_add")


class CampaignEditorError(Exception):
    """A 400-level error: the requested change is not valid."""


class NotFoundError(CampaignEditorError):
    """A 404-level error: the referenced entity does not exist locally."""


def _get_campaign(db: Session, campaign_id: int) -> CreatedCampaign:
    campaign = db.get(CreatedCampaign, campaign_id)
    if campaign is None:
        raise NotFoundError(f"Campaign {campaign_id} not found")
    return campaign


def _get_stream(db: Session, stream_id: int) -> CampaignStream:
    stream = db.get(CampaignStream, stream_id)
    if stream is None:
        raise NotFoundError(f"Stream {stream_id} not found")
    return stream


def _get_stream_offer(db: Session, stream_offer_id: int) -> CampaignStreamOffer:
    row = db.get(CampaignStreamOffer, stream_offer_id)
    if row is None:
        raise NotFoundError(f"Stream offer {stream_offer_id} not found")
    return row


def _recalculate_weights(stream: CampaignStream) -> None:
    contributing = [o for o in stream.offers if o.status in ACTIVE_STATUSES]
    inactive = [o for o in stream.offers if o.status not in ACTIVE_STATUSES]
    for row in inactive:
        row.weight = 0

    pinned = [o for o in contributing if o.pinned]
    unpinned = [o for o in contributing if not o.pinned]

    pinned_sum = sum(o.weight for o in pinned)
    remaining = max(0, 100 - pinned_sum)

    if not unpinned:
        return

    base = remaining // len(unpinned)
    remainder = remaining - base * len(unpinned)
    for index, row in enumerate(unpinned):
        row.weight = base + (1 if index < remainder else 0)


async def _fetch_offer_name(client: KeitaroClient, offer_id: int) -> str:
    try:
        offer = await client.get_offer(offer_id)
    except KeitaroAPIError:
        return f"Offer {offer_id}"
    return offer.get("name") or f"Offer {offer_id}"


def get_campaign_detail(db: Session, campaign_id: int) -> CreatedCampaign:
    return _get_campaign(db, campaign_id)


async def search_offers(query: str, limit: int = 20) -> list[dict]:
    query = query.strip()
    if not query:
        return []

    client = KeitaroClient()
    offers = await client.list_offers()

    query_lower = query.lower()
    matches = []
    for offer in offers:
        offer_id = offer.get("id")
        name = offer.get("name") or ""
        id_match = query.isdigit() and str(offer_id).startswith(query)
        name_match = query_lower in name.lower()
        if id_match or name_match:
            matches.append({"id": offer_id, "name": name})

    return matches[:limit]


async def fetch_streams_from_kt(db: Session, campaign_id: int) -> CreatedCampaign:
    campaign = _get_campaign(db, campaign_id)
    client = KeitaroClient()
    kt_streams = await client.get_campaign_streams(campaign.keitaro_campaign_id)

    existing_by_kt_id = {s.keitaro_stream_id: s for s in campaign.streams}

    for kt_stream in kt_streams:
        kt_stream_id = kt_stream["id"]
        stream = existing_by_kt_id.get(kt_stream_id)
        if stream is None:
            stream = CampaignStream(
                campaign_id=campaign.id,
                keitaro_stream_id=kt_stream_id,
                name=kt_stream.get("name") or "",
                position=kt_stream.get("position") or 0,
                kt_schema=kt_stream.get("schema") or "",
            )
            db.add(stream)
            db.flush()
            existing_by_kt_id[kt_stream_id] = stream
        else:
            stream.name = kt_stream.get("name") or stream.name
            stream.position = kt_stream.get("position", stream.position)
            stream.kt_schema = kt_stream.get("schema") or stream.kt_schema

        kt_offers = kt_stream.get("offers") or []
        if kt_offers:
            await _reconcile_stream_offers(db, stream, kt_offers, client)

    db.commit()
    db.refresh(campaign)
    return campaign


async def _reconcile_stream_offers(
    db: Session, stream: CampaignStream, kt_offers: list[dict], client: KeitaroClient
) -> None:
    kt_offer_ids = {int(o["offer_id"]) for o in kt_offers}
    existing_by_offer_id = {o.offer_id: o for o in stream.offers}

    for offer_id, row in existing_by_offer_id.items():
        if row.status == "active" and offer_id not in kt_offer_ids:
            row.status = "removed"
            row.weight = 0

    for kt_offer in kt_offers:
        offer_id = int(kt_offer["offer_id"])
        row = existing_by_offer_id.get(offer_id)
        if row is None:
            offer_name = await _fetch_offer_name(client, offer_id)
            row = CampaignStreamOffer(
                stream_id=stream.id,
                offer_id=offer_id,
                offer_name=offer_name,
                weight=int(kt_offer.get("share") or 0),
                pinned=False,
                status="active",
            )
            stream.offers.append(row)
            existing_by_offer_id[offer_id] = row
        elif row.status == "active":
            row.weight = int(kt_offer.get("share", row.weight))

    db.flush()
    _recalculate_weights(stream)


async def add_offer_to_stream(db: Session, stream_id: int, offer_id: int) -> CampaignStream:
    stream = _get_stream(db, stream_id)
    row = next((o for o in stream.offers if o.offer_id == offer_id), None)

    if row is not None and row.status != "removed":
        raise CampaignEditorError(f"Offer {offer_id} is already in this stream")

    if row is not None:
        row.status = "pending_add"
        row.pinned = False
    else:
        client = KeitaroClient()
        try:
            offer = await client.get_offer(offer_id)
        except KeitaroAPIError as exc:
            if exc.status_code == 404:
                raise CampaignEditorError(f"Offer {offer_id} does not exist in Keitaro") from exc
            raise
        row = CampaignStreamOffer(
            stream_id=stream.id,
            offer_id=offer_id,
            offer_name=offer.get("name") or f"Offer {offer_id}",
            weight=0,
            pinned=False,
            status="pending_add",
        )
        stream.offers.append(row)

    db.flush()
    _recalculate_weights(stream)
    db.commit()
    db.refresh(stream)
    return stream


def cancel_offer(db: Session, stream_offer_id: int) -> CampaignStream:
    row = _get_stream_offer(db, stream_offer_id)
    if row.status != "pending_add":
        raise CampaignEditorError("Only a not-yet-pushed offer can be canceled")

    stream = row.stream
    stream.offers.remove(row)
    db.flush()
    _recalculate_weights(stream)
    db.commit()
    db.refresh(stream)
    return stream


def remove_offer(db: Session, stream_offer_id: int) -> CampaignStream:
    row = _get_stream_offer(db, stream_offer_id)
    stream = row.stream

    if row.status == "pending_add":
        stream.offers.remove(row)
    elif row.status == "active":
        row.status = "pending_remove"
        row.weight = 0
    else:
        raise CampaignEditorError(f"Offer in status '{row.status}' cannot be removed")

    db.flush()
    _recalculate_weights(stream)
    db.commit()
    db.refresh(stream)
    return stream


def bring_back_offer(db: Session, stream_offer_id: int) -> CampaignStream:
    row = _get_stream_offer(db, stream_offer_id)
    if row.status not in ("pending_remove", "removed"):
        raise CampaignEditorError(f"Offer in status '{row.status}' cannot be brought back")

    row.status = "pending_add"
    stream = row.stream
    db.flush()
    _recalculate_weights(stream)
    db.commit()
    db.refresh(stream)
    return stream


def toggle_pin(db: Session, stream_offer_id: int, pinned: bool) -> CampaignStream:
    row = _get_stream_offer(db, stream_offer_id)
    row.pinned = pinned
    stream = row.stream
    db.flush()
    _recalculate_weights(stream)
    db.commit()
    db.refresh(stream)
    return stream


async def push_to_kt(db: Session, stream_id: int) -> CampaignStream:
    stream = _get_stream(db, stream_id)
    contributing = [o for o in stream.offers if o.status in ACTIVE_STATUSES]
    payload_offers = [{"offer_id": o.offer_id, "share": o.weight} for o in contributing]

    client = KeitaroClient()
    await client.update_stream(stream.keitaro_stream_id, {"offers": payload_offers})

    for row in stream.offers:
        if row.status == "pending_add":
            row.status = "active"
        elif row.status == "pending_remove":
            row.status = "removed"

    db.commit()
    db.refresh(stream)
    return stream
