from __future__ import annotations

import logging

from config import get_settings

logger = logging.getLogger(__name__)


def get_checkpointer():
    settings = get_settings()

    try:
        from langgraph.checkpoint.redis import RedisSaver

        checkpointer = RedisSaver.from_conn_string(settings.redis_url)
        checkpointer.setup()
        logger.info("LangGraph checkpointer using Redis at %s", settings.redis_url)
        return checkpointer
    except Exception as exc:
        logger.warning("Redis checkpointer unavailable (%s); using in-memory MemorySaver", exc)

    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver()
