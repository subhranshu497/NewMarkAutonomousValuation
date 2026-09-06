from fastapi import APIRouter

from app.schemas.request import ValuationRequest
from app.schemas.result import ValuationResponse

router = APIRouter(prefix="/api/valuations", tags=["valuations"])


@router.post("", response_model=ValuationResponse)
async def create_valuation(request: ValuationRequest) -> ValuationResponse:
    raise NotImplementedError


@router.get("/{valuation_id}", response_model=ValuationResponse)
async def get_valuation(valuation_id: str) -> ValuationResponse:
    raise NotImplementedError
