# Design: Autonomous Valuation & Market Intelligence Copilot

Companion to `README.md`. That doc makes the case for *agentic RAG*; this doc
is the detailed design — requirements, agent objectives, architecture,
memory/context design, and an implementation-status deep dive.

This revision reflects the **actual implementation** in `backend/` and
`frontend/`, not just the target design. Where the build diverges from the
original target architecture (e.g. no Redis, no live vector search at
runtime), that's called out explicitly rather than glossed over — see §6.9.

## 0. Suggested 1-Hour Walkthrough

| Time | Section | Goal |
|---|---|---|
| 0–5 min | README recap: problem, why agentic (not deterministic), why RAG | Frames the "why" fast |
| 5–12 min | §1–2 Functional / Non-functional requirements | Shows the problem was scoped like a product, not just a model |
| 12–20 min | §3 Agent objectives: autonomy vs. constraints | Usually the differentiator question — worth the most time |
| 20–35 min | §4 Architecture as built (diagram walkthrough) | The centerpiece — LangGraph orchestration loop, tools, verifier |
| 35–45 min | §5 Memory & context design | Shows systems maturity beyond "call an LLM in a loop" |
| 45–55 min | §6 Deep dive: pick one (sufficiency loop or groundedness verifier) | Depth beats breadth — no need to cover all of §6 |
| 55–60 min | §6.9 Build status vs. target design + risks | Shows judgment about what's real, what's mocked, and what's next |

If time is tight, §6 depth is the part to cut, not §3/§4 — objectives and
architecture matter most for evaluating an agentic design.

---

## 1. Functional Requirements

| ID | Requirement | Status |
|---|---|---|
| FR1 | Accept a valuation request: property/submarket, space size, property type, lease assumptions. | Built |
| FR2 | Dynamically formulate queries to `comps/search` and `market-stats` based on request parameters (not a fixed query template). | Built |
| FR3 | Iteratively refine retrieval (widen radius, adjust date window/property type) when initial evidence is thin, bounded by a max iteration count. | Built |
| FR4 | Synthesize a `$/PSF` rent recommendation with a written rationale grounded in retrieved evidence. | Built |
| FR5 | Cite every quantitative claim in the rationale to a specific source record (comp ID or market-stat series point). | Built |
| FR6 | Emit a confidence score alongside the recommendation. | Built |
| FR7 | Route low-confidence or ungrounded outputs to human review instead of auto-publishing. | Built |
| FR8 | Write the recommendation to `askingRentPsf` preview in the system of record and/or produce a client-facing submarket narrative. | Not built — the API returns the structured result and the frontend displays it; there's no write-back to an external system of record. |
| FR9 | Log the full agent trace (queries issued, evidence retrieved, decisions made) for audit/dispute defense. | Partially built — every run produces a full trace and the frontend renders it (`TraceTimeline`), but storage is an in-process dict (`trace_store.py`), not durable/retained (see §6.9). |
| FR10 *(v1.1)* | Support session-level follow-up refinement ("widen radius", "exclude pre-2021 comps") without re-running retrieval from scratch. | Not built — no session memory exists. |

## 2. Non-Functional Requirements

