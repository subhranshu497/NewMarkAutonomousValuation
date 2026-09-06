from typing import Literal

from app.data import mock_store
from app.schemas.evidence import TimeSeries

Metric = Literal["vacancy_rate", "net_absorption", "asking_rent_trend"]


def market_stats(submarket_id: str, metric: Metric, time_window: str) -> TimeSeries | None:
    """This is the seam where a real Snowflake/dbt-backed call replaces the
    mock store, without changing the contract callers rely on."""
    return mock_store.get_market_stats(submarket_id=submarket_id, metric=metric)
