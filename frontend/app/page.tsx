"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import ChatPanel from "./components/ChatPanel";
import URLInputForm from "./components/URLInputForm";
import VideoCard from "./components/VideoCard";
import { BACKEND_URL, checkBackendHealth, getIngestStatus, startIngest } from "@/lib/api";
import type { SourceCitation, VideoMetadata } from "@/lib/types";

const DEFAULT_YOUTUBE = "";
const DEFAULT_INSTAGRAM = "";

export default function Home() {
  const sessionId = useMemo(() => crypto.randomUUID(), []);
  const [youtubeUrl, setYoutubeUrl] = useState(DEFAULT_YOUTUBE);
  const [instagramUrl, setInstagramUrl] = useState(DEFAULT_INSTAGRAM);
  const [ingesting, setIngesting] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [videoA, setVideoA] = useState<VideoMetadata | null>(null);
  const [videoB, setVideoB] = useState<VideoMetadata | null>(null);
  const [ready, setReady] = useState(false);
  const [highlight, setHighlight] = useState<{ videoId: "A" | "B"; range: string } | null>(null);

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      const online = await checkBackendHealth();
      if (!cancelled) {
        setBackendOnline(online);
        if (!online) {
          setStatusMessage(`Backend offline at ${BACKEND_URL}. Run: cd backend && .\\run.bat`);
        }
      }
    };

    check();
    const interval = setInterval(check, 10000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const pollStatus = useCallback(async () => {
    try {
      const status = await getIngestStatus(sessionId);
      setStatusMessage(status.message || status.status);

      if (status.video_a) setVideoA(status.video_a);
      if (status.video_b) setVideoB(status.video_b);

      if (status.status === "completed") {
        setIngesting(false);
        setReady(true);
        return true;
      }

      if (status.status === "failed") {
        setIngesting(false);
        setReady(false);
        return true;
      }

      return false;
    } catch (error) {
      setIngesting(false);
      setReady(false);
      setStatusMessage(error instanceof Error ? error.message : "Failed to fetch ingest status");
      return true;
    }
  }, [sessionId]);

  useEffect(() => {
    if (!ingesting) return;

    const interval = setInterval(() => {
      void pollStatus();
    }, 2000);

    return () => clearInterval(interval);
  }, [ingesting, pollStatus]);

  const handleIngest = async () => {
    setIngesting(true);
    setReady(false);
    setVideoA(null);
    setVideoB(null);
    setStatusMessage("Starting ingestion...");

    try {
      await startIngest(sessionId, youtubeUrl, instagramUrl);
      await pollStatus();
    } catch (error) {
      setIngesting(false);
      setStatusMessage(error instanceof Error ? error.message : "Ingestion failed");
    }
  };

  const handleSourceClick = (source: SourceCitation) => {
    setHighlight({ videoId: source.video_id, range: source.time_range });
    const element = document.getElementById(`video-card-${source.video_id.toLowerCase()}`);
    element?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const ingestProgress = useMemo(() => {
    if (!ingesting) return 0;
    if (ready) return 100;
    if (videoA && videoB) return 95;
    if (videoA) return 55;
    if (statusMessage?.toLowerCase().includes("instagram")) return 40;
    if (statusMessage?.toLowerCase().includes("youtube")) return 20;
    return 10;
  }, [ingesting, ready, videoA, videoB, statusMessage]);

  const isError =
    statusMessage &&
    (statusMessage.toLowerCase().includes("fail") ||
      statusMessage.toLowerCase().includes("error") ||
      statusMessage.toLowerCase().includes("offline") ||
      statusMessage.toLowerCase().includes("cannot reach") ||
      statusMessage === "Session not found");

  return (
    <div className="min-h-screen bg-zinc-50">
      <div className="mx-auto max-w-7xl px-4 py-6">
        <URLInputForm
          youtubeUrl={youtubeUrl}
          instagramUrl={instagramUrl}
          loading={ingesting}
          onYoutubeChange={setYoutubeUrl}
          onInstagramChange={setInstagramUrl}
          onSubmit={handleIngest}
        />

        <div className="mt-2 flex items-center gap-2 text-xs">
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              backendOnline === null ? "bg-zinc-300" : backendOnline ? "bg-emerald-500" : "bg-red-500"
            }`}
          />
          <span className="text-zinc-500">
            Backend {backendOnline === null ? "checking..." : backendOnline ? "online" : "offline"} ({BACKEND_URL})
          </span>
        </div>

        {ingesting && (
          <div className="mt-3">
            <div className="mb-1 flex items-center justify-between text-xs text-zinc-500">
              <span>Ingestion progress</span>
              <span>{ingestProgress}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-zinc-200">
              <div
                className="h-full rounded-full bg-indigo-600 transition-all duration-500"
                style={{ width: `${ingestProgress}%` }}
              />
            </div>
          </div>
        )}

        {statusMessage && (
          <p className={`mt-3 text-sm ${isError ? "text-red-600" : "text-zinc-600"}`}>{statusMessage}</p>
        )}

        <div className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.2fr)]">
          <VideoCard
            label="Video A · YouTube"
            video={videoA}
            loading={ingesting && !videoA}
            highlighted={highlight?.videoId === "A"}
            highlightRange={highlight?.videoId === "A" ? highlight.range : null}
          />
          <VideoCard
            label="Video B · Instagram"
            video={videoB}
            loading={ingesting && !videoB}
            highlighted={highlight?.videoId === "B"}
            highlightRange={highlight?.videoId === "B" ? highlight.range : null}
          />
          <ChatPanel sessionId={sessionId} ready={ready} onSourceClick={handleSourceClick} />
        </div>
      </div>
    </div>
  );
}
