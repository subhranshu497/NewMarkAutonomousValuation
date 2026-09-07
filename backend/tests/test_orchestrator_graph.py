import ast
import json
import pathlib

import pytest

from app.agents.data_retrieval_agent import QueryPlan, RefinementStep
from app.logic.confidence import compute_confidence
from app.logic.groundedness_verifier import verify_groundedness
from app.orchestrator import graph as graph_module
from app.orchestrator import nodes
from app.retrieval.schema import RetrievalResult, RetrievedDocument
from app.schemas.evidence import TimeSeries, TimeSeriesPoint
from app.schemas.result import ValuationResult
from tests.test_orchestrator_nodes import StubVectorRetriever, make_comp, make_request


def make_query_plan(refinement_steps: list[dict], market_stats_params: list[dict] | None = None) -> QueryPlan:
    return QueryPlan(
        comps_search_params={
            "submarket_id": "chi-fulton-market",
            "property_type": "office",
            "min_sf": 15000,
            "max_sf": 25000,
            "lease_type": "direct",
            "date_from": "2025-01-01",
            "date_to": "2026-12-31",
            "radius_miles": 1.0,
            "k": 10,
        },
        market_stats_params=market_stats_params if market_stats_params is not None else [
            {"submarket_id": "chi-fulton-market", "metric": "vacancy_rate"}
        ],
        refinement_policy=[RefinementStep(**step) for step in refinement_steps],
    )


