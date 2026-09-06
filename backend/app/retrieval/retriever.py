import json
import logging

from app.config import Settings, get_settings
from app.retrieval.query_embedder import VoyageQueryEmbedder
from app.retrieval.schema import RetrievalResult, RetrievedDocument
from app.retrieval.vector_store import LanceRetrievalStore

logger = logging.getLogger(__name__)


class VectorRetriever:
    """Retrieval layer: embeds a free-text query with Voyage AI and returns
    the top-k most similar evidence documents from LanceDB by cosine
    similarity.

    Anti-hallucination contract: any row below `retrieval_min_similarity`
    is dropped, and an empty match list (empty store, or nothing clears the
    threshold) is a first-class, expected outcome — not an error, and never
    a reason to fabricate a result. Callers must branch on `result.found`
    before treating `matches` as evidence.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        embedder: VoyageQueryEmbedder | None = None,
        store: LanceRetrievalStore | None = None,
    ):
        self._settings = settings or get_settings()
        self._embedder = embedder or VoyageQueryEmbedder(self._settings)
        self._store = store or LanceRetrievalStore(self._settings)

    async def retrieve(
        self,
        query: str,
        k: int | None = None,
        doc_type: str | None = None,
    ) -> RetrievalResult:
        query = query.strip()
        if not query:
            return RetrievalResult(query=query, matches=[])

        top_k = k or self._settings.retrieval_top_k
        query_vector = await self._embedder.embed_query(query)
        rows = self._store.search_by_vector(query_vector, k=top_k, doc_type=doc_type)

        matches = []
        for row in rows:
            similarity = 1.0 - row["_distance"]
            if similarity < self._settings.retrieval_min_similarity:
                continue
            matches.append(
                RetrievedDocument(
                    doc_id=row["doc_id"],
                    doc_type=row["doc_type"],
                    text=row["text"],
                    metadata=json.loads(row["metadata_json"]),
                    source_system=row["source_system"],
                    score=round(similarity, 4),
                    embedding=row["vector"],
                )
            )

        if not matches:
            logger.info("no matches above similarity threshold for query=%r", query)

        return RetrievalResult(query=query, query_embedding=query_vector, matches=matches)
