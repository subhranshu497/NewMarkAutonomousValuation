from datetime import date, timedelta

from app.logic.sufficiency import is_sufficient
from app.schemas.evidence import Comp, TimeSeries, TimeSeriesPoint

TODAY = date.today()


def make_comp(comp_id: str, days_ago: int) -> Comp:
    return Comp(
        comp_id=comp_id,
        address="123 Test St",
        submarket_id="chi-fulton-market",
        sf=20000,
        lease_type="direct",
        asking_rent_psf=42.0,
        effective_rent_psf=39.0,
        lease_start_date=TODAY - timedelta(days=days_ago),
        tenant_industry="technology",
        concessions=None,
        source_system="test",
        last_verified_at="2026-08-01T00:00:00Z",
    )


def make_stats() -> list[TimeSeries]:
    return [
        TimeSeries(
            submarket_id="chi-fulton-market",
            metric="vacancy_rate",
            points=[TimeSeriesPoint(period="2026-Q2", value=0.1)],
            yoy_change=-0.01,
            percentile_rank=0.5,
        )
    ]


def test_sufficient_with_enough_recent_comps_and_stats():
    comps = [make_comp(f"c_{i}", days_ago=30 * i) for i in range(5)]
    assert is_sufficient(
        comps=comps,
        market_stats_results=make_stats(),
        submarket_id="chi-fulton-market",
        radius_miles=3.0,
        recent_window_months=12,
        min_comp_count=5,
        min_recent_comp_count=3,
    )


def test_insufficient_when_too_few_comps():
    comps = [make_comp(f"c_{i}", days_ago=30 * i) for i in range(3)]
    assert not is_sufficient(
        comps=comps,
        market_stats_results=make_stats(),
        submarket_id="chi-fulton-market",
        radius_miles=3.0,
        recent_window_months=12,
        min_comp_count=5,
        min_recent_comp_count=3,
    )


def test_insufficient_when_comps_are_stale():
    comps = [make_comp(f"c_{i}", days_ago=800) for i in range(5)]
    assert not is_sufficient(
        comps=comps,
        market_stats_results=make_stats(),
        submarket_id="chi-fulton-market",
        radius_miles=3.0,
        recent_window_months=12,
        min_comp_count=5,
        min_recent_comp_count=3,
    )


def test_insufficient_when_no_market_stats():
    comps = [make_comp(f"c_{i}", days_ago=30 * i) for i in range(5)]
    assert not is_sufficient(
        comps=comps,
        market_stats_results=[],
        submarket_id="chi-fulton-market",
        radius_miles=3.0,
        recent_window_months=12,
        min_comp_count=5,
        min_recent_comp_count=3,
    )
