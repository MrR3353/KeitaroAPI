from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.keitaro_client import KeitaroAPIError
from app.models import CampaignStream, CreatedCampaign
from app.schemas import AddOfferRequest, CampaignDetailOut, OfferSearchResult, PinRequest, StreamOut
from app.services import campaign_editor

router = APIRouter(prefix="/api", tags=["campaign-editor"])


def _handle(exc: Exception):
    if isinstance(exc, campaign_editor.NotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, campaign_editor.CampaignEditorError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, KeitaroAPIError):
        raise HTTPException(status_code=502, detail={"keitaro_status": exc.status_code, "detail": exc.detail}) from exc
    raise exc


@router.get("/campaigns/{campaign_id}/detail", response_model=CampaignDetailOut)
def get_campaign_detail(campaign_id: int, db: Session = Depends(get_db)) -> CreatedCampaign:
    try:
        return campaign_editor.get_campaign_detail(db, campaign_id)
    except Exception as exc:
        _handle(exc)


@router.post("/campaigns/{campaign_id}/fetch-streams", response_model=CampaignDetailOut)
async def fetch_streams(campaign_id: int, db: Session = Depends(get_db)) -> CreatedCampaign:
    try:
        return await campaign_editor.fetch_streams_from_kt(db, campaign_id)
    except Exception as exc:
        _handle(exc)


@router.get("/offers/search", response_model=list[OfferSearchResult])
async def search_offers(q: str = Query(default="")) -> list[dict]:
    try:
        return await campaign_editor.search_offers(q)
    except Exception as exc:
        _handle(exc)


@router.post("/streams/{stream_id}/offers", response_model=StreamOut)
async def add_offer(stream_id: int, request: AddOfferRequest, db: Session = Depends(get_db)) -> CampaignStream:
    try:
        return await campaign_editor.add_offer_to_stream(db, stream_id, request.offer_id)
    except Exception as exc:
        _handle(exc)


@router.delete("/stream-offers/{stream_offer_id}", response_model=StreamOut)
def cancel_offer(stream_offer_id: int, db: Session = Depends(get_db)) -> CampaignStream:
    try:
        return campaign_editor.cancel_offer(db, stream_offer_id)
    except Exception as exc:
        _handle(exc)


@router.post("/stream-offers/{stream_offer_id}/remove", response_model=StreamOut)
def remove_offer(stream_offer_id: int, db: Session = Depends(get_db)) -> CampaignStream:
    try:
        return campaign_editor.remove_offer(db, stream_offer_id)
    except Exception as exc:
        _handle(exc)


@router.post("/stream-offers/{stream_offer_id}/bring-back", response_model=StreamOut)
def bring_back_offer(stream_offer_id: int, db: Session = Depends(get_db)) -> CampaignStream:
    try:
        return campaign_editor.bring_back_offer(db, stream_offer_id)
    except Exception as exc:
        _handle(exc)


@router.post("/stream-offers/{stream_offer_id}/pin", response_model=StreamOut)
def pin_offer(stream_offer_id: int, request: PinRequest, db: Session = Depends(get_db)) -> CampaignStream:
    try:
        return campaign_editor.toggle_pin(db, stream_offer_id, request.pinned)
    except Exception as exc:
        _handle(exc)


@router.post("/streams/{stream_id}/push", response_model=StreamOut)
async def push_stream(stream_id: int, db: Session = Depends(get_db)) -> CampaignStream:
    try:
        return await campaign_editor.push_to_kt(db, stream_id)
    except Exception as exc:
        _handle(exc)
