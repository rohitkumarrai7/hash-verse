from __future__ import annotations

import re
from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    session_id: str
    question: str
    intent: str
    filter_is_hook: bool
    filter_video_id: str | None
    metadata_context: str
    retrieved_chunks: list[dict[str, Any]]
    response: str
    sources: list[dict[str, Any]]
    messages: Annotated[list[Any], add_messages]


HOOK_KEYWORDS = ("hook", "first 5 seconds", "first five seconds", "opening", "intro")
ENGAGEMENT_KEYWORDS = ("engagement rate", "engagement", "views", "likes", "comments")
CREATOR_KEYWORDS = ("creator", "follower", "followers", "who is", "who's")
IMPROVEMENT_KEYWORDS = ("improve", "suggest", "fix", "better", "recommend")
COMPARE_KEYWORDS = ("compare", "why did video", "more engagement", "difference")


def classify_intent(question: str) -> tuple[str, bool, str | None]:
    q = question.lower()

    if any(keyword in q for keyword in HOOK_KEYWORDS):
        return "hook_compare", True, None
    if any(keyword in q for keyword in ENGAGEMENT_KEYWORDS):
        return "engagement", False, None
    if any(keyword in q for keyword in CREATOR_KEYWORDS) and ("video b" in q or "reel" in q or "instagram" in q):
        return "creator_b", False, "B"
    if any(keyword in q for keyword in IMPROVEMENT_KEYWORDS):
        return "improve_b", False, None
    if any(keyword in q for keyword in COMPARE_KEYWORDS):
        return "compare", False, None
    return "general", False, None


def _normalize_time_range(raw: str) -> str:
    return re.sub(r"\s*-\s*", "-", raw.strip())


def parse_citations(text: str) -> list[dict[str, Any]]:
    patterns = [
        r"\[Video\s+(A|B)\s*[·\-\|,]\s*Chunk\s+(\d+)\s*[·\-\|,]\s*([0-9:]{2,}(?:\s*-\s*[0-9:]{2,})?)\]",
        r"\[Video\s+(A|B)\s+chunk\s+(\d+)\s+(?:at|@)\s+([0-9:]{2,}(?:\s*-\s*[0-9:]{2,})?)\]",
        r"Video\s+(A|B)\s*[·\-\|,]\s*Chunk\s+(\d+)\s*[·\-\|,]\s*([0-9:]{2,}(?:\s*-\s*[0-9:]{2,})?)",
    ]
    sources: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str]] = set()

    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            video_id = match.group(1).upper()
            chunk_index = int(match.group(2))
            time_range = _normalize_time_range(match.group(3))
            key = (video_id, chunk_index, time_range)
            if key in seen:
                continue
            seen.add(key)
            sources.append(
                {
                    "video_id": video_id,
                    "chunk_index": chunk_index,
                    "time_range": time_range,
                }
            )
    return sources


def sources_from_chunks(chunks: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    for chunk in chunks[:limit]:
        key = (chunk.get("video_id"), chunk.get("chunk_index"))
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            {
                "video_id": chunk.get("video_id"),
                "chunk_index": chunk.get("chunk_index"),
                "time_range": chunk.get("time_range"),
                "text": chunk.get("text"),
            }
        )
    return sources


SYSTEM_PROMPT = """You are a Creator Intelligence Analyst. You analyze YouTube and Instagram Reels performance.
You have access to two video transcripts with precise timestamps and metadata.

Rules:
- Every factual claim MUST include an inline citation in this exact format:
  [Video A · Chunk N · MM:SS-MM:SS] or [Video B · Chunk N · MM:SS-MM:SS]
- Use the middle dot character · between fields (not a hyphen).
- When comparing engagement, reference exact engagement rates from metadata first, then analyze content patterns.
- When comparing hooks, ONLY use transcript chunks from the first 5 seconds (is_hook: true).
- When suggesting improvements for Video B, base suggestions ONLY on patterns proven in Video A's transcript.
- Consider creator follower count as context for expected vs. actual performance.
- If data is missing, say "I don't have that data" rather than hallucinating.
- Be concise, analytical, and actionable.

Citation examples (copy this format exactly):
- "Video A opens with a geopolitical hook [Video A · Chunk 0 · 00:00-00:05]."
- "Video B's creator asks viewers to share the reel [Video B · Chunk 1 · 00:05-00:19]."
"""
