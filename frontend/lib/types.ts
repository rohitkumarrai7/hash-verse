export type VideoId = "A" | "B";

export interface VideoMetadata {
  video_id: VideoId;
  url: string;
  title?: string | null;
  creator?: string | null;
  follower_count?: number | null;
  views?: number | null;
  likes?: number | null;
  comments?: number | null;
  hashtags?: string[];
  upload_date?: string | null;
  duration?: number | null;
  thumbnail_url?: string | null;
  engagement_rate?: number | null;
}

export interface IngestStatus {
  session_id: string;
  status: "processing" | "completed" | "failed";
  message?: string | null;
  video_a?: VideoMetadata | null;
  video_b?: VideoMetadata | null;
}

export interface SourceCitation {
  video_id: VideoId;
  chunk_index: number;
  time_range: string;
  text?: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceCitation[];
  streaming?: boolean;
}

export type SSEEvent =
  | { type: "token"; content: string }
  | { type: "sources"; sources: SourceCitation[] }
  | { type: "done" }
  | { type: "error"; message: string };
