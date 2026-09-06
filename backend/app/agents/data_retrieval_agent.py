from dataclasses import dataclass

from app.schemas.request import ValuationRequest
from app.tools.comps_search import comps_search  # noqa: F401  (param shapes referenced below)
from app.tools.market_stats import market_stats  # noqa: F401


@dataclass
class RefinementStep:
    adjust: str
    to: str | float | int


@dataclass
class QueryPlan:
    comps_search_params: dict
    market_stats_params: list[dict]
    refinement_policy: list[RefinementStep]


def formulate_query(request: ValuationRequest) -> QueryPlan:
    """The single Data Retrieval Agent LLM call per request (see
    orchestrator/graph.py docstring for why this is one call, not one per
    iteration). Uses the query-formulation skill via claude_client."""
    raise NotImplementedError
