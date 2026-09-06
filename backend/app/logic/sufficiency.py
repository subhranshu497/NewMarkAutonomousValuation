from datetime import date, timedelta

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
    """DESIGN.md §6.3 — deterministic, never LLM-judged.

    `submarket_id` and `radius_miles` are accepted to mirror the design
    doc's rule ("comps within submarket ± configurable radius"), but the
    actual radius/submarket filtering already happened in comps_search
    (DESIGN.md §6.1) — every comp passed in here already satisfies that
    condition, so there's nothing further to check on those two fields.
    """
    if len(comps) < min_comp_count:
        return False

    cutoff = date.today() - timedelta(days=recent_window_months * 30)
    recent_count = sum(1 for comp in comps if comp.lease_start_date >= cutoff)
    if recent_count < min_recent_comp_count:
        return False

    if not market_stats_results:
        return False

    return True
