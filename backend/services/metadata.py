from __future__ import annotations

from typing import Any

from models import VideoMetadata


def compute_engagement_rate(views: int | None, likes: int | None, comments: int | None) -> float | None:
    if views is None or views <= 0:
        return None
    likes_val = likes or 0
    comments_val = comments or 0
    return round(((likes_val + comments_val) / views) * 100, 4)


def normalize_count(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "").upper()
        if not cleaned:
            return None
        multiplier = 1
        if cleaned.endswith("K"):
            multiplier = 1_000
            cleaned = cleaned[:-1]
        elif cleaned.endswith("M"):
            multiplier = 1_000_000
            cleaned = cleaned[:-1]
        elif cleaned.endswith("B"):
            multiplier = 1_000_000_000
            cleaned = cleaned[:-1]
        try:
            return int(float(cleaned) * multiplier)
        except ValueError:
            return None
    return None


def build_video_metadata(
    *,
    video_id: str,
    url: str,
    title: str | None = None,
    creator: str | None = None,
    follower_count: int | None = None,
    views: int | None = None,
    likes: int | None = None,
    comments: int | None = None,
    hashtags: list[str] | None = None,
    upload_date: str | None = None,
    duration: float | None = None,
    thumbnail_url: str | None = None,
) -> VideoMetadata:
    views_norm = normalize_count(views)
    likes_norm = normalize_count(likes)
    comments_norm = normalize_count(comments)
    follower_norm = normalize_count(follower_count)

    return VideoMetadata(
        video_id=video_id,  # type: ignore[arg-type]
        url=url,
        title=title,
        creator=creator,
        follower_count=follower_norm,
        views=views_norm,
        likes=likes_norm,
        comments=comments_norm,
        hashtags=hashtags or [],
        upload_date=upload_date,
        duration=duration,
        thumbnail_url=thumbnail_url,
        engagement_rate=compute_engagement_rate(views_norm, likes_norm, comments_norm),
    )


def metadata_to_dict(metadata: VideoMetadata) -> dict[str, Any]:
    return metadata.model_dump()
