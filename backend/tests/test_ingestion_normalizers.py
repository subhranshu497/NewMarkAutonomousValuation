import pytest

from app.ingestion.normalizers import normalize_comp, normalize_market_stat, normalize_record
from app.ingestion.schema import IngestionError
from app.logic.groundedness_verifier import market_stat_id


def make_raw_comp(**overrides) -> dict:
    raw = {
        "comp_id": "c_1042",
        "address": "1200 W Fulton Market",
        "submarket_id": "chi-fulton-market",
        "sf": 18500,
        "lease_type": "direct",
        "asking_rent_psf": 42.5,
        "effective_rent_psf": 39.75,
        "lease_start_date": "2025-11-01",
        "tenant_industry": "technology",
        "concessions": "3 months free on a 7-year term",
        "source_system": "opensearch-comps",
        "last_verified_at": "2026-08-15T00:00:00Z",
    }
    raw.update(overrides)
    return raw


def make_raw_market_stat(**overrides) -> dict:
    raw = {
        "submarket_id": "chi-fulton-market",
        "metric": "vacancy_rate",
        "points": [{"period": "2026-Q1", "value": 0.109}, {"period": "2026-Q2", "value": 0.104}],
        "yoy_change": -0.021,
        "percentile_rank": 0.72,
    }
    raw.update(overrides)
    return raw


def test_normalize_comp_builds_embeddable_text_and_metadata():
    doc = normalize_comp(make_raw_comp(), source_system="fallback")

    assert doc.doc_id == "c_1042"
    assert doc.doc_type == "comp"
    assert "18,500 SF direct lease" in doc.text
    assert "Concessions: 3 months free on a 7-year term." in doc.text
    assert doc.metadata["comp_id"] == "c_1042"
    assert doc.source_system == "opensearch-comps"


def test_normalize_comp_handles_aliased_non_uniform_field_names():
    raw = {
        "Comp ID": "c_2001",
        "Property Address": "500 W Madison St",
        "submarket_id": "chi-river-north",
        "Square Feet": 12000,
        "lease_type": "sublease",
        "Asking Rent": 38.0,
        "Effective Rent": 35.0,
        "Lease Start": "2026-02-01",
        "Industry": "legal",
        "concessions": "",
        "source_system": "csv-export",
        "Verified At": "2026-08-01T00:00:00Z",
    }
    doc = normalize_comp(raw, source_system="csv-export")
    assert doc.doc_id == "c_2001"
    assert doc.metadata["address"] == "500 W Madison St"
    assert doc.metadata["sf"] == 12000
    assert doc.metadata["concessions"] is None


def test_normalize_comp_raises_ingestion_error_on_invalid_record():
    raw = make_raw_comp(sf="not-a-number")
    with pytest.raises(IngestionError):
        normalize_comp(raw, source_system="opensearch-comps")


def test_normalize_comp_masks_pii_injected_into_free_text_fields():
    raw = make_raw_comp(concessions="3 months free, contact broker at jane@corp.com or 312-555-0134")
    doc = normalize_comp(raw, source_system="opensearch-comps")

    assert "jane@corp.com" not in doc.text
    assert "312-555-0134" not in doc.text
    assert "[REDACTED_EMAIL]" in doc.text
    assert "[REDACTED_PHONE]" in doc.text
    assert doc.metadata["concessions"] == "3 months free, contact broker at [REDACTED_EMAIL] or [REDACTED_PHONE]"
    assert doc.pii_redacted is True


def test_normalize_market_stat_builds_doc_id_matching_citation_convention():
    doc = normalize_market_stat(make_raw_market_stat(), source_system="snowflake-market-stats")
    assert doc.doc_id == market_stat_id("chi-fulton-market", "vacancy_rate")
    assert doc.doc_type == "market_stat"
    assert "down 2.1% YoY" in doc.text
    assert "percentile rank 72" in doc.text


def test_normalize_market_stat_raises_ingestion_error_on_invalid_record():
    raw = make_raw_market_stat(points="not-a-list")
    with pytest.raises(IngestionError):
        normalize_market_stat(raw, source_system="snowflake-market-stats")


def test_normalize_record_dispatches_on_doc_type():
    doc = normalize_record(make_raw_comp(), "comp", "opensearch-comps")
    assert doc.doc_type == "comp"


def test_normalize_record_raises_for_unknown_doc_type():
    with pytest.raises(IngestionError):
        normalize_record({}, "unknown_type", "some-source")
