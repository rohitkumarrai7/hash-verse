from __future__ import annotations

import logging

import asyncio

from fastapi import APIRouter, BackgroundTasks, Request

from models import IngestRequest, IngestResponse, IngestStatusResponse
from services.cache import CacheService
from services.instagram import ingest_instagram
from services.metadata import metadata_to_dict
from services.vectorstore import VectorStore
from services.youtube import ingest_youtube

router = APIRouter()
logger = logging.getLogger(__name__)


def _run_ingest(session_id: str, youtube_url: str, instagram_url: str, vector_store: VectorStore) -> None:
    cache = CacheService()
    cache.set_session_status(session_id, "processing", "Ingesting YouTube video (Video A)...")

    try:
        vector_store.delete_session(session_id)

        logger.info("Ingesting YouTube URL for session %s", session_id)
        video_a_metadata, video_a_chunks = ingest_youtube(youtube_url)
        cache.cache_video_metadata(youtube_url, video_a_metadata)
        vector_store.upsert_chunks(session_id, video_a_chunks)
        cache.set_session_status(
            session_id,
            "processing",
            "YouTube done. Ingesting Instagram Reel (Video B)...",
            video_a=metadata_to_dict(video_a_metadata),
        )

        logger.info("Ingesting Instagram URL for session %s", session_id)
        video_b_metadata, video_b_chunks = ingest_instagram(instagram_url)
        cache.cache_video_metadata(instagram_url, video_b_metadata)
        vector_store.upsert_chunks(session_id, video_b_chunks)

        cache.set_session_status(
            session_id,
            "completed",
            "Ingestion completed",
            video_a=metadata_to_dict(video_a_metadata),
            video_b=metadata_to_dict(video_b_metadata),
        )
        logger.info("Ingestion completed for session %s", session_id)
    except Exception as exc:
        logger.exception("Ingestion failed for session %s", session_id)
        cache.set_session_status(session_id, "failed", str(exc))


async def _ingest_task(
    session_id: str,
    youtube_url: str,
    instagram_url: str,
    vector_store: VectorStore,
) -> None:
    await asyncio.to_thread(_run_ingest, session_id, youtube_url, instagram_url, vector_store)


@router.post("/ingest", response_model=IngestResponse)
async def ingest_videos(payload: IngestRequest, background_tasks: BackgroundTasks, request: Request):
    vector_store: VectorStore = request.app.state.vector_store
    cache = CacheService()
    cache.set_session_status(payload.session_id, "processing", "Queued for ingestion")

    background_tasks.add_task(
        _ingest_task,
        payload.session_id,
        payload.youtube_url,
        payload.instagram_url,
        vector_store,
    )

    return IngestResponse(
        session_id=payload.session_id,
        status="processing",
        message="Ingestion started",
    )


@router.get("/ingest/{session_id}", response_model=IngestStatusResponse)
async def ingest_status(session_id: str):
    cache = CacheService()
    status = cache.get_session_status(session_id)
    if not status:
        return IngestStatusResponse(session_id=session_id, status="failed", message="Session not found")

    return IngestStatusResponse(
        session_id=session_id,
        status=status.get("status", "processing"),
        message=status.get("message"),
        video_a=status.get("video_a"),
        video_b=status.get("video_b"),
    )
