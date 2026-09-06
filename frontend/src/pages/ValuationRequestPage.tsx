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
      <h1>New Valuation Request</h1>
      <form onSubmit={handleSubmit}>
        <div>
          <label>
            Submarket
            <select value={submarketId} onChange={(e) => setSubmarketId(e.target.value)}>
              {SUBMARKETS.map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div>
          <label>
            Property type
            <input value={propertyType} onChange={(e) => setPropertyType(e.target.value)} />
          </label>
        </div>
        <div>
          <label>
            Space (SF)
            <input
              type="number"
              value={spaceSf}
              onChange={(e) => setSpaceSf(Number(e.target.value))}
              min={1}
            />
          </label>
        </div>
        <div>
          <label>
            Lease type
            <input value={leaseType} onChange={(e) => setLeaseType(e.target.value)} />
          </label>
        </div>
        <div>
          <label>
            Term (months)
            <input
              type="number"
              value={termMonths}
              onChange={(e) => setTermMonths(Number(e.target.value))}
              min={1}
            />
          </label>
        </div>
        <div>
          <label>
            Concessions assumed (optional)
            <input value={concessionsAssumed} onChange={(e) => setConcessionsAssumed(e.target.value)} />
          </label>
        </div>
        <div>
          <label>
            Requested by
            <input value={requestedBy} onChange={(e) => setRequestedBy(e.target.value)} />
          </label>
        </div>
        {error && <p role="alert">{error}</p>}
        <button type="submit" disabled={submitting}>
          {submitting ? "Running valuation..." : "Submit"}
        </button>
      </form>
    </section>
  );
}
