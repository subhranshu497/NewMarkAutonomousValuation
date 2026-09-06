from app.schemas.evidence import EvidenceBundle
from app.schemas.result import ValuationResult


def market_stat_id(submarket_id: str, metric: str) -> str:
    """Shared with the valuation-synthesis skill's citation convention —
    keep in sync with agent_skills/valuation_synthesis/SKILL.md."""
    return f"{submarket_id}_{metric}"


def verify_groundedness(result: ValuationResult, evidence: EvidenceBundle) -> bool:
    """DESIGN.md §6.4 — every cited_comp_id / cited_market_stat_id must exist
    in the evidence bundle actually passed to the model. Any mismatch means
    this returns False, which forces needs_human_review = true upstream."""
    known_comp_ids = {comp.comp_id for comp in evidence.top_comps}
    known_stat_ids = {
        market_stat_id(series.submarket_id, series.metric) for series in evidence.market_trend_deltas
    }

    if not set(result.cited_comp_ids) <= known_comp_ids:
        return False
    if not set(result.cited_market_stat_ids) <= known_stat_ids:
        return False
    return True
