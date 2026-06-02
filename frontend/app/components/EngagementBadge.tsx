interface EngagementBadgeProps {
  rate?: number | null;
}

export default function EngagementBadge({ rate }: EngagementBadgeProps) {
  const tooltip =
    "Engagement rate = (likes + comments) / views × 100. Computed from available platform metrics; some counts may be hidden or estimated.";

  if (rate === null || rate === undefined) {
    return (
      <span
        title={tooltip}
        className="inline-flex cursor-help items-center rounded-full border border-border bg-surface-muted px-2.5 py-1 text-xs font-medium text-text-muted"
      >
        Engagement N/A
      </span>
    );
  }

  const color =
    rate >= 5
      ? "border-success/20 bg-success/10 text-success"
      : rate >= 2
        ? "border-warning/20 bg-warning/10 text-warning"
        : "border-danger/20 bg-danger/10 text-danger";

  return (
    <span
      title={tooltip}
      className={`metric-value inline-flex cursor-help items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${color}`}
    >
      {rate.toFixed(2)}%
    </span>
  );
}
