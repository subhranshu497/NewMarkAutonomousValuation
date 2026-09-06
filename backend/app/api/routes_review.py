from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.result import ValuationResponse
from app.storage import review_queue

router = APIRouter(prefix="/api/review-queue", tags=["review-queue"])


class ReviewDecision(BaseModel):
    approved: bool
    analyst_override_psf: float | None = None


@router.get("", response_model=list[ValuationResponse])
async def list_review_queue() -> list[ValuationResponse]:
    return review_queue.list_pending()


@router.post("/{valuation_id}/decision")
async def submit_review_decision(valuation_id: str, decision: ReviewDecision) -> dict:
    review_queue.record_decision(valuation_id, decision.approved, decision.analyst_override_psf)
    return {"status": "ok"}
