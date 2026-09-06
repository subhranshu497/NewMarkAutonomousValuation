from app.schemas.evidence import Comp, TimeSeries


def is_sufficient(
    comps: list[Comp],
    market_stats_results: list[TimeSeries],
    submarket_id: str,
    radius_miles: float,
    recent_window_months: int,
    min_comp_count: int,
    min_recent_comp_count: int,
) -> bool:
    """DESIGN.md §6.3 — deterministic, never LLM-judged."""
    raise NotImplementedError
