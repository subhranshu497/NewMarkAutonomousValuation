from datetime import date, datetime

from pydantic import BaseModel


class Comp(BaseModel):
    comp_id: str
    address: str
    submarket_id: str
    sf: int
    lease_type: str
    asking_rent_psf: float
    effective_rent_psf: float
    lease_start_date: date
    tenant_industry: str
    concessions: str | None = None
    source_system: str
    last_verified_at: datetime


class TimeSeriesPoint(BaseModel):
    period: str
    value: float


class TimeSeries(BaseModel):
    submarket_id: str
    metric: str
    points: list[TimeSeriesPoint]
    yoy_change: float
    percentile_rank: float


class SummaryStats(BaseModel):
    median_asking_rent_psf: float
    mean_asking_rent_psf: float
    rent_spread: float
    comp_count: int
    comp_count_trailing_12mo: int


class EvidenceBundle(BaseModel):
    summary_stats: SummaryStats
    top_comps: list[Comp]
    market_trend_deltas: list[TimeSeries]