| Category | Requirement | Status |
|---|---|---|
| Latency | p50 < 15s, p95 < 30s end-to-end for an interactive single-property request. | Not formally measured; architecture supports it (2 LLM calls, small evidence bundle, in-memory data). |
| Groundedness | 100% of numeric claims must resolve to a retrieved record ID — zero tolerance for fabricated figures (this is the trust-critical NFR for a valuation product). | Enforced deterministically — see §6.4. |
| Cost control | Hard ceiling on tool calls (≤3 retrieval iterations) and LLM calls (≤2 reasoning calls) per request. | The 3-iteration cap is enforced by a LangGraph conditional edge (`route_after_retrieval`, `orchestrator/graph.py`). The 2-LLM-call ceiling is a structural property of the graph topology, not a runtime counter — `max_llm_calls` is defined in config but not read anywhere in code. |
| Consistency | Same inputs → low-variance outputs; aggregation math (medians, weighting) done in deterministic code, not left to the LLM. | Built — `logic/context_builder.py` computes medians/spread/relevance in Python. |
| Availability / degradation | If one data source (Snowflake or OpenSearch) is down, degrade to a lower-confidence result with a flag rather than fail the whole request. | Partially built for the semantic path: `semantic_retrieve_node` catches any exception from the vector store and degrades to structured-only retrieval. There are no real Snowflake/OpenSearch dependencies to fail against — both are simulated (§4.1). |
| Consistency vs. real dependencies | — | N/A today: `comps_search`/`market_stats` read from static in-memory JSON fixtures, not from external systems that can go down. |
| Auditability | Full agent trace retained per valuation for a defined retention window — real-estate valuations get disputed and need to be defensible after the fact. | Not built — trace exists per-run but lives in a process-local dict with no persistence or retention policy; restarting the API loses all history. Flagged as an MVP gap directly in `trace_store.py`. |
| Access control | Requests scoped to the user's authorized submarkets/portfolios, enforced at the tool layer, not by agent judgment. | Not built — `ValuationRequest.requested_by` is captured but never checked against anything; there is no authz layer. |
| Observability | Every agent step emits a trace span (tool called, params, latency, result count) for debugging and offline eval. | Built — each LangGraph node appends a `TraceSpan` (step, started_at/finished_at, params, result_summary) to state via an additive reducer; surfaced in the API response and rendered in the frontend `TraceTimeline`. |
| Extensibility | New data sources become new tools without redesigning the orchestrator. | Built — tools are thin, independently swappable functions (`tools/comps_search.py`, `tools/market_stats.py`) called from dedicated graph nodes. |
| Scalability | Orchestrator workers are stateless/horizontally scalable; repeated submarket queries hit a shared evidence cache. | Orchestrator itself is stateless per-request (state lives in the LangGraph run, not the process). No shared evidence cache exists — no Redis or any cache layer is present anywhere in the codebase. |

---

## 3. Agent Objectives

**Primary objective:** produce accurate, defensible, timely `$/PSF`
recommendations grounded in current data, with minimal manual analyst effort
— without ever fabricating a figure, and always leaving an audit trail.

Every design decision below falls out of splitting that objective into what
the agent is *trusted to decide* vs. what it is *never allowed to decide*.

### 3.1 Autonomy — what the agent decides for itself

- Which specific query parameters to issue to `comps/search` / `market-stats`
  (size range, date window, lease-type matching), **and** the ordered
  refinement policy to apply if evidence comes back thin — both produced in
  a single up-front LLM call (`data_retrieval_agent.formulate_query`), not
  re-decided on each iteration.
- How to weight comps when synthesizing a number (recency, size similarity)
  — computed deterministically from LLM-independent code
  (`context_builder._relevance`), not judged by the LLM per comp.
- How to phrase the rationale for the audience.
- Whether to flag its own output for human review based on its confidence
  assessment (the LLM's self-reported `needs_human_review` flag is one of
  several inputs to the actual gate — see §6.6).

### 3.2 Constraints — hard boundaries, not up for agent judgment

- May only use data returned by approved tools — no world-knowledge rent
  figures, no invented comps.
- Every numeric claim must be traceable to a cited source record; the
  verifier strips or rejects anything that isn't (§6.4).
- Max retrieval iterations (3, enforced by a LangGraph conditional edge) and
  a structurally-bounded 2 LLM calls per request — cannot loop forever
  chasing "perfect" evidence.
- Cannot auto-publish when confidence < threshold or comp count < minimum —
  must route to human review (FR7).
- Output must conform to a fixed structured schema (Pydantic models,
  validated on parse) for downstream integration — free-form-only answers
  are invalid; malformed LLM output fails fast rather than being
  silently accepted.
- No code execution, no open web access — restricted to the defined tool
  surface (`comps_search`, `market_stats`, plus an internal semantic
  retrieval step — §4.1).
- **Not currently enforced in code:** access control to the user's
  authorized submarkets/portfolios. `requested_by` is captured on the
  request but nothing checks it. This is a real gap against §3.2's own
  stated intent, not a design choice — see §6.9.

This autonomy/constraint split is the answer to "how do you keep an agentic
system from going off the rails" — autonomy is scoped to *how to search and
weigh evidence*, never to *whether to follow the rules*.

