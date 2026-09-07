import asyncio
import logging
from pathlib import Path

from app.ingestion.embedder import VoyageEmbedder
from app.ingestion.loaders import load_records
from app.ingestion.normalizers import normalize_record
from app.ingestion.schema import IngestDocument, IngestionError, IngestionReport
from app.ingestion.vector_store import LanceVectorStore

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "data" / "fixtures"

# Registry of ingestible sources: (file path, doc_type, source_system label).
# Onboarding a new heterogeneous source is one entry here; loaders.py and
# normalizers.py already handle format/schema drift generically.
SOURCES: list[tuple[Path, str, str]] = [
    (FIXTURES_DIR / "comps.json", "comp", "opensearch-comps"),
    (FIXTURES_DIR / "market_stats.json", "market_stat", "snowflake-market-stats"),
]


def _normalize_batch(
    raw_records: list[dict], doc_type: str, source_system: str
) -> tuple[list[IngestDocument], list[str]]:
    documents: list[IngestDocument] = []
    skipped_reasons: list[str] = []
    for raw in raw_records:
        try:
            documents.append(normalize_record(raw, doc_type, source_system))
        except IngestionError as exc:
            logger.warning("skipping unparseable %s record: %s", doc_type, exc.reason)
            skipped_reasons.append(exc.reason)
    return documents, skipped_reasons


async def ingest_source(
    path: Path,
    doc_type: str,
    source_system: str,
    embedder: VoyageEmbedder,
    vector_store: LanceVectorStore,
) -> IngestionReport:
    raw_records = load_records(path)
    documents, skipped_reasons = _normalize_batch(raw_records, doc_type, source_system)
    pii_redactions = sum(1 for doc in documents if doc.pii_redacted)

    embeddings = await embedder.embed_documents([doc.text for doc in documents])
    ingested = vector_store.upsert(documents, embeddings)

    return IngestionReport(
        source=str(path),
        total_records=len(raw_records),
        ingested=ingested,
        skipped=len(skipped_reasons),
        skipped_reasons=skipped_reasons,
        pii_redactions=pii_redactions,
    )


async def run_ingestion(sources: list[tuple[Path, str, str]] | None = None) -> list[IngestionReport]:
    """Ingestion-layer entry point: normalize every configured source into
    IngestDocuments, embed them with Voyage AI, and upsert them into the
    LanceDB vector store, keyed by doc_id for idempotent re-runs."""
    embedder = VoyageEmbedder()
    vector_store = LanceVectorStore()

    reports = []
    for path, doc_type, source_system in sources or SOURCES:
        report = await ingest_source(path, doc_type, source_system, embedder, vector_store)
        reports.append(report)
        logger.info(
            "ingested %s: %d/%d records (%d skipped, %d PII-redacted)",
            report.source,
            report.ingested,
            report.total_records,
            report.skipped,
            report.pii_redactions,
        )
    return reports


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    reports = asyncio.run(run_ingestion())
    total_ingested = sum(report.ingested for report in reports)
    total_skipped = sum(report.skipped for report in reports)
    total_pii_redactions = sum(report.pii_redactions for report in reports)
    logger.info(
        "ingestion complete: %d ingested, %d skipped, %d PII-redacted across %d source(s)",
        total_ingested,
        total_skipped,
        total_pii_redactions,
        len(reports),
    )


if __name__ == "__main__":
    main()
