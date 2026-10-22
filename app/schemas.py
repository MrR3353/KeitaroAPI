from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class CampaignCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    country_code: str = Field(min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code, e.g. 'US'")
    offer_id: int

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str) -> str:
        return value.upper()


class CampaignCreateResponse(BaseModel):
    id: int
    keitaro_campaign_id: int
    name: str
    alias: str
    country_code: str
    offer_id: int
    domain_id: int | None
    group_id: int | None
    traffic_source_id: int | None
    geo_stream_id: int
    offer_stream_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class StreamOfferOut(BaseModel):
    id: int
    offer_id: int
    offer_name: str
    weight: int
    pinned: bool
    status: str

    model_config = {"from_attributes": True}


class StreamOut(BaseModel):
    id: int
    keitaro_stream_id: int
    name: str
    position: int
    kt_schema: str
    pending_changes: bool
    offers: list[StreamOfferOut]

    model_config = {"from_attributes": True}


class CampaignDetailOut(CampaignCreateResponse):
    streams: list[StreamOut]


class OfferSearchResult(BaseModel):
    id: int
    name: str


class AddOfferRequest(BaseModel):
    offer_id: int


class PinRequest(BaseModel):
    pinned: bool
