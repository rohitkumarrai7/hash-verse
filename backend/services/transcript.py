from __future__ import annotations

import re
from dataclasses import dataclass

import tiktoken

from config import get_settings
from models import ChunkPayload, TranscriptSegment, VideoMetadata


@dataclass
class RawSegment:
    start_time: float
    end_time: float
    text: str


def format_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_time_range(start_time: float, end_time: float) -> str:
    return f"{format_time(start_time)}-{format_time(end_time)}"


def normalize_segments(segments: list[TranscriptSegment] | list[RawSegment]) -> list[RawSegment]:
    normalized: list[RawSegment] = []
    for segment in segments:
        if isinstance(segment, TranscriptSegment):
            text = segment.text.strip()
            if not text:
                continue
            normalized.append(RawSegment(segment.start_time, segment.end_time, text))
        else:
            text = segment.text.strip()
            if not text:
                continue
            normalized.append(segment)
    return normalized


def _get_encoder():
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


def _count_tokens(text: str) -> int:
    encoder = _get_encoder()
    if encoder is None:
        return len(text.split())
    return len(encoder.encode(text))


SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def _find_sentence_split_index(text: str, min_ratio: float = 0.65) -> int | None:
    if not text:
        return None

    min_chars = max(40, int(len(text) * min_ratio))
    matches = list(SENTENCE_BOUNDARY.finditer(text))
    if not matches:
        return None

    for match in reversed(matches):
        if match.end() >= min_chars:
            return match.end()
    return None


def _split_tokens(text: str, max_tokens: int) -> list[str]:
    encoder = _get_encoder()
    if encoder is None:
        words = text.split()
        if len(words) <= max_tokens:
            return [text]
        parts: list[str] = []
        for i in range(0, len(words), max_tokens):
            parts.append(" ".join(words[i : i + max_tokens]))
        return parts

    tokens = encoder.encode(text)
    if len(tokens) <= max_tokens:
        return [text]
    parts = []
    for i in range(0, len(tokens), max_tokens):
        parts.append(encoder.decode(tokens[i : i + max_tokens]))
    return parts


def _split_text_with_overlap(full_text: str, overlap: int) -> str:
    overlap_text_parts = _split_tokens(full_text, overlap)
    return overlap_text_parts[-1] if overlap_text_parts else full_text


def _split_at_sentence_boundary(full_text: str, chunk_size: int) -> tuple[str, str] | None:
    split_at = _find_sentence_split_index(full_text)
    if split_at is None:
        return None

    head = full_text[:split_at].strip()
    tail = full_text[split_at:].strip()
    if not head or _count_tokens(head) < int(chunk_size * 0.5):
        return None
    return head, tail


def chunk_transcript(
    segments: list[TranscriptSegment] | list[RawSegment],
    metadata: VideoMetadata,
) -> list[ChunkPayload]:
    settings = get_settings()
    chunk_size = settings.chunk_size
    overlap = settings.chunk_overlap
    hook_window = settings.hook_window_seconds

    normalized = normalize_segments(segments)
    if not normalized:
        return []

    chunks: list[ChunkPayload] = []
    current_text_parts: list[str] = []
    current_start: float | None = None
    current_end: float | None = None
    current_tokens = 0
    chunk_index = 0

    def flush_chunk() -> None:
        nonlocal chunk_index, current_text_parts, current_start, current_end, current_tokens
        if not current_text_parts or current_start is None or current_end is None:
            return

        text = " ".join(current_text_parts).strip()
        if not text:
            return

        is_hook = current_start < hook_window and current_end > 0
        chunks.append(
            ChunkPayload(
                video_id=metadata.video_id,
                chunk_index=chunk_index,
                start_time=current_start,
                end_time=current_end,
                time_range=format_time_range(current_start, current_end),
                is_hook=is_hook,
                text=text,
                engagement_rate=metadata.engagement_rate,
                creator=metadata.creator,
                follower_count=metadata.follower_count,
            )
        )
        chunk_index += 1

    def reset_with_overlap() -> None:
        nonlocal current_text_parts, current_start, current_end, current_tokens
        if not current_text_parts:
            return

        full_text = " ".join(current_text_parts).strip()
        overlap_text = _split_text_with_overlap(full_text, overlap)
        current_text_parts = [overlap_text]
        current_tokens = _count_tokens(overlap_text)
        current_start = current_end

    for segment in normalized:
        segment_tokens = _count_tokens(segment.text)
        if current_start is None:
            current_start = segment.start_time
        current_end = segment.end_time

        if current_tokens + segment_tokens > chunk_size and current_text_parts:
            full_text = " ".join(current_text_parts).strip()
            split = _split_at_sentence_boundary(full_text, chunk_size)
            if split:
                head, tail = split
                current_text_parts = [head]
                current_tokens = _count_tokens(head)
                flush_chunk()
                current_text_parts = [tail] if tail else []
                current_tokens = _count_tokens(tail) if tail else 0
                if tail:
                    current_start = current_end
            else:
                flush_chunk()
                reset_with_overlap()

        current_text_parts.append(segment.text)
        current_tokens += segment_tokens

    flush_chunk()
    return chunks


def extract_hashtags(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"#(\w+)", text or "")))
