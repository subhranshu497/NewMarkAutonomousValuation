import json
import logging
from pathlib import Path

import lancedb
from lancedb.pydantic import LanceModel, Vector

from app.config import Settings, get_settings
from app.ingestion.schema import IngestDocument

logger = logging.getLogger(__name__)


def _record_schema(dim: int) -> type[LanceModel]:
    class EvidenceDocumentRecord(LanceModel):
        doc_id: str
        doc_type: str
        text: str
        metadata_json: str
        source_system: str
        ingested_at: str
        vector: Vector(dim)  # type: ignore[valid-type]

    return EvidenceDocumentRecord


class LanceVectorStore:
    """Embedded (no server process) vector store for retrievable evidence
    documents, keyed by doc_id so re-running ingestion upserts idempotently
    instead of duplicating rows."""

    def __init__(self, settings: Settings | None = None):
        settings = settings or get_settings()
        self._table_name = settings.lancedb_table_name
        self._dim = settings.voyage_embedding_dimension
        Path(settings.lancedb_uri).mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(settings.lancedb_uri)

    def _table(self):
        return self._db.create_table(self._table_name, schema=_record_schema(self._dim), exist_ok=True)

    def upsert(self, documents: list[IngestDocument], embeddings: list[list[float]]) -> int:
        if len(documents) != len(embeddings):
            raise ValueError("documents and embeddings must be the same length")
        if not documents:
            return 0

        rows = [
            {
                "doc_id": doc.doc_id,
                "doc_type": doc.doc_type,
                "text": doc.text,
                "metadata_json": json.dumps(doc.metadata, default=str),
                "source_system": doc.source_system,
                "ingested_at": doc.ingested_at.isoformat(),
                "vector": vector,
            }
            for doc, vector in zip(documents, embeddings)
        ]

        table = self._table()
        table.merge_insert("doc_id").when_matched_update_all().when_not_matched_insert_all().execute(rows)
        logger.info("upserted %d documents into table=%s", len(rows), self._table_name)
        return len(rows)

    def count(self) -> int:
        return self._table().count_rows()

    def get_by_id(self, doc_id: str) -> dict | None:
        escaped = doc_id.replace("'", "''")
        results = self._table().search().where(f"doc_id = '{escaped}'").limit(1).to_list()
        return results[0] if results else None
