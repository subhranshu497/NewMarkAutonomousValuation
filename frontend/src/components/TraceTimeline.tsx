import type { TraceSpan } from "../types/valuation";

interface TraceTimelineProps {
  trace: TraceSpan[];
}

export function TraceTimeline({ trace }: TraceTimelineProps) {
  return (
    <ol>
      {trace.map((span) => (
        <li key={`${span.step}-${span.started_at}`}>
          {span.step}: {span.result_summary}
        </li>
      ))}
    </ol>
  );
}