---

## 4. Architecture As Built

```
                         ┌─────────────────────────┐
                         │   User Request            │
                         │ (React form, ValuationRequestPage) │
                         └────────────┬─────────────┘
                                      ▼
                         POST /api/valuations
                                      ▼
                         ┌─────────────────────────┐
                         │       Orchestrator         │  LangGraph StateGraph
                         │  (graph.py — real, compiled)│  (not hand-rolled)
                         └────────────┬─────────────┘
                                      ▼
                    ┌─────────────────────────────────┐
                    │  formulate_query (LLM call #1)    │  Data Retrieval Agent:
                    │  → initial params + refinement     │  Claude Haiku via
                    │    policy, in one shot             │  LangChain ChatAnthropic
                    └───────┬─────────────────┬────────┘
                            ▼                 ▼
                 fetch_market_stats     semantic_retrieve
                 (in-memory JSON        (Voyage embed query →
                  fixture lookup)        LanceDB cosine search;
                            │            table seeded from
                            │            fixtures on startup — see §6.9)
                            └────────┬────────┘
                                     ▼
                    ┌─────────────────────────────┐
                    │      retrieve_comps            │──(insufficient, budget
                    │  in-memory field-filter search  │   left)──┐
                    │  merged with any semantic hits  │           │
                    └───────────────┬───────────────┘             │
                              (sufficient, or                       │
                               iterations exhausted)                │
                                     ▼                       apply next
                    ┌─────────────────────────────┐          RefinementStep
                    │   is_sufficient() (rules)      │◀──────────────┘
                    │  ≥5 comps, ≥3 in trailing 12mo,│  (max 3 iterations,
                    │  market stats present           │   LangGraph conditional
                    └───────────────┬───────────────┘   edge enforces cap)
                                     ▼
                    ┌─────────────────────────────┐
                    │      build_context             │
                    │  dedupe, compute median/mean/   │
                    │  spread, select top-8 comps     │
                    │  (code, not LLM)                │
                    └───────────────┬───────────────┘
                                     ▼
                    ┌─────────────────────────────┐
                    │  synthesize_valuation (LLM #2) │  Valuation Agent:
                    │  → $/PSF + rationale + citations│  Claude Haiku via
                    └───────────────┬───────────────┘  LangChain ChatAnthropic
                                     ▼
                    ┌─────────────────────────────┐
                    │      verify_and_score          │
                    │  citations ⊆ evidence bundle?   │
                    │  + deterministic confidence      │
                    └───────┬─────────────┬─────────┘
                       (pass, high conf)  (fail / low conf)
                            ▼                 ▼
                 ┌─────────────────┐  ┌───────────────────┐
                 │  trace_store     │  │  review_queue       │
                 │  (in-process dict,│  │  (in-process dict,  │
                 │  lost on restart) │  │  lost on restart)   │
                 └────────┬─────────┘  └──────────┬──────────┘
                          ▼                        ▼
              GET /api/valuations/{id}   GET /api/review-queue
              → ValuationResultPage      POST .../decision
              (confidence badge,          → ReviewQueuePage
               evidence panel,             (analyst approve/
               trace timeline)              override)
```

**Component responsibilities**

