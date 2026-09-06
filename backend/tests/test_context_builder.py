from datetime import date, timedelta

from app.logic.context_builder import build_evidence_bundle
from app.schemas.evidence import Comp

TODAY = date.today()


def make_comp(comp_id: str, sf: int, days_ago: int, rent: float) -> Comp:
    return Comp(
        comp_id=comp_id,
        address="123 Test St",
        submarket_id="chi-fulton-market",
        sf=sf,
        lease_type="direct",
        asking_rent_psf=rent,
        effective_rent_psf=rent - 3,
        lease_start_date=TODAY - timedelta(days=days_ago),
        tenant_industry="technology",
        concessions=None,
        source_system="test",
        last_verified_at="2026-08-01T00:00:00Z",
    )


def test_summary_stats_and_dedupe():
    comps = [
        make_comp("c_1", sf=20000, days_ago=30, rent=40.0),
        make_comp("c_2", sf=20000, days_ago=30, rent=44.0),
        make_comp("c_3", sf=20000, days_ago=30, rent=42.0),
        make_comp("c_1", sf=20000, days_ago=30, rent=40.0),  # duplicate comp_id
    ]

    bundle = build_evidence_bundle(comps, market_stats_results=[], subject_space_sf=20000, top_n=10)

    assert bundle.summary_stats.comp_count == 3
    assert bundle.summary_stats.median_asking_rent_psf == 42.0
    assert bundle.summary_stats.mean_asking_rent_psf == 42.0
    assert bundle.summary_stats.rent_spread == 4.0
    assert bundle.summary_stats.comp_count_trailing_12mo == 3


def test_top_n_selects_most_relevant_by_size_and_recency():
    comps = [
        make_comp("close_recent", sf=20000, days_ago=10, rent=42.0),
        make_comp("far_old", sf=25000, days_ago=400, rent=42.0),
        make_comp("near_recent", sf=19000, days_ago=60, rent=42.0),
    ]

    bundle = build_evidence_bundle(comps, market_stats_results=[], subject_space_sf=20000, top_n=2)

    assert [comp.comp_id for comp in bundle.top_comps] == ["close_recent", "near_recent"]


def test_empty_comps_returns_zeroed_bundle():
    bundle = build_evidence_bundle([], market_stats_results=[], subject_space_sf=20000, top_n=10)

    assert bundle.summary_stats.comp_count == 0
    assert bundle.top_comps == []
