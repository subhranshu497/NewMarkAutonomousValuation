import { Fragment, useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { listReviewQueue, submitReviewDecision } from "../api/client";
import { ConfidenceBadge } from "../components/ConfidenceBadge";
import { EvidencePanel } from "../components/EvidencePanel";
import { TraceTimeline } from "../components/TraceTimeline";
import type { ValuationResponse } from "../types/valuation";

type DecisionAction = "approve" | "reject";

export function ReviewQueuePage() {
  const location = useLocation();
  const [items, setItems] = useState<ValuationResponse[]>([]);
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [expandedId, setExpandedId] = useState<string | null>(
    (location.state as { focusId?: string } | null)?.focusId ?? null,
  );
  const [busyId, setBusyId] = useState<string | null>(null);
  const [deferredIds, setDeferredIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    listReviewQueue()
      .then(setItems)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"));
  }

  useEffect(refresh, []);

  async function decide(id: string, action: DecisionAction) {
    const overrideValue = overrides[id];
    const analystOverridePsf = overrideValue ? Number(overrideValue) : undefined;
    setBusyId(id);
    setError(null);
    try {
      await submitReviewDecision(id, action === "approve", analystOverridePsf);
      setExpandedId(null);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit decision");
    } finally {
      setBusyId(null);
    }
  }

  function defer(id: string) {
    setDeferredIds((prev) => new Set(prev).add(id));
    setExpandedId(null);
  }

  return (
    <section>
      <div className="page-header">
        <div>
          <span className="eyebrow">Human review</span>
          <h1 className="page-title">Review Queue</h1>
          <p className="page-subtitle">Low-confidence valuations awaiting analyst sign-off.</p>
        </div>
        <span className="badge badge-neutral">{items.length} pending</span>
      </div>

      {error && (
        <div className="alert alert-error" role="alert" style={{ marginBottom: "1.5rem" }}>
          {error}
        </div>
      )}

      <div className="card" style={{ padding: 0 }}>
        {items.length === 0 ? (
          <div className="empty-state">No valuations pending review.</div>
        ) : (
          <div className="table-wrap" style={{ border: "none", borderRadius: "var(--radius-lg)" }}>
            <table>
              <thead>
                <tr>
                  <th>Request ID</th>
                  <th>Submarket</th>
                  <th>Recommended $/PSF</th>
                  <th>Confidence</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const isExpanded = expandedId === item.request_id;
                  const isBusy = busyId === item.request_id;
                  return (
                    <Fragment key={item.request_id}>
                      <tr>
                        <td>
                          <Link to={`/valuations/${item.request_id}`} className="cell-mono">
                            {item.request_id.slice(0, 8)}
                          </Link>
                        </td>
                        <td>{item.evidence.top_comps[0]?.submarket_id ?? "—"}</td>
                        <td>${item.result.recommended_rent_psf}</td>
                        <td>
                          <span
                            className={`badge ${
                              item.result.confidence >= 0.8
                                ? "badge-success"
                                : item.result.confidence >= 0.5
                                ? "badge-warning"
                                : "badge-danger"
                            }`}
                          >
                            {(item.result.confidence * 100).toFixed(0)}%
                          </span>
                        </td>
                        <td>
                          {deferredIds.has(item.request_id) ? (
                            <span className="badge badge-neutral">Deferred</span>
                          ) : (
                            <span className="cell-muted">Pending</span>
                          )}
                        </td>
                        <td>
                          <button
                            className="btn btn-outline btn-sm"
                            onClick={() => setExpandedId(isExpanded ? null : item.request_id)}
                          >
                            {isExpanded ? "Hide Detail" : "Show Detail"}
                          </button>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr className="detail-row">
                          <td colSpan={6}>
                            <div className="detail-panel">
                              <div className="detail-panel-header">
                                <div className="rent-figure">
                                  <span className="value">${item.result.recommended_rent_psf}</span>
                                  <span className="unit">/ PSF</span>
                                </div>
                                <p className="rent-range">
                                  Range ${item.result.range_low} – ${item.result.range_high}
                                </p>
                                <ConfidenceBadge
                                  confidence={item.result.confidence}
                                  needsHumanReview={item.result.needs_human_review}
                                />
                              </div>

                              <h4 className="section-title">Rationale</h4>
                              <p className="rationale-text">{item.result.rationale_text}</p>

                              <div className="field" style={{ maxWidth: 220, marginBottom: "1.5rem" }}>
                                <label className="field-label" htmlFor={`override-${item.request_id}`}>
                                  Override $/PSF
                                </label>
                                <input
                                  id={`override-${item.request_id}`}
                                  type="number"
                                  className="input"
                                  placeholder="optional"
                                  value={overrides[item.request_id] ?? ""}
                                  onChange={(e) => setOverrides({ ...overrides, [item.request_id]: e.target.value })}
                                />
                                <span className="field-hint">
                                  The only field an analyst decision persists back to the system.
                                </span>
                              </div>

                              <EvidencePanel
                                evidence={item.evidence}
                                citedCompIds={item.result.cited_comp_ids}
                                citedMarketStatIds={item.result.cited_market_stat_ids}
                              />

                              <h4 className="section-title">Trace</h4>
                              <TraceTimeline trace={item.trace} />

                              <div className="row-actions" style={{ marginTop: "1.5rem" }}>
                                <button
                                  className="btn btn-success btn-sm"
                                  disabled={isBusy}
                                  onClick={() => decide(item.request_id, "approve")}
                                >
                                  Approve
                                </button>
                                <button
                                  className="btn btn-danger btn-sm"
                                  disabled={isBusy}
                                  onClick={() => decide(item.request_id, "reject")}
                                >
                                  Reject
                                </button>
                                <button
                                  className="btn btn-warning btn-sm"
                                  disabled={isBusy}
                                  onClick={() => defer(item.request_id)}
                                >
                                  Defer
                                </button>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
