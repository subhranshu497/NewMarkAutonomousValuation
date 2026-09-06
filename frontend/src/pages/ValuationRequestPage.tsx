import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createValuation } from "../api/client";

const SUBMARKETS = ["chi-fulton-market", "chi-river-north"];

export function ValuationRequestPage() {
  const navigate = useNavigate();
  const [submarketId, setSubmarketId] = useState(SUBMARKETS[0]);
  const [propertyType, setPropertyType] = useState("office");
  const [spaceSf, setSpaceSf] = useState(19000);
  const [leaseType, setLeaseType] = useState("direct");
  const [termMonths, setTermMonths] = useState(84);
  const [concessionsAssumed, setConcessionsAssumed] = useState("");
  const [requestedBy, setRequestedBy] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const response = await createValuation({
        submarket_id: submarketId,
        property_type: propertyType,
        space_sf: spaceSf,
        lease_assumptions: {
          lease_type: leaseType,
          term_months: termMonths,
          concessions_assumed: concessionsAssumed || null,
        },
        requested_by: requestedBy || "anonymous",
      });
      navigate(`/valuations/${response.request_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
      setSubmitting(false);
    }
  }

  return (
    <section>
      <div className="page-header">
        <div>
          <span className="eyebrow">Valuation request</span>
          <h1 className="page-title">New Valuation Request</h1>
          <p className="page-subtitle">
            Submit deal parameters to generate an evidence-grounded rent recommendation.
          </p>
        </div>
      </div>

      <div className="card">
        <form onSubmit={handleSubmit}>
          <div className="form-grid">
            <div className="field">
              <label className="field-label" htmlFor="submarket">
                Submarket
              </label>
              <select
                id="submarket"
                className="select"
                value={submarketId}
                onChange={(e) => setSubmarketId(e.target.value)}
              >
                {SUBMARKETS.map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label className="field-label" htmlFor="propertyType">
                Property type
              </label>
              <input
                id="propertyType"
                className="input"
                value={propertyType}
                onChange={(e) => setPropertyType(e.target.value)}
              />
            </div>

            <div className="field">
              <label className="field-label" htmlFor="spaceSf">
                Space (SF)
              </label>
              <input
                id="spaceSf"
                className="input"
                type="number"
                value={spaceSf}
                onChange={(e) => setSpaceSf(Number(e.target.value))}
                min={1}
              />
            </div>

            <div className="field">
              <label className="field-label" htmlFor="leaseType">
                Lease type
              </label>
              <input
                id="leaseType"
                className="input"
                value={leaseType}
                onChange={(e) => setLeaseType(e.target.value)}
              />
            </div>

            <div className="field">
              <label className="field-label" htmlFor="termMonths">
                Term (months)
              </label>
              <input
                id="termMonths"
                className="input"
                type="number"
                value={termMonths}
                onChange={(e) => setTermMonths(Number(e.target.value))}
                min={1}
              />
            </div>

            <div className="field">
              <label className="field-label" htmlFor="concessions">
                Concessions assumed <span className="field-hint">(optional)</span>
              </label>
              <input
                id="concessions"
                className="input"
                value={concessionsAssumed}
                onChange={(e) => setConcessionsAssumed(e.target.value)}
              />
            </div>

            <div className="field span-2">
              <label className="field-label" htmlFor="requestedBy">
                Requested by
              </label>
              <input
                id="requestedBy"
                className="input"
                placeholder="anonymous"
                value={requestedBy}
                onChange={(e) => setRequestedBy(e.target.value)}
              />
            </div>
          </div>

          {error && (
            <div className="alert alert-error" role="alert" style={{ marginTop: "1.5rem" }}>
              {error}
            </div>
          )}

          <div className="form-actions">
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting && <span className="spinner" />}
              {submitting ? "Running valuation…" : "Submit"}
            </button>
            <span className="card-hint">Typically completes in a few seconds.</span>
          </div>
        </form>
      </div>
    </section>
  );
}
