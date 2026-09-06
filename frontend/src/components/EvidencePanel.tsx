import type { EvidenceBundle } from "../types/valuation";

interface EvidencePanelProps {
  evidence: EvidenceBundle;
}

export function EvidencePanel({ evidence }: EvidencePanelProps) {
  return (
    <div>
      <p>{evidence.top_comps.length} comps, {evidence.market_trend_deltas.length} market stat series</p>
    </div>
  );
}
