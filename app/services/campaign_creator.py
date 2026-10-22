import re
import secrets

from sqlalchemy.orm import Session

from app.config import get_settings
from app.keitaro_client import KeitaroAPIError, KeitaroClient
from app.models import CreatedCampaign
from app.schemas import CampaignCreateRequest

# Preferred-order candidates for the "country" stream filter name, since
# exact naming can vary slightly between Keitaro versions.
_COUNTRY_FILTER_CANDIDATES = ["country_code", "country"]


class CampaignCreationError(Exception):
    pass


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return (slug or "campaign") + "-" + secrets.token_hex(3)


async def _resolve_country_filter_name(client: KeitaroClient) -> str:
    filters = await client.list_stream_filters()
    available = {f.get("value") for f in filters}
    for candidate in _COUNTRY_FILTER_CANDIDATES:
        if candidate in available:
            return candidate
    raise CampaignCreationError(
        f"Could not find a country stream filter in Keitaro. Available filters: {sorted(available)}"
    )


async def _resolve_domain_id(client: KeitaroClient) -> int | None:
    settings = get_settings()
    if settings.keitaro_default_domain_id is not None:
        return settings.keitaro_default_domain_id

    domains = await client.list_domains()
    active_domains = [d for d in domains if d.get("state") == "active"]
    if not active_domains:
        return None
    return active_domains[0]["id"]


async def create_campaign(db: Session, request: CampaignCreateRequest) -> CreatedCampaign:
    settings = get_settings()
    client = KeitaroClient()

    try:
        await client.get_offer(request.offer_id)
    except KeitaroAPIError as exc:
        if exc.status_code == 404:
            raise CampaignCreationError(f"Offer {request.offer_id} does not exist in Keitaro") from exc
        raise

    country_filter_name = await _resolve_country_filter_name(client)
    domain_id = await _resolve_domain_id(client)
    alias = _slugify(request.name)

    group = None
    source = None
    campaign = None
    try:
        group = await client.create_group(name=request.name, group_type="campaigns")
        source = await client.create_traffic_source(name=request.name)

        campaign_payload = {
            "name": request.name,
            "alias": alias,
            "group_id": group["id"],
            "traffic_source_id": source["id"],
        }
        if domain_id is not None:
            campaign_payload["domain_id"] = domain_id

        campaign = await client.create_campaign(campaign_payload)
        campaign_id = campaign["id"]

        geo_stream = await client.create_stream(
            {
                "campaign_id": campaign_id,
                "type": "regular",
                "schema": "redirect",
                "name": f"GEO {request.country_code} -> Google",
                "position": 1,
                "action_type": "http",
                "action_payload": settings.google_redirect_url,
                "filters": [
                    {
                        "name": country_filter_name,
                        "mode": "accept",
                        "payload": [request.country_code],
                    }
                ],
            }
        )

        offer_stream = await client.create_stream(
            {
                "campaign_id": campaign_id,
                "type": "regular",
                "schema": "landings",
                "name": "Default -> Offer",
                "position": 2,
                "action_type": "http",
                "offers": [{"offer_id": request.offer_id, "share": 100}],
            }
        )
    except Exception:
        if campaign is not None:
            await _safe_cleanup(client.delete_campaign(campaign["id"]))
        if source is not None:
            await _safe_cleanup(client.delete_traffic_source(source["id"]))
        if group is not None:
            await _safe_cleanup(client.delete_group(group["id"]))
        raise

    record = CreatedCampaign(
        keitaro_campaign_id=campaign["id"],
        name=request.name,
        alias=alias,
        country_code=request.country_code,
        offer_id=request.offer_id,
        domain_id=domain_id,
        group_id=group["id"],
        traffic_source_id=source["id"],
        geo_stream_id=geo_stream["id"],
        offer_stream_id=offer_stream["id"],
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


async def _safe_cleanup(coro) -> None:
    try:
        await coro
    except Exception:
        pass
