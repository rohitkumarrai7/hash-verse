from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from config import get_settings


async def stream_llm(
    system_prompt: str,
    user_prompt: str,
    history: list[dict[str, str]] | None = None,
) -> AsyncIterator[str]:
    settings = get_settings()
    history = history or []
    provider = settings.llm_provider.lower()

    if provider == "openrouter":
        async for token in _stream_openrouter(system_prompt, user_prompt, history):
            yield token
        return

    if provider == "openai":
        async for token in _stream_openai(system_prompt, user_prompt, history):
            yield token
        return

    if settings.gemini_api_key:
        async for token in _stream_gemini(system_prompt, user_prompt, history):
            yield token
        return

    if settings.openrouter_api_key:
        async for token in _stream_openrouter(system_prompt, user_prompt, history):
            yield token
        return

    if settings.openai_api_key:
        async for token in _stream_openai(system_prompt, user_prompt, history):
            yield token
        return

    raise ValueError("No LLM configured. Set GEMINI_API_KEY (preferred) or OPENROUTER_API_KEY / OPENAI_API_KEY.")


def _build_messages(system_prompt: str, user_prompt: str, history: list[dict[str, str]]) -> list[Any]:
    messages: list[Any] = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_prompt})
    return messages


def _extract_chunk_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return str(content) if content else ""


async def _stream_openrouter(
    system_prompt: str,
    user_prompt: str,
    history: list[dict[str, str]],
) -> AsyncIterator[str]:
    from langchain_openai import ChatOpenAI

    settings = get_settings()
    if not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY is not configured")

    llm = ChatOpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        model=settings.openrouter_model,
        streaming=True,
        temperature=0.2,
        default_headers={
            "HTTP-Referer": settings.backend_url,
            "X-Title": "CreatorJoy RAG Analyst",
        },
    )

    async for chunk in llm.astream(_build_messages(system_prompt, user_prompt, history)):
        text = _extract_chunk_text(chunk.content)
        if text:
            yield text


async def _stream_openai(
    system_prompt: str,
    user_prompt: str,
    history: list[dict[str, str]],
) -> AsyncIterator[str]:
    from langchain_openai import ChatOpenAI

    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not configured")

    llm = ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        streaming=True,
        temperature=0.2,
    )

    async for chunk in llm.astream(_build_messages(system_prompt, user_prompt, history)):
        text = _extract_chunk_text(chunk.content)
        if text:
            yield text


async def _stream_gemini(
    system_prompt: str,
    user_prompt: str,
    history: list[dict[str, str]],
) -> AsyncIterator[str]:
    from langchain_google_genai import ChatGoogleGenerativeAI

    settings = get_settings()
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not configured")

    llm = ChatGoogleGenerativeAI(
        google_api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        streaming=True,
        temperature=0.2,
    )

    async for chunk in llm.astream(_build_messages(system_prompt, user_prompt, history)):
        text = _extract_chunk_text(chunk.content)
        if text:
            yield text
