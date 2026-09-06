from app.schemas.result import ValuationResponse


def enqueue(response: ValuationResponse) -> None:
    """DESIGN.md §6.6 — human review gate destination."""
    raise NotImplementedError


def list_pending() -> list[ValuationResponse]:
    raise NotImplementedError


def record_decision(request_id: str, approved: bool, analyst_override_psf: float | None) -> None:
    """Feeds the feedback/episodic store (§5): analyst overrides are the
    core signal for calibrating confidence thresholds later."""
    raise NotImplementedError
