from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from apify_client import ApifyClient

from config import get_settings
from models import TranscriptSegment, VideoMetadata
from services.metadata import build_video_metadata, normalize_count
from services.transcript import chunk_transcript, extract_hashtags
from services.whisper_transcribe import transcribe_media_file
from services.ytdlp_utils import ytdlp_command


def _extract_shortcode(url: str) -> str:
    patterns = [
        r"instagram\.com/reel/([^/?#]+)",
        r"instagram\.com/p/([^/?#]+)",
        r"instagram\.com/reels/([^/?#]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError("Invalid Instagram Reel URL")


def _dataset_id_from_run(run: Any) -> str:
    if isinstance(run, dict):
        return run["defaultDatasetId"]
    dataset_id = getattr(run, "default_dataset_id", None)
    if dataset_id:
        return dataset_id
    raise ValueError("Could not resolve Apify dataset id from actor run")


def fetch_via_apify(url: str) -> tuple[VideoMetadata, list[TranscriptSegment], dict[str, Any]]:
    settings = get_settings()
    if not settings.apify_token:
        raise ValueError("APIFY_TOKEN not configured")

    client = ApifyClient(settings.apify_token)
    run = client.actor(settings.apify_actor_id).call(
        run_input={
            "directUrls": [url],
            "resultsType": "posts",
            "resultsLimit": 1,
        }
    )
    dataset_items = list(client.dataset(_dataset_id_from_run(run)).iterate_items())
    if not dataset_items:
        raise ValueError("Apify returned no data for Instagram URL")

    item = dataset_items[0]
    caption = item.get("caption") or item.get("text") or ""
    owner = item.get("ownerUsername") or item.get("owner") or item.get("username")
    if isinstance(owner, dict):
        owner = owner.get("username") or owner.get("full_name")

    follower_count = (
        item.get("ownerFollowersCount")
        or item.get("followersCount")
        or (item.get("owner") or {}).get("followersCount")
    )

    hashtags = item.get("hashtags") or extract_hashtags(caption)
    if isinstance(hashtags, str):
        hashtags = extract_hashtags(hashtags)

    metadata = build_video_metadata(
        video_id="B",
        url=url,
        title=caption[:120] if caption else "Instagram Reel",
        creator=owner,
        follower_count=follower_count,
        views=item.get("videoViewCount") or item.get("playCount") or item.get("viewCount"),
        likes=item.get("likesCount") or item.get("likeCount"),
        comments=item.get("commentsCount") or item.get("commentCount"),
        hashtags=[tag.lstrip("#") for tag in hashtags] if hashtags else extract_hashtags(caption),
        upload_date=item.get("timestamp") or item.get("takenAtTimestamp") or item.get("date"),
        duration=float(item.get("videoDuration") or item.get("duration") or 0) or None,
        thumbnail_url=item.get("displayUrl") or item.get("thumbnailUrl"),
    )

    segments = _segments_from_apify_item(item, caption, metadata.duration)
    return metadata, segments, item


def _segments_from_apify_item(
    item: dict[str, Any], caption: str, duration: float | None
) -> list[TranscriptSegment]:
    transcript = item.get("transcript") or item.get("subtitles")
    if isinstance(transcript, list) and transcript:
        segments: list[TranscriptSegment] = []
        for entry in transcript:
            text = entry.get("text") or entry.get("caption") or ""
            start = float(entry.get("start") or entry.get("startTime") or 0)
            end = float(entry.get("end") or entry.get("endTime") or start + 2)
            if text.strip():
                segments.append(TranscriptSegment(start_time=start, end_time=end, text=text.strip()))
        if segments:
            return segments

    if caption.strip():
        end_time = duration or 30.0
        return [TranscriptSegment(start_time=0.0, end_time=end_time, text=caption.strip())]
    return []


def fetch_via_whisper(url: str) -> tuple[VideoMetadata, list[TranscriptSegment], dict[str, Any]]:
    settings = get_settings()
    with tempfile.TemporaryDirectory() as tmpdir:
        output_template = str(Path(tmpdir) / "reel.%(ext)s")
        download_cmd = ytdlp_command(
            "-o",
            output_template,
            "--write-info-json",
            url,
        )
        result = subprocess.run(download_cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise ValueError(f"yt-dlp download failed: {result.stderr.strip()}")

        media_files = [p for p in Path(tmpdir).glob("*") if p.suffix.lower() in {".mp4", ".webm", ".mkv", ".mov"}]
        if not media_files:
            raise ValueError("Could not download Instagram reel media")

        info_files = list(Path(tmpdir).glob("*.info.json"))
        info = json.loads(info_files[0].read_text(encoding="utf-8")) if info_files else {}

        segments = transcribe_media_file(str(media_files[0]))

        description = info.get("description") or info.get("title") or ""
        metadata = build_video_metadata(
            video_id="B",
            url=url,
            title=description[:120] if description else "Instagram Reel",
            creator=info.get("uploader") or info.get("channel"),
            follower_count=info.get("follower_count") or info.get("channel_follower_count"),
            views=info.get("view_count") or info.get("play_count"),
            likes=info.get("like_count"),
            comments=info.get("comment_count"),
            hashtags=extract_hashtags(description),
            upload_date=info.get("upload_date"),
            duration=float(info.get("duration") or segments[-1].end_time),
            thumbnail_url=info.get("thumbnail"),
        )
        return metadata, segments, info


def ingest_instagram(url: str) -> tuple[VideoMetadata, list]:
    settings = get_settings()
    errors: list[str] = []
    clean_url = url.split("?")[0].rstrip("/")

    if settings.apify_token:
        try:
            metadata, segments, _ = fetch_via_apify(clean_url)
            if segments:
                chunks = chunk_transcript(segments, metadata)
                return metadata, chunks
            errors.append("Apify returned metadata but no transcript segments")
        except Exception as exc:
            errors.append(f"Apify failed: {exc}")

    try:
        metadata, segments, _ = fetch_via_whisper(clean_url)
        chunks = chunk_transcript(segments, metadata)
        return metadata, chunks
    except Exception as exc:
        errors.append(f"Whisper fallback failed: {exc}")
        raise ValueError("; ".join(errors)) from exc
