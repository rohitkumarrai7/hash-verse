import EngagementBadge from "./EngagementBadge";
import type { VideoMetadata } from "@/lib/types";

interface VideoCardProps {
  label: string;
  platform: "youtube" | "instagram";
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

export default function VideoCard({
  label,
  platform,
  video,
  loading,
  highlighted,
  highlightRange,
}: VideoCardProps) {
  const platformClass = platform === "youtube" ? "platform-youtube" : "platform-instagram";
  const platformLabel = platform === "youtube" ? "YouTube" : "Reels";
  const platformBadgeClass =
    platform === "youtube"
      ? "bg-youtube/10 text-youtube"
      : "bg-instagram/10 text-instagram";

  if (loading) {
    return (
      <div className={`card animate-pulse p-4 ${platformClass}`}>
        <div className="mb-3 h-4 w-24 rounded bg-surface-muted" />
        <div className="mb-4 aspect-video rounded-lg bg-surface-muted" />
        <div className="space-y-2">
          <div className="h-4 w-full rounded bg-surface-muted" />
          <div className="h-4 w-2/3 rounded bg-surface-muted" />
          <div className="h-4 w-1/2 rounded bg-surface-muted" />
        </div>
      </div>
    );
  }

  const youtubeEmbed = platform === "youtube" ? getYoutubeEmbedUrl(video?.url) : null;
  const instagramEmbed = platform === "instagram" ? getInstagramEmbedUrl(video?.url) : null;

  return (
    <div
      id={`video-card-${(video?.video_id || label.split(" ")[1] || "x").toLowerCase()}`}
      className={`card p-4 transition ${platformClass} ${
        highlighted ? "ring-2 ring-accent ring-offset-2 ring-offset-background" : ""
      }`}
    >
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${platformBadgeClass}`}>
              {platformLabel}
            </span>
            <h2 className="text-xs font-semibold uppercase tracking-wide text-text-muted">{label}</h2>
          </div>
        </div>
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
        <div className="mb-4 aspect-[4/5] max-h-[420px] overflow-hidden rounded-lg bg-surface-muted">
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
        <div className="mb-4 flex aspect-video items-center justify-center rounded-lg bg-surface-muted text-sm text-text-muted">
          No preview available
        </div>
      )}

      <h3 className="mb-3 line-clamp-2 text-base font-semibold leading-snug text-foreground">
        {video?.title || "Waiting for ingestion..."}
      </h3>

      <dl className="grid grid-cols-2 gap-x-3 gap-y-3 text-sm">
        <div>
          <dt className="text-xs uppercase tracking-wide text-text-muted">Creator</dt>
          <dd className="mt-0.5 font-medium text-foreground">{video?.creator || "N/A"}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-text-muted">Followers</dt>
          <dd className="metric-value mt-0.5 font-medium text-foreground">
            {formatNumber(video?.follower_count)}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-text-muted">Views</dt>
          <dd className="metric-value mt-0.5 font-medium text-foreground">{formatNumber(video?.views)}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-text-muted">Likes</dt>
          <dd className="metric-value mt-0.5 font-medium text-foreground">{formatNumber(video?.likes)}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-text-muted">Comments</dt>
          <dd className="metric-value mt-0.5 font-medium text-foreground">{formatNumber(video?.comments)}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-text-muted">Duration</dt>
          <dd className="metric-value mt-0.5 font-medium text-foreground">
            {formatDuration(video?.duration)}
          </dd>
        </div>
        <div className="col-span-2">
          <dt className="text-xs uppercase tracking-wide text-text-muted">Upload date</dt>
          <dd className="mt-0.5 font-medium text-foreground">{video?.upload_date || "N/A"}</dd>
        </div>
      </dl>

      {video?.hashtags && video.hashtags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {video.hashtags.slice(0, 8).map((tag) => (
            <span
              key={tag}
              className="rounded-full border border-border bg-surface-muted px-2 py-0.5 text-xs font-medium text-text-muted"
            >
              #{tag}
            </span>
          ))}
        </div>
      )}

      {highlighted && highlightRange && (
        <p className="mt-3 rounded-md border border-accent/20 bg-accent-light px-2.5 py-1.5 text-xs font-medium text-accent">
          Cited segment: {highlightRange}
        </p>
      )}
    </div>
  );
}
