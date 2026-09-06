# Design: Autonomous Valuation & Market Intelligence Copilot

Companion to `README.md`. That doc makes the case for *agentic RAG*; this doc
is the detailed design — requirements, agent objectives, architecture,
memory/context design, and an MVP-scoped deep dive.

## 0. Suggested 1-Hour Walkthrough

| Time | Section | Goal |
|---|---|---|
| 0–5 min | README recap: problem, why agentic (not deterministic), why RAG | Frame the "why" fast |
| 5–12 min | §1–2 Functional / Non-functional requirements | Show you scoped it like a product, not just a model |
| 12–20 min | §3 Agent objectives: autonomy vs. constraints | This is usually the differentiator question — spend real time here |
| 20–35 min | §4 High-level architecture (draw the diagram live) | The centerpiece — orchestration loop, tools, verifier |
| 35–45 min | §5 Memory & context design | Shows systems maturity beyond "call an LLM in a loop" |
| 45–55 min | §6 Deep dive: pick ONE (sufficiency loop or groundedness verifier) | Depth beats breadth — don't try to cover all of §6 |
| 55–60 min | §6.8 MVP cut-line + risks | Shows judgment about what NOT to build first |

If time is tight, cut §6 depth, not §3/§4 — objectives and architecture are
the parts that matter most for evaluating an agentic design.

---

## 1. Functional Requirements

| ID | Requirement |
|---|---|
| FR1 | Accept a valuation request: property/submarket, space size, property type, lease assumptions. |
| FR2 | Dynamically formulate queries to `comps/search` and `market-stats` based on request parameters (not a fixed query template). |
| FR3 | Iteratively refine retrieval (widen radius, adjust date window/property type) when initial evidence is thin, bounded by a max iteration count. |
| FR4 | Synthesize a `$/PSF` rent recommendation with a written rationale grounded in retrieved evidence. |
| FR5 | Cite every quantitative claim in the rationale to a specific source record (comp ID or market-stat series point). |
| FR6 | Emit a confidence score alongside the recommendation. |
| FR7 | Route low-confidence or ungrounded outputs to human review instead of auto-publishing. |
| FR8 | Write the recommendation to `askingRentPsf` preview in the system of record and/or produce a client-facing submarket narrative. |
| FR9 | Log the full agent trace (queries issued, evidence retrieved, decisions made) for audit/dispute defense. |
| FR10 *(v1.1)* | Support session-level follow-up refinement ("widen radius", "exclude pre-2021 comps") without re-running retrieval from scratch. |

## 2. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Latency | p50 < 15s, p95 < 30s end-to-end for an interactive single-property request. |
| Groundedness | 100% of numeric claims must resolve to a retrieved record ID — zero tolerance for fabricated figures (this is the trust-critical NFR for a valuation product). |
| Cost control | Hard ceiling on tool calls (≤3 retrieval iterations) and LLM calls (≤2 reasoning calls) per request. |
| Consistency | Same inputs → low-variance outputs; aggregation math (medians, weighting) done in deterministic code, not left to the LLM. |
| Availability / degradation | If one data source (Snowflake or OpenSearch) is down, degrade to a lower-confidence result with a flag rather than fail the whole request. |
| Auditability | Full agent trace retained per valuation for a defined retention window — real-estate valuations get disputed and need to be defensible after the fact. |
| Access control | Requests scoped to the user's authorized submarkets/portfolios, enforced at the tool layer, not by agent judgment. |
| Observability | Every agent step emits a trace span (tool called, params, latency, result count) for debugging and offline eval. |
| Extensibility | New data sources become new tools without redesigning the orchestrator. |
| Scalability | Orchestrator workers are stateless/horizontally scalable; repeated submarket queries hit a shared evidence cache. |

---

## 3. Agent Objectives

**Primary objective:** produce accurate, defensible, timely `$/PSF`
recommendations grounded in current data, with minimal manual analyst effort
— without ever fabricating a figure, and always leaving an audit trail.

Every design decision below falls out of splitting that objective into what
the agent is *trusted to decide* vs. what it is *never allowed to decide*.

