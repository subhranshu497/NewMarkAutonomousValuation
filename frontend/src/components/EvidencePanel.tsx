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
      <h4 className="section-title">Summary Stats</h4>
      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Median $/PSF</div>
          <div className="stat-value">${evidence.summary_stats.median_asking_rent_psf}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Mean $/PSF</div>
          <div className="stat-value">${evidence.summary_stats.mean_asking_rent_psf}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Spread</div>
          <div className="stat-value">${evidence.summary_stats.rent_spread}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Comp count</div>
          <div className="stat-value">{evidence.summary_stats.comp_count}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Trailing 12mo</div>
          <div className="stat-value">{evidence.summary_stats.comp_count_trailing_12mo}</div>
        </div>
      </div>

      <h4 className="section-title">Comps ({evidence.top_comps.length})</h4>
      <div className="table-wrap" style={{ marginBottom: "1.5rem" }}>
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
                <td>{citedComps.has(comp.comp_id) && <span className="cell-check">✓</span>}</td>
                <td className="cell-mono">{comp.comp_id}</td>
                <td>{comp.address}</td>
                <td>{comp.sf.toLocaleString()}</td>
                <td className="cell-muted">{comp.lease_start_date}</td>
                <td>${comp.asking_rent_psf}</td>
                <td>${comp.effective_rent_psf}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h4 className="section-title">Market Trends</h4>
      <div className="trend-list">
        {evidence.market_trend_deltas.map((series) => {
          const id = `${series.submarket_id}_${series.metric}`;
          const isCited = citedMarketStatIds.includes(id);
          const isPositive = series.yoy_change >= 0;
          return (
            <div className="trend-item" key={id}>
              <span className="trend-metric">
                {isCited && <span className="cell-check">✓</span>}
                {series.metric}
              </span>
              <span className="trend-figures">
                <span className={`trend-change ${isPositive ? "positive" : "negative"}`}>
                  {isPositive ? "+" : ""}
                  {(series.yoy_change * 100).toFixed(1)}% YoY
                </span>
                <span>Percentile {(series.percentile_rank * 100).toFixed(0)}</span>
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
