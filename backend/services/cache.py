from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

from config import Settings, get_settings
from models import VideoMetadata
from services.metadata import metadata_to_dict

logger = logging.getLogger(__name__)


class _MemoryCache:
    """Process-wide in-memory cache used when Redis is unavailable."""

    _instance: "_MemoryCache | None" = None

    def __new__(cls) -> "_MemoryCache":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._store = {}
        return cls._instance

    def setex(self, key: str, ttl: int, value: str) -> None:
        expires = time.time() + ttl if ttl else None
        self._store[key] = (value, expires)

    def get(self, key: str) -> str | None:
        item = self._store.get(key)
        if not item:
            return None
        value, expires = item
        if expires is not None and time.time() > expires:
            del self._store[key]
            return None
        return value


class CacheService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.ttl_seconds = 60 * 60 * 24
        self._memory = _MemoryCache()
        self.client: Any = self._memory
        self.using_memory = True

        try:
            import redis

            client = redis.from_url(
                self.settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
            )
            client.ping()
            self.client = client
            self.using_memory = False
            logger.info("CacheService using Redis")
        except Exception:
            logger.info("CacheService using in-memory fallback (shared singleton)")

    def _session_key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def _url_key(self, url: str) -> str:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return f"url:{digest}"

    def set_session_status(
        self,
        session_id: str,
        status: str,
        message: str | None = None,
        video_a: dict[str, Any] | None = None,
        video_b: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "status": status,
            "message": message,
            "video_a": video_a,
            "video_b": video_b,
        }
        self.client.setex(self._session_key(session_id), self.ttl_seconds, json.dumps(payload))

    def get_session_status(self, session_id: str) -> dict[str, Any] | None:
        raw = self.client.get(self._session_key(session_id))
        if not raw:
            return None
        return json.loads(raw)

    def cache_video_metadata(self, url: str, metadata: VideoMetadata) -> None:
        self.client.setex(self._url_key(url), self.ttl_seconds, json.dumps(metadata_to_dict(metadata)))

    def get_cached_video_metadata(self, url: str) -> dict[str, Any] | None:
        raw = self.client.get(self._url_key(url))
        if not raw:
            return None
        return json.loads(raw)
