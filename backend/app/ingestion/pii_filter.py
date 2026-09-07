import logging
import re
from typing import Any

from app.ingestion.schema import IngestDocument

logger = logging.getLogger(__name__)

# Order matters: SSN is checked before PHONE/CREDIT_CARD since its narrow
# fixed shape (3-2-4 digits) would otherwise get partially swallowed by the
# looser digit-run patterns if they ran first.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("PHONE", re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
]


def mask_text(text: str) -> tuple[str, set[str]]:
    """Redacts common structured PII patterns (email, SSN, phone, credit
    card) from free text. Returns the masked text and the set of PII types
    found, so callers can log/report on what was caught without ever
    persisting the original value anywhere, including logs.

    This is regex-based pattern matching, not named-entity recognition —
    it won't catch unstructured PII like a person's name embedded in prose.
    That's a known limitation of this guardrail, not an oversight; proper
    name detection needs an NER model, which is out of scope here.
    """
    found: set[str] = set()
    masked = text
    for label, pattern in _PATTERNS:
        if pattern.search(masked):
            found.add(label)
            masked = pattern.sub(f"[REDACTED_{label}]", masked)
    return masked, found


def _mask_value(value: Any, found: set[str]) -> Any:
    if isinstance(value, str):
        masked, hits = mask_text(value)
        found |= hits
        return masked
    if isinstance(value, dict):
        return {key: _mask_value(val, found) for key, val in value.items()}
    if isinstance(value, list):
        return [_mask_value(item, found) for item in value]
    return value


def mask_document(doc: IngestDocument) -> IngestDocument:
    """Ingestion-layer guardrail — the last checkpoint before a document is
    embedded and persisted. Scans every string in the embeddable `text` and
    the preserved `metadata`, regardless of which field it showed up in:
    non-uniform sources can put anything in any field, so this doesn't
    special-case which fields are "safe" to skip.
    """
    found: set[str] = set()
    masked_text, text_hits = mask_text(doc.text)
    found |= text_hits
    masked_metadata = _mask_value(doc.metadata, found)

    if found:
        logger.warning("PII redacted from doc_id=%r types=%s", doc.doc_id, sorted(found))

    return doc.model_copy(update={"text": masked_text, "metadata": masked_metadata, "pii_redacted": bool(found)})
