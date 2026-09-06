from fastapi import APIRouter, HTTPException

from app.orchestrator.graph import run_valuation
from app.schemas.request import ValuationRequest
from app.schemas.result import ValuationResponse
from app.storage import trace_store

router = APIRouter(prefix="/api/valuations", tags=["valuations"])


@router.post("", response_model=ValuationResponse)
async def create_valuation(request: ValuationRequest) -> ValuationResponse:
    return await run_valuation(request)


@router.get("/{valuation_id}", response_model=ValuationResponse)
async def get_valuation(valuation_id: str) -> ValuationResponse:
    response = trace_store.get_result(valuation_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Valuation not found")
    return response
