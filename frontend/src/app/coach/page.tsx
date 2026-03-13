"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { api, ChatMessage, ConversationSummary, Briefing, BriefingChange } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import ReactMarkdown from "react-markdown";

function formatTime(dateStr: string) {
  const d = new Date(dateStr);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - d.getTime()) / 86400000);
  if (diffDays === 0) return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return d.toLocaleDateString([], { weekday: "short" });
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

interface MessageWithChanges {
  role: string;
  content: string;
  changes?: { tool: string; reason: string; result?: Record<string, unknown> }[];
}

function MarkdownContent({ content }: { content: string }) {
  return (
    <ReactMarkdown
      components={{
        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
        ul: ({ children }) => <ul className="list-disc ml-4 mb-2 space-y-0.5">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal ml-4 mb-2 space-y-0.5">{children}</ol>,
        li: ({ children }) => <li>{children}</li>,
        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
        em: ({ children }) => <em>{children}</em>,
        h1: ({ children }) => <h3 className="font-bold text-base mb-1 mt-2">{children}</h3>,
        h2: ({ children }) => <h3 className="font-bold text-base mb-1 mt-2">{children}</h3>,
        h3: ({ children }) => <h4 className="font-semibold text-sm mb-1 mt-2">{children}</h4>,
        h4: ({ children }) => <h4 className="font-semibold text-sm mb-1 mt-1">{children}</h4>,
        code: ({ children }) => <code className="bg-black/10 rounded px-1 py-0.5 text-xs">{children}</code>,
        blockquote: ({ children }) => <blockquote className="border-l-2 border-primary/30 pl-3 italic opacity-80 mb-2">{children}</blockquote>,
        hr: () => <hr className="my-2 border-border" />,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

function MessageBubble({ message }: { message: MessageWithChanges }) {
  const isUser = message.role === "user";
  const changes = message.changes || [];
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${
          isUser
            ? "bg-primary text-primary-foreground rounded-br-md whitespace-pre-wrap"
            : "bg-muted text-foreground rounded-bl-md"
        }`}
      >
        {isUser ? message.content : <MarkdownContent content={message.content} />}
        {changes.length > 0 && (
          <div className="mt-3 pt-2 border-t border-border/50 space-y-1">
            {changes.map((c, i) => {
              const style = CHANGE_STYLES[c.tool] || { label: c.tool, color: "bg-gray-100 text-gray-800 border-gray-200" };
              return (
                <div key={i} className="flex items-start gap-2 text-xs">
                  <span className={`px-1.5 py-0.5 rounded border text-[10px] font-medium shrink-0 ${style.color}`}>
                    {style.label}
                  </span>
                  <span className="opacity-70">{c.reason}</span>
                </div>
              );
            })}
          </div>
        )}
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

const CHANGE_STYLES: Record<string, { label: string; color: string }> = {
  create_workout: { label: "Added", color: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  move_workout: { label: "Moved", color: "bg-blue-100 text-blue-800 border-blue-200" },
  skip_workout: { label: "Skipped", color: "bg-amber-100 text-amber-800 border-amber-200" },
  delete_workout: { label: "Removed", color: "bg-red-100 text-red-800 border-red-200" },
  generate_training_plan: { label: "Plan Created", color: "bg-purple-100 text-purple-800 border-purple-200" },
};

function BriefingCard({ briefing, onDismiss, onAsk, onRegenerate, generating }: {
  briefing: Briefing;
  onDismiss: () => void;
  onAsk: (question: string) => void;
  onRegenerate: () => void;
  generating: boolean;
}) {
  const changes = briefing.changes_made || [];

  return (
    <Card className="border-primary/20 bg-primary/5">
      <CardContent className="pt-5 pb-4">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-2">
            <span className="text-lg">🌅</span>
            <h3 className="text-sm font-semibold">
              Daily Briefing
              <span className="ml-2 text-xs font-normal text-muted-foreground">
                {new Date(briefing.date + "T12:00:00").toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}
                {briefing.generated_at && (
                  <> at {new Date(briefing.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</>
                )}
              </span>
            </h3>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={onRegenerate}
              disabled={generating}
              className="text-muted-foreground hover:text-foreground p-0.5 transition-colors disabled:opacity-50"
              title="Regenerate briefing"
            >
              <svg className={`w-4 h-4 ${generating ? "animate-spin" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M1 4v6h6M23 20v-6h-6" />
                <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15" />
              </svg>
            </button>
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
        </div>

        {briefing.status === "pending" ? (
          <div className="space-y-2">
            <div className="h-3 bg-muted rounded animate-pulse w-full" />
            <div className="h-3 bg-muted rounded animate-pulse w-5/6" />
            <div className="h-3 bg-muted rounded animate-pulse w-4/6" />
            <p className="text-xs text-muted-foreground mt-3">Syncing data and generating your briefing...</p>
          </div>
        ) : (
          <>
            <div className="text-sm leading-relaxed max-h-[50vh] overflow-y-auto">
              <MarkdownContent content={briefing.content} />
            </div>

            {changes.length > 0 && (
              <div className="mt-4 p-3 rounded-lg bg-background/60 border border-border">
                <h4 className="text-xs font-semibold mb-2 text-muted-foreground uppercase tracking-wide">
                  Plan Changes Made
                </h4>
                <div className="space-y-1.5">
                  {changes.map((c, i) => {
                    const style = CHANGE_STYLES[c.tool] || { label: c.tool, color: "bg-gray-100 text-gray-800 border-gray-200" };
                    return (
                      <div key={i} className="flex items-start gap-2 text-xs">
                        <span className={`px-1.5 py-0.5 rounded border text-[10px] font-medium shrink-0 ${style.color}`}>
                          {style.label}
                        </span>
                        <span className="text-muted-foreground">{c.reason}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

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
          </>
        )}
      </CardContent>
    </Card>
  );
}

export default function CoachPage() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<(ChatMessage & { changes?: { tool: string; reason: string; result?: Record<string, unknown> }[] })[]>([]);
  const [streamingText, setStreamingText] = useState("");
  const [streamingToolActions, setStreamingToolActions] = useState<{ tool: string; reason: string; result?: Record<string, unknown> }[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [briefingLoading, setBriefingLoading] = useState(false);
  const [briefingDismissed, setBriefingDismissed] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [pastBriefings, setPastBriefings] = useState<Briefing[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [selectedPastBriefing, setSelectedPastBriefing] = useState<Briefing | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    api.getConversations().then(setConversations).catch(() => {});
    api.getBriefings(30).then(setPastBriefings).catch(() => {});
  }, []);

  const loadBriefing = useCallback(() => {
    setBriefingLoading(true);
    api
      .getBriefing()
      .then((b) => {
        setBriefing(b);
        // If pending, poll for completion
        if (b.status === "pending") {
          setTimeout(loadBriefing, 5000);
        }
      })
      .catch(() => {})
      .finally(() => setBriefingLoading(false));
  }, []);

  useEffect(() => {
    loadBriefing();
  }, [loadBriefing]);

  async function handleRegenerate() {
    setGenerating(true);
    try {
      await api.generateBriefing();
      setBriefing({ date: new Date().toISOString().split("T")[0], content: "Syncing data and generating your briefing...", status: "pending" });
      setBriefingDismissed(false);
      // Poll for completion
      const poll = setInterval(async () => {
        try {
          const b = await api.getBriefing();
          if (b.status !== "pending") {
            setBriefing(b);
            setGenerating(false);
            clearInterval(poll);
            api.getBriefings(30).then(setPastBriefings).catch(() => {});
          }
        } catch {
          clearInterval(poll);
          setGenerating(false);
        }
      }, 4000);
      setTimeout(() => { clearInterval(poll); setGenerating(false); }, 120000);
    } catch {
      setGenerating(false);
    }
  }

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingText, scrollToBottom]);

  async function loadConversation(id: string) {
    setActiveConversationId(id);
    setSidebarOpen(false);
    const msgs = await api.getConversation(id);
    setMessages(msgs);
    setStreamingText("");
  }

  function startNewConversation() {
    setActiveConversationId(crypto.randomUUID());
    setMessages([]);
    setStreamingText("");
    setInput("");
    setSidebarOpen(false);
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
    setStreamingToolActions([]);

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
      const toolActions: { tool: string; reason: string; result?: Record<string, unknown> }[] = [];

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
            } else if (data.type === "tool_action") {
              const style = CHANGE_STYLES[data.tool];
              const label = style?.label || data.tool;
              toolActions.push({ tool: data.tool, reason: data.reason, result: data.result });
              setStreamingToolActions([...toolActions]);
            } else if (data.type === "message_complete") {
              const finalContent = accumulated;
              const finalChanges = data.changes || [];
              setMessages((prev) => [
                ...prev,
                {
                  id: data.message_id,
                  role: "assistant",
                  content: finalContent,
                  created_at: new Date().toISOString(),
                  changes: finalChanges.length > 0 ? finalChanges : undefined,
                },
              ]);
              setStreamingText("");
              setStreamingToolActions([]);
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
      setStreamingToolActions([]);
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
  const showBriefing = briefing && briefing.status === "completed" && !briefingDismissed && !hasMessages;
  const showBriefingPending = briefing && briefing.status === "pending" && !briefingDismissed && !hasMessages;
  const showGenerateButton = (!briefing || briefing.status === "none") && !briefingDismissed && !hasMessages;

  const suggestions = [
    "How should I approach today's workout?",
    "Am I on track for my marathon goal?",
    "How is my recovery looking?",
    "Should I adjust my training this week?",
    "What should I eat before my run today?",
    "Am I overtraining?",
  ];

  return (
    <div className="flex h-[calc(100vh-3.5rem)] md:h-[calc(100vh-3.5rem)] -mt-6 -mx-4 mobile-chat-height">
      {/* Sidebar - overlay on mobile, inline on desktop */}
      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/30 z-40 md:hidden" onClick={() => setSidebarOpen(false)} />
      )}
      <div
        className={`${
          sidebarOpen ? "w-64 translate-x-0" : "w-0 -translate-x-full md:translate-x-0"
        } fixed md:relative z-50 md:z-auto h-full transition-all duration-200 border-r border-border bg-background md:bg-muted/30 flex flex-col overflow-hidden shrink-0`}
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
            <div className="flex flex-col items-center md:justify-center h-full text-center max-w-2xl mx-auto overflow-y-auto">
              {/* Completed briefing */}
              {showBriefing && (
                <div className="w-full mb-6">
                  <BriefingCard
                    briefing={briefing}
                    onDismiss={() => setBriefingDismissed(true)}
                    onAsk={(q) => handleSend(q)}
                    onRegenerate={handleRegenerate}
                    generating={generating}
                  />
                </div>
              )}

              {/* Pending briefing */}
              {showBriefingPending && (
                <div className="w-full mb-6">
                  <BriefingCard
                    briefing={briefing}
                    onDismiss={() => setBriefingDismissed(true)}
                    onAsk={(q) => handleSend(q)}
                    onRegenerate={handleRegenerate}
                    generating={generating}
                  />
                </div>
              )}

              {!showBriefing && !showBriefingPending && (
                <>
                  <h3 className="text-lg font-semibold mb-2">Your Personal Coach</h3>
                  <p className="text-sm text-muted-foreground max-w-md">
                    I know your training, recovery, and health data. Ask me anything about your
                    training, and I&apos;ll give you personalized advice.
                  </p>
                  {showGenerateButton && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="mt-4"
                      onClick={handleRegenerate}
                      disabled={generating}
                    >
                      {generating ? (
                        <>
                          <svg className="w-4 h-4 mr-2 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M1 4v6h6M23 20v-6h-6" />
                            <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15" />
                          </svg>
                          Generating...
                        </>
                      ) : (
                        "Generate Daily Briefing"
                      )}
                    </Button>
                  )}
                </>
              )}

              {/* Selected past briefing */}
              {selectedPastBriefing && (
                <div className="w-full mb-6">
                  <BriefingCard
                    briefing={selectedPastBriefing}
                    onDismiss={() => setSelectedPastBriefing(null)}
                    onAsk={(q) => handleSend(q)}
                    onRegenerate={handleRegenerate}
                    generating={generating}
                  />
                </div>
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

              {/* Past briefings history */}
              {pastBriefings.length > 0 && (
                <div className="w-full mt-6">
                  <button
                    onClick={() => setShowHistory(!showHistory)}
                    className="text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1 mx-auto"
                  >
                    <svg className={`w-3 h-3 transition-transform ${showHistory ? "rotate-180" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M6 9l6 6 6-6" />
                    </svg>
                    Past Briefings ({pastBriefings.length})
                  </button>
                  {showHistory && (
                    <div className="mt-3 space-y-1">
                      {pastBriefings.map((b) => (
                        <button
                          key={b.date}
                          onClick={() => setSelectedPastBriefing(b)}
                          className={`w-full text-left px-3 py-2 rounded-lg text-sm hover:bg-muted transition-colors flex items-center justify-between ${
                            selectedPastBriefing?.date === b.date ? "bg-muted" : ""
                          }`}
                        >
                          <span className="font-medium">
                            {new Date(b.date + "T12:00:00").toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}
                          </span>
                          {b.generated_at && (
                            <span className="text-xs text-muted-foreground">
                              {new Date(b.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                            </span>
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-3">
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
              {streamingText && (
                <MessageBubble message={{ role: "assistant", content: streamingText, changes: streamingToolActions }} />
              )}
              {!streamingText && streamingToolActions.length > 0 && (
                <div className="flex justify-start">
                  <div className="bg-muted rounded-2xl rounded-bl-md px-4 py-2.5 text-sm space-y-1">
                    {streamingToolActions.map((c, i) => {
                      const style = CHANGE_STYLES[c.tool] || { label: c.tool, color: "bg-gray-100 text-gray-800 border-gray-200" };
                      return (
                        <div key={i} className="flex items-center gap-2 text-xs">
                          <span className={`px-1.5 py-0.5 rounded border text-[10px] font-medium ${style.color}`}>
                            {style.label}
                          </span>
                          <span className="text-muted-foreground">{c.reason}</span>
                        </div>
                      );
                    })}
                    <p className="text-xs text-muted-foreground italic mt-1">Working on it...</p>
                  </div>
                </div>
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
