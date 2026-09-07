"""The orchestration hub (DESIGN.md §4/§6.2).

This module owns the plan -> act -> check control flow as a LangGraph
StateGraph: it is the *only* caller of every spoke in app.orchestrator.nodes
(which in turn are the only callers of the Data Retrieval Agent, the
Valuation Agent, the semantic retrieval layer, and the comps/market-stats
tools). No spoke calls another spoke or agent directly — every transition,
including the bounded retrieval refinement loop, is a graph edge decided
here. That's the hub-and-spoke guarantee: agent-to-agent communication only
happens by going through this orchestrator.

Retrieval is hybrid: semantic_retrieve (Voyage + LanceDB cosine search)
runs once to seed additional evidence, then retrieve_comps runs the
deterministic exact-match structured search/refinement loop on top of it —
semantic retrieval augments, it never replaces, the structured path.

Exactly 2 LLM calls total per request (NFR "<=2 reasoning calls"): the Data
Retrieval Agent returns both the initial query params AND an ordered
refinement policy in one call, so the up-to-3 retrieval iterations that
follow apply that policy mechanically with no further LLM calls. The
Valuation Agent is the second and last LLM call. (Semantic retrieval calls
Voyage's embedding API, not an LLM reasoning call, so it isn't counted here.)
"""

import uuid

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.config import get_settings
from app.orchestrator import nodes
from app.orchestrator.state import OrchestratorState
from app.schemas.request import ValuationRequest
from app.schemas.result import ValuationResponse
from app.storage import review_queue, trace_store


def route_after_retrieval(state: OrchestratorState) -> str:
    """Hub decision: loop back to retrieve_comps, or move on to
    build_context. This conditional edge is the only place iteration
    continues or stops — retrieve_comps_node never decides this itself."""
    settings = get_settings()
    if state["stop_retrieval"] or state["iteration"] >= settings.max_retrieval_iterations:
        return "build_context"
    return "retrieve_comps"


def build_graph() -> CompiledStateGraph:
    graph = StateGraph(OrchestratorState)

    graph.add_node("formulate_query", nodes.formulate_query_node)
    graph.add_node("fetch_market_stats", nodes.fetch_market_stats_node)
    graph.add_node("semantic_retrieve", nodes.semantic_retrieve_node)
    graph.add_node("retrieve_comps", nodes.retrieve_comps_node)
    graph.add_node("build_context", nodes.build_context_node)
    graph.add_node("synthesize_valuation", nodes.synthesize_valuation_node)
    graph.add_node("verify_and_score", nodes.verify_and_score_node)

    graph.add_edge(START, "formulate_query")
    graph.add_edge("formulate_query", "fetch_market_stats")
    graph.add_edge("fetch_market_stats", "semantic_retrieve")
    graph.add_edge("semantic_retrieve", "retrieve_comps")
    graph.add_conditional_edges(
        "retrieve_comps",
        route_after_retrieval,
        {"retrieve_comps": "retrieve_comps", "build_context": "build_context"},
    )
    graph.add_edge("build_context", "synthesize_valuation")
    graph.add_edge("synthesize_valuation", "verify_and_score")
    graph.add_edge("verify_and_score", END)

    return graph.compile()


_compiled_graph: CompiledStateGraph | None = None


def get_graph() -> CompiledStateGraph:
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


async def run_valuation(request: ValuationRequest) -> ValuationResponse:
    """Public entry point (unchanged signature — api/routes_valuation.py
    doesn't need to know the orchestrator runs on LangGraph)."""
    final_state = await get_graph().ainvoke({"request": request, "trace": []})

    response = ValuationResponse(
        request_id=uuid.uuid4().hex,
        result=final_state["result"],
        evidence=final_state["evidence"],
        trace=final_state["trace"],
    )
    trace_store.save_result(response)
    if response.result.needs_human_review:
        review_queue.enqueue(response)
    return response