@pytest.mark.anyio
async def test_full_graph_run_reaches_sufficiency_on_second_iteration(monkeypatch):
    """End-to-end: the hub (compiled graph) drives Data Retrieval Agent ->
    market stats -> a 2-pass retrieval loop -> context builder -> Valuation
    Agent -> verifier, with no step calling another directly."""
    plan = make_query_plan(refinement_steps=[{"adjust": "radius_miles", "to": 5.0}])

    async def fake_formulate_query(request):
        return plan

    series = TimeSeries(
        submarket_id="chi-fulton-market",
        metric="vacancy_rate",
        points=[TimeSeriesPoint(period="2026-Q2", value=0.1)],
        yoy_change=-0.01,
        percentile_rank=0.5,
    )

    call_count = {"n": 0}

    def fake_comps_search(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return [make_comp("c_1")]
        return [make_comp(f"c_{i}") for i in range(2, 7)]

    result = ValuationResult(
        recommended_rent_psf=42.0,
        range_low=40.0,
        range_high=44.0,
        confidence=0.9,
        rationale_text="test",
        cited_comp_ids=["c_2"],
        cited_market_stat_ids=["chi-fulton-market_vacancy_rate"],
        needs_human_review=False,
    )

    async def fake_synthesize_valuation(evidence):
        return result

    monkeypatch.setattr(nodes, "formulate_query", fake_formulate_query)
    monkeypatch.setattr(nodes, "market_stats", lambda submarket_id, metric, time_window: series)
    monkeypatch.setattr(nodes, "VectorRetriever", lambda: StubVectorRetriever())
    monkeypatch.setattr(nodes, "comps_search", fake_comps_search)
    monkeypatch.setattr(nodes, "synthesize_valuation", fake_synthesize_valuation)

    compiled = graph_module.build_graph()
    final_state = await compiled.ainvoke({"request": make_request(), "trace": []})

    assert call_count["n"] == 2
    assert final_state["iteration"] == 2
    steps = [span.step for span in final_state["trace"]]
    assert steps == [
        "query_formulation",
        "market_stats_fetch",
        "semantic_retrieval",
        "retrieval_iteration_1",
        "retrieval_iteration_2",
        "context_builder",
        "valuation_synthesis",
        "verification_and_confidence",
    ]
    assert final_state["result"].needs_human_review is False


@pytest.mark.anyio
async def test_full_graph_run_stops_at_max_iterations_when_never_sufficient(monkeypatch):
    plan = make_query_plan(
        refinement_steps=[
            {"adjust": "radius_miles", "to": 5.0},
            {"adjust": "radius_miles", "to": 10.0},
        ],
        market_stats_params=[],
    )

    async def fake_formulate_query(request):
        return plan

    result = ValuationResult(
        recommended_rent_psf=42.0,
        range_low=40.0,
        range_high=44.0,
        confidence=0.3,
        rationale_text="thin evidence",
        cited_comp_ids=[],
        cited_market_stat_ids=[],
        needs_human_review=False,
    )

    async def fake_synthesize_valuation(evidence):
        return result

    monkeypatch.setattr(nodes, "formulate_query", fake_formulate_query)
    monkeypatch.setattr(nodes, "market_stats", lambda **kwargs: None)
    monkeypatch.setattr(nodes, "VectorRetriever", lambda: StubVectorRetriever())
    monkeypatch.setattr(nodes, "comps_search", lambda **kwargs: [make_comp("c_1")])
    monkeypatch.setattr(nodes, "synthesize_valuation", fake_synthesize_valuation)

    compiled = graph_module.build_graph()
    final_state = await compiled.ainvoke({"request": make_request(), "trace": []})

    retrieval_spans = [span for span in final_state["trace"] if span.step.startswith("retrieval_iteration_")]
    assert len(retrieval_spans) == 3  # default max_retrieval_iterations, never sufficient
    assert final_state["result"].needs_human_review is True


@pytest.mark.anyio
async def test_evaluation_layer_grounds_a_semantic_only_citation(monkeypatch):
    """Evaluation-layer cohesion check: a comp that exists ONLY because the
    semantic retrieval layer surfaced it (structured comps_search finds
    nothing) must still verify as grounded when cited, and must still count
    toward the deterministic confidence score — groundedness_verifier.py and
    confidence.py are provenance-agnostic by design, and this proves it end
    to end rather than at the unit level."""
    plan = make_query_plan(refinement_steps=[], market_stats_params=[])

    async def fake_formulate_query(request):
        return plan

    semantic_comp = make_comp("c_semantic_only")
    semantic_doc = RetrievedDocument(
        doc_id=semantic_comp.comp_id,
        doc_type="comp",
        text="semantic match",
        metadata=json.loads(semantic_comp.model_dump_json()),
        source_system="test",
        score=0.42,
    )
    stub_result = RetrievalResult(query="q", matches=[semantic_doc])

    result = ValuationResult(
        recommended_rent_psf=42.0,
        range_low=40.0,
        range_high=44.0,
        confidence=0.9,
        rationale_text="Based on comp c_semantic_only.",
        cited_comp_ids=["c_semantic_only"],
        cited_market_stat_ids=[],
        needs_human_review=False,
    )

    async def fake_synthesize_valuation(evidence):
        # Structured retrieval contributed nothing; this citation can only
        # resolve if the semantic match survived context building.
        assert [c.comp_id for c in evidence.top_comps] == ["c_semantic_only"]
        return result

    monkeypatch.setattr(nodes, "formulate_query", fake_formulate_query)
    monkeypatch.setattr(nodes, "market_stats", lambda **kwargs: None)
    monkeypatch.setattr(nodes, "VectorRetriever", lambda: StubVectorRetriever(result=stub_result))
    monkeypatch.setattr(nodes, "comps_search", lambda **kwargs: [])  # structured path finds nothing
    monkeypatch.setattr(nodes, "synthesize_valuation", fake_synthesize_valuation)

    compiled = graph_module.build_graph()
    final_state = await compiled.ainvoke({"request": make_request(), "trace": []})

    evidence = final_state["evidence"]
    assert evidence.summary_stats.comp_count == 1
    assert verify_groundedness(final_state["result"], evidence) is True
    assert compute_confidence(evidence) > 0.0
    assert final_state["result"].needs_human_review is True  # only 1 comp, correctly still routed to review


def test_agents_do_not_import_each_other():
    """Hub-and-spoke guardrail: the Data Retrieval Agent and Valuation
    Agent must only ever be invoked by the orchestrator, never each other."""
    import app.agents.data_retrieval_agent as retrieval_agent
    import app.agents.valuation_agent as valuation_agent

    assert "valuation_agent" not in vars(retrieval_agent)
    assert "data_retrieval_agent" not in vars(valuation_agent)


def test_only_orchestrator_nodes_import_the_agents():
    """Static guardrail: app.agents.* is imported only from within
    app/orchestrator (the hub) or the agents' own package — nothing else in
    the app is allowed to call an agent directly, enforcing hub-and-spoke."""
    app_dir = pathlib.Path(__file__).resolve().parent.parent / "app"
    offenders = []
    for path in app_dir.rglob("*.py"):
        if "agents" in path.parts or "orchestrator" in path.parts:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.agents"):
                offenders.append(str(path))
    assert offenders == []
