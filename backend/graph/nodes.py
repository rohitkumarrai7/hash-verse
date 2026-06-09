from __future__ import annotations

import json
from typing import Any

from graph.state import SYSTEM_PROMPT, classify_intent, parse_citations, sources_from_chunks
from services.cache import get_cache_service
from services.vectorstore import VectorStore


def classify_intent_node(state: dict[str, Any]) -> dict[str, Any]:
    intent, filter_is_hook, filter_video_id = classify_intent(state["question"])
    return {
        "intent": intent,
        "filter_is_hook": filter_is_hook,
        "filter_video_id": filter_video_id,
    }


def load_metadata_node(state: dict[str, Any]) -> dict[str, Any]:
    cache = get_cache_service()
    session = cache.get_session_status(state["session_id"]) or {}
    video_a = session.get("video_a") or {}
    video_b = session.get("video_b") or {}

    metadata_context = json.dumps(
        {
            "video_a": video_a,
            "video_b": video_b,
        },
        indent=2,
    )
    return {"metadata_context": metadata_context}


def retrieve_node(state: dict[str, Any], vector_store: VectorStore) -> dict[str, Any]:
    question = state["question"]
    session_id = state["session_id"]
    intent = state.get("intent", "general")
    filter_is_hook = state.get("filter_is_hook", False)
    filter_video_id = state.get("filter_video_id")

    retrieved: list[dict[str, Any]] = []

    if intent == "improve_b":
        retrieved.extend(
            vector_store.search(session_id, question, video_id="A", limit=6)
        )
        retrieved.extend(
            vector_store.search(session_id, question, video_id="B", limit=4)
        )
    elif intent == "creator_b":
        retrieved.extend(
            vector_store.search(session_id, question, video_id="B", limit=3)
        )
    else:
        retrieved.extend(
            vector_store.search(
                session_id,
                question,
                video_id=filter_video_id,
                is_hook=filter_is_hook if filter_is_hook else None,
                limit=8,
            )
        )

    # Deduplicate by chunk key
    seen = set()
    unique: list[dict[str, Any]] = []
    for chunk in retrieved:
        key = (chunk.get("video_id"), chunk.get("chunk_index"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(chunk)

    return {"retrieved_chunks": unique}


def build_user_prompt(state: dict[str, Any]) -> str:
    chunks_text = []
    for chunk in state.get("retrieved_chunks", []):
        chunks_text.append(
            f"- Video {chunk.get('video_id')} · Chunk {chunk.get('chunk_index')} · "
            f"{chunk.get('time_range')} · is_hook={chunk.get('is_hook')}: {chunk.get('text')}"
        )

    return f"""Session metadata:
{state.get('metadata_context', '{}')}

Retrieved transcript chunks:
{chr(10).join(chunks_text) if chunks_text else 'No transcript chunks retrieved.'}

User question:
{state['question']}

Answer with inline citations in the required format."""


def finalize_response_node(state: dict[str, Any]) -> dict[str, Any]:
    response = state.get("response", "")
    sources = parse_citations(response)

    if not sources and state.get("retrieved_chunks"):
        sources = sources_from_chunks(state["retrieved_chunks"], limit=3)

    return {"sources": sources}
