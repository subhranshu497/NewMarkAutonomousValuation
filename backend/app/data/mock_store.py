import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from app.schemas.evidence import Comp, TimeSeries

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@lru_cache
def load_comps() -> list[Comp]:
    data = json.loads((FIXTURES_DIR / "comps.json").read_text())
    return [Comp(**row) for row in data]


@lru_cache
def load_market_stats() -> list[TimeSeries]:
    data = json.loads((FIXTURES_DIR / "market_stats.json").read_text())
    return [TimeSeries(**row) for row in data]


def search_comps(
    submarket_id: str,
    property_type: str,
    min_sf: int,
    max_sf: int,
    lease_type: str,
    date_from: date,
    date_to: date,
    radius_miles: float,
    k: int,
) -> list[Comp]:
    """Stands in for OpenSearch-backed comps_search (DESIGN.md §6.1) using
    the local fixtures. `property_type` and `radius_miles` are accepted to
    match the real tool contract but are no-ops here: the fixtures don't
    carry a property_type dimension or geocoordinates, so every comp is
    treated as matching on those two axes until a real search index backs
    this."""
    matches = [
        comp
        for comp in load_comps()
        if comp.submarket_id == submarket_id
        and comp.lease_type == lease_type
        and min_sf <= comp.sf <= max_sf
        and date_from <= comp.lease_start_date <= date_to
    ]
    matches.sort(key=lambda comp: comp.lease_start_date, reverse=True)
    return matches[:k]


def get_market_stats(submarket_id: str, metric: str) -> TimeSeries | None:
    """Stands in for the Snowflake/dbt-backed market_stats tool using the
    local fixtures. `time_window` is accepted by the caller but is a no-op
    here: fixtures only carry one fixed window per submarket/metric."""
    for series in load_market_stats():
        if series.submarket_id == submarket_id and series.metric == metric:
            return series
    return None
