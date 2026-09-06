from app.schemas.evidence import EvidenceBundle

# MVP placeholder weights/saturation points — DESIGN.md §8 flags these as
# needing calibration against the feedback store once labeled overrides exist.
_COUNT_SATURATION = 10
_WEIGHT_COUNT = 0.4
_WEIGHT_RECENCY = 0.3
_WEIGHT_SPREAD = 0.3


def compute_confidence(evidence: EvidenceBundle) -> float:
    """DESIGN.md §6.5 — composite of comp count, recency mix, and $/PSF
    spread/variance. Computed in code from the evidence bundle, not asked of
    the LLM, so it stays auditable and stable."""
    stats = evidence.summary_stats
    if stats.comp_count == 0:
        return 0.0

    count_score = min(stats.comp_count / _COUNT_SATURATION, 1.0)
    recency_score = min(stats.comp_count_trailing_12mo / stats.comp_count, 1.0)

    spread_ratio = stats.rent_spread / stats.median_asking_rent_psf if stats.median_asking_rent_psf else 1.0
    spread_score = max(0.0, 1 - spread_ratio)

    confidence = (
        _WEIGHT_COUNT * count_score
        + _WEIGHT_RECENCY * recency_score
        + _WEIGHT_SPREAD * spread_score
    )
    return round(min(max(confidence, 0.0), 1.0), 2)
