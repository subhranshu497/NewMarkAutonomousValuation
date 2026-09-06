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

**System integration**

- **Analytics Tier & Comparables Service** — the copilot integrates with:
    - `GET /v1/market-stats` — Snowflake/dbt aggregates (vacancy, net
      absorption, submarket trends)
    - `GET /v1/comps/search` — OpenSearch-backed comparable transaction records

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
4. **Output** — The recommendation automatically populates `askingRentPsf`
   previews in the system of record, and/or generates a customized submarket
   analysis report for client-facing presentations.

**Flow at a glance**

```
User request (property / submarket)
        │
        ▼
Data Retrieval Agent ──▶ GET /v1/comps/search (OpenSearch)
        │            └─▶ GET /v1/market-stats (Snowflake/dbt)
        ▼
Analytical RAG (grounds trends + comps together)
        ▼
Valuation Agent ──▶ $/PSF recommendation + rationale
        ▼
Output: askingRentPsf preview  /  submarket analysis report
```
