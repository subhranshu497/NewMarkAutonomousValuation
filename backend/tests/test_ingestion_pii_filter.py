from app.ingestion.pii_filter import mask_document, mask_text
from app.ingestion.schema import IngestDocument


def test_mask_text_redacts_email():
    masked, found = mask_text("Contact john.doe@example.com for details.")
    assert "john.doe@example.com" not in masked
    assert "[REDACTED_EMAIL]" in masked
    assert found == {"EMAIL"}


def test_mask_text_redacts_ssn():
    masked, found = mask_text("SSN on file: 123-45-6789.")
    assert "123-45-6789" not in masked
    assert "[REDACTED_SSN]" in masked
    assert found == {"SSN"}


def test_mask_text_redacts_phone_number():
    masked, found = mask_text("Call the broker at (312) 555-0134.")
    assert "555-0134" not in masked
    assert "[REDACTED_PHONE]" in masked
    assert found == {"PHONE"}


def test_mask_text_redacts_credit_card():
    masked, found = mask_text("Card on file: 4111 1111 1111 1111.")
    assert "4111 1111 1111 1111" not in masked
    assert "[REDACTED_CREDIT_CARD]" in masked
    assert found == {"CREDIT_CARD"}


def test_mask_text_redacts_multiple_types_in_one_string():
    masked, found = mask_text("Email jane@corp.com or call 312-555-0199.")
    assert found == {"EMAIL", "PHONE"}
    assert "jane@corp.com" not in masked
    assert "312-555-0199" not in masked


def test_mask_text_leaves_clean_text_unchanged():
    text = "3 months free on a 7-year term at 1200 W Fulton Market."
    masked, found = mask_text(text)
    assert masked == text
    assert found == set()


def test_mask_text_does_not_false_positive_on_dates_and_ids():
    # Real-estate dates/ids that share superficial digit-grouping shapes
    # with PII patterns should not be caught.
    text = "Comp c_1042, lease started 2026-01-01, verified 2026-08-15T00:00:00Z."
    masked, found = mask_text(text)
    assert masked == text
    assert found == set()


def test_mask_document_redacts_text_and_metadata_and_sets_flag():
    doc = IngestDocument(
        doc_id="c_1",
        doc_type="comp",
        text="Concessions: contact broker at jane@corp.com.",
        metadata={"concessions": "call 312-555-0134 for terms", "sf": 20000, "nested": {"note": "ssn 123-45-6789"}},
        source_system="test",
    )

    masked = mask_document(doc)

    assert "jane@corp.com" not in masked.text
    assert "[REDACTED_EMAIL]" in masked.text
    assert masked.metadata["concessions"] == "call [REDACTED_PHONE] for terms"
    assert masked.metadata["nested"]["note"] == "ssn [REDACTED_SSN]"
    assert masked.metadata["sf"] == 20000  # non-string values pass through untouched
    assert masked.pii_redacted is True


def test_mask_document_leaves_clean_document_unchanged():
    doc = IngestDocument(
        doc_id="c_1",
        doc_type="comp",
        text="Comp c_1: 20,000 SF direct lease at 1 Main St.",
        metadata={"address": "1 Main St", "sf": 20000, "concessions": None},
        source_system="test",
    )

    masked = mask_document(doc)

    assert masked.text == doc.text
    assert masked.metadata == doc.metadata
    assert masked.pii_redacted is False


def test_mask_document_recurses_through_lists():
    doc = IngestDocument(
        doc_id="ms_1",
        doc_type="market_stat",
        text="clean text",
        metadata={"points": [{"period": "2026-Q1", "value": 0.1}, {"period": "2026-Q2", "note": "call 312-555-0134"}]},
        source_system="test",
    )

    masked = mask_document(doc)

    assert masked.metadata["points"][0] == {"period": "2026-Q1", "value": 0.1}
    assert masked.metadata["points"][1]["note"] == "call [REDACTED_PHONE]"
    assert masked.pii_redacted is True
