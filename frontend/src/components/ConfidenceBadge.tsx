interface ConfidenceBadgeProps {
  confidence: number;
  needsHumanReview: boolean;
}

export function ConfidenceBadge({ confidence, needsHumanReview }: ConfidenceBadgeProps) {
  return (
    <span>
      Confidence: {(confidence * 100).toFixed(0)}%{needsHumanReview ? " — needs review" : ""}
    </span>
  );
}
