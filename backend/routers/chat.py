from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import AIMessage, HumanMessage
from sse_starlette.sse import EventSourceResponse

from graph.builder import build_graph
from graph.nodes import build_user_prompt, finalize_response_node
from graph.state import SYSTEM_PROMPT, parse_citations
from models import ChatRequest
from services.cache import get_cache_service
from services.llm import stream_llm

router = APIRouter()
logger = logging.getLogger(__name__)


def _sse_payload(event_type: str, **fields) -> dict:
    # sse-starlette expects `data` as a string; dicts would be sent as Python repr.
    return {"event": "message", "data": json.dumps({"type": event_type, **fields})}


@router.post("/chat")
async def chat(payload: ChatRequest, request: Request):
    cache = get_cache_service()
    session = cache.get_session_status(payload.session_id)
    if not session or session.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Session not ready. Complete ingestion first.")

    vector_store = request.app.state.vector_store
    graph = build_graph(vector_store)
    config = {"configurable": {"thread_id": payload.session_id}}

    prep_state = await asyncio.to_thread(
        graph.invoke,
        {
            "session_id": payload.session_id,
            "question": payload.message,
        },
        config,
    )

    history_messages: list[dict[str, str]] = []
    try:
        snapshot = graph.get_state(config)
        if snapshot.values:
            for msg in snapshot.values.get("messages", []):
                if isinstance(msg, HumanMessage):
                    history_messages.append({"role": "user", "content": str(msg.content)})
                elif isinstance(msg, AIMessage):
                    history_messages.append({"role": "assistant", "content": str(msg.content)})
    except Exception:
        history_messages = []

    user_prompt = build_user_prompt(prep_state)

    async def event_generator() -> AsyncIterator[dict]:
        full_response = ""
        token_count = 0
        try:
            async for token in stream_llm(SYSTEM_PROMPT, user_prompt, history_messages[-6:]):
                full_response += token
                token_count += 1
                yield _sse_payload("token", content=token)

            if not full_response.strip():
                raise ValueError("LLM returned an empty response")

            prep_state["response"] = full_response
            finalized = finalize_response_node(prep_state)
            sources = finalized.get("sources") or parse_citations(full_response)

            yield _sse_payload("sources", sources=sources)

            graph.update_state(
                config,
                {
                    "messages": [
                        HumanMessage(content=payload.message),
                        AIMessage(content=full_response),
                    ]
                },
            )

            logger.info("Chat completed for session %s (%s tokens)", payload.session_id, token_count)
            yield _sse_payload("done")
        except Exception as exc:
            logger.exception("Chat failed for session %s", payload.session_id)
            yield _sse_payload("error", message=str(exc))

    return EventSourceResponse(event_generator())
