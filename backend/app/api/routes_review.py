from fastapi import APIRouter

from app.schemas.result import ValuationResponse

router = APIRouter(prefix="/api/review-queue", tags=["review-queue"])


@router.get("", response_model=list[ValuationResponse])
async def list_review_queue() -> list[ValuationResponse]:
    raise NotImplementedError


@router.post("/{valuation_id}/decision")
async def submit_review_decision(valuation_id: str, approved: bool, analyst_override_psf: float | None = None) -> dict:
    raise NotImplementedError
