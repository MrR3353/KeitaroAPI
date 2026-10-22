from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Offer statuses that are part of what a push would currently send to Keitaro.
ACTIVE_OFFER_STATUSES = ("active", "pending_add")


class CreatedCampaign(Base):
    __tablename__ = "created_campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    keitaro_campaign_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    alias: Mapped[str] = mapped_column(String(255))
    country_code: Mapped[str] = mapped_column(String(2))
    offer_id: Mapped[int] = mapped_column(Integer)

    domain_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    group_id: Mapped[int] = mapped_column(Integer, nullable=True)
    traffic_source_id: Mapped[int] = mapped_column(Integer, nullable=True)

    geo_stream_id: Mapped[int] = mapped_column(Integer)
    offer_stream_id: Mapped[int] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    streams: Mapped[list["CampaignStream"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )


class CampaignStream(Base):
    """Local cache of a Keitaro campaign stream (flow)."""

    __tablename__ = "campaign_streams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("created_campaigns.id"), index=True)

    keitaro_stream_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    position: Mapped[int] = mapped_column(Integer)
    kt_schema: Mapped[str] = mapped_column(String(50))
    # Snapshot of {offer_id (str): share} last confirmed live in Keitaro (via push or fetch),
    # used to detect whether local edits actually differ from it (e.g. add then cancel == no-op).
    last_synced_offers: Mapped[dict] = mapped_column(JSON, default=dict)

    campaign: Mapped["CreatedCampaign"] = relationship(back_populates="streams")
    offers: Mapped[list["CampaignStreamOffer"]] = relationship(
        back_populates="stream", cascade="all, delete-orphan", order_by="CampaignStreamOffer.id"
    )

    @property
    def pending_changes(self) -> bool:
        """Whether a push to Keitaro is needed: either the weights/offer set that would be
        sent differ from what's live, or some offer is sitting in an unconfirmed status
        (pending_add/pending_remove) that a push would resolve, even if its weight happens
        to already match (e.g. an offer was removed and brought back to its original share)."""
        has_unconfirmed_status = any(o.status in ("pending_add", "pending_remove") for o in self.offers)
        effective = {str(o.offer_id): o.weight for o in self.offers if o.status in ACTIVE_OFFER_STATUSES}
        return has_unconfirmed_status or effective != (self.last_synced_offers or {})


class CampaignStreamOffer(Base):
    """An offer attached to a stream, tracked through its local/Keitaro lifecycle."""

    __tablename__ = "campaign_stream_offers"
    __table_args__ = (UniqueConstraint("stream_id", "offer_id", name="uq_stream_offer"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stream_id: Mapped[int] = mapped_column(ForeignKey("campaign_streams.id"), index=True)

    offer_id: Mapped[int] = mapped_column(Integer)
    offer_name: Mapped[str] = mapped_column(String(255))
    weight: Mapped[int] = mapped_column(Integer, default=0)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    # One of: active, pending_add, pending_remove, removed
    status: Mapped[str] = mapped_column(String(20), default="pending_add")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    stream: Mapped["CampaignStream"] = relationship(back_populates="offers")
