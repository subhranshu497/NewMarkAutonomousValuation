from app.orchestrator.state import OrchestratorState
from app.schemas.request import ValuationRequest
from app.schemas.result import ValuationResponse


async def run_valuation(request: ValuationRequest) -> ValuationResponse:
    """DESIGN.md §4/§6.2 — deterministic plan -> act -> check state machine.

    Steps (to be implemented):
    1. plan: call agents.data_retrieval_agent once to get initial query
       params + refinement_policy (1 of the 2 LLM calls this request budget
       allows, per the NFR "<=2 reasoning calls" cap).
    2. act: call tools.comps_search + tools.market_stats.
    3. check: logic.sufficiency.is_sufficient. If insufficient and
       state.iteration < max_retrieval_iterations, apply the next
       refinement_policy step mechanically (no further LLM calls) and
       repeat from (2).
    4. logic.context_builder.build_evidence_bundle over whatever evidence
       exists once sufficient or the iteration cap is hit.
    5. agents.valuation_agent (2nd and last LLM call) reasons over the
       evidence bundle.
    6. logic.groundedness_verifier + logic.confidence score the output.
    7. Route to auto-publish or storage.review_queue per §6.6 thresholds.
    8. Persist the full trace via storage.trace_store (FR9).
    """
    state = OrchestratorState(request=request)
    raise NotImplementedError
