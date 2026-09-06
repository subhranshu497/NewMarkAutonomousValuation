from pathlib import Path

from app.config import Settings
from app.ingestion.schema import IngestDocument
from app.ingestion.vector_store import LanceVectorStore

DIM = 4


def make_store(tmp_path: Path) -> LanceVectorStore:
    settings = Settings(
        lancedb_uri=str(tmp_path / "lancedb"),
        lancedb_table_name="evidence_documents",
        voyage_embedding_dimension=DIM,
    )
    return LanceVectorStore(settings=settings)


def make_doc(doc_id: str, text: str = "hello") -> IngestDocument:
    return IngestDocument(
        doc_id=doc_id,
        doc_type="comp",
        text=text,
        metadata={"comp_id": doc_id},
        source_system="test",
    )


def test_upsert_and_count(tmp_path: Path):
    store = make_store(tmp_path)
    docs = [make_doc("c_1"), make_doc("c_2")]
    embeddings = [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]]

    ingested = store.upsert(docs, embeddings)

    assert ingested == 2
    assert store.count() == 2


def test_upsert_is_idempotent_on_doc_id(tmp_path: Path):
    store = make_store(tmp_path)
    store.upsert([make_doc("c_1", text="first")], [[0.1, 0.2, 0.3, 0.4]])
    store.upsert([make_doc("c_1", text="second")], [[0.9, 0.9, 0.9, 0.9]])

    assert store.count() == 1
    record = store.get_by_id("c_1")
    assert record is not None
    assert record["text"] == "second"


def test_get_by_id_returns_none_when_missing(tmp_path: Path):
    store = make_store(tmp_path)
    store.upsert([make_doc("c_1")], [[0.1, 0.2, 0.3, 0.4]])
    assert store.get_by_id("does-not-exist") is None


def test_upsert_with_empty_documents_is_a_noop(tmp_path: Path):
    store = make_store(tmp_path)
    assert store.upsert([], []) == 0
