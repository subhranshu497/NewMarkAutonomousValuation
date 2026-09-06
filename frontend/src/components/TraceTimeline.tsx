import type { TraceSpan } from "../types/valuation";

interface TraceTimelineProps {
  trace: TraceSpan[];
}

export function TraceTimeline({ trace }: TraceTimelineProps) {
  return (
    <ol className="timeline">
      {trace.map((span) => (
        <li className="timeline-item" key={`${span.step}-${span.started_at}`}>
          <div className="timeline-step">{span.step}</div>
          <div className="timeline-summary">{span.result_summary}</div>
          <div className="timeline-meta">
            {span.started_at} → {span.finished_at}
          </div>
        </li>
      ))}
    </ol>
  );
}
