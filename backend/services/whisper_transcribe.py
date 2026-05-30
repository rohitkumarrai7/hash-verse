from __future__ import annotations

import logging
import re
import subprocess
import tempfile
from pathlib import Path

from config import get_settings
from models import TranscriptSegment
from services.ytdlp_utils import ytdlp_command

logger = logging.getLogger(__name__)


def transcribe_media_file(media_path: str) -> list[TranscriptSegment]:
    settings = get_settings()
    from faster_whisper import WhisperModel

    logger.info("Transcribing with faster-whisper model=%s", settings.whisper_model)
    model = WhisperModel(settings.whisper_model, device="cpu", compute_type="int8")
    segments_iter, _ = model.transcribe(media_path, word_timestamps=False)

    segments: list[TranscriptSegment] = []
    for seg in segments_iter:
        text = seg.text.strip()
        if not text:
            continue
        segments.append(
            TranscriptSegment(
                start_time=float(seg.start),
                end_time=float(seg.end),
                text=text,
            )
        )

    if not segments:
        raise ValueError("Whisper returned no transcript segments")
    return segments


def transcribe_url_with_ytdlp(url: str, output_stem: str = "media") -> list[TranscriptSegment]:
    settings = get_settings()
    with tempfile.TemporaryDirectory() as tmpdir:
        output_template = str(Path(tmpdir) / f"{output_stem}.%(ext)s")
        cmd = ytdlp_command(
            "-o",
            output_template,
            "-f",
            "bestaudio/best",
            "--extract-audio",
            "--audio-format",
            "mp3",
            url,
        )
        if settings.ytdlp_cookies_from_browser:
            cmd = ytdlp_command(
                "--cookies-from-browser",
                settings.ytdlp_cookies_from_browser,
                "-o",
                output_template,
                "-f",
                "bestaudio/best",
                "--extract-audio",
                "--audio-format",
                "mp3",
                url,
            )

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise ValueError(f"yt-dlp audio download failed: {result.stderr.strip() or result.stdout.strip()}")

        media_files = [
            p
            for p in Path(tmpdir).glob("*")
            if p.suffix.lower() in {".mp3", ".mp4", ".webm", ".mkv", ".m4a", ".wav"}
        ]
        if not media_files:
            raise ValueError("Could not download audio for Whisper transcription")

        return transcribe_media_file(str(media_files[0]))


def parse_srt(content: str) -> list[TranscriptSegment]:
    blocks = re.split(r"\n\s*\n", content.strip())
    segments: list[TranscriptSegment] = []

    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 2:
            continue
        time_line = lines[1] if "-->" in lines[1] else lines[0]
        text_lines = lines[2:] if "-->" in lines[1] else lines[1:]
        if "-->" not in time_line:
            continue
        start_raw, end_raw = [part.strip() for part in time_line.split("-->")]

        def to_seconds(raw: str) -> float:
            raw = raw.replace(",", ".")
            parts = raw.split(":")
            if len(parts) == 3:
                h, m, s = parts
                return int(h) * 3600 + int(m) * 60 + float(s)
            if len(parts) == 2:
                m, s = parts
                return int(m) * 60 + float(s)
            return float(parts[0])

        text = " ".join(line.strip() for line in text_lines).strip()
        if not text:
            continue
        segments.append(
            TranscriptSegment(
                start_time=to_seconds(start_raw),
                end_time=to_seconds(end_raw),
                text=text,
            )
        )

    return segments
