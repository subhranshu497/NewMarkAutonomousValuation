from pathlib import Path

from app.config import Settings
from app.ingestion.schema import IngestDocument
from app.ingestion.vector_store import LanceVectorStore
from app.retrieval.vector_store import LanceRetrievalStore

DIM = 4


def make_settings(tmp_path: Path) -> Settings:
    return Settings(lancedb_uri=str(tmp_path / "lancedb"), voyage_embedding_dimension=DIM)


def seed(tmp_path: Path, settings: Settings) -> None:
    writer = LanceVectorStore(settings=settings)
    docs = [
        IngestDocument(doc_id="c_1", doc_type="comp", text="comp one", metadata={}, source_system="test"),
        IngestDocument(
            doc_id="ms_1", doc_type="market_stat", text="stat one", metadata={}, source_system="test"
        ),
    ]
    embeddings = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]]
    writer.upsert(docs, embeddings)


def test_search_by_vector_returns_closest_matches_first(tmp_path: Path):
    settings = make_settings(tmp_path)
    seed(tmp_path, settings)
    store = LanceRetrievalStore(settings=settings)

    results = store.search_by_vector([1.0, 0.0, 0.0, 0.0], k=5)

    assert results[0]["doc_id"] == "c_1"
    assert results[0]["_distance"] == 0.0


def test_search_by_vector_filters_by_doc_type(tmp_path: Path):
    settings = make_settings(tmp_path)
    seed(tmp_path, settings)
    store = LanceRetrievalStore(settings=settings)

    results = store.search_by_vector([1.0, 0.0, 0.0, 0.0], k=5, doc_type="market_stat")

    assert [row["doc_id"] for row in results] == ["ms_1"]


def test_search_by_vector_returns_empty_list_when_table_missing(tmp_path: Path):
    settings = make_settings(tmp_path)
    store = LanceRetrievalStore(settings=settings)

    assert store.search_by_vector([1.0, 0.0, 0.0, 0.0], k=5) == []
