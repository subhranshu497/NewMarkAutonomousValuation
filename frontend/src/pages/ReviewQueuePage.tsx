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
      <h1>Human Review Queue</h1>
      {error && <p role="alert">{error}</p>}
      {items.length === 0 && <p>No valuations pending review.</p>}
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
                <Link to={`/valuations/${item.request_id}`}>{item.request_id.slice(0, 8)}</Link>
              </td>
              <td>{item.evidence.top_comps[0]?.submarket_id ?? "—"}</td>
              <td>{item.result.recommended_rent_psf}</td>
              <td>{(item.result.confidence * 100).toFixed(0)}%</td>
              <td>
                <input
                  type="number"
                  placeholder="optional"
                  value={overrides[item.request_id] ?? ""}
                  onChange={(e) => setOverrides({ ...overrides, [item.request_id]: e.target.value })}
                />
              </td>
              <td>
                <button onClick={() => decide(item.request_id, true)}>Approve</button>
                <button onClick={() => decide(item.request_id, false)}>Reject</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
