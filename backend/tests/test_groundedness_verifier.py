from datetime import date

from app.logic.groundedness_verifier import market_stat_id, verify_groundedness
from app.schemas.evidence import Comp, EvidenceBundle, SummaryStats, TimeSeries, TimeSeriesPoint
from app.schemas.result import ValuationResult


def make_evidence() -> EvidenceBundle:
    comp = Comp(
        comp_id="c_1042",
        address="123 Test St",
        submarket_id="chi-fulton-market",
        sf=20000,
        lease_type="direct",
        asking_rent_psf=42.0,
        effective_rent_psf=39.0,
        lease_start_date=date(2026, 3, 1),
        tenant_industry="technology",
        concessions=None,
        source_system="test",
        last_verified_at="2026-08-01T00:00:00Z",
    )
    stats = TimeSeries(
        submarket_id="chi-fulton-market",
        metric="vacancy_rate",
        points=[TimeSeriesPoint(period="2026-Q2", value=0.1)],
        yoy_change=-0.01,
        percentile_rank=0.5,
    )
    return EvidenceBundle(
        summary_stats=SummaryStats(
            median_asking_rent_psf=42.0,
            mean_asking_rent_psf=42.0,
            rent_spread=0.0,
            comp_count=1,
            comp_count_trailing_12mo=1,
        ),
        top_comps=[comp],
        market_trend_deltas=[stats],
    )


def make_result(cited_comp_ids: list[str], cited_market_stat_ids: list[str]) -> ValuationResult:
    return ValuationResult(
        recommended_rent_psf=42.0,
        range_low=40.0,
        range_high=44.0,
        confidence=0.8,
        rationale_text="test",
        cited_comp_ids=cited_comp_ids,
        cited_market_stat_ids=cited_market_stat_ids,
        needs_human_review=False,
    )


def test_market_stat_id_format():
    assert market_stat_id("chi-fulton-market", "vacancy_rate") == "chi-fulton-market_vacancy_rate"


def test_grounded_when_all_citations_resolve():
    evidence = make_evidence()
    result = make_result(["c_1042"], ["chi-fulton-market_vacancy_rate"])
    assert verify_groundedness(result, evidence)


def test_ungrounded_when_comp_id_not_in_evidence():
    evidence = make_evidence()
    result = make_result(["c_9999"], ["chi-fulton-market_vacancy_rate"])
    assert not verify_groundedness(result, evidence)


def test_ungrounded_when_market_stat_id_not_in_evidence():
    evidence = make_evidence()
    result = make_result(["c_1042"], ["chi-fulton-market_net_absorption"])
    assert not verify_groundedness(result, evidence)