### 3.1 Autonomy — what the agent decides for itself

- Which specific query parameters to issue to `comps/search` / `market-stats`
  (radius, date window, property-type matching, submarket boundary
  interpretation).
- Whether the retrieved evidence is *sufficient*, and if not, how to refine
  and re-query (within the iteration cap).
- How to weight comps when synthesizing a number (recency, size similarity,
  lease-type match, proximity).
- How to phrase the rationale for the audience (internal analyst note vs.
  client-facing narrative).
- Whether to flag its own output for human review based on its confidence
  assessment.

### 3.2 Constraints — hard boundaries, not up for agent judgment

- May only use data returned by approved tools — no world-knowledge rent
  figures, no invented comps.
- Every numeric claim must be traceable to a cited source record; the
  verifier strips or rejects anything that isn't (§6.4).
- Max retrieval iterations / max LLM calls per request — cannot loop forever
  chasing "perfect" evidence.
- Cannot auto-publish when confidence < threshold or comp count < minimum —
  must route to human review (FR7).
- Cannot access data outside the requesting user's authorized
  submarkets/portfolios — enforced at the tool/API layer, never left to the
  model to self-police.
- Output must conform to a fixed structured schema for downstream
  integration — free-form-only answers are invalid.
- No code execution, no open web access — restricted to the defined tool
  surface (`comps/search`, `market-stats`).

This autonomy/constraint split is the answer to "how do you keep an agentic
system from going off the rails" — autonomy is scoped to *how to search and
weigh evidence*, never to *whether to follow the rules*.

---

## 4. High-Level Agentic Architecture

```
                         ┌─────────────────────────┐
                         │   User Request           │
                         │ (property / submarket)   │
                         └────────────┬─────────────┘
                                      ▼
                         ┌─────────────────────────┐
                         │       Orchestrator        │  (LangGraph-style
                         │   (plan → act → check)    │   state machine)
                         └────────────┬─────────────┘
                                      ▼
                    ┌─────────────────────────────────┐
                    │      Data Retrieval Agent         │
                    │  issues tool calls, owns retries  │
                    └───────┬─────────────────┬────────┘
                            ▼                 ▼
                 GET /v1/comps/search   GET /v1/market-stats
                    (OpenSearch)           (Snowflake/dbt)
                            │                 │
                            └────────┬────────┘
                                     ▼
                    ┌─────────────────────────────┐
                    │   Sufficiency Check (rules)   │──(insufficient)──┐
                    │  ≥N comps? stats present?     │                  │
                    └───────────────┬───────────────┘                  │
                              (sufficient)                              │
                                     ▼                          refine params
                    ┌─────────────────────────────┐             (widen radius/
                    │      Context Builder          │              date window)
                    │  dedupe, summarize, compute    │                  │
                    │  aggregate stats (code, not LLM)│◀────────────────┘
                    └───────────────┬───────────────┘   (≤3 iterations, then
                                     ▼                    proceed w/ flag)
                    ┌─────────────────────────────┐
                    │      Valuation Agent (LLM)    │
                    │ reasons over evidence bundle,  │
                    │ produces $/PSF + rationale     │
                    └───────────────┬───────────────┘
                                     ▼
                    ┌─────────────────────────────┐
                    │   Groundedness Verifier       │
                    │ every claim ↔ cited record?    │
                    └───────┬─────────────┬─────────┘
                       (pass, high conf)  (fail / low conf)
                            ▼                 ▼
                 ┌─────────────────┐  ┌───────────────────┐
                 │  Auto-publish    │  │  Human Review Queue │
                 │ askingRentPsf /  │  │ (analyst sign-off) │
                 │ client report    │  └───────────────────┘
                 └─────────────────┘
```

**Component responsibilities**

