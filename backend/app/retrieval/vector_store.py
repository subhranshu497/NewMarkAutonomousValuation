import logging

import lancedb

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class LanceRetrievalStore:
    """Read-only access to the LanceDB table the ingestion layer writes to.
    Deliberately separate from app.ingestion.vector_store.LanceVectorStore —
    that class owns the write/upsert path, this one only ever queries."""

    def __init__(self, settings: Settings | None = None):
        settings = settings or get_settings()
        self._uri = settings.lancedb_uri
        self._table_name = settings.lancedb_table_name

    def _open_table(self):
        db = lancedb.connect(self._uri)
        try:
            return db.open_table(self._table_name)
        except ValueError:
            # Table doesn't exist yet (ingestion hasn't run) — treat as
            # "no data," never an error, so callers can't mistake this for
            # a broken query and improvise an answer instead.
            logger.warning("lancedb table %r not found at %r", self._table_name, self._uri)
            return None

    def search_by_vector(self, vector: list[float], k: int, doc_type: str | None = None) -> list[dict]:
        table = self._open_table()
        if table is None or table.count_rows() == 0:
            return []

        query = table.search(vector).metric("cosine")
        if doc_type is not None:
            escaped = doc_type.replace("'", "''")
            query = query.where(f"doc_type = '{escaped}'", prefilter=True)
        return query.limit(k).to_list()
