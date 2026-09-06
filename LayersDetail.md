Here's the current implementation mapped to those six layers:

1. Ingestion — No real pipeline: static JSON fixtures (comps.json, market_stats.json) are read once at startup. Tech: Python json + Pydantic models, no ETL, no embeddings.
2. Storage — Data sits in memory as loaded Python objects (@lru_cache over the fixtures); results/traces also cached in a plain in-process dict, not a database. Tech:
   in-memory Python — no vector DB, no SQL/NoSQL store.
3. Retrieval — Exact-match field filtering (submarket, size range, lease type, dates) against the in-memory data, not similarity search. Tech: plain Python list
   comprehensions standing in for OpenSearch/Snowflake calls.
4. Orchestration — A hand-written async state machine runs plan → retrieve → check-sufficiency → refine (up to 3x) → build context → synthesize → verify. Tech: custom Python
   orchestrator (graph.py), no LangGraph/LangChain — just structured control flow.
5. Generation — Two scoped LLM calls: one turns the request into search parameters, one reasons over the assembled evidence to produce the $/PSF number + rationale +
   citations. Tech: Anthropic Claude API (AsyncAnthropic client), each call scoped to a single "skill" system prompt.
6. Evaluation — Deterministic code checks that every citation the LLM made actually exists in the evidence it was given, and computes a confidence score from comp
   count/spread; failures route to human review. Tech: plain Python logic (groundedness_verifier.py, confidence.py) — no LLM-as-judge.

In one line: it's a real orchestration + generation loop, but ingestion/storage/retrieval are simple/mocked (no vector DB), and evaluation is rule-based rather than
model-based — deterministic trust by design, not classic embedding RAG.

