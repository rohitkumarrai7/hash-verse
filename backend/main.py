from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from routers import chat, ingest
from services.vectorstore import VectorStore

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    vector_store = VectorStore(settings)
    vector_store.ensure_collection()
    app.state.vector_store = vector_store
    yield


app = FastAPI(title="CreatorJoy RAG API", version="1.0.0", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router, prefix="/api/v1", tags=["ingest"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])


@app.get("/health")
async def health():
    return {"status": "ok"}
