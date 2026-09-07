from fastapi.testclient import TestClient

from app.agents.data_retrieval_agent import QueryPlan
from app.main import app
from app.orchestrator import nodes
from app.schemas.result import ValuationResult
from tests.test_orchestrator_nodes import StubVectorRetriever

client = TestClient(app)


def test_create_valuation_runs_the_full_hub_and_spoke_graph(monkeypatch):
    """Full stack: API -> orchestrator hub (LangGraph) -> real comps_search
    / market_stats tools (real fixtures, unmocked) -> mocked LLM agents and
    semantic retriever -> deterministic verifier/confidence -> response.
    Only the two LLM calls and the Voyage/LanceDB-backed semantic retriever
    are mocked (no real network calls in tests); everything else is the
    real deterministic pipeline."""

    plan = QueryPlan(
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
        refinement_policy=[],
    )

    async def fake_formulate_query(request):
        return plan

    result = ValuationResult(
        recommended_rent_psf=43.0,
        range_low=41.0,
        range_high=45.0,
        confidence=0.85,
        rationale_text="Rents are trending up based on recent comps.",
        cited_comp_ids=["c_1042"],
        cited_market_stat_ids=["chi-fulton-market_vacancy_rate"],
        needs_human_review=False,
    )

    async def fake_synthesize_valuation(evidence):
        return result

    monkeypatch.setattr(nodes, "formulate_query", fake_formulate_query)
    monkeypatch.setattr(nodes, "VectorRetriever", lambda: StubVectorRetriever())
    monkeypatch.setattr(nodes, "synthesize_valuation", fake_synthesize_valuation)

    response = client.post(
        "/api/valuations",
        json={
            "submarket_id": "chi-fulton-market",
            "property_type": "office",
            "space_sf": 19000,
            "lease_assumptions": {"lease_type": "direct", "term_months": 84, "concessions_assumed": None},
            "requested_by": "tester",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["recommended_rent_psf"] == 43.0
    assert body["result"]["needs_human_review"] is False
    assert body["evidence"]["summary_stats"]["comp_count"] == 6
    steps = [span["step"] for span in body["trace"]]
    assert steps == [
        "query_formulation",
        "market_stats_fetch",
        "semantic_retrieval",
        "retrieval_iteration_1",
        "context_builder",
        "valuation_synthesis",
        "verification_and_confidence",
    ]

    fetched = client.get(f"/api/valuations/{body['request_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["request_id"] == body["request_id"]
