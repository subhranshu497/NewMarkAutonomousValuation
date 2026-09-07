import operator
from typing import Annotated, TypedDict

from app.agents.data_retrieval_agent import QueryPlan
from app.schemas.evidence import Comp, EvidenceBundle, TimeSeries
from app.schemas.request import ValuationRequest
from app.schemas.result import TraceSpan, ValuationResult


class OrchestratorState(TypedDict, total=False):
    """DESIGN.md §5 working memory, reshaped as a LangGraph state schema.

    This is the shared blackboard the hub (the compiled graph in graph.py)
    passes between spokes (the node functions in nodes.py). Spokes never
    call each other directly — each one only reads this state and returns a
    partial update; the graph runtime is what decides which spoke runs next.
    `trace` uses an additive reducer so every spoke only reports its own
    span and the hub concatenates the full audit trail automatically.
    """

    request: ValuationRequest
    plan: QueryPlan
    current_comps_params: dict
    iteration: int
    sufficient: bool
    stop_retrieval: bool
    comps: list[Comp]
    market_stats_results: list[TimeSeries]
    evidence: EvidenceBundle
    result: ValuationResult
    trace: Annotated[list[TraceSpan], operator.add]
