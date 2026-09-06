import logging

from voyageai import AsyncClient

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class VoyageEmbedder:
    """Batching wrapper around the Voyage AI embeddings API, scoped to
    document-side embedding (as opposed to query-side embedding, which the
    retrieval layer will use with input_type="query" to keep the two
    embedding spaces aligned per Voyage's asymmetric-search convention)."""

    def __init__(self, settings: Settings | None = None):
        settings = settings or get_settings()
        self._client = AsyncClient(api_key=settings.voyage_api_key, max_retries=5, timeout=30.0)
        self._model = settings.voyage_model
        self._batch_size = settings.ingestion_batch_size

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            result = await self._client.embed(batch, model=self._model, input_type="document")
            vectors.extend(result.embeddings)
            logger.info(
                "embedded batch of %d texts (offset=%d, model=%s)", len(batch), start, self._model
            )
        return vectors
