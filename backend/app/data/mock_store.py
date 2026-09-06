import json
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
    radius_miles: float,
    k: int,
) -> list[Comp]:
    """Stands in for OpenSearch-backed comps_search (DESIGN.md §6.1) using
    the local fixtures. Filtering/ranking logic to be implemented alongside
    tools.comps_search."""
    raise NotImplementedError


def get_market_stats(submarket_id: str, metric: str) -> TimeSeries:
    """Stands in for the Snowflake/dbt-backed market_stats tool using the
    local fixtures."""
    raise NotImplementedError
