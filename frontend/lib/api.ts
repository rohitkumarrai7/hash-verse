import type { IngestStatus, SSEEvent } from "./types";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch {
    throw new ApiError(
      `Cannot reach backend at ${BACKEND_URL}. Start it with: cd backend && .\\run.bat`,
    );
  }
}

function parseSseBuffer(buffer: string): { events: SSEEvent[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const parts = normalized.split("\n\n");
  const rest = parts.pop() || "";
  const events: SSEEvent[] = [];

  for (const part of parts) {
    if (!part.trim() || part.trimStart().startsWith(":")) continue;

    let dataPayload = "";
    for (const line of part.split("\n")) {
      if (line.startsWith("data:")) {
        dataPayload += line.startsWith("data: ") ? line.slice(6) : line.slice(5);
      }
    }

    if (!dataPayload) continue;

    try {
      const parsed = JSON.parse(dataPayload) as SSEEvent | string;
      if (typeof parsed === "string") {
        events.push(JSON.parse(parsed) as SSEEvent);
      } else {
        events.push(parsed);
      }
    } catch {
      // ignore malformed chunks
    }
  }

  return { events, rest };
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const response = await apiFetch(`${BACKEND_URL}/health`, { cache: "no-store" });
    return response.ok;
  } catch {
    return false;
  }
}

export async function startIngest(sessionId: string, youtubeUrl: string, instagramUrl: string) {
  const healthy = await checkBackendHealth();
  if (!healthy) {
    throw new ApiError(
      `Backend is not running at ${BACKEND_URL}. Open a terminal and run: cd backend && .\\run.bat`,
    );
  }

  const response = await apiFetch(`${BACKEND_URL}/api/v1/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      youtube_url: youtubeUrl,
      instagram_url: instagramUrl,
    }),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new ApiError(detail || "Failed to start ingestion");
  }

  return response.json();
}

export async function getIngestStatus(sessionId: string): Promise<IngestStatus> {
  const response = await apiFetch(`${BACKEND_URL}/api/v1/ingest/${sessionId}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new ApiError(detail || "Failed to fetch ingest status");
  }

  return response.json();
}

export async function streamChat(
  sessionId: string,
  message: string,
  onEvent: (event: SSEEvent) => void,
  signal?: AbortSignal,
) {
  const response = await apiFetch(`${BACKEND_URL}/api/v1/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({ session_id: sessionId, message }),
    signal,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new ApiError(detail || "Chat request failed");
  }

  if (!response.body) {
    throw new ApiError("No response stream");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let gotDone = false;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSseBuffer(buffer);
    buffer = parsed.rest;

    for (const event of parsed.events) {
      if (event.type === "done") gotDone = true;
      onEvent(event);
    }
  }

  if (buffer.trim()) {
    const parsed = parseSseBuffer(`${buffer}\n\n`);
    for (const event of parsed.events) {
      if (event.type === "done") gotDone = true;
      onEvent(event);
    }
  }

  if (!gotDone) {
    onEvent({ type: "done" });
  }
}

export { BACKEND_URL };