| Component | Responsibility | Type |
|---|---|---|
| Orchestrator | Owns the control loop and state; routes between retrieval, valuation, verification | Deterministic state machine |
| Data Retrieval Agent | Decides *what* to query and *when* it has enough (calls the sufficiency check) | LLM-guided tool use |
| Sufficiency Check | Enforces the "enough evidence?" gate | Rule-based (deterministic — see §6.3) |
| Context Builder | Dedupe/normalize comps, compute medians/spread programmatically, assemble a bounded-size evidence bundle | Deterministic code |
| Valuation Agent | Reasons over the evidence bundle to produce number + rationale | LLM |
| Groundedness Verifier | Confirms every cited number in the rationale exists in the evidence bundle | Deterministic parsing/cross-check |
| Human Review Queue | Catches low-confidence/ungrounded outputs before they reach a client | Human-in-the-loop |

Why a rule-based sufficiency check and a deterministic verifier instead of
"another LLM call to judge the LLM"? For an MVP, determinism buys speed,
cost, and — critically for a valuation product — reproducibility: the same
evidence set always yields the same pass/fail decision, which matters when a
recommendation gets challenged later.

---

## 5. Memory and Context Design

Four distinct kinds of "memory," each solving a different problem — worth
being explicit about the difference, since conflating them is a common tell
of shallow agentic design.

| Memory type | Scope | Storage | Purpose |
|---|---|---|---|
| **Working memory** | Single request | In-process orchestrator state | The ReAct/plan-execute scratchpad: what's been queried, what's been found, iteration count. Discarded after the run, but the trace is persisted for audit (FR9). |
| **Session memory** | One user session (multi-turn refinement) | Redis, keyed by `session_id`, short TTL | Lets a follow-up ("widen the radius") reuse prior evidence instead of re-fetching everything. *v1.1, not MVP (FR10).* |
| **Evidence cache** | Cross-user, cross-session | Redis/cache layer, keyed by `hash(submarket, property_type, params)`, short TTL (e.g. 24h) | Pure performance/cost optimization — popular submarkets get queried repeatedly; avoids redundant Snowflake/OpenSearch load. Not "learning," just caching. |
| **Feedback / episodic store** | Long-term, cross-request | Append-only table: request params, retrieved evidence, agent output, analyst override (if any), final accepted rent | The actual learning loop: labeled examples for periodic prompt/few-shot refresh and an offline eval regression set. In MVP this is just *logged*, not live-consumed — closing the loop automatically is a v2 concern. |

**Context assembly (the part that keeps token usage bounded and predictable
regardless of how much was retrieved):**

The Valuation Agent never sees raw retrieval JSON. The Context Builder:

1. Dedupes comps (same transaction surfaced by overlapping queries).
2. Computes aggregate stats in code — median/mean `$/PSF`, spread, comp count
   by recency bucket — rather than asking the LLM to eyeball a table of
   numbers.
3. Selects the top-N comps by relevance (size/date/type match) rather than
   dumping everything retrieved.
4. Assembles a fixed-shape "evidence bundle": `{summary_stats, top_comps[≤K],
   market_trend_deltas}` — bounded size regardless of how many records the
   retrieval iterations pulled in.

This matters for two NFRs at once: latency/cost (bounded prompt size) and
consistency (the LLM reasons over the same *shape* of input every time,
rather than a variable-length dump).

---

## 6. Detailed Deep Dive (MVP-Scoped)

Pick one of §6.3 or §6.4 to actually walk through live — they're the two
pieces that make this "agentic" rather than "RAG with extra steps."

### 6.1 Tool contracts

```
comps_search(submarket_id, property_type, min_sf, max_sf, lease_type,
             date_from, date_to, radius_miles, k) -> Comp[]

Comp = { comp_id, address, submarket_id, sf, lease_type,
         asking_rent_psf, effective_rent_psf, lease_start_date,
         tenant_industry, concessions, source_system, last_verified_at }

market_stats(submarket_id, metric ∈ {vacancy_rate, net_absorption,
             asking_rent_trend}, time_window) -> TimeSeries

TimeSeries = { submarket_id, metric, points: [{period, value}],
               yoy_change, percentile_rank }
```

Narrow, typed tool contracts are what let the Data Retrieval Agent's
"autonomy" (§3.1) stay safe — it can choose *parameters* freely, but the
return shape is always structured and validated.

### 6.2 Orchestration loop (plan → act → check)

