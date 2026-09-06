from typing import Literal

from app.schemas.evidence import TimeSeries

Metric = Literal["vacancy_rate", "net_absorption", "asking_rent_trend"]


def market_stats(submarket_id: str, metric: Metric, time_window: str) -> TimeSeries:
    raise NotImplementedError
