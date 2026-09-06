"""Manual, non-interactive smoke test for the ingestion, generation
(embedding), and retrieval layers using live Voyage AI calls.

Reads the JSON sample data in this directory, normalizes it, generates real
Voyage embeddings, upserts them into an isolated LanceDB index scoped to
testdata/lancedb (so it never touches the app's own vector store), then runs
a few sample queries through the retrieval layer to show top-5 cosine-
similarity matches and the "no data found" path for an unrelated query.

Run with: cd backend && .venv/bin/python testdata/run_pipeline_demo.py
Requires VOYAGE_API_KEY to be set in backend/.env.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings, get_settings
from app.ingestion.embedder import VoyageEmbedder
from app.ingestion.loaders import load_records
from app.ingestion.normalizers import normalize_record
from app.ingestion.vector_store import LanceVectorStore
from app.retrieval.retriever import VectorRetriever
from app.retrieval.vector_store import LanceRetrievalStore

TESTDATA_DIR = Path(__file__).resolve().parent

SOURCES = [
    (TESTDATA_DIR / "comps_sample.json", "comp", "opensearch-comps"),
    (TESTDATA_DIR / "market_stats_sample.json", "market_stat", "snowflake-market-stats"),
]

SAMPLE_QUERIES = [
    "direct lease office space in River North with a legal tenant",
    "sublease space in Fulton Market for a tech company",
    "vacancy trends for suburban Denver office parks",  # related domain, different market
    "best chocolate chip cookie recipe",  # expected: no match, unrelated domain
]


def vector_preview(vector: list[float], n: int = 8) -> str:
    preview = ", ".join(f"{v:.4f}" for v in vector[:n])
    return f"dim={len(vector)}  first_{n}=[{preview}, ...]"


def build_demo_settings() -> Settings:
    """Reuses the app's real Voyage config but redirects LanceDB to an
    isolated index under testdata/ so this script never mutates
    app/data/lancedb."""
    base = get_settings()
    return base.model_copy(update={"lancedb_uri": str(TESTDATA_DIR / "lancedb")})


async def run_ingestion_and_generation(settings: Settings) -> None:
    embedder = VoyageEmbedder(settings)
    store = LanceVectorStore(settings)

    print("\n=== INGESTION + GENERATION (Voyage AI embeddings) ===")
    for path, doc_type, source_system in SOURCES:
        raw_records = load_records(path)
        documents = [normalize_record(raw, doc_type, source_system) for raw in raw_records]

        vectors = await embedder.embed_documents([doc.text for doc in documents])
        store.upsert(documents, vectors)

        print(f"\n-- {path.name} ({doc_type}, model={settings.voyage_model}) --")
        for doc, vector in zip(documents, vectors):
            print(f"doc_id={doc.doc_id!r}")
            print(f"  text: {doc.text}")
            print(f"  embedding: {vector_preview(vector)}")


async def run_retrieval(settings: Settings) -> None:
    retriever = VectorRetriever(settings=settings, store=LanceRetrievalStore(settings))

    print("\n=== RETRIEVAL (cosine similarity, top 5) ===")
    for query in SAMPLE_QUERIES:
        result = await retriever.retrieve(query, k=5)
        print(f"\nQuery: {query!r}")
        print(f"  query_embedding: {vector_preview(result.query_embedding)}")
        if not result.found:
            print(f"  {result.message}")
            continue
        for match in result.matches:
            print(f"  score={match.score:.4f}  doc_id={match.doc_id}  doc_type={match.doc_type}")
            print(f"    text: {match.text}")
            print(f"    result_embedding: {vector_preview(match.embedding)}")


async def main() -> None:
    settings = build_demo_settings()
    if not settings.voyage_api_key:
        raise SystemExit("VOYAGE_API_KEY is not set in backend/.env — cannot run a live embedding test.")

    await run_ingestion_and_generation(settings)
    await run_retrieval(settings)


if __name__ == "__main__":
    asyncio.run(main())
