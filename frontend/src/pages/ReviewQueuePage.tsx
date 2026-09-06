import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listReviewQueue, submitReviewDecision } from "../api/client";
import type { ValuationResponse } from "../types/valuation";

export function ReviewQueuePage() {
  const [items, setItems] = useState<ValuationResponse[]>([]);
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    listReviewQueue()
      .then(setItems)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"));
  }

  useEffect(refresh, []);

  async function decide(id: string, approved: boolean) {
    const overrideValue = overrides[id];
    const analystOverridePsf = overrideValue ? Number(overrideValue) : undefined;
    await submitReviewDecision(id, approved, analystOverridePsf);
    refresh();
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
                  <th>Override $/PSF</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.request_id}>
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
                      <input
                        type="number"
                        className="override-input"
                        placeholder="optional"
                        value={overrides[item.request_id] ?? ""}
                        onChange={(e) => setOverrides({ ...overrides, [item.request_id]: e.target.value })}
                      />
                    </td>
                    <td>
                      <div className="row-actions">
                        <button className="btn btn-success btn-sm" onClick={() => decide(item.request_id, true)}>
                          Approve
                        </button>
                        <button className="btn btn-danger btn-sm" onClick={() => decide(item.request_id, false)}>
                          Reject
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
