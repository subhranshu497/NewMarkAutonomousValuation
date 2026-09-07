import json
from datetime import date, timedelta

import pytest

from app.agents.data_retrieval_agent import QueryPlan, RefinementStep
from app.orchestrator import nodes
from app.retrieval.schema import RetrievalResult, RetrievedDocument
from app.schemas.evidence import Comp, EvidenceBundle, SummaryStats, TimeSeries, TimeSeriesPoint
from app.schemas.request import LeaseAssumptions, ValuationRequest
from app.schemas.result import ValuationResult

TODAY = date.today()


class StubVectorRetriever:
    """Stands in for app.retrieval.retriever.VectorRetriever so orchestrator
    tests never make real Voyage/LanceDB calls."""

    def __init__(self, result: RetrievalResult | None = None, error: Exception | None = None, *args, **kwargs):
        self._result = result
        self._error = error

    async def retrieve(self, query, k=None, doc_type=None):
        if self._error is not None:
            raise self._error
        return self._result or RetrievalResult(query=query, matches=[])


def make_request() -> ValuationRequest:
    return ValuationRequest(
        submarket_id="chi-fulton-market",
        property_type="office",
        space_sf=20000,
        lease_assumptions=LeaseAssumptions(lease_type="direct", term_months=84, concessions_assumed=None),
        requested_by="tester",
    )


def make_comp(comp_id: str, days_ago: int = 30) -> Comp:
    return Comp(
        comp_id=comp_id,
        address="123 Test St",
        submarket_id="chi-fulton-market",
        sf=20000,
        lease_type="direct",
        asking_rent_psf=42.0,
        effective_rent_psf=39.0,
        lease_start_date=TODAY - timedelta(days=days_ago),
        tenant_industry="technology",
        concessions=None,
        source_system="test",
        last_verified_at="2026-08-01T00:00:00Z",
    )


def make_market_stats() -> list[TimeSeries]:
    return [
        TimeSeries(
            submarket_id="chi-fulton-market",
            metric="vacancy_rate",
            points=[TimeSeriesPoint(period="2026-Q2", value=0.1)],
            yoy_change=-0.01,
            percentile_rank=0.5,
        )
    ]


def make_plan(refinement_steps=None) -> QueryPlan:
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
        market_stats_params=[{"submarket_id": "chi-fulton-market", "metric": "vacancy_rate"}],
        refinement_policy=[RefinementStep(**step) for step in (refinement_steps or [])],
    )


@pytest.mark.anyio
async def test_formulate_query_node_seeds_state(monkeypatch):
    plan = make_plan()

    async def fake_formulate_query(request):
        return plan

    monkeypatch.setattr(nodes, "formulate_query", fake_formulate_query)

    update = await nodes.formulate_query_node({"request": make_request()})

    assert update["plan"] is plan
    assert update["current_comps_params"] == plan.comps_search_params
    assert update["iteration"] == 0
    assert update["comps"] == []
    assert update["trace"][0].step == "query_formulation"


@pytest.mark.anyio
async def test_fetch_market_stats_node(monkeypatch):
    series = make_market_stats()[0]
    monkeypatch.setattr(nodes, "market_stats", lambda submarket_id, metric, time_window: series)

    update = await nodes.fetch_market_stats_node({"plan": make_plan()})

    assert update["market_stats_results"] == [series]
    assert update["trace"][0].step == "market_stats_fetch"


@pytest.mark.anyio
async def test_semantic_retrieve_node_merges_new_comps_and_stats(monkeypatch):
    comp = make_comp("c_sem")
    series = make_market_stats()[0]
    comp_doc = RetrievedDocument(
        doc_id=comp.comp_id,
        doc_type="comp",
        text="comp text",
        metadata=json.loads(comp.model_dump_json()),
        source_system="test",
        score=0.9,
    )
    stat_doc = RetrievedDocument(
        doc_id="chi-fulton-market_vacancy_rate",
        doc_type="market_stat",
        text="stat text",
        metadata=json.loads(series.model_dump_json()),
        source_system="test",
        score=0.8,
    )
    stub_result = RetrievalResult(query="q", matches=[comp_doc, stat_doc])
    monkeypatch.setattr(nodes, "VectorRetriever", lambda: StubVectorRetriever(result=stub_result))

    state = {"request": make_request(), "comps": [], "market_stats_results": []}
    update = await nodes.semantic_retrieve_node(state)

    assert [c.comp_id for c in update["comps"]] == ["c_sem"]
    assert update["market_stats_results"] == [series]
    assert update["trace"][0].step == "semantic_retrieval"


@pytest.mark.anyio
async def test_semantic_retrieve_node_dedupes_against_existing_comps(monkeypatch):
    existing = make_comp("c_1")
    comp_doc = RetrievedDocument(
        doc_id="c_1",
        doc_type="comp",
        text="comp text",
        metadata=json.loads(existing.model_dump_json()),
        source_system="test",
        score=0.9,
    )
    stub_result = RetrievalResult(query="q", matches=[comp_doc])
    monkeypatch.setattr(nodes, "VectorRetriever", lambda: StubVectorRetriever(result=stub_result))

    state = {"request": make_request(), "comps": [existing], "market_stats_results": []}
    update = await nodes.semantic_retrieve_node(state)

    assert len(update["comps"]) == 1


@pytest.mark.anyio
async def test_semantic_retrieve_node_no_matches_contributes_nothing(monkeypatch):
    monkeypatch.setattr(nodes, "VectorRetriever", lambda: StubVectorRetriever())

    state = {"request": make_request(), "comps": [], "market_stats_results": []}
    update = await nodes.semantic_retrieve_node(state)

    assert update["comps"] == []
    assert update["market_stats_results"] == []
    assert "No data found" in update["trace"][0].result_summary


