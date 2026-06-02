"""End-to-end smoke test for CreatorJoy RAG pipeline."""
from __future__ import annotations

import asyncio
import uuid

from config import get_settings
from graph.builder import build_graph
from graph.nodes import build_user_prompt, finalize_response_node
from graph.state import SYSTEM_PROMPT
from services.cache import CacheService
from services.llm import stream_llm
from services.metadata import metadata_to_dict
from services.vectorstore import VectorStore
from services.youtube import ingest_youtube

# Verified public URLs (replace if a platform blocks scraping during CI)
TEST_URL_PAIRS = [
    {
        "name": "classic-youtube-reel",
        "youtube": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        "instagram": "https://www.instagram.com/reel/DCqVQ8oxSKj/",
    },
    {
        "name": "short-form-comparison",
        "youtube": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "instagram": "https://www.instagram.com/reel/Cx0QjJvR_fH/",
    },
]

YOUTUBE_URL = TEST_URL_PAIRS[0]["youtube"]
INSTAGRAM_URL = TEST_URL_PAIRS[0]["instagram"]


async def test_llm_stream() -> None:
    print("Testing LLM stream...")
    tokens = []
    async for token in stream_llm(
        "You are a test assistant.",
        "Reply with exactly: CreatorJoy OK",
    ):
        tokens.append(token)
    response = "".join(tokens)
    print(f"  LLM response: {response[:120]}")
    if not response.strip():
        raise RuntimeError("LLM returned empty response")


def test_youtube_ingest(url: str = YOUTUBE_URL) -> tuple[object, list]:
    print(f"Testing YouTube ingest: {url}")
    metadata, chunks = ingest_youtube(url)
    print(f"  title={metadata.title}")
    print(f"  engagement_rate={metadata.engagement_rate}")
    print(f"  chunks={len(chunks)}")
    if not chunks:
        raise RuntimeError("YouTube produced no chunks")
    return metadata, chunks


def test_instagram_ingest(url: str = INSTAGRAM_URL) -> tuple[object, list]:
    print(f"Testing Instagram ingest: {url}")
    from services.instagram import ingest_instagram

    metadata, chunks = ingest_instagram(url)
    print(f"  creator={metadata.creator}")
    print(f"  engagement_rate={metadata.engagement_rate}")
    print(f"  chunks={len(chunks)}")
    if not chunks:
        raise RuntimeError("Instagram produced no chunks")
    return metadata, chunks


async def test_rag_chat(session_id: str, vector_store: VectorStore) -> None:
    print("Testing RAG chat pipeline...")
    graph = build_graph(vector_store)
    config = {"configurable": {"thread_id": session_id}}
    question = "What's the engagement rate of each video?"

    prep = graph.invoke({"session_id": session_id, "question": question}, config=config)
    user_prompt = build_user_prompt(prep)

    tokens = []
    async for token in stream_llm(SYSTEM_PROMPT, user_prompt):
        tokens.append(token)
    response = "".join(tokens)
    prep["response"] = response
    sources = finalize_response_node(prep).get("sources", [])

    print(f"  answer preview: {response[:200]}...")
    print(f"  sources: {len(sources)}")
    if not response.strip():
        raise RuntimeError("RAG chat returned empty response")
    if not sources:
        raise RuntimeError("RAG chat returned no sources (citation parser + fallback failed)")


async def main() -> None:
    settings = get_settings()
    print(f"LLM provider: {settings.llm_provider} / gemini model: {settings.gemini_model}")

    await test_llm_stream()

    vector_store = VectorStore()
    vector_store.ensure_collection()
    print(f"Vector store ready (memory fallback={vector_store.client is None})")

    cache = CacheService()
    print(f"Cache ready (memory fallback={cache.using_memory})")

    video_a_meta, video_a_chunks = test_youtube_ingest()
    video_b_meta, video_b_chunks = test_instagram_ingest()

    session_id = str(uuid.uuid4())
    vector_store.delete_session(session_id)
    vector_store.upsert_chunks(session_id, video_a_chunks)
    vector_store.upsert_chunks(session_id, video_b_chunks)

    cache.set_session_status(
        session_id,
        "completed",
        "E2E test session",
        video_a=metadata_to_dict(video_a_meta),
        video_b=metadata_to_dict(video_b_meta),
    )

    await test_rag_chat(session_id, vector_store)
    print("\nE2E tests passed for YouTube + Instagram + LLM + RAG citations.")


if __name__ == "__main__":
    asyncio.run(main())
