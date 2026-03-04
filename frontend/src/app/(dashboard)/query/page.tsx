"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MessageSquare, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { ChatMessage } from "@/components/query/chat-message";
import { SourceCitation } from "@/components/query/source-citation";
import { api } from "@/lib/api-client";
import type { Manual, QueryMode, ConfidenceLevel } from "@/types";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  confidence?: number;
  confidenceLevel?: ConfidenceLevel;
  sources?: Source[];
  latency_ms?: number;
}

interface Source {
  page_id: string;
  page_number: number;
  classification: string;
  text_preview: string;
  relevance_score: number;
  manual_title?: string;
}

interface QueryApiResponse {
  id: string;
  session_id?: string;
  response_text: string;
  confidence_score?: number;
  confidence_level?: string;
  sources?: Source[];
  model_used?: string;
  latency_ms?: number;
}

const EXAMPLE_QUERIES = [
  "What's the torque spec for the main relief valve?",
  "Trace the hydraulic flow from pump to cylinder",
  "How do I replace the fuel injectors?",
  "What causes low hydraulic pressure?",
];

const MODE_MAP: Record<string, string> = {
  "Q&A": "qa",
  Troubleshoot: "troubleshoot",
};

export default function QueryPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [manuals, setManuals] = useState<Manual[]>([]);
  const [selectedManual, setSelectedManual] = useState<string>("");
  const [mode, setMode] = useState("qa");
  const [lastSources, setLastSources] = useState<Source[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api
      .get<Manual[]>("/api/manuals")
      .then((data) => {
        const ready = data.filter((m) => m.upload_status === "ready");
        setManuals(ready);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const submitQuery = useCallback(
    async (queryText: string) => {
      if (!queryText.trim() || loading) return;

      const userMsg: Message = {
        id: `user-${Date.now()}`,
        role: "user",
        content: queryText.trim(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setLoading(true);

      try {
        const manual_ids = selectedManual ? [selectedManual] : undefined;
        const result = await api.post<QueryApiResponse>("/api/query", {
          query_text: queryText.trim(),
          query_mode: mode,
          manual_ids,
        });

        const assistantMsg: Message = {
          id: result.id,
          role: "assistant",
          content: result.response_text,
          confidence: result.confidence_score
            ? Math.round(result.confidence_score * 100)
            : undefined,
          confidenceLevel: result.confidence_level as ConfidenceLevel | undefined,
          sources: result.sources,
          latency_ms: result.latency_ms,
        };
        setMessages((prev) => [...prev, assistantMsg]);
        setLastSources(result.sources || []);
      } catch (err: any) {
        setMessages((prev) => [
          ...prev,
          {
            id: `error-${Date.now()}`,
            role: "assistant",
            content: `Error: ${err.detail || "Failed to get response"}`,
          },
        ]);
      } finally {
        setLoading(false);
        textareaRef.current?.focus();
      }
    },
    [loading, selectedManual, mode]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        submitQuery(input);
      }
    },
    [input, submitQuery]
  );

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      {/* Chat area */}
      <div className="flex flex-1 flex-col">
        {/* Messages */}
        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {messages.length === 0 && (
            <>
              <EmptyState
                icon={MessageSquare}
                title="Ask anything about your equipment manuals"
                description="Get answers with page references, confidence scores, and spec values — all backed by your actual service manuals."
              />
              <div className="flex flex-wrap justify-center gap-2">
                {EXAMPLE_QUERIES.map((q) => (
                  <button
                    key={q}
                    className="rounded-full border bg-white px-3 py-1.5 text-xs text-slate-600 transition hover:bg-slate-50"
                    onClick={() => {
                      setInput(q);
                      textareaRef.current?.focus();
                    }}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </>
          )}

          {messages.map((msg) => (
            <ChatMessage
              key={msg.id}
              role={msg.role}
              content={msg.content}
              confidence={msg.confidence}
              confidenceLevel={msg.confidenceLevel}
              sources={msg.sources?.map(
                (s) => `p.${s.page_number + 1} (${s.classification})`
              )}
            />
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="max-w-[80%] space-y-2 rounded-2xl rounded-bl-md border bg-white px-4 py-3">
                <Skeleton className="h-4 w-64" />
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-4 w-56" />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input bar */}
        <div className="border-t p-4">
          <div className="flex gap-2">
            <div className="hidden gap-1 sm:flex">
              {Object.entries(MODE_MAP).map(([label, value]) => (
                <Button
                  key={label}
                  variant={mode === value ? "default" : "ghost"}
                  size="sm"
                  className="text-xs"
                  onClick={() => setMode(value)}
                >
                  {label}
                </Button>
              ))}
              {["Diagram", "Procedure"].map((label) => (
                <Button
                  key={label}
                  variant="ghost"
                  size="sm"
                  disabled
                  className="text-xs"
                >
                  {label}
                </Button>
              ))}
            </div>
            <div className="flex flex-1 gap-2">
              <textarea
                ref={textareaRef}
                placeholder="Ask about your equipment manuals..."
                className="flex-1 resize-none rounded-lg border bg-white px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-emerald-600"
                rows={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={loading}
              />
              <Button
                size="icon"
                disabled={!input.trim() || loading}
                onClick={() => submitQuery(input)}
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Context panel */}
      <div className="hidden w-72 flex-col border-l pl-4 lg:flex">
        <h3 className="mb-3 text-sm font-semibold">Context</h3>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-muted-foreground">Manual</label>
            <select
              className="mt-1 w-full rounded-md border bg-white px-2 py-1.5 text-sm"
              value={selectedManual}
              onChange={(e) => setSelectedManual(e.target.value)}
            >
              <option value="">All manuals</option>
              {manuals.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.title}
                </option>
              ))}
            </select>
          </div>
          <div className="border-t pt-3">
            <h4 className="mb-2 text-xs font-medium text-muted-foreground">
              Sources
            </h4>
            {lastSources.length > 0 ? (
              <div className="space-y-2 overflow-y-auto" style={{ maxHeight: "50vh" }}>
                {lastSources.map((source) => (
                  <SourceCitation
                    key={source.page_id}
                    pageNumber={source.page_number + 1}
                    classification={source.classification}
                    textPreview={source.text_preview}
                  />
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                Source pages will appear here after querying.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
