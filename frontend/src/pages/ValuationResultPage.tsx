import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getValuation } from "../api/client";
import { ConfidenceBadge } from "../components/ConfidenceBadge";
import { EvidencePanel } from "../components/EvidencePanel";
import { TraceTimeline } from "../components/TraceTimeline";
import type { ValuationResponse } from "../types/valuation";

export function ValuationResultPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [response, setResponse] = useState<ValuationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getValuation(id)
      .then(setResponse)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"));
  }, [id]);

  if (error) {
    return (
      <div className="alert alert-error" role="alert">
        {error}
      </div>
    );
  }

  if (!response) {
    return <div className="loading-state">Loading valuation…</div>;
  }

  const { result, evidence, trace } = response;

  return (
    <section>
      <div className="page-header">
        <div>
          <span className="eyebrow">Valuation result</span>
          <h1 className="page-title">Recommended Rent</h1>
        </div>
        <span className="request-id">{response.request_id}</span>
      </div>

      <div className="card">
        <div className="result-hero">
          <div>
            <div className="rent-figure">
              <span className="value">${result.recommended_rent_psf}</span>
              <span className="unit">/ PSF</span>
            </div>
            <p className="rent-range">
              Range ${result.range_low} – ${result.range_high}
            </p>
          </div>
          <div className="result-hero-actions">
            <ConfidenceBadge confidence={result.confidence} needsHumanReview={result.needs_human_review} />
            {result.needs_human_review && (
              <button
                className="btn btn-outline btn-sm"
                onClick={() => navigate("/review-queue", { state: { focusId: response.request_id } })}
              >
                Review
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="card">
        <h3 className="card-title" style={{ marginBottom: "0.75rem" }}>
          Rationale
        </h3>
        <p className="rationale-text">{result.rationale_text}</p>
      </div>

      <div className="card">
        <h3 className="card-title" style={{ marginBottom: "1.1rem" }}>
          Evidence
        </h3>
        <EvidencePanel
          evidence={evidence}
          citedCompIds={result.cited_comp_ids}
          citedMarketStatIds={result.cited_market_stat_ids}
        />
      </div>

      <div className="card">
        <h3 className="card-title" style={{ marginBottom: "1.1rem" }}>
          Trace
        </h3>
        <TraceTimeline trace={trace} />
      </div>
    </section>
  );
}
