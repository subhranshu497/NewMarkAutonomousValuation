import type { EvidenceBundle } from "../types/valuation";

interface EvidencePanelProps {
  evidence: EvidenceBundle;
  citedCompIds: string[];
  citedMarketStatIds: string[];
}

export function EvidencePanel({ evidence, citedCompIds, citedMarketStatIds }: EvidencePanelProps) {
  const citedComps = new Set(citedCompIds);

  return (
    <div>
      <h3>Summary Stats</h3>
      <ul>
        <li>Median asking $/PSF: {evidence.summary_stats.median_asking_rent_psf}</li>
        <li>Mean asking $/PSF: {evidence.summary_stats.mean_asking_rent_psf}</li>
        <li>Spread: {evidence.summary_stats.rent_spread}</li>
        <li>Comp count: {evidence.summary_stats.comp_count}</li>
        <li>Trailing 12mo comp count: {evidence.summary_stats.comp_count_trailing_12mo}</li>
      </ul>

      <h3>Comps ({evidence.top_comps.length})</h3>
      <table>
        <thead>
          <tr>
            <th>Cited</th>
            <th>Comp ID</th>
            <th>Address</th>
            <th>SF</th>
            <th>Lease start</th>
            <th>Asking $/PSF</th>
            <th>Effective $/PSF</th>
          </tr>
        </thead>
        <tbody>
          {evidence.top_comps.map((comp) => (
            <tr key={comp.comp_id}>
              <td>{citedComps.has(comp.comp_id) ? "✓" : ""}</td>
              <td>{comp.comp_id}</td>
              <td>{comp.address}</td>
              <td>{comp.sf.toLocaleString()}</td>
              <td>{comp.lease_start_date}</td>
              <td>{comp.asking_rent_psf}</td>
              <td>{comp.effective_rent_psf}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Market Trends</h3>
      <ul>
        {evidence.market_trend_deltas.map((series) => {
          const id = `${series.submarket_id}_${series.metric}`;
          return (
            <li key={id}>
              {citedMarketStatIds.includes(id) ? "✓ " : ""}
              {series.metric}: YoY {(series.yoy_change * 100).toFixed(1)}% (percentile {(series.percentile_rank * 100).toFixed(0)})
            </li>
          );
        })}
      </ul>
    </div>
  );
}
