from typing import Any

import httpx

from app.config import get_settings


class KeitaroAPIError(Exception):
    def __init__(self, status_code: int, detail: Any):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Keitaro API error {status_code}: {detail}")


class KeitaroClient:
    """Thin async wrapper around the Keitaro Admin API."""

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.keitaro_base_url.rstrip("/") + "/admin_api/v1"
        self._headers = {"Api-Key": settings.keitaro_api_key}
        self._timeout = settings.http_timeout_seconds

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.request(
                method, f"{self._base_url}{path}", headers=self._headers, **kwargs
            )
        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            raise KeitaroAPIError(response.status_code, detail)
        if not response.content:
            return None
        return response.json()

    # Offers

    async def get_offer(self, offer_id: int) -> dict:
        return await self._request("GET", f"/offers/{offer_id}")

    # Domains

    async def list_domains(self) -> list[dict]:
        return await self._request("GET", "/domains")

    # Groups

    async def create_group(self, name: str, group_type: str = "campaigns") -> dict:
        return await self._request("POST", "/groups", json={"name": name, "type": group_type})

    async def delete_group(self, group_id: int) -> None:
        await self._request("DELETE", f"/groups/{group_id}/delete")

    # Traffic sources

    async def create_traffic_source(self, name: str) -> dict:
        return await self._request("POST", "/traffic_sources", json={"name": name})

    async def delete_traffic_source(self, source_id: int) -> None:
        await self._request("DELETE", f"/traffic_sources/{source_id}")

    # Campaigns

    async def create_campaign(self, payload: dict) -> dict:
        return await self._request("POST", "/campaigns", json=payload)

    async def get_campaign(self, campaign_id: int) -> dict:
        return await self._request("GET", f"/campaigns/{campaign_id}")

    async def delete_campaign(self, campaign_id: int) -> None:
        await self._request("DELETE", f"/campaigns/{campaign_id}")

    async def get_campaign_streams(self, campaign_id: int) -> list[dict]:
        return await self._request("GET", f"/campaigns/{campaign_id}/streams")

    # Streams

    async def list_stream_filters(self) -> list[dict]:
        return await self._request("GET", "/stream_filters")

    async def create_stream(self, payload: dict) -> dict:
        return await self._request("POST", "/streams", json=payload)

    async def get_stream(self, stream_id: int) -> dict:
        return await self._request("GET", f"/streams/{stream_id}")

    async def update_stream(self, stream_id: int, payload: dict) -> dict:
        return await self._request("PUT", f"/streams/{stream_id}", json=payload)

    async def delete_stream(self, stream_id: int) -> None:
        await self._request("DELETE", f"/streams/{stream_id}")
