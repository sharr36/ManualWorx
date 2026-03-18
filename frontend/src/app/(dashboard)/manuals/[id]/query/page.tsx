"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import {
  AlertTriangle,
  Clock,
  ChevronDown,
  ChevronUp,
  MessageSquare,
  Plus,
  Send,
  Shield,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { ChatMessage } from "@/components/query/chat-message";
import { SourceCitation } from "@/components/query/source-citation";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import type { ConfidenceLevel, Claim, RefinementSuggestion } from "@/types";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  queryId?: string;
  confidence?: number;
  confidenceLevel?: ConfidenceLevel;
  sources?: Source[];
  latency_ms?: number;
  claims?: Claim[];
  contradictionCount?: number;
  safetyClaims?: number;
  refinements?: RefinementSuggestion[];
}

interface Source {
  page_id: string;
  page_number: number;
  classification: string;
  text_preview: string;
  relevance_score: number;
  manual_title?: string;
}

interface HistoryItem {
  id: string;
  query_text: string;
  query_mode: string;
  response_preview: string;
  latency_ms?: number;
  created_at?: string;
}

const EXAMPLE_QUERIES = [
  "What's the torque spec for the main relief valve?",
  "Trace the hydraulic flow from pump to cylinder",
  "How do I replace the fuel injectors?",
  "What causes low hydraulic pressure?",
];

const MODE_MAP: Record<string, string> = {
  Auto: "auto",
  "Q&A": "qa",
  Troubleshoot: "troubleshoot",
  Diagram: "diagram",
  Procedure: "procedure",
};

const CLAIM_TYPE_COLORS: Record<string, string> = {
  spec: "bg-blue-100 text-blue-800",
  description: "bg-slate-100 text-slate-700",
  procedure_step: "bg-emerald-100 text-emerald-800",
  warning: "bg-amber-100 text-amber-800",
};

