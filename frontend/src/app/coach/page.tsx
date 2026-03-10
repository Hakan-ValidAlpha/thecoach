"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { api, ChatMessage, ConversationSummary, Briefing } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

function formatTime(dateStr: string) {
  const d = new Date(dateStr);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - d.getTime()) / 86400000);
  if (diffDays === 0) return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return d.toLocaleDateString([], { weekday: "short" });
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

function MessageBubble({ message }: { message: { role: string; content: string } }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap ${
          isUser
            ? "bg-primary text-primary-foreground rounded-br-md"
            : "bg-muted text-foreground rounded-bl-md"
        }`}
      >
        {message.content}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="bg-muted rounded-2xl rounded-bl-md px-4 py-3 flex gap-1">
        <span className="w-2 h-2 bg-muted-foreground/40 rounded-full animate-bounce [animation-delay:0ms]" />
        <span className="w-2 h-2 bg-muted-foreground/40 rounded-full animate-bounce [animation-delay:150ms]" />
        <span className="w-2 h-2 bg-muted-foreground/40 rounded-full animate-bounce [animation-delay:300ms]" />
      </div>
    </div>
  );
}

function BriefingCard({ briefing, onDismiss, onAsk }: {
  briefing: Briefing;
  onDismiss: () => void;
  onAsk: (question: string) => void;
}) {
  return (
    <Card className="border-primary/20 bg-primary/5">
      <CardContent className="pt-5 pb-4">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-2">
            <span className="text-lg">🌅</span>
            <h3 className="text-sm font-semibold">Good Morning</h3>
          </div>
          <button
            onClick={onDismiss}
            className="text-muted-foreground hover:text-foreground p-0.5 transition-colors"
            title="Dismiss"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
        <p className="text-sm whitespace-pre-wrap leading-relaxed">{briefing.content}</p>
        <div className="mt-4 flex gap-2">
          <Button
            size="sm"
            variant="outline"
            className="text-xs"
            onClick={() => onAsk("Tell me more about today's workout — what should I focus on?")}
          >
            More about today&apos;s workout
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="text-xs"
            onClick={() => onAsk("How am I progressing toward my goal?")}
          >
            Check my progress
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function CoachPage() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streamingText, setStreamingText] = useState("");
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [briefingLoading, setBriefingLoading] = useState(false);
  const [briefingDismissed, setBriefingDismissed] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    api.getConversations().then(setConversations).catch(() => {});
  }, []);

  // Load morning briefing on mount (only once per day)
  useEffect(() => {
    const today = new Date().toISOString().split("T")[0];
    const lastBriefingDate = sessionStorage.getItem("lastBriefingDate");
    const cachedBriefing = sessionStorage.getItem("briefingContent");

    if (lastBriefingDate === today && cachedBriefing) {
      setBriefing(JSON.parse(cachedBriefing));
      return;
    }

    setBriefingLoading(true);
    api
      .getBriefing()
      .then((b) => {
        setBriefing(b);
        sessionStorage.setItem("lastBriefingDate", today);
        sessionStorage.setItem("briefingContent", JSON.stringify(b));
      })
      .catch(() => {})
      .finally(() => setBriefingLoading(false));
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingText, scrollToBottom]);

  async function loadConversation(id: string) {
    setActiveConversationId(id);
    const msgs = await api.getConversation(id);
    setMessages(msgs);
    setStreamingText("");
  }

  function startNewConversation() {
    setActiveConversationId(crypto.randomUUID());
    setMessages([]);
    setStreamingText("");
    setInput("");
    textareaRef.current?.focus();
  }

  async function deleteConversation(id: string) {
    await api.deleteConversation(id);
    setConversations((prev) => prev.filter((c) => c.conversation_id !== id));
    if (activeConversationId === id) {
      setActiveConversationId(null);
      setMessages([]);
    }
  }

  async function handleSend(overrideText?: string) {
    const text = (overrideText || input).trim();
    if (!text || isStreaming) return;

    let convId = activeConversationId;
    if (!convId) {
      convId = crypto.randomUUID();
      setActiveConversationId(convId);
    }

    const userMsg: ChatMessage = {
      id: Date.now(),
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsStreaming(true);
    setStreamingText("");

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    try {
      const response = await api.streamChat(convId, text);
      if (!response.ok) {
        const errText = await response.text();
        throw new Error(errText);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let accumulated = "";
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === "content_delta") {
              accumulated += data.text;
              setStreamingText(accumulated);
            } else if (data.type === "message_complete") {
              setMessages((prev) => [
                ...prev,
                {
                  id: data.message_id,
                  role: "assistant",
                  content: accumulated,
                  created_at: new Date().toISOString(),
                },
              ]);
              setStreamingText("");
            } else if (data.type === "error") {
              setStreamingText(`Error: ${data.text}`);
            }
          } catch {}
        }
      }

      api.getConversations().then(setConversations).catch(() => {});
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : "Failed to send message";
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: "assistant",
          content: `Error: ${errMsg}`,
          created_at: new Date().toISOString(),
        },
      ]);
      setStreamingText("");
    } finally {
      setIsStreaming(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleTextareaInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value);
    const ta = e.target;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 120) + "px";
  }

  const hasMessages = messages.length > 0 || streamingText;
  const showBriefing = briefing && !briefingDismissed && !hasMessages;

  const suggestions = [
    "How should I approach today's workout?",
    "Am I on track for my marathon goal?",
    "How is my recovery looking?",
    "Should I adjust my training this week?",
    "What should I eat before my run today?",
    "Am I overtraining?",
  ];

  return (
    <div className="flex h-[calc(100vh-3.5rem)] -mt-6 -mx-4">
      {/* Sidebar */}
      <div
        className={`${
          sidebarOpen ? "w-64" : "w-0"
        } transition-all duration-200 border-r border-border bg-muted/30 flex flex-col overflow-hidden shrink-0`}
      >
        <div className="p-3 border-b border-border">
          <Button onClick={startNewConversation} size="sm" className="w-full">
            New Chat
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {conversations.map((c) => (
            <div
              key={c.conversation_id}
              className={`group flex items-center gap-1 px-3 py-2.5 cursor-pointer hover:bg-muted transition-colors ${
                activeConversationId === c.conversation_id ? "bg-muted" : ""
              }`}
              onClick={() => loadConversation(c.conversation_id)}
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate">{c.title}</p>
                <p className="text-xs text-muted-foreground">{formatTime(c.last_message_at)}</p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  deleteConversation(c.conversation_id);
                }}
                className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-red-500 p-1 transition-opacity"
                title="Delete conversation"
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>
          ))}
          {conversations.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-4">No conversations yet</p>
          )}
        </div>
      </div>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="flex items-center gap-2 px-4 py-2 border-b border-border shrink-0">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="text-muted-foreground hover:text-foreground p-1"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 12h18M3 6h18M3 18h18" />
            </svg>
          </button>
          <h2 className="text-sm font-medium">Coach</h2>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4">
          {!hasMessages ? (
            <div className="flex flex-col items-center justify-center h-full text-center max-w-2xl mx-auto">
              {/* Morning briefing */}
              {briefingLoading && (
                <div className="w-full mb-6">
                  <Card className="border-primary/20 bg-primary/5">
                    <CardContent className="pt-5 pb-4">
                      <div className="flex items-center gap-2 mb-3">
                        <span className="text-lg">🌅</span>
                        <h3 className="text-sm font-semibold">Loading your morning briefing...</h3>
                      </div>
                      <div className="space-y-2">
                        <div className="h-3 bg-muted rounded animate-pulse w-full" />
                        <div className="h-3 bg-muted rounded animate-pulse w-5/6" />
                        <div className="h-3 bg-muted rounded animate-pulse w-4/6" />
                      </div>
                    </CardContent>
                  </Card>
                </div>
              )}
              {showBriefing && (
                <div className="w-full mb-6">
                  <BriefingCard
                    briefing={briefing}
                    onDismiss={() => setBriefingDismissed(true)}
                    onAsk={(q) => handleSend(q)}
                  />
                </div>
              )}

              {!showBriefing && !briefingLoading && (
                <>
                  <h3 className="text-lg font-semibold mb-2">Your Personal Coach</h3>
                  <p className="text-sm text-muted-foreground max-w-md">
                    I know your training, recovery, and health data. Ask me anything about your
                    running journey, and I&apos;ll give you personalized advice.
                  </p>
                </>
              )}

              <div className="mt-6 flex flex-wrap gap-2 justify-center max-w-lg">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => {
                      setInput(suggestion);
                      textareaRef.current?.focus();
                    }}
                    className="text-xs px-3 py-1.5 rounded-full border border-border hover:bg-muted transition-colors text-muted-foreground"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-3">
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
              {streamingText && (
                <MessageBubble message={{ role: "assistant", content: streamingText }} />
              )}
              {isStreaming && !streamingText && <TypingIndicator />}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="border-t border-border px-4 py-3 shrink-0">
          <div className="max-w-3xl mx-auto flex gap-2">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={handleTextareaInput}
              onKeyDown={handleKeyDown}
              placeholder="Ask your coach..."
              rows={1}
              disabled={isStreaming}
              className="flex-1 resize-none rounded-xl border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
            />
            <Button
              onClick={() => handleSend()}
              disabled={!input.trim() || isStreaming}
              size="sm"
              className="self-end rounded-xl px-4"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
              </svg>
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
