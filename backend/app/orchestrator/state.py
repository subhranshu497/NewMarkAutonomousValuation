from dataclasses import dataclass, field

from app.schemas.evidence import Comp, EvidenceBundle, TimeSeries
from app.schemas.request import ValuationRequest
from app.schemas.result import TraceSpan, ValuationResult


@dataclass
class OrchestratorState:
    """DESIGN.md §5 — working memory: single request, in-process, discarded
    after the run (the trace is what gets persisted, per FR9)."""

    request: ValuationRequest
    iteration: int = 0
    comps: list[Comp] = field(default_factory=list)
    market_stats_results: list[TimeSeries] = field(default_factory=list)
    evidence: EvidenceBundle | None = None
    result: ValuationResult | None = None
    trace: list[TraceSpan] = field(default_factory=list)
