from pathlib import Path

import pytest

from app.config import Settings
from app.ingestion.schema import IngestDocument
from app.ingestion.vector_store import LanceVectorStore
from app.retrieval.retriever import VectorRetriever
from app.retrieval.schema import NO_DATA_FOUND_MESSAGE
from app.retrieval.vector_store import LanceRetrievalStore

DIM = 4


class StubQueryEmbedder:
    """Returns a fixed vector regardless of query text, so tests control
    similarity purely via the vectors seeded into the store."""

    def __init__(self, vector: list[float]):
        self._vector = vector

    async def embed_query(self, query: str) -> list[float]:
        return self._vector


def make_settings(tmp_path: Path, min_similarity: float = 0.2) -> Settings:
    return Settings(
        lancedb_uri=str(tmp_path / "lancedb"),
        voyage_embedding_dimension=DIM,
        retrieval_min_similarity=min_similarity,
        retrieval_top_k=5,
    )


def seed(settings: Settings) -> None:
    writer = LanceVectorStore(settings=settings)
    docs = [
        IngestDocument(doc_id="close", doc_type="comp", text="close match", metadata={}, source_system="t"),
        IngestDocument(doc_id="far", doc_type="comp", text="far match", metadata={}, source_system="t"),
    ]
    # "close" is identical to the query vector (similarity 1.0); "far" is
    # orthogonal (similarity 0.0), which the default 0.2 threshold rejects.
    embeddings = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]]
    writer.upsert(docs, embeddings)


@pytest.mark.anyio
async def test_retrieve_returns_top_matches_above_threshold(tmp_path: Path):
    settings = make_settings(tmp_path)
    seed(settings)
    retriever = VectorRetriever(
        settings=settings,
        embedder=StubQueryEmbedder([1.0, 0.0, 0.0, 0.0]),
        store=LanceRetrievalStore(settings=settings),
    )

    result = await retriever.retrieve("space at 123 Main St")

    assert result.found is True
    assert [m.doc_id for m in result.matches] == ["close"]
    assert result.matches[0].score == 1.0
    assert result.message is None


@pytest.mark.anyio
async def test_retrieve_reports_no_data_found_when_nothing_clears_threshold(tmp_path: Path):
    settings = make_settings(tmp_path, min_similarity=0.99)
    seed(settings)
    retriever = VectorRetriever(
        settings=settings,
        # Orthogonal to both seeded vectors, so cosine similarity to each is 0.0.
        embedder=StubQueryEmbedder([0.0, 0.0, 1.0, 0.0]),
        store=LanceRetrievalStore(settings=settings),
    )

    result = await retriever.retrieve("something unrelated")

    assert result.found is False
    assert result.matches == []
    assert result.message == NO_DATA_FOUND_MESSAGE


@pytest.mark.anyio
async def test_retrieve_reports_no_data_found_on_empty_store(tmp_path: Path):
    settings = make_settings(tmp_path)
    retriever = VectorRetriever(
        settings=settings,
        embedder=StubQueryEmbedder([1.0, 0.0, 0.0, 0.0]),
        store=LanceRetrievalStore(settings=settings),
    )

    result = await retriever.retrieve("anything")

    assert result.found is False
    assert result.message == NO_DATA_FOUND_MESSAGE


@pytest.mark.anyio
async def test_retrieve_blank_query_returns_no_matches_without_embedding_call(tmp_path: Path):
    settings = make_settings(tmp_path)
    seed(settings)

    class ExplodingEmbedder:
        async def embed_query(self, query: str) -> list[float]:
            raise AssertionError("should not embed a blank query")

    retriever = VectorRetriever(
        settings=settings,
        embedder=ExplodingEmbedder(),
        store=LanceRetrievalStore(settings=settings),
    )

    result = await retriever.retrieve("   ")

    assert result.found is False
