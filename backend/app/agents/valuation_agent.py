from app.schemas.evidence import EvidenceBundle
from app.schemas.result import ValuationResult


def synthesize_valuation(evidence: EvidenceBundle) -> ValuationResult:
    """The Valuation Agent LLM call (2nd and last per request). Uses the
    valuation-synthesis skill via claude_client, then the result is checked
    by logic.groundedness_verifier before being trusted."""
    raise NotImplementedError
