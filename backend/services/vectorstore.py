from __future__ import annotations

import logging
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from config import Settings, get_settings
from models import ChunkPayload
from services.embedder import embed_texts, get_embedding_dimension

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.collection_name = self.settings.collection_name
        # Avoid loading the embedding model during API startup
        self.vector_size = get_embedding_dimension()
        self.client = self._connect_client()
        self.using_memory = getattr(self, "_using_memory", False)
        self.using_cloud = getattr(self, "_using_cloud", False)

    def _connect_client(self) -> QdrantClient:
        settings = self.settings

        if settings.qdrant_url and settings.qdrant_api_key:
            try:
                client = QdrantClient(
                    url=settings.qdrant_url.rstrip("/"),
                    api_key=settings.qdrant_api_key,
                    timeout=10,
                    check_compatibility=False,
                )
                client.get_collections()
                self._using_memory = False
                self._using_cloud = True
                logger.info("Qdrant connected via cloud URL")
                return client
            except Exception as exc:
                logger.warning("Qdrant cloud connection failed (%s); trying local fallback", exc)

        try:
            client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                timeout=3,
                check_compatibility=False,
            )
            client.get_collections()
            self._using_memory = False
            self._using_cloud = False
            logger.info("Qdrant connected at %s:%s", settings.qdrant_host, settings.qdrant_port)
            return client
        except Exception as exc:
            logger.warning("Qdrant local connection failed (%s); using in-memory store", exc)

        self._using_memory = True
        self._using_cloud = False
        return QdrantClient(":memory:", check_compatibility=False)

    def ensure_collection(self) -> None:
        collections = self.client.get_collections().collections
        names = {collection.name for collection in collections}
        if self.collection_name in names:
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=qmodels.VectorParams(size=self.vector_size, distance=qmodels.Distance.COSINE),
        )

        for field_name, schema in [
            ("session_id", qmodels.PayloadSchemaType.KEYWORD),
            ("video_id", qmodels.PayloadSchemaType.KEYWORD),
            ("is_hook", qmodels.PayloadSchemaType.BOOL),
        ]:
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=schema,
                )
            except Exception:
                pass

    def delete_session(self, session_id: str) -> None:
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[qmodels.FieldCondition(key="session_id", match=qmodels.MatchValue(value=session_id))]
                )
            ),
        )

    def upsert_chunks(self, session_id: str, chunks: list[ChunkPayload]) -> None:
        if not chunks:
            return

        texts = [chunk.text for chunk in chunks]
        vectors = embed_texts(texts)

        points = []
        for chunk, vector in zip(chunks, vectors):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{session_id}:{chunk.video_id}:{chunk.chunk_index}"))
            payload = {
                "session_id": session_id,
                "video_id": chunk.video_id,
                "chunk_index": chunk.chunk_index,
                "start_time": chunk.start_time,
                "end_time": chunk.end_time,
                "time_range": chunk.time_range,
                "is_hook": chunk.is_hook,
                "text": chunk.text,
                "engagement_rate": chunk.engagement_rate,
                "creator": chunk.creator,
                "follower_count": chunk.follower_count,
            }
            points.append(qmodels.PointStruct(id=point_id, vector=vector, payload=payload))

        self.client.upsert(collection_name=self.collection_name, points=points)

    def search(
        self,
        session_id: str,
        query: str,
        *,
        video_id: str | None = None,
        is_hook: bool | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        query_vector = embed_texts([query])[0]
        must_conditions = [
            qmodels.FieldCondition(key="session_id", match=qmodels.MatchValue(value=session_id)),
        ]
        if video_id:
            must_conditions.append(
                qmodels.FieldCondition(key="video_id", match=qmodels.MatchValue(value=video_id))
            )
        if is_hook is not None:
            must_conditions.append(
                qmodels.FieldCondition(key="is_hook", match=qmodels.MatchValue(value=is_hook))
            )

        query_filter = qmodels.Filter(must=must_conditions)

        if hasattr(self.client, "query_points"):
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            ).points
        else:
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )

        hits: list[dict[str, Any]] = []
        for result in results:
            payload = result.payload or {}
            hits.append(
                {
                    "score": getattr(result, "score", None),
                    "video_id": payload.get("video_id"),
                    "chunk_index": payload.get("chunk_index"),
                    "time_range": payload.get("time_range"),
                    "text": payload.get("text"),
                    "is_hook": payload.get("is_hook"),
                    "engagement_rate": payload.get("engagement_rate"),
                    "creator": payload.get("creator"),
                    "follower_count": payload.get("follower_count"),
                }
            )
        return hits
