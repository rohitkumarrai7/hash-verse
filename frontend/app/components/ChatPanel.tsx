"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ChatMessageItem from "./ChatMessage";
import type { ChatMessage, SourceCitation } from "@/lib/types";
import { streamChat } from "@/lib/api";

interface ChatPanelProps {
  sessionId: string;
  ready: boolean;
  onSourceClick?: (source: SourceCitation) => void;
}

function useDebouncedValue<T>(value: T, delay: number) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}

export default function ChatPanel({ sessionId, ready, onSourceClick }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const debouncedInput = useDebouncedValue(input, 150);
  const listRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const suggestions = useMemo(
    () => [
      "Why did Video A get more engagement than Video B?",
      "What's the engagement rate of each?",
      "Compare the hooks in the first 5 seconds.",
      "Who is the creator of Video B and what's their follower count?",
      "Suggest improvements for B based on what worked in A.",
    ],
    [],
  );

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || !ready || sending) return;

      setSending(true);
      setInput("");

      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: trimmed,
      };

      const assistantId = crypto.randomUUID();
      setMessages((prev) => [
        ...prev,
        userMessage,
        { id: assistantId, role: "assistant", content: "", streaming: true, sources: [] },
      ]);

      abortRef.current?.abort();
      abortRef.current = new AbortController();

      try {
        await streamChat(
          sessionId,
          trimmed,
          (event) => {
            if (event.type === "token") {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantId ? { ...msg, content: msg.content + event.content } : msg,
                ),
              );
            }

            if (event.type === "sources") {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantId ? { ...msg, sources: event.sources } : msg,
                ),
              );
            }

            if (event.type === "done") {
              setMessages((prev) =>
                prev.map((msg) => (msg.id === assistantId ? { ...msg, streaming: false } : msg)),
              );
            }

            if (event.type === "error") {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantId
                    ? { ...msg, content: `Error: ${event.message}`, streaming: false }
                    : msg,
                ),
              );
            }
          },
          abortRef.current.signal,
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown chat error";
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantId ? { ...msg, content: `Error: ${message}`, streaming: false } : msg,
          ),
        );
      } finally {
        setSending(false);
      }
    },
    [ready, sending, sessionId],
  );

  return (
    <div className="card flex h-full min-h-[640px] flex-col overflow-hidden">
      <div className="border-b border-border bg-surface-muted px-4 py-3">
        <h2 className="text-base font-semibold text-foreground">Creator Intelligence Chat</h2>
        <p className="text-xs text-text-muted">Streaming RAG with source citations and memory</p>
      </div>

      <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <div className="space-y-3">
            <p className="text-sm text-text-muted">
              {ready
                ? "Ask a comparative question about Video A (YouTube) and Video B (Instagram)."
                : "Ingest both videos to start chatting."}
            </p>
            <div className="flex flex-wrap gap-2">
              {suggestions.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  disabled={!ready || sending}
                  onClick={() => sendMessage(suggestion)}
                  className="btn-secondary text-left"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message) => (
          <ChatMessageItem key={message.id} message={message} onSourceClick={onSourceClick} />
        ))}
      </div>

      <form
        className="border-t border-border bg-surface p-4"
        onSubmit={(event) => {
          event.preventDefault();
          sendMessage(debouncedInput || input);
        }}
      >
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            disabled={!ready || sending}
            placeholder={ready ? "Ask about engagement, hooks, creators..." : "Waiting for ingestion..."}
            className="input flex-1"
          />
          <button type="submit" disabled={!ready || sending || !input.trim()} className="btn-primary shrink-0">
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
