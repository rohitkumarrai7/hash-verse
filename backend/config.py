from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    openai_model: str = "gpt-4o-mini"
    openrouter_model: str = "google/gemini-2.5-flash"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    apify_token: str = ""
    apify_actor_id: str = "apify/instagram-reel-scraper"
    apify_youtube_actor_id: str = "pintostudio/youtube-transcript-scraper"

    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    collection_name: str = "video_chunks"

    redis_url: str = "redis://localhost:6379/0"

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    # On Render free tier (512MB), use: sentence-transformers/all-MiniLM-L6-v2 (~90MB ONNX via FastEmbed)
    whisper_model: str = "base"
    ytdlp_cookies_from_browser: str = ""

    backend_url: str = "http://localhost:8000"
    cors_origins: str = (
        "http://localhost:3000,https://hash-verse.vercel.app,https://hashverse-two.vercel.app"
    )

    chunk_size: int = 512
    chunk_overlap: int = 128
    hook_window_seconds: float = 5.0

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
