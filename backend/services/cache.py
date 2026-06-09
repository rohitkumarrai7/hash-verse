from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from functools import lru_cache
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from config import Settings, get_settings
from models import VideoMetadata
from services.metadata import metadata_to_dict

logger = logging.getLogger(__name__)

SESSION_COLLECTION = "app_sessions"
SESSION_VECTOR_SIZE = 4
ZERO_VECTOR = [0.0] * SESSION_VECTOR_SIZE


class _MemoryCache:
    """Process-wide in-memory cache used when Redis and Qdrant are unavailable."""

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


class _QdrantSessionStore:
    """Persist ingest session status in Qdrant so Render restarts do not drop sessions."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.ttl_seconds = 60 * 60 * 24
        self.client = self._connect_client()
        self._ensure_collection()

    def _connect_client(self) -> QdrantClient:
        if self.settings.qdrant_url and self.settings.qdrant_api_key:
            client = QdrantClient(
                url=self.settings.qdrant_url.rstrip("/"),
                api_key=self.settings.qdrant_api_key,
                timeout=10,
                check_compatibility=False,
            )
            client.get_collections()
            logger.info("Session cache using Qdrant cloud")
            return client

        client = QdrantClient(
            host=self.settings.qdrant_host,
            port=self.settings.qdrant_port,
            timeout=3,
            check_compatibility=False,
        )
        client.get_collections()
        logger.info("Session cache using Qdrant at %s:%s", self.settings.qdrant_host, self.settings.qdrant_port)
        return client

    def _ensure_collection(self) -> None:
        names = {collection.name for collection in self.client.get_collections().collections}
        if SESSION_COLLECTION in names:
            return
        self.client.create_collection(
            collection_name=SESSION_COLLECTION,
            vectors_config=qmodels.VectorParams(size=SESSION_VECTOR_SIZE, distance=qmodels.Distance.COSINE),
        )

    def _point_id(self, key: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, key))

    def setex(self, key: str, ttl: int, value: str) -> None:
        expires_at = time.time() + (ttl or self.ttl_seconds)
        self.client.upsert(
            collection_name=SESSION_COLLECTION,
            points=[
                qmodels.PointStruct(
                    id=self._point_id(key),
                    vector=ZERO_VECTOR,
                    payload={"key": key, "value": value, "expires_at": expires_at},
                )
            ],
        )

    def get(self, key: str) -> str | None:
        results = self.client.retrieve(
            collection_name=SESSION_COLLECTION,
            ids=[self._point_id(key)],
            with_payload=True,
        )
        if not results:
            return None
        payload = results[0].payload or {}
        expires_at = payload.get("expires_at")
        if expires_at is not None and time.time() > float(expires_at):
            self.client.delete(
                collection_name=SESSION_COLLECTION,
                points_selector=qmodels.PointIdsList(points=[self._point_id(key)]),
            )
            return None
        value = payload.get("value")
        return value if isinstance(value, str) else None


class CacheService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.ttl_seconds = 60 * 60 * 24
        self._memory = _MemoryCache()
        self.client: Any = self._memory
        self.backend = "memory"

        if self._try_redis():
            return
        if self._try_qdrant():
            return
        logger.info("CacheService using in-memory fallback (shared singleton)")

    def _try_redis(self) -> bool:
        try:
            import redis

            client = redis.from_url(
                self.settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
            )
            client.ping()
            self.client = client
            self.backend = "redis"
            logger.info("CacheService using Redis")
            return True
        except Exception:
            return False

    def _try_qdrant(self) -> bool:
        try:
            self.client = _QdrantSessionStore(self.settings)
            self.backend = "qdrant"
            return True
        except Exception as exc:
            logger.info("Qdrant session cache unavailable (%s)", exc)
            return False

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


@lru_cache
def get_cache_service() -> CacheService:
    return CacheService()