| Component | Responsibility | Type | As built |
|---|---|---|---|
| Orchestrator | Owns the control loop and state; routes between retrieval, valuation, verification | LangGraph `StateGraph` | Real — `orchestrator/graph.py`, compiled once and reused; state additive-reduces a `trace` list across nodes. |
| Data Retrieval Agent | Decides *what* to query, produces an ordered refinement policy up front | LLM-guided (1 call) | Real — `agents/data_retrieval_agent.py`, Claude Haiku via LangChain. |
| Semantic Retrieval | Embeds the request as free text, does a cosine-similarity ANN search over an evidence corpus | Real embedding + vector search infra | `retrieval/` package (Voyage + LanceDB) is fully implemented; a `lifespan` startup hook re-runs the ingestion pipeline against the fixtures on every boot, so the LanceDB table is populated with real embeddings by the time the API serves traffic. |
| Sufficiency Check | Enforces the "enough evidence?" gate | Rule-based, deterministic | Real — `logic/sufficiency.py`. |
| Context Builder | Dedupe/normalize comps, compute medians/spread programmatically, assemble a bounded-size evidence bundle | Deterministic code | Real — `logic/context_builder.py`. |
| Valuation Agent | Reasons over the evidence bundle to produce number + rationale | LLM (1 call) | Real — `agents/valuation_agent.py`, Claude Haiku via LangChain. |
| Groundedness Verifier | Confirms every cited number in the rationale exists in the evidence bundle | Deterministic set-membership check | Real — `logic/groundedness_verifier.py`. |
| Human Review Queue | Catches low-confidence/ungrounded outputs before they reach a client | Human-in-the-loop | Real workflow end-to-end (backend queue + `ReviewQueuePage` UI for approve/override), but storage is an in-process dict, not a database. |
| Trace Store | Persists the full per-request trace for audit | Should be durable storage | In-process dict only — no persistence (§6.9). |
| Frontend | Request intake, result display, review workflow | React 18 + Vite + TypeScript SPA (separately deployed on Netlify) | Real — see §4.2. |

Why a rule-based sufficiency check and a deterministic verifier instead of
"another LLM call to judge the LLM"? Determinism buys speed, cost, and —
critically for a valuation product — reproducibility: the same evidence set
always yields the same pass/fail decision, which matters when a
recommendation gets challenged later.

### 4.1 What's real vs. simulated in the data layer

The design targets `comps/search` (OpenSearch-backed) and `market-stats`
(Snowflake/dbt-backed) as external services. As built:

- `tools/comps_search.py` and `tools/market_stats.py` are thin, intentionally
  swappable wrappers whose docstrings explicitly mark them as "the seam
  where a real OpenSearch/Snowflake-backed call replaces the mock."
- Underneath, `data/mock_store.py` does pure in-memory Python
  list-comprehension filtering (exact match on submarket, lease type, SF
  range, date range) over two static JSON files (`data/input/comps.json`,
  14 comps; `data/input/market_stats.json`, 6 series) loaded once at import
  time via `@lru_cache`. `property_type` and `radius_miles` are accepted
  parameters but are no-ops — the source files don't carry those dimensions.
- Separately, a genuine embedding-based retrieval path exists and is wired
  into the graph (`semantic_retrieve` node): a real ingestion pipeline
  (`ingestion/pipeline.py`) normalizes every file under `data/input/`,
  redacts PII, embeds them with Voyage AI, and upserts into a LanceDB table;
  a real retrieval client (`retrieval/`) embeds the query and does cosine
  ANN search against that table. This is not a design aspiration — it's
  implemented and tested code. `discover_sources()` scans `data/input/` at
  ingestion time rather than reading from a hardcoded file list — it infers
  each file's `doc_type` from filename (anything with "comp" in the stem,
  anything with "market_stat"), so any number of comp/market-stat files
  dropped into that one directory get ingested without a code change. A
  FastAPI `lifespan` hook (`main.py`) re-runs this discovery + ingestion on
  every process startup — idempotent (upserts are keyed by `doc_id`) and
  failure-isolated (an ingestion error is logged, not raised, so a Voyage
  outage degrades semantic retrieval to empty results instead of blocking
  the API from serving the deterministic comps_search/market_stats path).
  The remaining gap: `mock_store.py` (the deterministic path) still reads
  exactly `comps.json`/`market_stats.json` by fixed name, so it won't pick
  up extra files the same way ingestion does — only the semantic path
  benefits from multi-file discovery today.
- No Redis, no SQL/NoSQL database, and no message queue exist anywhere in
  the stack. Every stateful store in the running system (fixture cache,
  trace store, review queue) is a process-local Python object.

### 4.2 Frontend

A React 18 + TypeScript SPA (Vite build), deployed separately from the
backend (Netlify), talking to the FastAPI backend over CORS-allowlisted
origins (`config.py: cors_allow_origins`):

