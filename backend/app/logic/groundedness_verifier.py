from app.schemas.evidence import EvidenceBundle
from app.schemas.result import ValuationResult


def verify_groundedness(result: ValuationResult, evidence: EvidenceBundle) -> bool:
    """DESIGN.md §6.4 — every cited_comp_id / cited_market_stat_id must exist
    in the evidence bundle actually passed to the model. Any mismatch means
    this returns False, which forces needs_human_review = true upstream."""
    raise NotImplementedError
