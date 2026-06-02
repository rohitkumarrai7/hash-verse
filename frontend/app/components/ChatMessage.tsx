import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import SourceBadge from "./SourceBadge";
import type { ChatMessage, SourceCitation } from "@/lib/types";

interface ChatMessageProps {
  message: ChatMessage;
  onSourceClick?: (source: SourceCitation) => void;
}

export default function ChatMessageItem({ message, onSourceClick }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[95%] rounded-2xl px-4 py-3 text-sm leading-6 ${
          isUser
            ? "bg-accent text-white"
            : "border border-border bg-surface text-foreground"
        }`}
      >
        {isUser ? (
          <p>{message.content}</p>
        ) : (
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content || " "}</ReactMarkdown>
          </div>
        )}

        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {message.sources.map((source, index) => (
              <SourceBadge
                key={`${source.video_id}-${source.chunk_index}-${index}`}
                source={source}
                onClick={onSourceClick}
              />
            ))}
          </div>
        )}

        {message.streaming && (
          <span className="ml-1 inline-block h-4 w-1 animate-pulse rounded-sm bg-accent" />
        )}
      </div>
    </div>
  );
}
