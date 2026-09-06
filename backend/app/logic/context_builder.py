from app.schemas.evidence import Comp, EvidenceBundle, TimeSeries


def build_evidence_bundle(
    comps: list[Comp],
    market_stats_results: list[TimeSeries],
    subject_space_sf: int,
    top_n: int,
) -> EvidenceBundle:
    """DESIGN.md §5 — dedupe, compute aggregate stats in code, select top-N by
    relevance, assemble a fixed-shape bundle. Never delegated to the LLM."""
    raise NotImplementedError
