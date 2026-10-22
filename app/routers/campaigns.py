from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.keitaro_client import KeitaroAPIError
from app.models import CreatedCampaign
from app.schemas import CampaignCreateRequest, CampaignCreateResponse
from app.services.campaign_creator import CampaignCreationError, create_campaign

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignCreateResponse)
async def create_campaign_endpoint(
    request: CampaignCreateRequest, db: Session = Depends(get_db)
) -> CreatedCampaign:
    try:
        return await create_campaign(db, request)
    except CampaignCreationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeitaroAPIError as exc:
        raise HTTPException(status_code=502, detail={"keitaro_status": exc.status_code, "detail": exc.detail}) from exc


@router.get("", response_model=list[CampaignCreateResponse])
def list_campaigns(db: Session = Depends(get_db)) -> list[CreatedCampaign]:
    return list(db.scalars(select(CreatedCampaign).order_by(CreatedCampaign.created_at.desc())))
