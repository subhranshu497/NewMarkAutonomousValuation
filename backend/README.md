FastAPI backend for the Autonomous Valuation & Market Intelligence Copilot.

- `/health` — liveness check
- Routes registered under `app/api/routes_valuation.py` and `app/api/routes_review.py`

## Deploying on Render

Deployed via the `render.yaml` Blueprint at the repo root (Docker runtime, root directory `backend`).
Set these two secrets in the Render dashboard after the first deploy (they're intentionally left
out of `render.yaml` and git):

- `ANTHROPIC_API_KEY`
- `VOYAGE_API_KEY`
