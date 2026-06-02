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
        className="inline-flex cursor-help items-center rounded-full bg-zinc-200 px-2 py-1 text-xs font-medium text-zinc-700"
      >
        Engagement N/A
      </span>
    );
  }

  const color =
    rate >= 5
      ? "bg-emerald-100 text-emerald-800"
      : rate >= 2
        ? "bg-amber-100 text-amber-800"
        : "bg-rose-100 text-rose-800";

  return (
    <span
      title={tooltip}
      className={`inline-flex cursor-help items-center rounded-full px-2 py-1 text-xs font-semibold ${color}`}
    >
      {rate.toFixed(2)}% engagement
    </span>
  );
}
