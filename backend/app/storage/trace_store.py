from app.schemas.result import TraceSpan, ValuationResponse


def save_trace(request_id: str, spans: list[TraceSpan]) -> None:
    """DESIGN.md FR9/§6.7 — append-only audit trace, retained per valuation
    for a defined retention window."""
    raise NotImplementedError


def get_trace(request_id: str) -> list[TraceSpan]:
    raise NotImplementedError


def save_result(response: ValuationResponse) -> None:
    """Also backs the feedback/episodic store (§5) for MVP: logged only,
    not yet consumed by any live learning loop."""
    raise NotImplementedError
