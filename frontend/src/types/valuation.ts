export interface LeaseAssumptions {
  lease_type: string;
  term_months: number;
  concessions_assumed: string | null;
}

export interface ValuationRequest {
  submarket_id: string;
  property_type: string;
  space_sf: number;
  lease_assumptions: LeaseAssumptions;
  requested_by: string;
}

export interface Comp {
  comp_id: string;
  address: string;
  submarket_id: string;
  sf: number;
  lease_type: string;
  asking_rent_psf: number;
  effective_rent_psf: number;
  lease_start_date: string;
  tenant_industry: string;
  concessions: string | null;
  source_system: string;
  last_verified_at: string;
}

export interface TimeSeriesPoint {
  period: string;
  value: number;
}

export interface TimeSeries {
  submarket_id: string;
  metric: string;
  points: TimeSeriesPoint[];
  yoy_change: number;
  percentile_rank: number;
}

export interface SummaryStats {
  median_asking_rent_psf: number;
  mean_asking_rent_psf: number;
  rent_spread: number;
  comp_count: number;
  comp_count_trailing_12mo: number;
}

export interface EvidenceBundle {
  summary_stats: SummaryStats;
  top_comps: Comp[];
  market_trend_deltas: TimeSeries[];
}

export interface ValuationResult {
  recommended_rent_psf: number;
  range_low: number;
  range_high: number;
  confidence: number;
  rationale_text: string;
  cited_comp_ids: string[];
  cited_market_stat_ids: string[];
  needs_human_review: boolean;
}

export interface TraceSpan {
  step: string;
  started_at: string;
  finished_at: string;
  params: Record<string, unknown>;
  result_summary: string;
}

export interface ValuationResponse {
  request_id: string;
  result: ValuationResult;
  trace: TraceSpan[];
}
