# Future Scope

Items not implemented today, grouped by area. See `DESIGN.md` §6.9/§8 for
current build-status detail behind each item.

## 1. Data & Retrieval

- Replace mock `comps_search` / `market_stats` with real OpenSearch /
  Snowflake-dbt API calls (tool interfaces already isolated for this swap).
- Add resilience (timeout/retry/fallback) around real external tool calls —
  today only the semantic path degrades gracefully on failure.
- Add a new data source for supply pipeline / shadow vacancy signals
  (market news, SEC filings, construction permits) — no such source exists
  today; only comps + market stats.
- Normalize lease structures (Gross vs. NNN vs. Modified Gross) — not
  implemented; `lease_type` today only means deal type (direct/renewal/
  sublease), not rent structure.
- Increase fixture/data volume — 14 comps is tight against the
  `min_comp_count=5` sufficiency threshold.

## 2. Performance & Cost

- Add an evidence cache (Redis or similar) keyed by
  `hash(submarket, property_type, params)` — avoids repeat retrieval calls
  for popular submarkets; needed before pointing at real, rate-limited APIs.
- Add session memory (Redis, `session_id`-scoped) for multi-turn refinement
  ("widen radius," "exclude pre-2021 comps") without full re-retrieval (FR10).
- Instrument and measure actual p50/p95 latency against the 15s/30s NFR
  targets — not currently tracked.

## 3. Persistence & Auditability

- Move trace store off the in-process dict to durable storage with a
  retention policy (FR9) — currently lost on every restart.
- Move review queue off the in-process dict to a real database.
- Make analyst override decisions actually consumable — `record_decision()`
  writes today but nothing reads it back; needed for the feedback/episodic
  loop and override-rate metric (§7).
- Write back the recommendation to `askingRentPsf` in an external system of
  record, and/or generate a client-facing submarket report (FR8).

## 4. Access Control & Security

- Add authentication/authorization — no auth middleware exists on any route
  today.
- Enforce `requested_by` against actual submarket/portfolio entitlements —
  field is captured but never checked.
- Add rate limiting / abuse controls before exposing any endpoint beyond
  trusted internal users.

## 5. External User Support (landlords, property owners, equity investors)

- Design an ownership/entitlement model (which user can see which
  property/portfolio) — no such concept exists in the schemas today.
- Build an audience-appropriate output — a client-facing narrative distinct
  from the internal analyst rationale (a second synthesis skill or a
  redaction layer), instead of exposing the same raw trace/citations to
  everyone.
- Hide or restrict the trace timeline for external audiences — currently
  exposes internal methodology to any viewer.
- Apply a stricter confidence bar for numbers shown directly to external
  users with no analyst in the loop (today's 0.6 threshold only gates
  routing to human review, not direct external exposure).

## 6. Scale

- Support portfolio-level batch valuation (e.g., 50 properties across 10
  submarkets in one request) — today the API only accepts one property per
  request.

## 7. Model & Calibration

- Tune confidence-score weights (0.4/0.3/0.3) and thresholds
  (confidence 0.6, comp-count 3/5) against real outcome data — currently
  placeholder defaults, self-flagged as such in code.
- Consider whether `last_verified_at` staleness should factor into the
  sufficiency check.
