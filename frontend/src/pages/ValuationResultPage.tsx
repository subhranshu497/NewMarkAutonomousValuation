import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getValuation } from "../api/client";
import { ConfidenceBadge } from "../components/ConfidenceBadge";
import { EvidencePanel } from "../components/EvidencePanel";
import { TraceTimeline } from "../components/TraceTimeline";
import type { ValuationResponse } from "../types/valuation";

export function ValuationResultPage() {
  const { id } = useParams<{ id: string }>();
  const [response, setResponse] = useState<ValuationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getValuation(id)
      .then(setResponse)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"));
  }, [id]);

  if (error) return <p role="alert">{error}</p>;
  if (!response) return <p>Loading...</p>;

  const { result, evidence, trace } = response;

  return (
    <section>
      <h1>Valuation Result</h1>
      <p>Request ID: {response.request_id}</p>

      <h2>
        ${result.recommended_rent_psf} / PSF{" "}
        <small>
          (range ${result.range_low}–${result.range_high})
        </small>
      </h2>
      <ConfidenceBadge confidence={result.confidence} needsHumanReview={result.needs_human_review} />

      <h3>Rationale</h3>
      <p>{result.rationale_text}</p>

      <h3>Evidence</h3>
      <EvidencePanel
        evidence={evidence}
        citedCompIds={result.cited_comp_ids}
        citedMarketStatIds={result.cited_market_stat_ids}
      />

      <h3>Trace</h3>
      <TraceTimeline trace={trace} />
    </section>
  );
}
