from __future__ import annotations

import shutil
import sys

# Helps yt-dlp on cloud/datacenter IPs (Render, AWS, etc.)
YOUTUBE_EXTRACTOR_ARGS = "youtube:player_client=android_vr,android,web"


def ytdlp_command(*args: str) -> list[str]:
    return [sys.executable, "-m", "yt_dlp", *args]


def _cloud_ytdlp_flags() -> list[str]:
    flags = ["--remote-components", "ejs:github"]
    if shutil.which("node"):
        flags.extend(["--js-runtimes", "node"])
    return flags


def ytdlp_youtube_command(*args: str) -> list[str]:
    return ytdlp_command(
        *_cloud_ytdlp_flags(),
        "--extractor-args",
        YOUTUBE_EXTRACTOR_ARGS,
        *args,
    )