| Route | Page | Purpose |
|---|---|---|
| `/` | `ValuationRequestPage` | Intake form (submarket, property type, SF, lease type, term, concessions, requested-by) → `POST /api/valuations`. |
| `/valuations/:id` | `ValuationResultPage` | Displays recommended `$/PSF`, range, `ConfidenceBadge`, rationale, `EvidencePanel` (summary stats + cited-comp table + market trend deltas with citation checkmarks), and `TraceTimeline` (full orchestration trace). |
| `/review-queue` | `ReviewQueuePage` | Lists pending low-confidence/ungrounded valuations; lets an analyst enter an override `$/PSF` and approve/reject. |

The frontend is a first-class part of the trust story here, not an
afterthought: confidence, cited evidence, and the full execution trace are
surfaced directly to the end user, and the human-review gate has a working
UI, not just a backend flag.

### 4.3 API surface (as built)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/valuations` | Run the full orchestration graph for a new request. |
| `GET` | `/api/valuations/{valuation_id}` | Fetch a previously computed result (404 if not found, e.g. after a restart). |
| `GET` | `/api/review-queue` | List pending human-review items. |
| `POST` | `/api/review-queue/{valuation_id}/decision` | Record an analyst's approve/override decision. |
| `GET` | `/health` | Liveness check (also used by the frontend to show a live/offline indicator). |

No authentication or authorization middleware exists on any route.

---

## 5. Memory and Context Design

Four distinct kinds of "memory" were designed for — worth being explicit
about which ones actually exist today, since conflating "designed" with
"built" is a common tell of shallow agentic design writeups.

| Memory type | Scope | Designed storage | As built |
|---|---|---|---|
| **Working memory** | Single request | In-process orchestrator state | Real — the LangGraph `OrchestratorState` (a `TypedDict`) carries the request, plan, iteration count, comps, evidence, and result through the run; `trace` uses LangGraph's additive-reducer pattern to accumulate spans from every node automatically. |
| **Session memory** | One user session (multi-turn refinement) | Redis, keyed by `session_id`, short TTL | Not built (FR10 is v1.1/deferred, as originally scoped). |
| **Evidence cache** | Cross-user, cross-session | Redis/cache layer, keyed by `hash(submarket, property_type, params)`, short TTL | Not built. No Redis or any cache layer exists in the codebase — every request re-runs retrieval from scratch. |
| **Feedback / episodic store** | Long-term, cross-request | Append-only table: request params, retrieved evidence, agent output, analyst override, final accepted rent | Not built. `review_queue.record_decision()` writes an analyst's decision into an in-process dict, but that dict is never read back anywhere — it's write-only today, not a real feedback loop. |

**Context assembly (the part that keeps token usage bounded and predictable
regardless of how much was retrieved):**

The Valuation Agent never sees raw retrieval JSON. `logic/context_builder.py`:

1. Dedupes comps by `comp_id` (same transaction surfaced by both the
   structured search and the semantic-retrieval seed).
2. Computes aggregate stats in code — median/mean `$/PSF`, spread, comp
   count and trailing-12-month comp count — rather than asking the LLM to
   eyeball a table of numbers.
3. Selects the top-8 comps (`top_n_comps` config) by a relevance score that
   is 50% size-similarity / 50% recency, both linearly normalized against
   the retrieved population — not a fixed absolute scale, and notably
   **no lease-type-match term**, despite that being part of the original
   weighting design (§3.1).
4. Assembles a fixed-shape `EvidenceBundle`: `{summary_stats, top_comps[≤8],
   market_trend_deltas}` — bounded size regardless of how many records the
   retrieval iterations pulled in.

This matters for two NFRs at once: latency/cost (bounded prompt size) and
consistency (the LLM reasons over the same *shape* of input every time,
rather than a variable-length dump).

---

## 6. Detailed Deep Dive

Pick one of §6.3 or §6.4 to actually walk through live — they're the two
pieces that make this "agentic" rather than "RAG with extra steps."

### 6.1 Tool contracts (as implemented)

```
comps_search(submarket_id, property_type, min_sf, max_sf, lease_type,
             date_from, date_to, k) -> Comp[]
# property_type is accepted but currently a no-op (mock_store.py) —
# fixtures don't carry it. No radius_miles parameter exists; matching is
# exact submarket_id equality, not geo-radius.

Comp = { comp_id, address, submarket_id, sf, lease_type,
         asking_rent_psf, effective_rent_psf, lease_start_date,
         tenant_industry, concessions, source_system, last_verified_at }

market_stats(submarket_id, metric ∈ {vacancy_rate, net_absorption,
             asking_rent_trend}, time_window) -> TimeSeries
# time_window is accepted but currently a no-op — full series is always
# returned for the matching submarket_id + metric.

TimeSeries = { submarket_id, metric, points: [{period, value}],
               yoy_change, percentile_rank }
```

