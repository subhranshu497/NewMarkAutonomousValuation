from voyageai import AsyncClient

from app.config import Settings, get_settings


class VoyageQueryEmbedder:
    """Query-side counterpart to the ingestion layer's document embedder.

    Voyage embeddings are asymmetric: documents are embedded with
    input_type="document" (see app/ingestion/embedder.py) and queries must be
    embedded with input_type="query" to land in the same similarity space.
    Kept independent of the ingestion layer so the two layers can evolve
    (and fail) without coupling to each other's internals.
    """

    def __init__(self, settings: Settings | None = None):
        settings = settings or get_settings()
        self._client = AsyncClient(api_key=settings.voyage_api_key, max_retries=5, timeout=30.0)
        self._model = settings.voyage_model

    async def embed_query(self, query: str) -> list[float]:
        result = await self._client.embed([query], model=self._model, input_type="query")
        return result.embeddings[0]
