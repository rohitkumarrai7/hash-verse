import type { SourceCitation } from "@/lib/types";

interface SourceBadgeProps {
  source: SourceCitation;
  onClick?: (source: SourceCitation) => void;
}

export default function SourceBadge({ source, onClick }: SourceBadgeProps) {
  return (
    <button
      type="button"
      onClick={() => onClick?.(source)}
      className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
    >
      Video {source.video_id} · Chunk {source.chunk_index} · {source.time_range}
    </button>
  );
}
