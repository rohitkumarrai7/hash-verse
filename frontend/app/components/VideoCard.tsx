import EngagementBadge from "./EngagementBadge";
import type { VideoMetadata } from "@/lib/types";

interface VideoCardProps {
  label: string;
  video?: VideoMetadata | null;
  loading?: boolean;
  highlighted?: boolean;
  highlightRange?: string | null;
}

function formatNumber(value?: number | null) {
  if (value === null || value === undefined) return "N/A";
  return new Intl.NumberFormat("en-US", { notation: "compact" }).format(value);
}

function formatDuration(seconds?: number | null) {
  if (!seconds) return "N/A";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

function getYoutubeEmbedUrl(url?: string | null) {
  if (!url) return null;
  const match = url.match(/(?:v=|youtu\.be\/|embed\/)([\w-]{11})/);
  return match ? `https://www.youtube.com/embed/${match[1]}` : null;
}

function getInstagramEmbedUrl(url?: string | null) {
  if (!url) return null;
  const match = url.match(/instagram\.com\/(?:reel|p)\/([^/?#]+)/i);
  return match ? `https://www.instagram.com/reel/${match[1]}/embed` : null;
}

function isYoutubeCard(label: string, url?: string | null) {
  return label.toLowerCase().includes("youtube") || Boolean(url && url.includes("youtube"));
}

export default function VideoCard({
  label,
  video,
  loading,
  highlighted,
  highlightRange,
}: VideoCardProps) {
  if (loading) {
    return (
      <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm animate-pulse">
        <div className="mb-3 h-4 w-24 rounded bg-zinc-200" />
        <div className="mb-4 aspect-video rounded-lg bg-zinc-200" />
        <div className="space-y-2">
          <div className="h-4 w-full rounded bg-zinc-200" />
          <div className="h-4 w-2/3 rounded bg-zinc-200" />
          <div className="h-4 w-1/2 rounded bg-zinc-200" />
        </div>
      </div>
    );
  }

  const youtubeEmbed = isYoutubeCard(label, video?.url) ? getYoutubeEmbedUrl(video?.url) : null;
  const instagramEmbed = !youtubeEmbed ? getInstagramEmbedUrl(video?.url) : null;

  return (
    <div
      id={`video-card-${(video?.video_id || label.split(" ")[1] || "x").toLowerCase()}`}
      className={`rounded-xl border bg-white p-4 shadow-sm transition ring-offset-2 ${
        highlighted ? "border-indigo-500 ring-2 ring-indigo-300" : "border-zinc-200"
      }`}
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">{label}</h2>
        <EngagementBadge rate={video?.engagement_rate} />
      </div>

      {youtubeEmbed ? (
        <div className="mb-4 aspect-video overflow-hidden rounded-lg bg-black">
          <iframe
            src={youtubeEmbed}
            title={video?.title || label}
            className="h-full w-full"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        </div>
      ) : instagramEmbed ? (
        <div className="mb-4 aspect-[4/5] max-h-[420px] overflow-hidden rounded-lg bg-zinc-100">
          <iframe
            src={instagramEmbed}
            title={video?.title || label}
            className="h-full w-full border-0"
            allowFullScreen
          />
        </div>
      ) : video?.thumbnail_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={video.thumbnail_url}
          alt={video.title || label}
          loading="lazy"
          className="mb-4 aspect-video w-full rounded-lg object-cover"
        />
      ) : (
        <div className="mb-4 flex aspect-video items-center justify-center rounded-lg bg-zinc-100 text-sm text-zinc-500">
          No preview available
        </div>
      )}

      <h3 className="mb-2 line-clamp-2 text-base font-semibold text-zinc-900">
        {video?.title || "Waiting for ingestion..."}
      </h3>

      <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-sm text-zinc-700">
        <div>
          <dt className="text-zinc-500">Creator</dt>
          <dd className="font-medium">{video?.creator || "N/A"}</dd>
        </div>
        <div>
          <dt className="text-zinc-500">Followers</dt>
          <dd className="font-medium">{formatNumber(video?.follower_count)}</dd>
        </div>
        <div>
          <dt className="text-zinc-500">Views</dt>
          <dd className="font-medium">{formatNumber(video?.views)}</dd>
        </div>
        <div>
          <dt className="text-zinc-500">Likes</dt>
          <dd className="font-medium">{formatNumber(video?.likes)}</dd>
        </div>
        <div>
          <dt className="text-zinc-500">Comments</dt>
          <dd className="font-medium">{formatNumber(video?.comments)}</dd>
        </div>
        <div>
          <dt className="text-zinc-500">Duration</dt>
          <dd className="font-medium">{formatDuration(video?.duration)}</dd>
        </div>
        <div className="col-span-2">
          <dt className="text-zinc-500">Upload date</dt>
          <dd className="font-medium">{video?.upload_date || "N/A"}</dd>
        </div>
      </dl>

      {video?.hashtags && video.hashtags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {video.hashtags.slice(0, 8).map((tag) => (
            <span
              key={tag}
              className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700"
            >
              #{tag}
            </span>
          ))}
        </div>
      )}

      {highlighted && highlightRange && (
        <p className="mt-3 rounded-md bg-indigo-50 px-2 py-1 text-xs font-medium text-indigo-700">
          Cited segment: {highlightRange}
        </p>
      )}
    </div>
  );
}
