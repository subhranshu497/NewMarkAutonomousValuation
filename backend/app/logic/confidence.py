from app.schemas.evidence import EvidenceBundle


def compute_confidence(evidence: EvidenceBundle) -> float:
    """DESIGN.md §6.5 — composite of comp count, recency mix, and $/PSF
    spread/variance. Computed in code from the evidence bundle, not asked of
    the LLM, so it stays auditable and stable."""
    raise NotImplementedError
