interface ConfidenceBadgeProps {
  confidence: number;
  needsHumanReview: boolean;
}

export function ConfidenceBadge({ confidence, needsHumanReview }: ConfidenceBadgeProps) {
  const tier = confidence >= 0.8 ? "success" : confidence >= 0.5 ? "warning" : "danger";

  return (
    <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
      <span className={`badge badge-${tier}`}>
        <span className="badge-dot" />
        Confidence {(confidence * 100).toFixed(0)}%
      </span>
      {needsHumanReview && <span className="badge badge-warning">Needs human review</span>}
    </div>
  );
}
