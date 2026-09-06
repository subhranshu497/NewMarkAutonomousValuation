from datetime import datetime

from pydantic import BaseModel

from app.schemas.evidence import EvidenceBundle


class ValuationResult(BaseModel):
    recommended_rent_psf: float
    range_low: float
    range_high: float
    confidence: float
    rationale_text: str
    cited_comp_ids: list[str]
    cited_market_stat_ids: list[str]
    needs_human_review: bool


class TraceSpan(BaseModel):
    step: str
    started_at: datetime
    finished_at: datetime
    params: dict
    result_summary: str


class ValuationResponse(BaseModel):
    request_id: str
    result: ValuationResult
    evidence: EvidenceBundle
    trace: list[TraceSpan]