Narrow, typed (Pydantic-validated) tool contracts are what let the Data
Retrieval Agent's "autonomy" (§3.1) stay safe — it can choose *parameters*
freely, but the return shape is always structured and validated, and
malformed LLM output is rejected rather than silently coerced.

### 6.2 Orchestration loop (plan → act → check), as built in LangGraph

1. **Plan** (`formulate_query` node, LLM call #1): parse the request into
   initial `comps_search`/`market_stats` params *and* an ordered
   `refinement_policy` (list of `RefinementStep{adjust, to}`) — both
   produced in this single call.
2. **Act**: `fetch_market_stats` runs, then `semantic_retrieve` (Voyage
   embed + LanceDB cosine search over the seeded fixture table — §4.1), then
   `retrieve_comps` (in-memory field-filter search), merging any semantic
   hits with structured hits by `comp_id`.
3. **Check** (§6.3, `is_sufficient`): sufficient → proceed to
   `build_context`. Insufficient and iterations remain → apply the next
   `RefinementStep` (a single field mutation, e.g. widen the SF range or
   extend the date window) and loop back to `retrieve_comps`. This loop is
   a LangGraph conditional edge (`route_after_retrieval`), capped at 3
   iterations (`max_retrieval_iterations`).

   Note: the *specific* refinement strategy per iteration (which field to
   adjust and by how much) is decided once, up front, by the LLM in step 1
   — it is not re-derived by a rule or a fresh LLM call on each iteration.
   The orchestrator's job during the loop is purely mechanical: apply the
   next step in the policy and re-check sufficiency.
4. On cap exhaustion without sufficiency: proceed anyway with whatever
   evidence was gathered; the confidence score is naturally penalized by
   thin/sparse evidence (§6.5) and the human-review gate (§6.6) catches it.

### 6.3 Sufficiency check (deterministic, not LLM-judged)

```python
# logic/sufficiency.py — actual implementation
def is_sufficient(comps, market_stats_results, ...,
                   min_comp_count=5, min_recent_comp_count=3,
                   recent_window_months=12) -> bool:
    if len(comps) < min_comp_count:
        return False
    cutoff = date.today() - timedelta(days=recent_window_months * 30)
    recent_count = sum(1 for c in comps if c.lease_start_date >= cutoff)
    if recent_count < min_recent_comp_count:
        return False
    if not market_stats_results:
        return False
    return True
```

Defaults (`config.py`): `min_comp_count=5`, `min_recent_comp_count=3`,
`recent_window_months=12` (approximated as a fixed 360-day window, not
calendar months). Rule-based on purpose: cheap, fast, fully reproducible,
and easy to unit test — important for trusting the "agentic" retrieval loop
before ever letting an LLM judge its own inputs. Note the 14-comp fixture
corpus is tight against a `min_comp_count` of 5 — several submarket/filter
combinations will genuinely exhaust all 3 refinement iterations without
becoming sufficient.

### 6.4 Groundedness verifier

The Valuation Agent is required to emit structured output, not free text:

```json
{
  "recommended_rent_psf": 42.50,
  "range_low": 39.00,
  "range_high": 46.00,
  "confidence": 0.78,
  "rationale_text": "...",
  "cited_comp_ids": ["c_1042", "c_1077", "c_1103"],
  "cited_market_stat_ids": ["ms_vacancy_q3_2026"],
  "needs_human_review": false
}
```

The verifier (`logic/groundedness_verifier.py`) is deterministic: it checks
`cited_comp_ids` is a subset of the comp IDs actually included in the
evidence bundle's `top_comps`, and `cited_market_stat_ids` is a subset of
the `{submarket_id}_{metric}` keys actually present in the bundle. Any
citation outside those sets fails the check. This is the single most
important trust mechanism in the system: it makes hallucination
structurally detectable instead of relying on the model to "try not to."

### 6.5 Confidence scoring (also deterministic)

```python
# logic/confidence.py — actual weights (flagged in code as MVP placeholders
# pending calibration against real outcome data)
confidence = 0.4 * min(comp_count / 10, 1.0)                       # count
           + 0.3 * min(recent_12mo_count / comp_count, 1.0)        # recency mix
           + 0.3 * max(0.0, 1 - rent_spread / median_asking_rent_psf)  # tight spread → higher
# rounded to 2dp, clamped to [0, 1]; returns 0.0 immediately if comp_count == 0
```

Computed in code from the evidence bundle, not asked of the LLM — keeps it
auditable and stable. The weights (0.4/0.3/0.3) and the count-saturation
point (10 comps) are concrete, code-level defaults, not yet tuned against
any real feedback data.

### 6.6 Human-in-the-loop gate (as implemented)

`orchestrator/nodes.py:verify_and_score_node` routes to human review if
**any** of the following is true:

- the LLM's own `needs_human_review` flag is set, **or**
- the groundedness verifier fails (an uncited/unfound citation), **or**
- `min(LLM-reported confidence, deterministic confidence) < 0.6`
  (`confidence_threshold`), **or**
- `comp_count < 3` (`review_min_comp_count`).

This is a superset of the original design's `confidence < 0.6 OR
comp_count < 3 OR verifier fails` — the LLM's self-flagging is also
consulted, and the confidence check takes the *lower* of the LLM's stated
confidence and the deterministic score, so an overconfident LLM output
can't bypass the gate. Otherwise, the result is returned as auto-published
(no actual write-back to an external system of record exists yet — see FR8).

### 6.7 Observability

Every LangGraph node appends a `TraceSpan` (`step`, `started_at`,
`finished_at`, `params`, `result_summary`) to the run's trace via an
additive reducer on `OrchestratorState`, so the full trace assembles itself
across the graph without any node needing to know about the others. The
trace is returned in the API response and rendered end-to-end in the
frontend's `TraceTimeline` component — this satisfies the *shape* of FR9,
but not its durability requirement (§6.9).

### 6.8 PII handling in ingestion

`ingestion/pii_filter.py` is a regex-based scanner (not NER, not an LLM
call) that detects email, SSN, phone, and credit-card patterns in both a
document's embeddable text and its metadata dict before it's written to the
vector store, setting a `pii_redacted` flag and logging a warning if
anything is found. This only runs in the ingestion pipeline (the semantic
retrieval seeding path) — the structured `comps_search`/`mock_store` path
has no PII filtering, since its fixture data is trusted/synthetic already.
Self-documented limitation: it won't catch unstructured PII like names
embedded in prose, which would need an NER model.

### 6.9 Build status vs. target design, and what's next

What's fully real and working end-to-end today:

- LangGraph-orchestrated plan → act → check loop with a genuine bounded
  refinement cycle.
- Two scoped Claude Haiku calls (via LangChain `ChatAnthropic`) — query
  formulation and valuation synthesis.
- Deterministic sufficiency, confidence, and groundedness logic.
- A working human-review workflow with a real UI.
- A real ingestion pipeline (normalize → PII-redact → embed via Voyage →
  upsert into LanceDB) and a real semantic retrieval client (embed query →
  cosine ANN search) — architecturally complete, code-tested.
- A React frontend that surfaces confidence, evidence, and trace directly
  to the end user.

What's simulated or not yet wired up, and should not be assumed "done"
just because the code exists:

- **Semantic retrieval is now seeded on every startup**, via a FastAPI
  `lifespan` hook in `main.py` that runs the ingestion pipeline (previously
  CLI-triggered only, via `python -m app.ingestion.pipeline`) before the API
  starts serving traffic. It re-embeds the same static fixtures each boot —
  idempotent by `doc_id`, and a Voyage failure is caught and logged rather
  than blocking startup, so the deterministic comps_search/market_stats path
  still serves even if the semantic path can't seed. What's still not
  built: a way to ingest *new* or *changed* source data at runtime — this
  only re-syncs the fixed fixture set.
- **No Redis/cache layer anywhere** — session memory (FR10) and the
  evidence cache (§5) are unimplemented, not just deferred-and-stubbed.
- **Trace store and review queue are process-local dicts.** Both are
  explicitly flagged as MVP gaps in their own source comments. A restart
  loses all history — this is a real conflict with FR9/auditability, not a
  cosmetic gap, for a product whose stated NFR is dispute defense.
- **No access control.** `requested_by` is captured but never checked
  against anything, contradicting §3.2's stated constraint.
- **No write-back to a system of record** (FR8) — the API returns a
  structured result; there's no integration that actually populates an
  `askingRentPsf` field anywhere external.
- **Data volume is tiny.** The fixture corpus has 14 comps and 6
  market-stat series — enough to exercise the logic paths, not enough to
  stress-test the sufficiency thresholds or confidence formula
  meaningfully.

| In scope (built) | Designed but not yet real | Deferred (v2 backlog, unchanged from original scope) |
|---|---|---|
| Single-turn request → structured recommendation with citations | Semantic/vector retrieval (code exists, not populated at runtime) | Multi-turn conversational refinement / session memory (FR10) |
| LangGraph orchestrator, 2 tools + 1 semantic-retrieval step | Redis session/evidence cache | Additional data sources (e.g., permits, foot traffic) |
| Rule-based sufficiency check + deterministic confidence score | Durable trace storage / retention policy (FR9) | LLM-judged sufficiency / self-critique |
| Deterministic groundedness verifier | Access control at the tool layer | Automated fine-tuning or prompt refresh from analyst feedback |
| Manual review queue with a working UI | Write-back to system of record (FR8) | Auto-generated client-facing PDF reports |
| Basic per-run tracing, surfaced in the frontend | | Portfolio-level batch valuation |

The one-sentence version: **the build proves the full agentic loop
(retrieve → judge sufficiency → refine → ground → verify) end to end,
including a working review UI — the gaps left are almost entirely
persistence/production-hardening (durable storage, cache, auth, triggering
ingestion), not gaps in the agentic reasoning design itself.**

---

## 7. Success Metrics (ties back to NFRs)

- **Groundedness rate**: % of published recommendations with zero verifier
  failures — target 100% (anything else auto-routes to review, so this is
  really "% requiring human review," tracked as a leading indicator).
- **Turnaround time**: p50/p95 latency vs. the 15s/30s NFR targets. Not yet
  instrumented — there's no latency measurement in the current trace spans
  beyond per-step `started_at`/`finished_at`, and no aggregation layer.
- **Analyst override rate**: % of auto-published recommendations later
  corrected by an analyst — the core signal for whether autonomy boundaries
  (§3.1) are calibrated correctly. Not measurable today: `record_decision()`
  writes overrides but nothing reads them back for analysis (§5).
- **Coverage**: % of requests resolved without hitting the human review
  gate.

## 8. Risks & Open Questions

- **Startup ingestion re-syncs `data/input/`, restart is still required for new data, and mock_store.py doesn't share the multi-file discovery
- **In-memory trace/review storage** means every deploy or restart silently
  destroys the audit trail FR9 exists for — a real risk for a product whose
  core pitch is defensibility, not just a scale limitation.
- **Submarket boundary ambiguity**: matching is exact `submarket_id`
  equality today (no radius/geo search exists in the implementation), so
  the original concern about radius-vs-submarket-ID disagreement doesn't
  yet apply — but will resurface once/if radius search is added.
- **Stale comps**: `last_verified_at` staleness isn't part of the
  sufficiency check — should it be, or is recency-of-lease-date sufficient?
- **Fixture corpus size**: 14 comps total makes the `min_comp_count=5`
  threshold tight; realistic behavior of the refinement loop and confidence
  scoring can't be fully validated until real-scale data is loaded.
- **Confidence threshold calibration**: 0.6/comp-count-3 (§6.6) and the
  0.4/0.3/0.3 confidence weights (§6.5) are placeholder defaults, explicitly
  flagged as such in code — should be tuned against real outcome data once
  the feedback store is actually consumed somewhere (§5).
- **No access control**: `requested_by` is unused; this needs to be closed
  before this could handle real, portfolio-scoped data.
