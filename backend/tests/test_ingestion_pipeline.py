import asyncio
import json
from pathlib import Path

from app.config import Settings
from app.ingestion.pipeline import _normalize_batch, ingest_source
from app.ingestion.vector_store import LanceVectorStore

DIM = 4


class StubEmbedder:
    """Deterministic stand-in for VoyageEmbedder so pipeline tests don't
    make real network calls."""

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(i)] * DIM for i in range(len(texts))]


def make_store(tmp_path: Path) -> LanceVectorStore:
    settings = Settings(lancedb_uri=str(tmp_path / "lancedb"), voyage_embedding_dimension=DIM)
    return LanceVectorStore(settings=settings)


def test_normalize_batch_skips_invalid_records_and_reports_reasons():
    raw_records = [
        {
            "comp_id": "c_1",
            "address": "1 Main St",
            "submarket_id": "chi-fulton-market",
            "sf": 10000,
            "lease_type": "direct",
            "asking_rent_psf": 40.0,
            "effective_rent_psf": 38.0,
            "lease_start_date": "2026-01-01",
            "tenant_industry": "technology",
            "concessions": None,
            "source_system": "opensearch-comps",
            "last_verified_at": "2026-01-01T00:00:00Z",
        },
        {"comp_id": "c_bad"},  # missing required fields
    ]

    documents, skipped_reasons = _normalize_batch(raw_records, "comp", "opensearch-comps")

    assert [doc.doc_id for doc in documents] == ["c_1"]
    assert len(skipped_reasons) == 1


def test_ingest_source_embeds_and_upserts_valid_records(tmp_path: Path):
    source_path = tmp_path / "comps.json"
    source_path.write_text(
        json.dumps(
            [
                {
                    "comp_id": "c_1",
                    "address": "1 Main St",
                    "submarket_id": "chi-fulton-market",
                    "sf": 10000,
                    "lease_type": "direct",
                    "asking_rent_psf": 40.0,
                    "effective_rent_psf": 38.0,
                    "lease_start_date": "2026-01-01",
                    "tenant_industry": "technology",
                    "concessions": None,
                    "source_system": "opensearch-comps",
                    "last_verified_at": "2026-01-01T00:00:00Z",
                },
                {"comp_id": "c_bad"},
            ]
        )
    )

    store = make_store(tmp_path)
    report = asyncio.run(
        ingest_source(source_path, "comp", "opensearch-comps", StubEmbedder(), store)
    )

    assert report.total_records == 2
    assert report.ingested == 1
    assert report.skipped == 1
    assert store.count() == 1
    assert store.get_by_id("c_1") is not None
