from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path

import httpx
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled

from config import get_settings
from models import TranscriptSegment, VideoMetadata
from services.metadata import build_video_metadata
from services.transcript import chunk_transcript, extract_hashtags
from services.whisper_transcribe import parse_srt, transcribe_url_with_ytdlp
from services.ytdlp_utils import ytdlp_command, ytdlp_youtube_command

logger = logging.getLogger(__name__)

PREFERRED_LANGUAGES = ["en", "en-US", "en-GB", "en-IN", "hi", "hi-IN", "es", "fr", "de"]


def _extract_video_id(url: str) -> str:
    if "youtu.be/" in url:
        return url.split("youtu.be/")[-1].split("?")[0]
    if "v=" in url:
        return url.split("v=")[-1].split("&")[0]
    if "/shorts/" in url:
        return url.split("/shorts/")[-1].split("?")[0]
    raise ValueError("Invalid YouTube URL")


def _segments_from_fetched(transcript_data) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    for snippet in transcript_data:
        text = snippet.text.strip()
        if not text:
            continue
        start = float(snippet.start)
        duration = float(getattr(snippet, "duration", 0) or 0)
        segments.append(
            TranscriptSegment(
                start_time=start,
                end_time=start + duration,
                text=text,
            )
        )
    return segments


def _fetch_via_transcript_api(video_id: str) -> list[TranscriptSegment]:
    api = YouTubeTranscriptApi()
    transcript_list = api.list(video_id)

    attempts = [
        lambda: transcript_list.find_transcript(PREFERRED_LANGUAGES),
        lambda: transcript_list.find_generated_transcript(PREFERRED_LANGUAGES),
        lambda: transcript_list.find_manually_created_transcript(PREFERRED_LANGUAGES),
    ]

    for attempt in attempts:
        try:
            transcript = attempt()
            segments = _segments_from_fetched(transcript.fetch())
            if segments:
                logger.info("YouTube transcript fetched via API (%s)", transcript.language_code)
                return segments
        except NoTranscriptFound:
            continue

    for transcript in transcript_list:
        segments = _segments_from_fetched(transcript.fetch())
        if segments:
            logger.info("YouTube transcript fetched via API fallback language (%s)", transcript.language_code)
            return segments

    raise NoTranscriptFound(video_id, PREFERRED_LANGUAGES, transcript_list)


def _parse_json3(path: Path) -> list[TranscriptSegment]:
    data = json.loads(path.read_text(encoding="utf-8"))
    segments: list[TranscriptSegment] = []
    for event in data.get("events", []):
        start_ms = event.get("tStartMs")
        duration_ms = event.get("dDurationMs", 0)
        segs = event.get("segs") or []
        text = "".join(seg.get("utf8", "") for seg in segs).strip()
        if start_ms is None or not text:
            continue
        start = start_ms / 1000.0
        end = start + (duration_ms / 1000.0)
        segments.append(TranscriptSegment(start_time=start, end_time=end, text=text))
    return segments


def _fetch_transcript_ytdlp(url: str) -> list[TranscriptSegment]:
    settings = get_settings()
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "subs"
        sub_langs = "en.*,hi.*,a.en,a.hi,en-orig"
        cmd = ytdlp_youtube_command(
            "--skip-download",
            "--write-auto-sub",
            "--write-sub",
            "--sub-langs",
            sub_langs,
            "--sub-format",
            "json3/srt/best",
            "-o",
            str(output_path),
            url,
        )
        if settings.ytdlp_cookies_from_browser:
            cmd = ytdlp_youtube_command(
                "--cookies-from-browser",
                settings.ytdlp_cookies_from_browser,
                "--skip-download",
                "--write-auto-sub",
                "--write-sub",
                "--sub-langs",
                sub_langs,
                "--sub-format",
                "json3/srt/best",
                "-o",
                str(output_path),
                url,
            )

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            logger.warning("yt-dlp subtitle download stderr: %s", result.stderr.strip())

        for pattern in ("*.srt", "*.json3", "*.vtt"):
            for file_path in Path(tmpdir).glob(pattern):
                if file_path.suffix.lower() == ".json3":
                    segments = _parse_json3(file_path)
                else:
                    segments = parse_srt(file_path.read_text(encoding="utf-8", errors="ignore"))
                if segments:
                    logger.info("YouTube transcript fetched via yt-dlp (%s)", file_path.name)
                    return segments

        raise ValueError("Could not fetch YouTube transcript via yt-dlp subtitles")


def fetch_transcript(url: str) -> list[TranscriptSegment]:
    video_id = _extract_video_id(url)
    errors: list[str] = []

    # yt-dlp first — more reliable for Shorts and cloud server IPs
    try:
        return _fetch_transcript_ytdlp(url)
    except Exception as exc:
        errors.append(f"yt-dlp subs: {exc}")

    try:
        return _fetch_via_transcript_api(video_id)
    except (NoTranscriptFound, TranscriptsDisabled) as exc:
        errors.append(f"transcript API: {exc}")
    except Exception as exc:
        errors.append(f"transcript API: {exc}")

    try:
        logger.info("Falling back to Whisper for YouTube URL")
        return transcribe_url_with_ytdlp(url, output_stem="youtube")
    except Exception as exc:
        errors.append(f"whisper: {exc}")
        raise ValueError("; ".join(errors)) from exc


def _fetch_oembed(url: str) -> dict:
    response = httpx.get(
        "https://www.youtube.com/oembed",
        params={"url": url, "format": "json"},
        timeout=20.0,
    )
    response.raise_for_status()
    return response.json()


def fetch_metadata(url: str) -> dict:
    settings = get_settings()
    cmd = ytdlp_youtube_command("--dump-json", "--no-download", url)
    if settings.ytdlp_cookies_from_browser:
        cmd = ytdlp_youtube_command(
            "--cookies-from-browser",
            settings.ytdlp_cookies_from_browser,
            "--dump-json",
            "--no-download",
            url,
        )

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode == 0 and result.stdout.strip():
        return json.loads(result.stdout)

    oembed = _fetch_oembed(url)
    return {
        "title": oembed.get("title"),
        "channel": oembed.get("author_name"),
        "uploader": oembed.get("author_name"),
        "thumbnail": oembed.get("thumbnail_url"),
        "duration": None,
        "view_count": None,
        "like_count": None,
        "comment_count": None,
        "channel_follower_count": None,
        "description": "",
        "tags": [],
        "upload_date": None,
        "_metadata_source": "oembed_fallback",
    }


def ingest_youtube(url: str) -> tuple[VideoMetadata, list]:
    transcript = fetch_transcript(url)
    info = fetch_metadata(url)

    if not info.get("duration") and transcript:
        info["duration"] = transcript[-1].end_time

    description = info.get("description") or ""
    tags = info.get("tags") or []
    hashtags = extract_hashtags(description) + [tag.lstrip("#") for tag in tags if tag.startswith("#")]

    metadata = build_video_metadata(
        video_id="A",
        url=url,
        title=info.get("title"),
        creator=info.get("channel") or info.get("uploader"),
        follower_count=info.get("channel_follower_count") or info.get("subscriber_count"),
        views=info.get("view_count"),
        likes=info.get("like_count"),
        comments=info.get("comment_count"),
        hashtags=list(dict.fromkeys(hashtags)),
        upload_date=info.get("upload_date"),
        duration=float(info.get("duration") or 0) or None,
        thumbnail_url=info.get("thumbnail"),
    )

    chunks = chunk_transcript(transcript, metadata)
    return metadata, chunks
