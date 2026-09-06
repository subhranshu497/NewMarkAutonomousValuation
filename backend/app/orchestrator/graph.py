import uuid
from datetime import date, datetime

from app.agents.data_retrieval_agent import formulate_query
from app.agents.valuation_agent import synthesize_valuation
from app.config import get_settings
from app.logic.confidence import compute_confidence
from app.logic.context_builder import build_evidence_bundle
from app.logic.groundedness_verifier import verify_groundedness
from app.logic.sufficiency import is_sufficient
from app.orchestrator.state import OrchestratorState
from app.schemas.evidence import TimeSeries
from app.schemas.request import ValuationRequest
from app.schemas.result import TraceSpan, ValuationResponse
from app.storage import review_queue, trace_store
from app.tools.comps_search import comps_search
from app.tools.market_stats import market_stats


async def run_valuation(request: ValuationRequest) -> ValuationResponse:
    """DESIGN.md §4/§6.2 — deterministic plan -> act -> check state machine.

    Exactly 2 LLM calls total (NFR "<=2 reasoning calls"): the Data
    Retrieval Agent below returns both the initial query params AND an
    ordered refinement policy in one call, so the up-to-3 retrieval
    iterations that follow apply that policy mechanically with no further
    LLM calls. The Valuation Agent is the second and last LLM call.
    """
    settings = get_settings()
    state = OrchestratorState(request=request)

    t0 = datetime.utcnow()
    plan = await formulate_query(request)
    state.trace.append(
        _span(
            "query_formulation",
            t0,
            {"initial_comps_search_params": plan.comps_search_params, "market_stats_params": plan.market_stats_params},
            f"{len(plan.refinement_policy)} refinement steps planned",
        )
    )

    t1 = datetime.utcnow()
    state.market_stats_results = _fetch_market_stats(plan.market_stats_params)
    state.trace.append(
        _span(
            "market_stats_fetch",
            t1,
            {"requested": plan.market_stats_params},
            f"{len(state.market_stats_results)} series returned",
        )
    )

    comps_search_params = dict(plan.comps_search_params)
    for iteration in range(settings.max_retrieval_iterations):
        state.iteration = iteration
        t_iter = datetime.utcnow()
        coerced_params = _coerce_comps_params(comps_search_params)
        new_comps = comps_search(**coerced_params)
        state.comps = list({comp.comp_id: comp for comp in state.comps + new_comps}.values())

        sufficient = is_sufficient(
            comps=state.comps,
            market_stats_results=state.market_stats_results,
            submarket_id=request.submarket_id,
            radius_miles=coerced_params.get("radius_miles", 0),
            recent_window_months=settings.recent_window_months,
            min_comp_count=settings.min_comp_count,
            min_recent_comp_count=settings.min_recent_comp_count,
        )
        state.trace.append(
            _span(
                f"retrieval_iteration_{iteration + 1}",
                t_iter,
                {"comps_search_params": coerced_params},
                f"{len(new_comps)} new / {len(state.comps)} total comps, sufficient={sufficient}",
            )
        )

        if sufficient:
            break
        if iteration < len(plan.refinement_policy):
            step = plan.refinement_policy[iteration]
            comps_search_params[step.adjust] = step.to
        else:
            break

    t_ctx = datetime.utcnow()
    state.evidence = build_evidence_bundle(state.comps, state.market_stats_results, request.space_sf, settings.top_n_comps)
    state.trace.append(
        _span(
            "context_builder",
            t_ctx,
            {"top_n": settings.top_n_comps},
            f"{state.evidence.summary_stats.comp_count} deduped comps, {len(state.evidence.top_comps)} selected",
        )
    )

    t_val = datetime.utcnow()
    state.result = await synthesize_valuation(state.evidence)
    state.trace.append(
        _span(
            "valuation_synthesis",
            t_val,
            {},
            f"recommended={state.result.recommended_rent_psf}/PSF, llm_confidence={state.result.confidence}",
        )
    )

    t_verify = datetime.utcnow()
    grounded = verify_groundedness(state.result, state.evidence)
    deterministic_confidence = compute_confidence(state.evidence)
    if not grounded:
        state.result.needs_human_review = True
    if (
        min(state.result.confidence, deterministic_confidence) < settings.confidence_threshold
        or state.evidence.summary_stats.comp_count < settings.review_min_comp_count
    ):
        state.result.needs_human_review = True
    state.trace.append(
        _span(
            "verification_and_confidence",
            t_verify,
            {"deterministic_confidence": deterministic_confidence, "grounded": grounded},
            f"needs_human_review={state.result.needs_human_review}",
        )
    )

    response = ValuationResponse(
        request_id=uuid.uuid4().hex,
        result=state.result,
        evidence=state.evidence,
        trace=state.trace,
    )
    trace_store.save_result(response)
    if response.result.needs_human_review:
        review_queue.enqueue(response)
    return response


def _span(step: str, started_at: datetime, params: dict, result_summary: str) -> TraceSpan:
    return TraceSpan(step=step, started_at=started_at, finished_at=datetime.utcnow(), params=params, result_summary=result_summary)


def _fetch_market_stats(params_list: list[dict]) -> list[TimeSeries]:
    results = []
    for params in params_list:
        series = market_stats(
            submarket_id=params["submarket_id"],
            metric=params["metric"],
            time_window=params.get("time_window", ""),
        )
        if series is not None:
            results.append(series)
    return results


def _coerce_comps_params(params: dict) -> dict:
    """The Data Retrieval Agent returns JSON, so date fields arrive as
    'YYYY-MM-DD' strings — comps_search expects real `date` objects."""
    coerced = dict(params)
    for key in ("date_from", "date_to"):
        value = coerced.get(key)
        if isinstance(value, str):
            coerced[key] = date.fromisoformat(value)
    return coerced
