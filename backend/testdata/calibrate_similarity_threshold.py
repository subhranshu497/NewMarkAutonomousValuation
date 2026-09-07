"""Repeatable calibration check for RETRIEVAL_MIN_SIMILARITY.

Cosine similarity between embeddings has a non-zero baseline even for
unrelated text (a known embedding-space artifact), so a threshold that's too
low lets off-topic queries "match" real evidence — the exact failure mode
retrieval/schema.py's NO_DATA_FOUND_MESSAGE contract is supposed to prevent.
This script probes the live Voyage/LanceDB retrieval layer with a labeled
set of relevant and irrelevant queries against the testdata corpus and
reports whether the configured threshold actually separates them, instead of
eyeballing printed scores.

Run with: cd backend && .venv/bin/python testdata/calibrate_similarity_threshold.py
Requires VOYAGE_API_KEY in backend/.env and testdata/lancedb to be populated
(run testdata/run_pipeline_demo.py first if it isn't).

Re-run this whenever the corpus composition changes meaningfully — if the
gap between relevant and irrelevant scores narrows or disappears, the fixed
threshold in app/config.py needs re-tuning (or a relative/margin-based
scheme instead of an absolute floor).
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.retrieval.retriever import VectorRetriever  # noqa: E402
from app.retrieval.vector_store import LanceRetrievalStore  # noqa: E402

TESTDATA_DIR = Path(__file__).resolve().parent

RELEVANT_QUERIES = [
    "office space in River North",
    "legal tenant direct lease downtown Chicago",
    "Fulton Market sublease for a startup",
    "financial services tenant taking a long-term lease",
    "net absorption trend in Fulton Market",
    "asking rent growth in River North",
]

IRRELEVANT_QUERIES = [
    "best chocolate chip cookie recipe",
    "top hiking trails in Colorado",
    "how to fix a flat bike tire",
    "recommend a good science fiction novel",
    "weather forecast for next week",
]


def build_probe_settings():
    return get_settings().model_copy(
        update={"lancedb_uri": str(TESTDATA_DIR / "lancedb"), "retrieval_min_similarity": 0.0}
    )


async def top_score(retriever: VectorRetriever, query: str) -> float:
    result = await retriever.retrieve(query, k=1)
    return result.matches[0].score if result.matches else 0.0


async def main() -> None:
    settings = build_probe_settings()
    if not settings.voyage_api_key:
        raise SystemExit("VOYAGE_API_KEY is not set in backend/.env — cannot run a live calibration probe.")

    retriever = VectorRetriever(settings=settings, store=LanceRetrievalStore(settings))
    threshold = get_settings().retrieval_min_similarity

    print(f"Configured RETRIEVAL_MIN_SIMILARITY = {threshold}\n")

    relevant_scores = []
    print("--- Relevant queries (expect score >= threshold) ---")
    for query in RELEVANT_QUERIES:
        score = await top_score(retriever, query)
        relevant_scores.append(score)
        verdict = "OK" if score >= threshold else "FAIL (false negative)"
        print(f"{score:.4f}  [{verdict}]  {query}")

    irrelevant_scores = []
    print("\n--- Irrelevant queries (expect score < threshold) ---")
    for query in IRRELEVANT_QUERIES:
        score = await top_score(retriever, query)
        irrelevant_scores.append(score)
        verdict = "OK" if score < threshold else "FAIL (false positive)"
        print(f"{score:.4f}  [{verdict}]  {query}")

    false_negatives = sum(1 for s in relevant_scores if s < threshold)
    false_positives = sum(1 for s in irrelevant_scores if s >= threshold)
    gap = min(relevant_scores) - max(irrelevant_scores)

    print(f"\nMin relevant score:    {min(relevant_scores):.4f}")
    print(f"Max irrelevant score:  {max(irrelevant_scores):.4f}")
    print(f"Separation gap:        {gap:.4f} ({'threshold has margin' if gap > 0 else 'NO SEPARATION — recalibrate'})")
    print(f"False negatives: {false_negatives}/{len(relevant_scores)}   False positives: {false_positives}/{len(irrelevant_scores)}")

    if false_negatives or false_positives or gap <= 0:
        raise SystemExit(1)
    print("\nThreshold cleanly separates relevant from irrelevant queries.")


if __name__ == "__main__":
    asyncio.run(main())
