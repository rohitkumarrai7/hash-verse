from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class IngestRequest(BaseModel):
    youtube_url: str = Field(..., description="YouTube video URL (Video A)")
    instagram_url: str = Field(..., description="Instagram Reel URL (Video B)")
    session_id: str = Field(..., min_length=1, description="Unique session identifier")


class IngestResponse(BaseModel):
    session_id: str
    status: Literal["processing", "completed", "failed"]
    message: str


class IngestStatusResponse(BaseModel):
    session_id: str
    status: Literal["processing", "completed", "failed"]
    message: str | None = None
    video_a: dict[str, Any] | None = None
    video_b: dict[str, Any] | None = None


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class TranscriptSegment(BaseModel):
    start_time: float
    end_time: float
    text: str


class VideoMetadata(BaseModel):
    video_id: Literal["A", "B"]
    url: str
    title: str | None = None
    creator: str | None = None
    follower_count: int | None = None
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    hashtags: list[str] = Field(default_factory=list)
    upload_date: str | None = None
    duration: float | None = None
    thumbnail_url: str | None = None
    engagement_rate: float | None = None


class ChunkPayload(BaseModel):
    video_id: Literal["A", "B"]
    chunk_index: int
    start_time: float
    end_time: float
    time_range: str
    is_hook: bool
    text: str
    engagement_rate: float | None = None
    creator: str | None = None
    follower_count: int | None = None


class SourceCitation(BaseModel):
    video_id: Literal["A", "B"]
    chunk_index: int
    time_range: str
    text: str | None = None
