"""Spoke node functions for the orchestration graph (see graph.py).

Every function here is invoked exclusively by the compiled LangGraph state
machine — the hub. No node imports or calls another node/agent directly;
each one only reads `OrchestratorState` and returns a partial update, and
the hub's edges (plain and conditional) decide what runs next. This is the
hub-and-spoke contract: agent-to-agent communication only ever happens by
going through the graph.
"""

import logging
from datetime import date, datetime

from pydantic import ValidationError

from app.agents.data_retrieval_agent import formulate_query
from app.agents.valuation_agent import synthesize_valuation
from app.config import get_settings
from app.logic.confidence import compute_confidence
from app.logic.context_builder import build_evidence_bundle
from app.logic.groundedness_verifier import verify_groundedness
from app.logic.sufficiency import is_sufficient
from app.orchestrator.state import OrchestratorState
from app.retrieval.retriever import VectorRetriever
from app.retrieval.schema import RetrievedDocument
from app.schemas.evidence import Comp, TimeSeries
from app.schemas.request import ValuationRequest
from app.schemas.result import TraceSpan
from app.tools.comps_search import comps_search
from app.tools.market_stats import market_stats

logger = logging.getLogger(__name__)


def _span(step: str, started_at: datetime, params: dict, result_summary: str) -> TraceSpan:
    return TraceSpan(step=step, started_at=started_at, finished_at=datetime.utcnow(), params=params, result_summary=result_summary)


def _coerce_comps_params(params: dict) -> dict:
    """The Data Retrieval Agent returns JSON, so date fields arrive as
    'YYYY-MM-DD' strings — comps_search expects real `date` objects."""
    coerced = dict(params)
    for key in ("date_from", "date_to"):
        value = coerced.get(key)
        if isinstance(value, str):
            coerced[key] = date.fromisoformat(value)
    return coerced


def _fetch_market_stats(params_list: list[dict]) -> list[TimeSeries]:
    results = []
    for params in params_list:
        series = market_stats(
            submarket_id=params["submarket_id"], metric=params["metric"], time_window=params.get("time_window", "")
        )
        if series is not None:
            results.append(series)
    return results


async def formulate_query_node(state: OrchestratorState) -> dict:
    """Spoke: Data Retrieval Agent (1st of 2 LLM calls per request)."""
    t0 = datetime.utcnow()
    plan = await formulate_query(state["request"])
    return {
        "plan": plan,
        "current_comps_params": dict(plan.comps_search_params),
        "iteration": 0,
        "comps": [],
        "trace": [
            _span(
                "query_formulation",
                t0,
                {
                    "initial_comps_search_params": plan.comps_search_params,
                    "market_stats_params": plan.market_stats_params,
                },
                f"{len(plan.refinement_policy)} refinement steps planned",
            )
        ],
    }


async def fetch_market_stats_node(state: OrchestratorState) -> dict:
    """Spoke: market_stats tool."""
    t0 = datetime.utcnow()
    results = _fetch_market_stats(state["plan"].market_stats_params)
    return {
        "market_stats_results": results,
        "trace": [
            _span(
                "market_stats_fetch",
                t0,
                {"requested": state["plan"].market_stats_params},
                f"{len(results)} series returned",
            )
        ],
    }


def _build_semantic_query(request: ValuationRequest) -> str:
    lease = request.lease_assumptions
    parts = [
        f"{request.property_type} space in {request.submarket_id}",
        f"{request.space_sf:,} SF",
        f"{lease.lease_type} lease",
    ]
    if lease.concessions_assumed:
        parts.append(f"concessions: {lease.concessions_assumed}")
    return ", ".join(parts)


def _document_to_comp(doc: RetrievedDocument) -> Comp | None:
    try:
        return Comp(**doc.metadata)
    except ValidationError:
        logger.warning("semantic match %r had comp-shaped metadata that failed validation", doc.doc_id)
        return None


def _document_to_market_stat(doc: RetrievedDocument) -> TimeSeries | None:
    try:
        return TimeSeries(**doc.metadata)
    except ValidationError:
        logger.warning("semantic match %r had market-stat-shaped metadata that failed validation", doc.doc_id)
        return None


