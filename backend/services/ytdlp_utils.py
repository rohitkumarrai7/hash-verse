from __future__ import annotations

import sys


def ytdlp_command(*args: str) -> list[str]:
    return [sys.executable, "-m", "yt_dlp", *args]
