import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_review import router as review_router
from app.api.routes_valuation import router as valuation_router
from app.config import get_settings
from app.ingestion.pipeline import run_ingestion

logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Seeds the LanceDB evidence table from the fixtures on every startup so
    `semantic_retrieve` has data to search against — the ingestion pipeline
    upserts keyed by doc_id (LanceVectorStore.upsert), so re-running this on
    every boot is idempotent, not a duplicate-accumulation risk. Failure here
    must never block the API from serving the deterministic comps_search /
    market_stats path, so it's caught and logged rather than raised — same
    availability posture as semantic_retrieve_node's own degrade-on-failure
    behavior."""
    try:
        reports = await run_ingestion()
        total = sum(report.ingested for report in reports)
        logger.info("startup ingestion complete: %d documents seeded into LanceDB", total)
    except Exception:
        logger.warning("startup ingestion failed — semantic retrieval will return no matches", exc_info=True)
    yield


app = FastAPI(title="Autonomous Valuation & Market Intelligence Copilot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(valuation_router)
app.include_router(review_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