@pytest.mark.anyio
async def test_semantic_retrieve_node_degrades_gracefully_on_error(monkeypatch):
    monkeypatch.setattr(nodes, "VectorRetriever", lambda: StubVectorRetriever(error=RuntimeError("voyage down")))

    state = {"request": make_request(), "comps": [], "market_stats_results": []}
    update = await nodes.semantic_retrieve_node(state)

    assert "comps" not in update
    assert "unavailable" in update["trace"][0].result_summary


def test_retrieve_comps_node_stops_when_sufficient(monkeypatch):
    comps = [make_comp(f"c_{i}") for i in range(5)]
    monkeypatch.setattr(nodes, "comps_search", lambda **kwargs: comps)
    plan = make_plan()

    state = {
        "request": make_request(),
        "plan": plan,
        "current_comps_params": plan.comps_search_params,
        "iteration": 0,
        "comps": [],
        "market_stats_results": make_market_stats(),
    }

    update = nodes.retrieve_comps_node(state)

    assert update["sufficient"] is True
    assert update["stop_retrieval"] is True
    assert update["iteration"] == 1
    assert len(update["comps"]) == 5


def test_retrieve_comps_node_applies_refinement_step_when_insufficient(monkeypatch):
    monkeypatch.setattr(nodes, "comps_search", lambda **kwargs: [make_comp("c_1")])
    plan = make_plan(refinement_steps=[{"adjust": "radius_miles", "to": 5.0}])

    state = {
        "request": make_request(),
        "plan": plan,
        "current_comps_params": plan.comps_search_params,
        "iteration": 0,
        "comps": [],
        "market_stats_results": [],
    }

    update = nodes.retrieve_comps_node(state)

    assert update["sufficient"] is False
    assert update["stop_retrieval"] is False
    assert update["current_comps_params"]["radius_miles"] == 5.0


def test_retrieve_comps_node_stops_when_refinement_exhausted(monkeypatch):
    monkeypatch.setattr(nodes, "comps_search", lambda **kwargs: [make_comp("c_1")])
    plan = make_plan(refinement_steps=[])

    state = {
        "request": make_request(),
        "plan": plan,
        "current_comps_params": plan.comps_search_params,
        "iteration": 0,
        "comps": [],
        "market_stats_results": [],
    }

    update = nodes.retrieve_comps_node(state)

    assert update["stop_retrieval"] is True


def test_build_context_node():
    comps = [make_comp(f"c_{i}") for i in range(3)]

    update = nodes.build_context_node({"comps": comps, "market_stats_results": [], "request": make_request()})

    assert update["evidence"].summary_stats.comp_count == 3
    assert update["trace"][0].step == "context_builder"


@pytest.mark.anyio
async def test_synthesize_valuation_node(monkeypatch):
    result = ValuationResult(
        recommended_rent_psf=42.0,
        range_low=40.0,
        range_high=44.0,
        confidence=0.8,
        rationale_text="test",
        cited_comp_ids=[],
        cited_market_stat_ids=[],
        needs_human_review=False,
    )

    async def fake_synthesize_valuation(evidence):
        return result

    monkeypatch.setattr(nodes, "synthesize_valuation", fake_synthesize_valuation)

    evidence = EvidenceBundle(
        summary_stats=SummaryStats(
            median_asking_rent_psf=42.0,
            mean_asking_rent_psf=42.0,
            rent_spread=0.0,
            comp_count=1,
            comp_count_trailing_12mo=1,
        ),
        top_comps=[],
        market_trend_deltas=[],
    )

    update = await nodes.synthesize_valuation_node({"evidence": evidence})

    assert update["result"] is result
    assert update["trace"][0].step == "valuation_synthesis"


def test_verify_and_score_node_flags_review_when_ungrounded():
    comps = [make_comp(f"c_{i}") for i in range(5)]
    evidence = EvidenceBundle(
        summary_stats=SummaryStats(
            median_asking_rent_psf=42.0,
            mean_asking_rent_psf=42.0,
            rent_spread=1.0,
            comp_count=5,
            comp_count_trailing_12mo=5,
        ),
        top_comps=comps,
        market_trend_deltas=[],
    )
    result = ValuationResult(
        recommended_rent_psf=42.0,
        range_low=40.0,
        range_high=44.0,
        confidence=0.9,
        rationale_text="test",
        cited_comp_ids=["does-not-exist"],
        cited_market_stat_ids=[],
        needs_human_review=False,
    )

    update = nodes.verify_and_score_node({"evidence": evidence, "result": result})

    assert update["result"].needs_human_review is True
    assert update["trace"][0].params["grounded"] is False


def test_verify_and_score_node_no_review_when_grounded_and_confident():
    comps = [make_comp(f"c_{i}") for i in range(5)]
    evidence = EvidenceBundle(
        summary_stats=SummaryStats(
            median_asking_rent_psf=42.0,
            mean_asking_rent_psf=42.0,
            rent_spread=1.0,
            comp_count=5,
            comp_count_trailing_12mo=5,
        ),
        top_comps=comps,
        market_trend_deltas=[],
    )
    result = ValuationResult(
        recommended_rent_psf=42.0,
        range_low=40.0,
        range_high=44.0,
        confidence=0.95,
        rationale_text="test",
        cited_comp_ids=["c_0"],
        cited_market_stat_ids=[],
        needs_human_review=False,
    )

    update = nodes.verify_and_score_node({"evidence": evidence, "result": result})

    assert update["result"].needs_human_review is False
    assert update["trace"][0].params["grounded"] is True
