from app.schemas.result import ValuationResponse
from app.storage import trace_store

# In-memory, process-local — same MVP-gap note as trace_store.py.
_pending_ids: set[str] = set()
_decisions: dict[str, dict] = {}


def enqueue(response: ValuationResponse) -> None:
    """DESIGN.md §6.6 — human review gate destination."""
    _pending_ids.add(response.request_id)


def list_pending() -> list[ValuationResponse]:
    return [
        response
        for request_id in _pending_ids
        if (response := trace_store.get_result(request_id)) is not None
    ]


def record_decision(request_id: str, approved: bool, analyst_override_psf: float | None) -> None:
    """Feeds the feedback/episodic store (§5): analyst overrides are the
    core signal for calibrating confidence thresholds later. MVP: kept as
    an in-memory decision log, not the durable, queryable feedback store
    DESIGN.md §5 describes — that's a later step."""
    _pending_ids.discard(request_id)
    _decisions[request_id] = {"approved": approved, "analyst_override_psf": analyst_override_psf}
