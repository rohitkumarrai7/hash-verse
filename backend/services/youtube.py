from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

import httpx
from apify_client import ApifyClient
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
TRANSCRIPT_AI_BASE = "https://youtube-transcript.ai/transcript"

APIFY_AUTH_HINT = (
    "Apify token invalid or missing on the server. In Render → hashverse-api → Environment, "
    "set APIFY_TOKEN to your key from https://console.apify.com/account/integrations"
)


def is_cloud_host() -> bool:
    return bool(os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID"))


def _format_apify_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if (
        "token is not valid" in msg
        or "user was not found" in msg
        or "unauthorized" in msg
        or "header value" in msg
        and "bearer" in msg
    ):
        return APIFY_AUTH_HINT
    return str(exc)


def _parse_transcript_ai_markdown(text: str) -> list[TranscriptSegment]:
    pattern = re.compile(r"\[(\d+):(\d{2})\]\s*([^[\n]+)")
    matches = list(pattern.finditer(text))
    segments: list[TranscriptSegment] = []

    for index, match in enumerate(matches):
        start = int(match.group(1)) * 60 + int(match.group(2))
        content = match.group(3).strip()
        if not content:
            continue
        end = float(start + 5)
        if index + 1 < len(matches):
            next_match = matches[index + 1]
            end = float(int(next_match.group(1)) * 60 + int(next_match.group(2)))
        segments.append(
            TranscriptSegment(start_time=float(start), end_time=end, text=content)
        )

    return segments


def _fetch_via_transcript_ai_service(video_id: str) -> list[TranscriptSegment]:
    """Free cloud-friendly fallback — no API key (youtube-transcript.ai)."""
    lang_attempts = ["en", "hi", None]
    last_error = "no response"

    for lang in lang_attempts:
        url = f"{TRANSCRIPT_AI_BASE}/{video_id}.txt"
        if lang:
            url = f"{url}?lang={lang}"
        try:
            response = httpx.get(url, timeout=30.0, follow_redirects=True)
            if response.status_code != 200:
                last_error = f"HTTP {response.status_code}"
                continue
            segments = _parse_transcript_ai_markdown(response.text)
            if segments:
                logger.info(
                    "YouTube transcript fetched via youtube-transcript.ai (%s segments, lang=%s)",
                    len(segments),
                    lang or "auto",
                )
                return segments
            last_error = "empty transcript"
        except Exception as exc:
            last_error = str(exc)

    raise ValueError(f"youtube-transcript.ai failed: {last_error}")


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


def _dataset_id_from_run(run) -> str:
    if isinstance(run, dict):
        return run["defaultDatasetId"]
    dataset_id = getattr(run, "default_dataset_id", None)
    if dataset_id:
        return dataset_id
    raise ValueError("Could not resolve Apify dataset id from actor run")


def _segments_from_apify_item(item: dict) -> list[TranscriptSegment]:
    rows = item.get("data") or item.get("transcript") or []
    segments: list[TranscriptSegment] = []
    for row in rows:
        text = (row.get("text") or "").strip()
        if not text:
            continue
        start = float(row.get("start") or row.get("startTime") or 0)
        duration = float(row.get("dur") or row.get("duration") or 0)
        segments.append(
            TranscriptSegment(
                start_time=start,
                end_time=start + duration,
                text=text,
            )
        )
    return segments


def _fetch_via_apify(url: str) -> list[TranscriptSegment]:
    settings = get_settings()
    if not settings.apify_token:
        raise ValueError(APIFY_AUTH_HINT)

    try:
        client = ApifyClient(settings.apify_token)
        run = client.actor(settings.apify_youtube_actor_id).call(run_input={"videoUrl": url})
    except Exception as exc:
        raise ValueError(_format_apify_error(exc)) from exc
    items = list(client.dataset(_dataset_id_from_run(run)).iterate_items())
    if not items:
        raise ValueError("Apify returned no YouTube transcript data")

    for item in items:
        segments = _segments_from_apify_item(item)
        if segments:
            logger.info("YouTube transcript fetched via Apify (%s segments)", len(segments))
            return segments

    raise ValueError("Apify returned empty YouTube transcript")


def fetch_transcript(url: str) -> list[TranscriptSegment]:
    video_id = _extract_video_id(url)
    settings = get_settings()
    errors: list[str] = []

    strategies: list[tuple[str, Callable[[], list[TranscriptSegment]]]] = []

    if is_cloud_host():
        # Render IPs are blocked by YouTube — use keyless edge service first
        strategies.append(
            ("youtube-transcript.ai", lambda: _fetch_via_transcript_ai_service(video_id))
        )

    strategies.extend(
        [
            ("yt-dlp subs", lambda: _fetch_transcript_ytdlp(url)),
            ("transcript API", lambda: _fetch_via_transcript_api(video_id)),
        ]
    )

    if settings.apify_token:
        strategies.append(("apify", lambda: _fetch_via_apify(url)))

    if not is_cloud_host():
        strategies.append(("whisper", lambda: transcribe_url_with_ytdlp(url, output_stem="youtube")))

    apify_auth_failed = False
    for name, attempt in strategies:
        if apify_auth_failed and name == "apify":
            continue
        try:
            logger.info("Trying YouTube transcript via %s", name)
            return attempt()
        except Exception as exc:
            detail = _format_apify_error(exc) if name == "apify" else str(exc)
            errors.append(f"{name}: {detail}")
            if name == "apify" and detail == APIFY_AUTH_HINT:
                apify_auth_failed = True

    if is_cloud_host() and not settings.apify_token:
        errors.insert(0, f"apify: {APIFY_AUTH_HINT}")

    raise ValueError("; ".join(errors))


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
