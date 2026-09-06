from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_review import router as review_router
from app.api.routes_valuation import router as valuation_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(title="Autonomous Valuation & Market Intelligence Copilot")

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
