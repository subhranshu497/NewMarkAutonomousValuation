import json
from dataclasses import dataclass
from datetime import date

from app import claude_client
from app.schemas.request import ValuationRequest


@dataclass
class RefinementStep:
    adjust: str
    to: str | float | int


@dataclass
class QueryPlan:
    comps_search_params: dict
    market_stats_params: list[dict]
    refinement_policy: list[RefinementStep]


async def formulate_query(request: ValuationRequest) -> QueryPlan:
    """The single Data Retrieval Agent LLM call per request (see
    orchestrator/graph.py docstring for why this is one call, not one per
    iteration). Uses the query-formulation skill via claude_client."""
    user_content = json.dumps(
        {
            "today": date.today().isoformat(),
            "submarket_id": request.submarket_id,
            "property_type": request.property_type,
            "space_sf": request.space_sf,
            "lease_assumptions": request.lease_assumptions.model_dump(),
        }
    )
    response_text = await claude_client.call_with_skill("query-formulation", user_content)
    data = claude_client.extract_json(response_text)
    return QueryPlan(
        comps_search_params=data["comps_search_params"],
        market_stats_params=data["market_stats_params"],
        refinement_policy=[RefinementStep(**step) for step in data["refinement_policy"]],
    )