async def semantic_retrieve_node(state: OrchestratorState) -> dict:
    """Spoke: semantic retrieval layer (Voyage embeddings + LanceDB cosine
    search, app/retrieval). Runs once per request ahead of the deterministic
    structured retrieval loop, seeding it with additional evidence the exact-
    match comps_search/market_stats tools might miss (e.g. submarket
    boundary edge cases). Never replaces structured retrieval and never
    fabricates: an empty/unreachable vector store just means this node
    contributes nothing, degrading gracefully rather than failing the
    request (Availability NFR)."""
    t0 = datetime.utcnow()
    query = _build_semantic_query(state["request"])
    settings = get_settings()

    try:
        result = await VectorRetriever().retrieve(query, k=settings.retrieval_top_k)
    except Exception:
        logger.warning("semantic retrieval unavailable, degrading to structured retrieval only", exc_info=True)
        return {
            "trace": [
                _span(
                    "semantic_retrieval", t0, {"query": query}, "unavailable — degraded to structured retrieval only"
                )
            ]
        }

    new_comps = [
        comp for doc in result.matches if doc.doc_type == "comp" and (comp := _document_to_comp(doc)) is not None
    ]
    new_stats = [
        series
        for doc in result.matches
        if doc.doc_type == "market_stat" and (series := _document_to_market_stat(doc)) is not None
    ]

    merged_comps = list({comp.comp_id: comp for comp in state["comps"] + new_comps}.values())
    merged_stats = list(
        {(series.submarket_id, series.metric): series for series in state["market_stats_results"] + new_stats}.values()
    )

    summary = (
        f"{len(new_comps)} comps + {len(new_stats)} market stats above similarity threshold"
        if result.found
        else result.message
    )

    return {
        "comps": merged_comps,
        "market_stats_results": merged_stats,
        "trace": [_span("semantic_retrieval", t0, {"query": query, "k": settings.retrieval_top_k}, summary)],
    }


def retrieve_comps_node(state: OrchestratorState) -> dict:
    """Spoke: comps_search tool + deterministic sufficiency check
    (DESIGN.md §6.3). Runs once per pass; route_after_retrieval (graph.py)
    is the hub decision of whether to loop back here or move on, capped at
    settings.max_retrieval_iterations."""
    settings = get_settings()
    iteration = state["iteration"]
    plan = state["plan"]

    t0 = datetime.utcnow()
    coerced_params = _coerce_comps_params(state["current_comps_params"])
    new_comps = comps_search(**coerced_params)
    merged_comps = list({comp.comp_id: comp for comp in state["comps"] + new_comps}.values())

    sufficient = is_sufficient(
        comps=merged_comps,
        market_stats_results=state["market_stats_results"],
        submarket_id=state["request"].submarket_id,
        radius_miles=coerced_params.get("radius_miles", 0),
        recent_window_months=settings.recent_window_months,
        min_comp_count=settings.min_comp_count,
        min_recent_comp_count=settings.min_recent_comp_count,
    )

    can_refine = iteration < len(plan.refinement_policy)
    next_params = dict(state["current_comps_params"])
    if not sufficient and can_refine:
        step = plan.refinement_policy[iteration]
        next_params[step.adjust] = step.to

    span = _span(
        f"retrieval_iteration_{iteration + 1}",
        t0,
        {"comps_search_params": coerced_params},
        f"{len(new_comps)} new / {len(merged_comps)} total comps, sufficient={sufficient}",
    )

    return {
        "comps": merged_comps,
        "current_comps_params": next_params,
        "iteration": iteration + 1,
        "sufficient": sufficient,
        "stop_retrieval": sufficient or not can_refine,
        "trace": [span],
    }


def build_context_node(state: OrchestratorState) -> dict:
    """Spoke: deterministic Context Builder (DESIGN.md §5)."""
    settings = get_settings()
    t0 = datetime.utcnow()
    evidence = build_evidence_bundle(
        state["comps"], state["market_stats_results"], state["request"].space_sf, settings.top_n_comps
    )
    return {
        "evidence": evidence,
        "trace": [
            _span(
                "context_builder",
                t0,
                {"top_n": settings.top_n_comps},
                f"{evidence.summary_stats.comp_count} deduped comps, {len(evidence.top_comps)} selected",
            )
        ],
    }


async def synthesize_valuation_node(state: OrchestratorState) -> dict:
    """Spoke: Valuation Agent (2nd and last LLM call per request)."""
    t0 = datetime.utcnow()
    result = await synthesize_valuation(state["evidence"])
    return {
        "result": result,
        "trace": [
            _span(
                "valuation_synthesis",
                t0,
                {},
                f"recommended={result.recommended_rent_psf}/PSF, llm_confidence={result.confidence}",
            )
        ],
    }


def verify_and_score_node(state: OrchestratorState) -> dict:
    """Spoke: deterministic Groundedness Verifier + confidence + human
    review gate (DESIGN.md §6.4/§6.5/§6.6)."""
    settings = get_settings()
    t0 = datetime.utcnow()
    evidence = state["evidence"]
    result = state["result"]

    grounded = verify_groundedness(result, evidence)
    deterministic_confidence = compute_confidence(evidence)

    needs_human_review = result.needs_human_review or not grounded
    if (
        min(result.confidence, deterministic_confidence) < settings.confidence_threshold
        or evidence.summary_stats.comp_count < settings.review_min_comp_count
    ):
        needs_human_review = True
    result.needs_human_review = needs_human_review

    return {
        "result": result,
        "trace": [
            _span(
                "verification_and_confidence",
                t0,
                {"deterministic_confidence": deterministic_confidence, "grounded": grounded},
                f"needs_human_review={needs_human_review}",
            )
        ],
    }
