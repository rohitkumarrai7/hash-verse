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


def _require_faster_whisper():
    try:
        from faster_whisper import WhisperModel

        return WhisperModel
    except ImportError as exc:
        raise ImportError(
            "faster-whisper is not installed. On cloud hosts (Render 512MB), use Apify for "
            "Instagram and youtube-transcript-api for YouTube. Install locally with: "
            "pip install faster-whisper"
        ) from exc


def transcribe_media_file(media_path: str) -> list[TranscriptSegment]:
    settings = get_settings()
    WhisperModel = _require_faster_whisper()

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


def parse_srt(srt_text: str) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    blocks = re.split(r"\n\s*\n", srt_text.strip())
    time_re = re.compile(
        r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
    )

    def to_seconds(h: str, m: str, s: str, ms: str) -> float:
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        match = time_re.search(lines[1] if "-->" in lines[1] else lines[0])
        if not match:
            continue
        start = to_seconds(*match.groups()[:4])
        end = to_seconds(*match.groups()[4:])
        text_lines = lines[2:] if "-->" in lines[1] else lines[1:]
        text = " ".join(text_lines).strip()
        if text:
            segments.append(TranscriptSegment(start_time=start, end_time=end, text=text))

    return segments


def transcribe_url_with_ytdlp(url: str, output_stem: str = "audio") -> list[TranscriptSegment]:
    with tempfile.TemporaryDirectory() as tmpdir:
        output_base = str(Path(tmpdir) / output_stem)
        cmd = ytdlp_command(
            "-x",
            "--audio-format",
            "wav",
            "--audio-quality",
            "0",
            "-o",
            output_base,
            url,
        )
        subprocess.run(cmd, check=True, capture_output=True, text=True)

        wav_files = list(Path(tmpdir).glob("*.wav"))
        if not wav_files:
            raise ValueError("yt-dlp did not produce an audio file for Whisper")

        return transcribe_media_file(str(wav_files[0]))
