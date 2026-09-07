# Autonomous Valuation & Market Intelligence Copilot

## Problem Statement

When someone needs to value a commercial property or understand trends in a
submarket, they currently have to manually pull together data from several
different places — past comparable deals, how much space is being leased vs.
vacated, vacancy rates, and what similar spaces are currently asking for rent.
This data lives across millions of records in different systems, and stitching
it together into a defensible rent recommendation takes significant manual
effort and expertise. It's slow, inconsistent between analysts, and hard to
scale as the portfolio and market coverage grows.

## Business Benefit

- **Faster turnaround** on valuations and market analysis — from hours/days of
  manual research to near real-time recommendations.
- **Consistency** — every valuation follows the same rigorous process against
  the same underlying data, reducing analyst-to-analyst variance.
- **Scalability** — the same system can cover many more submarkets and
  properties than a fixed team of analysts could manually research.
- **Better client experience** — brokers and clients get faster, data-backed
  asking rent guidance and market intelligence reports for presentations.
- **Frees up analyst time** for higher-value work (negotiation strategy,
  client relationships) instead of manual data aggregation.

## Deterministic vs. Agentic — Which Fits Best

**Agentic** is the better fit here, not a deterministic (fixed-pipeline)
solution.

A deterministic pipeline works well when the steps and data sources needed are
always the same, in the same order, for every request. Here, that's not the
case:

- The right query depends on the specific property/submarket in question —
  which comps are relevant, which time window matters, and which macro trends
  apply all vary case by case.
- Multiple, heterogeneous systems (structured analytics in Snowflake/dbt,
  search-based comps in OpenSearch) need to be queried dynamically and the
  results reasoned over together, not just concatenated.
- The system needs to decide *what to retrieve next* based on what it's
  already found — e.g., pulling additional comps if the initial set is too
  thin, or narrowing the submarket if trends look inconsistent.

That kind of dynamic, multi-step reasoning and tool use is exactly what an
agentic architecture is designed for.

## Why RAG Fits (Agentic RAG)

Given an agentic approach, Retrieval-Augmented Generation is the right
grounding strategy because:

- **Freshness**: Market data — asking rents, vacancy, absorption — changes
  constantly. An LLM's static training knowledge can't reflect this; every
  recommendation must be grounded in freshly retrieved, current records.
  *(Design rationale — see note on current data sources below.)*
- **Groundedness / trust**: Valuation numbers need to be defensible and
  traceable back to real comps and market stats, not generated from the
  model's general knowledge. RAG ties every output to retrieved evidence.
- **Heterogeneous data**: The system needs to combine structured aggregates
  (Snowflake/dbt market stats) with comp-level search results (OpenSearch) and
  synthesize both into a coherent narrative and number — a natural fit for
  retrieval feeding a reasoning/generation step.
- **Agentic retrieval**: Rather than a single fixed retrieval step, the agent
  can iteratively query, evaluate whether it has enough evidence, and issue
  follow-up queries — a pattern that plain RAG (single retrieve-then-generate)
  doesn't support but Agentic RAG does.

## High-Level Solution

**System integration (target architecture)**

- **Analytics Tier & Comparables Service** — the copilot is designed to
  integrate with:
    - `GET /v1/market-stats` — Snowflake/dbt aggregates (vacancy, net
      absorption, submarket trends)
    - `GET /v1/comps/search` — OpenSearch-backed comparable transaction records

  *Current build:* both are implemented as thin, swappable tool interfaces
  (`comps_search`, `market_stats`) sitting in front of a small in-memory
  fixture dataset rather than live Snowflake/OpenSearch — see
  `DESIGN.md` §4.1 for exactly what's real vs. simulated today, and what
  needs to change to point these tools at production systems.

**Agentic RAG pipeline**

1. **Data Retrieval Agent** — Translates the user's request (e.g., "value this
   space in Submarket X") into dynamic structured queries against OpenSearch
   (`comps/search`) and Snowflake (`market-stats`), rather than a single fixed
   query.
2. **Analytical RAG** — Ingests the retrieved submarket macro trends alongside
   structured `Comp` snapshots, grounding the reasoning step in this
   retrieved, current evidence.
3. **Valuation Agent** — Reasons over the retrieved comps and market trends to
   produce an estimated market rent recommendation (`$/PSF`) for the new
   availability, along with supporting rationale.
4. **Verification & human-in-the-loop** — A deterministic groundedness check
   confirms every cited figure exists in the retrieved evidence, and a
   confidence score is computed from comp count/recency/spread. Anything
   ungrounded or low-confidence routes to an analyst review queue instead of
   auto-publishing, rather than trusting the LLM's own judgment. This is
   built end-to-end, including a review UI — see `DESIGN.md` §6.4–§6.6.
5. **Output** — The recommendation is returned as a structured result with
   citations, confidence, and full trace, surfaced in the app UI. Automatic
   write-back to `askingRentPsf` in an external system of record and
   auto-generated client-facing reports are targeted but not yet built
   (`DESIGN.md` FR8).

**Flow at a glance**

```
User request (property / submarket)
        │
        ▼
Data Retrieval Agent ──▶ GET /v1/comps/search (OpenSearch — target;
        │                 in-memory fixtures today)
        └─▶ GET /v1/market-stats (Snowflake/dbt — target;
                                    in-memory fixtures today)
        ▼
Analytical RAG (grounds trends + comps together)
        ▼
Valuation Agent ──▶ $/PSF recommendation + rationale + citations
        ▼
Groundedness verifier + confidence score ──▶ pass ──▶ Output
        │
        └─▶ fail / low confidence ──▶ Human review queue (built, with UI)
        ▼
Output: structured result in app UI  /  askingRentPsf preview (target)
```

See `DESIGN.md` for the full architecture as actually implemented
(orchestration graph, agent objectives, memory design, and an honest
build-status breakdown in §6.9).
