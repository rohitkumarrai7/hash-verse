from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from routers import chat, ingest
from services.vectorstore import VectorStore
from services.youtube import is_cloud_host

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    vector_store = VectorStore(settings)
    vector_store.ensure_collection()
    app.state.vector_store = vector_store
    qdrant_mode = (
        "cloud"
        if vector_store.using_cloud
        else "memory"
        if vector_store.using_memory
        else f"{settings.qdrant_host}:{settings.qdrant_port}"
    )
    logger.info("API ready (qdrant=%s, embedding=%s)", qdrant_mode, settings.embedding_model)
    yield


app = FastAPI(title="CreatorJoy RAG API", version="1.0.0", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    # Vercel production + preview deployments (*.vercel.app)
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router, prefix="/api/v1", tags=["ingest"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])


@app.get("/")
async def root():
    return {"message": "CreatorJoy RAG API is running", "health": "/health"}


@app.get("/health")
async def health(request: Request):
    vector_store = request.app.state.vector_store
    qdrant_status = (
        "cloud"
        if vector_store.using_cloud
        else "memory"
        if vector_store.using_memory
        else "local"
    )
    cfg = get_settings()
    return {
        "status": "ok",
        "qdrant": qdrant_status,
        "collection": vector_store.collection_name,
        "apify": "configured" if cfg.apify_token else "missing",
        "host": "render" if is_cloud_host() else "local",
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, workers=1)
