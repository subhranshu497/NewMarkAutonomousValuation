import asyncio
import logging
from pathlib import Path

from app.ingestion.embedder import VoyageEmbedder
from app.ingestion.loaders import load_records
from app.ingestion.normalizers import normalize_record
from app.ingestion.schema import IngestDocument, IngestionError, IngestionReport
from app.ingestion.vector_store import LanceVectorStore

logger = logging.getLogger(__name__)

INPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "input"

# Filename substring -> (doc_type, source_system label). Checked in order,
# against the lowercased file stem, so e.g. "comps_batch2.json" and
# "market_stats_q3.csv" both resolve without a code change per file.
_DOC_TYPE_BY_FILENAME: list[tuple[str, str, str]] = [
    ("market_stat", "market_stat", "snowflake-market-stats"),
    ("comp", "comp", "opensearch-comps"),
]

_LOADABLE_SUFFIXES = {".json", ".csv"}


def discover_sources(input_dir: Path = INPUT_DIR) -> list[tuple[Path, str, str]]:
    """Scans `input_dir` for every ingestible file and infers doc_type/
    source_system from the filename, so dropping additional comp or
    market-stat files (or multiple of either) into the directory is picked
    up automatically — no registry to edit. A file whose name matches
    neither pattern is skipped with a warning rather than failing the whole
    scan."""
    if not input_dir.is_dir():
        logger.warning("ingestion input directory %s does not exist — nothing to ingest", input_dir)
        return []

    sources = []
    for path in sorted(input_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in _LOADABLE_SUFFIXES:
            continue
        stem = path.stem.lower()
        match = next((entry for entry in _DOC_TYPE_BY_FILENAME if entry[0] in stem), None)
        if match is None:
            logger.warning("skipping %s: filename doesn't indicate a known doc_type (comp/market_stat)", path.name)
            continue
        _, doc_type, source_system = match
        sources.append((path, doc_type, source_system))
    return sources


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
    """Ingestion-layer entry point: normalize every source under
    `data/input/` (or an explicit `sources` list) into IngestDocuments, embed
    them with Voyage AI, and upsert them into the LanceDB vector store, keyed
    by doc_id for idempotent re-runs."""
    embedder = VoyageEmbedder()
    vector_store = LanceVectorStore()

    reports = []
    for path, doc_type, source_system in sources if sources is not None else discover_sources():
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