1. **Plan**: parse request into initial query params for both tools.
2. **Act**: call `comps_search` + `market_stats` in parallel.
3. **Check** (§6.3): sufficient? → proceed. Insufficient? → refine params
   (widen radius, extend date window) and repeat, capped at 3 iterations.
4. On cap exhaustion without sufficiency: proceed anyway, but confidence
   score is penalized and `needs_human_review` is forced `true`.

### 6.3 Sufficiency check (deterministic, not LLM-judged)

```
sufficient = (comp_count >= 5)
         AND (comps within submarket ± configurable radius)
         AND (>= 3 comps within trailing 12 months)
         AND (market_stats response present for submarket)
```

Rule-based on purpose: cheap, fast, fully reproducible, and easy to unit
test — important for an MVP where you want the "agentic" retrieval loop to
be trustworthy before you ever let an LLM judge its own inputs.

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

The verifier is deterministic: every ID in `cited_comp_ids` /
`cited_market_stat_ids` must exist in the evidence bundle that was actually
passed to the model. Any mismatch → force `needs_human_review = true`. This
is the single most important trust mechanism in the system: it makes
hallucination structurally detectable instead of relying on the model to
"try not to."

### 6.5 Confidence scoring (also deterministic)

Composite of: comp count, recency mix, and spread/variance of comp
`$/PSF` (tight spread → higher confidence). Computed in code from the
evidence bundle, not asked of the LLM — keeps it auditable and stable.

### 6.6 Human-in-the-loop gate

Route to review queue if: `confidence < 0.6` OR `comp_count < 3` OR verifier
citation check fails. Otherwise auto-publish to `askingRentPsf` preview.

### 6.7 Observability

Every step (tool call + params, iteration count, verifier pass/fail,
confidence) emitted as a trace span, keyed by request ID — this is what
FR9/auditability actually requires operationally, not just conceptually.

### 6.8 MVP cut-line

| In scope (MVP) | Deferred (v2 backlog) |
|---|---|
| Single-turn request → structured recommendation with citations | Multi-turn conversational refinement / session memory (FR10) |
| 2 tools: `comps_search`, `market_stats` | Additional data sources (e.g., permits, foot traffic) |
| Rule-based sufficiency check + deterministic confidence score | LLM-judged sufficiency / self-critique |
| Deterministic groundedness verifier | Vector-store long-term memory of past rationales |
| Basic tracing/logging per request | Automated fine-tuning from analyst feedback (feedback store is logged but not yet consumed) |
| Manual review queue (simple flag + list) | Auto-generated client-facing PDF reports |
| Single-property valuation | Portfolio-level batch valuation |

The one-sentence version: **the MVP proves the agentic loop (retrieve →
judge sufficiency → refine → ground → verify) end to end on the narrowest
possible surface — two tools, one property at a time — before spending
effort on breadth.**

---

## 7. Success Metrics (ties back to NFRs)

- **Groundedness rate**: % of published recommendations with zero verifier
  failures — target 100% (anything else auto-routes to review, so this is
  really "% requiring human review," tracked as a leading indicator).
- **Turnaround time**: p50/p95 latency vs. the 15s/30s NFR targets.
- **Analyst override rate**: % of auto-published recommendations later
  corrected by an analyst — the core signal for whether autonomy boundaries
  (§3.1) are calibrated correctly.
- **Coverage**: % of requests resolved without hitting the human review gate.

## 8. Risks & Open Questions

- **Submarket boundary ambiguity**: if `submarket_id` taxonomy is coarser
  than the property in question, the agent's "autonomy" to interpret
  boundaries could quietly bias results — worth a v1 guardrail (e.g., flag
  when radius search and submarket-ID search disagree materially).
- **Stale comps**: `last_verified_at` staleness isn't currently part of the
  sufficiency check — should it be, or is recency-of-lease-date sufficient?
- **Cache correctness vs. freshness**: the evidence cache (§5) trades
  freshness for cost; TTL needs tuning against how fast `market-stats`
  actually changes.
- **Confidence threshold calibration**: 0.6/comp-count-3 (§6.6) are
  placeholder defaults — should be tuned against the feedback store (§5)
  once enough labeled overrides exist.