function ClaimBreakdown({
  claims,
  contradictionCount,
  safetyClaims,
}: {
  claims: Claim[];
  contradictionCount: number;
  safetyClaims: number;
}) {
  const [expanded, setExpanded] = useState(false);

  if (claims.length === 0) return null;

  const avgConfidence = Math.round(
    (claims.reduce((s, c) => s + c.confidence, 0) / claims.length) * 100
  );

  return (
    <div className="mt-2 rounded-lg border bg-slate-50 p-3">
      <button
        className="flex w-full items-center justify-between text-xs"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="font-medium">
          {claims.length} claims analyzed &middot; {avgConfidence}% avg
          confidence
          {safetyClaims > 0 && (
            <span className="ml-2 inline-flex items-center gap-0.5 text-amber-600">
              <Shield className="h-3 w-3" />
              {safetyClaims} safety-critical
            </span>
          )}
          {contradictionCount > 0 && (
            <span className="ml-2 inline-flex items-center gap-0.5 text-red-600">
              <AlertTriangle className="h-3 w-3" />
              {contradictionCount} contradictions
            </span>
          )}
        </span>
        {expanded ? (
          <ChevronUp className="h-3.5 w-3.5" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5" />
        )}
      </button>

      {expanded && (
        <div className="mt-2 space-y-1.5">
          {claims.map((claim, i) => (
            <div
              key={i}
              className="flex items-start gap-2 rounded border bg-white p-2 text-xs"
            >
              <div
                className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${
                  claim.confidence >= 0.8
                    ? "bg-emerald-500"
                    : claim.confidence >= 0.6
                      ? "bg-amber-500"
                      : "bg-red-500"
                }`}
                title={`${Math.round(claim.confidence * 100)}%`}
              />
              <div className="flex-1">
                <p>{claim.claim_text}</p>
                <div className="mt-1 flex flex-wrap items-center gap-1">
                  <span
                    className={`rounded px-1 py-0.5 text-[10px] font-medium ${
                      CLAIM_TYPE_COLORS[claim.claim_type] || CLAIM_TYPE_COLORS.description
                    }`}
                  >
                    {claim.claim_type.replace("_", " ")}
                  </span>
                  <span className="text-[10px] text-muted-foreground">
                    {Math.round(claim.confidence * 100)}%
                  </span>
                  {claim.safety_critical && (
                    <Shield className="h-3 w-3 text-amber-500" />
                  )}
                  {claim.corroborated && (
                    <span className="text-[10px] text-emerald-600">
                      corroborated
                    </span>
                  )}
                  {claim.source_pages.length > 0 && (
                    <span className="text-[10px] text-muted-foreground">
                      p.{claim.source_pages.join(", p.")}
                    </span>
                  )}
                </div>
                {claim.contradictions.length > 0 && (
                  <div className="mt-1 rounded bg-red-50 px-1.5 py-0.5 text-[10px] text-red-700">
                    <AlertTriangle className="mr-0.5 inline h-2.5 w-2.5" />
                    {claim.contradictions[0]}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function RefinementChips({
  refinements,
  onSelect,
}: {
  refinements: RefinementSuggestion[];
  onSelect: (query: string) => void;
}) {
  if (refinements.length === 0) return null;

  return (
    <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3">
      <p className="mb-2 flex items-center gap-1 text-xs font-medium text-emerald-800">
        <Sparkles className="h-3 w-3" />
        Try a more specific query:
      </p>
      <div className="flex flex-wrap gap-1.5">
        {refinements.map((r, i) => (
          <button
            key={i}
            className="rounded-full border border-emerald-300 bg-white px-2.5 py-1 text-xs text-emerald-800 transition hover:bg-emerald-100"
            onClick={() => onSelect(r.query)}
            title={r.reason}
          >
            {r.query}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function ManualQueryPage() {
  const params = useParams();
  const manualId = params.id as string;

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState("auto");
  const [lastSources, setLastSources] = useState<Source[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [sessionQueryId, setSessionQueryId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api
      .get<HistoryItem[]>("/api/query/history?limit=30")
      .then(setHistory)
      .catch((e: Error) => toast.error(e.message || "Failed to load history"));
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadHistoryQuery = useCallback(async (queryId: string) => {
    try {
      const result = await api.get<{
        query_text: string;
        response_text: string;
        sources?: Source[];
      }>(`/api/query/${queryId}`);
      setMessages([
        {
          id: `user-${queryId}`,
          role: "user",
          content: result.query_text,
        },
        {
          id: queryId,
          role: "assistant",
          content: result.response_text,
          sources: result.sources,
        },
      ]);
      setLastSources(result.sources || []);
      setShowHistory(false);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to load query");
    }
  }, []);

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

      const assistantId = `assistant-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        { id: assistantId, role: "assistant", content: "" },
      ]);

      try {
        const isFollowup = sessionQueryId && messages.length > 0;
        const streamPath = isFollowup
          ? `/api/query/${sessionQueryId}/followup/stream`
          : "/api/query/stream";
        const streamBody = isFollowup
          ? { query_text: queryText.trim() }
          : { query_text: queryText.trim(), query_mode: mode, manual_ids: [manualId] };
        await api.stream(
          streamPath,
          streamBody,
          // onToken
          (text) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: m.content + text }
                  : m
              )
            );
          },
          // onDone
          (data) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      confidence: data.confidence_score
                        ? Math.round((data.confidence_score as number) * 100)
                        : undefined,
                      confidenceLevel: data.confidence_level as
                        | ConfidenceLevel
                        | undefined,
                      sources: data.sources as Source[] | undefined,
                      latency_ms: data.latency_ms as number | undefined,
                    }
                  : m
              )
            );
            setLastSources((data.sources as Source[]) || []);
            api
              .get<HistoryItem[]>("/api/query/history?limit=30")
              .then(setHistory)
              .catch(() => {});
          },
          // onError
          (error) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: `Error: ${error}` }
                  : m
              )
            );
          },
          // onClaims
          (data) => {
            const qid = data.query_id as string | undefined;
            if (qid) setSessionQueryId(qid);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      queryId: qid,
                      claims: data.claims as Claim[] | undefined,
                      contradictionCount: data.contradiction_count as
                        | number
                        | undefined,
                      safetyClaims: data.safety_claims as number | undefined,
                      refinements: data.refinements as
                        | RefinementSuggestion[]
                        | undefined,
                      confidence: data.overall_confidence
                        ? Math.round(
                            (data.overall_confidence as number) * 100
                          )
                        : m.confidence,
                    }
                  : m
              )
            );
          }
        );
      } catch (err: unknown) {
        const detail =
          err && typeof err === "object" && "detail" in err
            ? (err as { detail: string }).detail
            : "Failed to get response";
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: `Error: ${detail}` }
              : m
          )
        );
      } finally {
        setLoading(false);
        textareaRef.current?.focus();
      }
    },
    [loading, manualId, mode, messages, sessionQueryId]
  );

  const handleGenerateDoc = useCallback(
    async (queryId: string, docType: string) => {
      try {
        await api.post("/api/documents/generate", {
          query_id: queryId,
          doc_type: docType,
          format: "pdf",
        });
        window.location.href = "/documents";
      } catch (e: unknown) {
        toast.error(e instanceof Error ? e.message : "Failed to generate document");
      }
    },
    []
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
    <div className="flex h-[calc(100vh-12rem)] gap-4">
      {/* History sidebar */}
      {showHistory && (
        <div className="w-64 shrink-0 overflow-y-auto border-r pr-3">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold">History</h3>
            <Button
              variant="ghost"
              size="sm"
              className="text-xs"
              onClick={() => setShowHistory(false)}
            >
              Close
            </Button>
          </div>
          {history.length > 0 ? (
            <div className="space-y-1">
              {history.map((item) => (
                <button
                  key={item.id}
                  className="w-full rounded-md px-2 py-2 text-left transition hover:bg-slate-50"
                  onClick={() => loadHistoryQuery(item.id)}
                >
                  <p className="line-clamp-1 text-xs font-medium">
                    {item.query_text}
                  </p>
                  <p className="line-clamp-1 text-[10px] text-muted-foreground">
                    {item.response_preview}
                  </p>
                  {item.created_at && (
                    <p className="mt-0.5 text-[10px] text-muted-foreground">
                      {new Date(item.created_at).toLocaleDateString()}
                    </p>
                  )}
                </button>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              No previous queries.
            </p>
          )}
        </div>
      )}

      {/* Chat area */}
      <div className="flex flex-1 flex-col">
        {/* Messages */}
        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {messages.length === 0 && (
            <>
              <EmptyState
                icon={MessageSquare}
                title="Ask anything about this manual"
                description="Get answers with page references, confidence scores, and spec values — backed by this service manual."
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
            <div key={msg.id}>
              <ChatMessage
                role={msg.role}
                content={msg.content}
                confidence={msg.confidence}
                confidenceLevel={msg.confidenceLevel}
                latency_ms={msg.latency_ms}
                sources={msg.sources?.map(
                  (s) => `p.${s.page_number + 1} (${s.classification})`
                )}
                onGenerateDoc={
                  msg.role === "assistant" && msg.queryId
                    ? (docType) => handleGenerateDoc(msg.queryId!, docType)
                    : undefined
                }
              />
              {msg.role === "assistant" && msg.claims && msg.claims.length > 0 && (
                <div className="ml-0 max-w-[80%]">
                  <ClaimBreakdown
                    claims={msg.claims}
                    contradictionCount={msg.contradictionCount || 0}
                    safetyClaims={msg.safetyClaims || 0}
                  />
                </div>
              )}
              {msg.role === "assistant" &&
                msg.refinements &&
                msg.refinements.length > 0 && (
                  <div className="ml-0 max-w-[80%]">
                    <RefinementChips
                      refinements={msg.refinements}
                      onSelect={(q) => {
                        setInput(q);
                        textareaRef.current?.focus();
                      }}
                    />
                  </div>
                )}
            </div>
          ))}

          {loading && messages[messages.length - 1]?.content === "" && (
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
          {/* Mode + actions row */}
          <div className="mb-2 flex items-center gap-2 flex-wrap">
            <div className="hidden gap-1 sm:flex">
              <Button
                variant="ghost"
                size="sm"
                className="text-xs"
                onClick={() => {
                  setMessages([]);
                  setSessionQueryId(null);
                  setLastSources([]);
                }}
                title="New conversation"
              >
                <Plus className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="text-xs"
                onClick={() => setShowHistory(!showHistory)}
                title="Query history"
              >
                <Clock className="h-3.5 w-3.5" />
              </Button>

              <div className="h-4 w-px bg-border" />

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
            </div>
          </div>

          <div className="flex gap-2">
            <textarea
              ref={textareaRef}
              placeholder="Ask about this manual..."
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

      {/* Context panel */}
      <div className="hidden w-72 flex-col border-l pl-4 lg:flex">
        <h3 className="mb-3 text-sm font-semibold">Sources</h3>
        <div className="space-y-3">
          {lastSources.length > 0 ? (
            <div
              className="space-y-2 overflow-y-auto"
              style={{ maxHeight: "60vh" }}
            >
              {lastSources.map((source) => (
                <SourceCitation
                  key={source.page_id}
                  pageNumber={source.page_number + 1}
                  classification={source.classification}
                  textPreview={source.text_preview}
                  relevanceScore={source.relevance_score}
                  manualTitle={source.manual_title}
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
  );
}
