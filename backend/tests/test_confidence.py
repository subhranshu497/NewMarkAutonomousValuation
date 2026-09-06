from app.logic.confidence import compute_confidence
from app.schemas.evidence import EvidenceBundle, SummaryStats


def make_bundle(comp_count: int, trailing_12mo: int, median: float, spread: float) -> EvidenceBundle:
    return EvidenceBundle(
        summary_stats=SummaryStats(
            median_asking_rent_psf=median,
            mean_asking_rent_psf=median,
            rent_spread=spread,
            comp_count=comp_count,
            comp_count_trailing_12mo=trailing_12mo,
        ),
        top_comps=[],
        market_trend_deltas=[],
    )


def test_zero_comps_yields_zero_confidence():
    bundle = make_bundle(comp_count=0, trailing_12mo=0, median=0, spread=0)
    assert compute_confidence(bundle) == 0.0


def test_confidence_is_bounded():
    bundle = make_bundle(comp_count=100, trailing_12mo=100, median=40, spread=0)
    assert 0.0 <= compute_confidence(bundle) <= 1.0


def test_more_comps_and_tighter_spread_increase_confidence():
    strong = make_bundle(comp_count=10, trailing_12mo=10, median=40, spread=1)
    weak = make_bundle(comp_count=5, trailing_12mo=2, median=40, spread=20)
    assert compute_confidence(strong) > compute_confidence(weak)


def test_wider_spread_lowers_confidence_all_else_equal():
    tight = make_bundle(comp_count=8, trailing_12mo=8, median=40, spread=1)
    wide = make_bundle(comp_count=8, trailing_12mo=8, median=40, spread=15)
    assert compute_confidence(tight) > compute_confidence(wide)
