import type { SourceCitation } from "@/lib/types";

interface SourceBadgeProps {
  source: SourceCitation;
  onClick?: (source: SourceCitation) => void;
}

export default function SourceBadge({ source, onClick }: SourceBadgeProps) {
  const dotClass = source.video_id === "A" ? "bg-youtube" : "bg-instagram";

  return (
    <button
      type="button"
      onClick={() => onClick?.(source)}
      className="inline-flex items-center gap-1.5 rounded-full border border-accent/25 bg-surface px-2.5 py-1 text-xs font-medium text-accent transition hover:border-accent hover:bg-accent-light"
    >
      <span className={`inline-block h-1.5 w-1.5 rounded-full ${dotClass}`} />
      Video {source.video_id} · Chunk {source.chunk_index} · {source.time_range}
    </button>
  );
}
