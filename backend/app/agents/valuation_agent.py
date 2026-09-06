from app import claude_client
from app.schemas.evidence import EvidenceBundle
from app.schemas.result import ValuationResult


async def synthesize_valuation(evidence: EvidenceBundle) -> ValuationResult:
    """The Valuation Agent LLM call (2nd and last per request). Uses the
    valuation-synthesis skill via claude_client, then the result is checked
    by logic.groundedness_verifier before being trusted."""
    user_content = evidence.model_dump_json()
    response_text = await claude_client.call_with_skill("valuation-synthesis", user_content)
    data = claude_client.extract_json(response_text)
    return ValuationResult(**data)
