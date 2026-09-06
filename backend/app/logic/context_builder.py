import statistics
from datetime import date, timedelta

from app.schemas.evidence import Comp, EvidenceBundle, SummaryStats, TimeSeries


def build_evidence_bundle(
    comps: list[Comp],
    market_stats_results: list[TimeSeries],
    subject_space_sf: int,
    top_n: int,
) -> EvidenceBundle:
    """DESIGN.md §5 — dedupe, compute aggregate stats in code, select top-N
    by relevance, assemble a fixed-shape bundle. Never delegated to the LLM."""
    deduped = list({comp.comp_id: comp for comp in comps}.values())

    if not deduped:
        return EvidenceBundle(
            summary_stats=SummaryStats(
                median_asking_rent_psf=0,
                mean_asking_rent_psf=0,
                rent_spread=0,
                comp_count=0,
                comp_count_trailing_12mo=0,
            ),
            top_comps=[],
            market_trend_deltas=market_stats_results,
        )

    rents = [comp.asking_rent_psf for comp in deduped]
    trailing_12mo_cutoff = date.today() - timedelta(days=365)
    summary_stats = SummaryStats(
        median_asking_rent_psf=round(statistics.median(rents), 2),
        mean_asking_rent_psf=round(statistics.mean(rents), 2),
        rent_spread=round(max(rents) - min(rents), 2),
        comp_count=len(deduped),
        comp_count_trailing_12mo=sum(1 for comp in deduped if comp.lease_start_date >= trailing_12mo_cutoff),
    )

    top_comps = sorted(deduped, key=lambda comp: _relevance(comp, deduped, subject_space_sf), reverse=True)[:top_n]

    return EvidenceBundle(
        summary_stats=summary_stats,
        top_comps=top_comps,
        market_trend_deltas=market_stats_results,
    )


def _relevance(comp: Comp, population: list[Comp], subject_space_sf: int) -> float:
    """Higher is more relevant: closer in size to the subject space and
    more recent, weighted equally (DESIGN.md §5: "top-N comps by relevance
    (size/date/type match)")."""
    max_size_diff = max(abs(c.sf - subject_space_sf) for c in population) or 1
    max_age_days = max((date.today() - c.lease_start_date).days for c in population) or 1

    size_score = 1 - abs(comp.sf - subject_space_sf) / max_size_diff
    recency_score = 1 - (date.today() - comp.lease_start_date).days / max_age_days
    return 0.5 * size_score + 0.5 * recency_score
