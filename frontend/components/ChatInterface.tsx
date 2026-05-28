"use client";

// =============================================================================
// DevBrain AI — Chat Interface
// Reusable chat component for the interview simulator and any conversational UI.
// Auto-scrolls to latest message. Typing indicator. Disabled when complete.
// =============================================================================

import {
  useRef,
  useEffect,
  useState,
  KeyboardEvent,
  FormEvent,
} from "react";
import { Send, Bot, User, Lock } from "lucide-react";
import type { InterviewMessage } from "@/lib/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
}

interface ChatInterfaceProps {
  messages: ChatMessage[];
  onSend: (message: string) => void;
  isLoading?: boolean;
  sessionComplete?: boolean;
  placeholder?: string;
  className?: string;
  /** If provided, shows at top of chat */
  headerSlot?: React.ReactNode;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTimestamp(iso?: string): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

/** Convert newlines and simple backtick code to HTML-safe JSX */
function renderContent(text: string) {
  // Split on code blocks (```...```) and inline code (`...`)
  const parts = text.split(/(```[\s\S]*?```|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith("```") && part.endsWith("```")) {
      const code = part.slice(3, -3).replace(/^\w*\n/, ""); // strip lang hint
      return (
        <pre
          key={i}
          className="mt-2 mb-2 bg-[#0f1117] border border-[#2d3148] rounded-lg
                     p-3 overflow-x-auto text-xs font-mono text-green-300"
        >
          {code}
        </pre>
      );
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code
          key={i}
          className="bg-[#0f1117] border border-[#2d3148] rounded px-1 py-0.5
                     text-xs font-mono text-[#818cf8]"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    // Plain text: preserve line breaks
    return (
      <span key={i}>
        {part.split("\n").map((line, j, arr) => (
          <span key={j}>
            {line}
            {j < arr.length - 1 && <br />}
          </span>
        ))}
      </span>
    );
  });
}

// ---------------------------------------------------------------------------
// Typing indicator
// ---------------------------------------------------------------------------

function TypingIndicator() {
  return (
    <div className="flex items-start gap-2.5">
      <div className="w-7 h-7 rounded-full bg-[#6366f1]/20 flex items-center justify-center shrink-0 mt-0.5">
        <Bot size={14} className="text-[#818cf8]" />
      </div>
      <div className="bg-[#6366f1]/10 border border-[#6366f1]/20 rounded-2xl rounded-tl-sm px-4 py-3">
        <div className="flex items-center gap-1">
          <span className="typing-dot w-1.5 h-1.5 rounded-full bg-[#818cf8]" />
          <span className="typing-dot w-1.5 h-1.5 rounded-full bg-[#818cf8]" />
          <span className="typing-dot w-1.5 h-1.5 rounded-full bg-[#818cf8]" />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Message bubble
// ---------------------------------------------------------------------------

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div
      className={`flex items-start gap-2.5 fade-in ${
        isUser ? "flex-row-reverse" : "flex-row"
      }`}
    >
      {/* Avatar */}
      <div
        className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5
          ${isUser
            ? "bg-[#2d3148]"
            : "bg-[#6366f1]/20"
          }`}
      >
        {isUser ? (
          <User size={14} className="text-gray-400" />
        ) : (
          <Bot size={14} className="text-[#818cf8]" />
        )}
      </div>

      {/* Bubble */}
      <div
        className={`max-w-[78%] rounded-2xl px-4 py-3 text-sm leading-relaxed
          ${isUser
            ? "bg-[#2d3148] text-gray-100 rounded-tr-sm"
            : "bg-[#6366f1]/10 border border-[#6366f1]/20 text-gray-200 rounded-tl-sm"
          }`}
      >
        <div>{renderContent(message.content)}</div>
        {message.timestamp && (
          <p className={`text-[10px] mt-1.5 ${isUser ? "text-gray-500 text-right" : "text-gray-600"}`}>
            {formatTimestamp(message.timestamp)}
          </p>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function ChatInterface({
  messages,
  onSend,
  isLoading = false,
  sessionComplete = false,
  placeholder = "Type a message…",
  className = "",
  headerSlot,
}: ChatInterfaceProps) {
  const [input, setInput] = useState("");
  const bottomRef         = useRef<HTMLDivElement>(null);
  const inputRef          = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll on new messages or typing indicator
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Focus input on mount
  useEffect(() => {
    if (!sessionComplete) inputRef.current?.focus();
  }, [sessionComplete]);

  const handleSubmit = (e?: FormEvent) => {
    e?.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isLoading || sessionComplete) return;
    onSend(trimmed);
    setInput("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends; Shift+Enter adds newline
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const canSend = input.trim().length > 0 && !isLoading && !sessionComplete;

  return (
    <div className={`flex flex-col bg-[#0f1117] rounded-xl overflow-hidden ${className}`}>

      {/* Header slot */}
      {headerSlot && (
        <div className="border-b border-[#2d3148] px-4 py-3">
          {headerSlot}
        </div>
      )}

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-5 space-y-4 min-h-0">
        {messages.length === 0 && !isLoading && (
          <div className="flex flex-col items-center justify-center h-full gap-3 py-10 text-center">
            <div className="w-12 h-12 rounded-full bg-[#6366f1]/10 flex items-center justify-center">
              <Bot size={22} className="text-[#6366f1]" />
            </div>
            <p className="text-sm text-gray-500 max-w-xs">
              The conversation will appear here. Start by sending a message.
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}

        {isLoading && <TypingIndicator />}

        {sessionComplete && (
          <div className="flex items-center justify-center gap-2 py-3 text-xs text-gray-500">
            <Lock size={12} />
            Session complete — thanks for participating!
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="border-t border-[#2d3148] px-4 py-3">
        {sessionComplete ? (
          <div className="flex items-center justify-center gap-2 py-2 text-sm text-gray-500">
            <Lock size={14} />
            This session has ended.
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex items-end gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              rows={1}
              disabled={isLoading}
              className="flex-1 input-base resize-none min-h-[42px] max-h-[120px] py-2.5
                         text-sm leading-snug overflow-y-auto
                         disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ height: "auto" }}
              onInput={(e) => {
                const el = e.currentTarget;
                el.style.height = "auto";
                el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
              }}
            />
            <button
              type="submit"
              disabled={!canSend}
              className={`
                w-10 h-10 rounded-lg flex items-center justify-center shrink-0
                transition-all duration-200
                ${canSend
                  ? "bg-[#6366f1] hover:bg-[#5254cc] text-white"
                  : "bg-[#2d3148] text-gray-600 cursor-not-allowed"
                }
              `}
              aria-label="Send message"
            >
              <Send size={16} />
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

// Re-export the InterviewMessage-compatible type alias for Part 5B convenience
export type { ChatMessage as ChatMessageType };