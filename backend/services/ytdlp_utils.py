from __future__ import annotations

import sys

# Helps yt-dlp on cloud/datacenter IPs (Render, AWS, etc.)
YOUTUBE_EXTRACTOR_ARGS = "youtube:player_client=android,web"


def ytdlp_command(*args: str) -> list[str]:
    return [sys.executable, "-m", "yt_dlp", *args]


def ytdlp_youtube_command(*args: str) -> list[str]:
    return ytdlp_command("--extractor-args", YOUTUBE_EXTRACTOR_ARGS, *args)
