"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  BookOpen,
  FileText,
  Image as ImageIcon,
  Loader2,
  RefreshCw,
  Search,
  Trash2,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ComingSoon } from "@/components/ui/coming-soon";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import type { CoverageAnalysis, GapAnalysis, InferredComponent, Manual, Page } from "@/types";

interface ManualDetail extends Manual {
  pages_processed?: number;
}

const statusColors: Record<string, string> = {
  pending: "bg-slate-400",
  processing: "bg-amber-500",
  ready: "bg-emerald-600",
  failed: "bg-red-600",
};

const classificationLabels: Record<string, string> = {
  text: "Text",
  hydraulic_schematic: "Hydraulic Schematic",
  electrical_diagram: "Electrical Diagram",
  parts_exploded_view: "Parts Exploded View",
  torque_spec_table: "Torque Spec Table",
  diagnostic_flowchart: "Diagnostic Flowchart",
  wiring_harness: "Wiring Harness",
  general_illustration: "General Illustration",
};

export default function ManualDetailPage() {
  const params = useParams();
  const router = useRouter();
  const manualId = params.id as string;

  const [manual, setManual] = useState<ManualDetail | null>(null);
  const [pages, setPages] = useState<Page[]>([]);
  const [loading, setLoading] = useState(true);
  const [progressStage, setProgressStage] = useState("");
  const [progressPage, setProgressPage] = useState(0);
  const [progressTotal, setProgressTotal] = useState(0);
  const [expandedImage, setExpandedImage] = useState<number | null>(null);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "";

  useEffect(() => {
    async function load() {
      try {
        const [m, p] = await Promise.all([
          api.get<ManualDetail>(`/api/manuals/${manualId}`),
          api.get<Page[]>(`/api/manuals/${manualId}/pages`).catch(() => [] as Page[]),
        ]);
        setManual(m);
        setPages(p);
      } catch (e: unknown) {
        toast.error(e instanceof Error ? e.message : "Failed to load manual");
        router.push("/manuals");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [manualId, router]);

  // SSE progress stream while processing
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sseActiveRef = useRef(false);

  useEffect(() => {
    if (
      !manual ||
      (manual.upload_status !== "processing" && manual.upload_status !== "pending")
    )
      return;

    // Always start polling immediately — SSE is unreliable on Fly.io
    const startPolling = () => {
      if (pollingRef.current) return; // already polling
      const interval = setInterval(async () => {
        try {
          const [m, p] = await Promise.all([
            api.get<ManualDetail>(`/api/manuals/${manualId}`),
            api.get<Page[]>(`/api/manuals/${manualId}/pages`).catch(() => []),
          ]);
          setManual(m);
          setPages(p);
          // Update progress display from polled data (unless SSE is active)
          if (!sseActiveRef.current && m.upload_status === "processing") {
            setProgressPage(p.length);
            setProgressTotal(m.total_pages || 0);
            setProgressStage("ocr");
          }
          if (m.upload_status === "ready" || m.upload_status === "failed") {
            clearInterval(interval);
            pollingRef.current = null;
          }
        } catch {}
      }, 3000);
      pollingRef.current = interval;
    };

    startPolling();

    // Also try SSE for faster updates — but don't depend on it
    let es: EventSource | null = null;
    try {
      es = new EventSource(
        `${apiBase}/api/manuals/${manualId}/progress`,
        { withCredentials: true }
      );
      es.onmessage = async (event) => {
        try {
          const data = JSON.parse(event.data);
          sseActiveRef.current = true;
          setProgressStage(data.stage || "");
          setProgressPage(data.page || 0);
          setProgressTotal(data.total || 0);

          if (data.stage === "ready" || data.stage === "failed") {
            es?.close();
            sseActiveRef.current = false;
            // Refresh full data
            const [m, p] = await Promise.all([
              api.get<ManualDetail>(`/api/manuals/${manualId}`),
              api.get<Page[]>(`/api/manuals/${manualId}/pages`).catch(() => []),
            ]);
            setManual(m);
            setPages(p);
          }
        } catch {}
      };

      es.onerror = () => {
        es?.close();
        sseActiveRef.current = false;
        // Polling is already running — no action needed
      };
    } catch {
      // SSE not supported or blocked — polling handles it
    }

    return () => {
      es?.close();
      sseActiveRef.current = false;
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [manual?.upload_status, manualId, apiBase]);

  const [retrying, setRetrying] = useState(false);

  const handleRetry = async () => {
    setRetrying(true);
    try {
      const updated = await api.post<ManualDetail>(`/api/manuals/${manualId}/retry`);
      setManual(updated);
      toast.success("Manual re-queued for processing");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to retry processing");
    } finally {
      setRetrying(false);
    }
  };

  const [reclassifying, setReclassifying] = useState(false);

  const handleReclassify = async () => {
    setReclassifying(true);
    try {
      const result = await api.post<{ pages: number }>(`/api/manuals/${manualId}/reclassify`);
      toast.success(`Reclassifying ${result.pages} pages with AI...`);
      // Poll for updated classifications
      const poll = setInterval(async () => {
        try {
          const p = await api.get<Page[]>(`/api/manuals/${manualId}/pages`).catch(() => []);
          setPages(p);
          // Check if classifications have changed from mostly general_illustration
          const giCount = p.filter((pg) => pg.classification === "general_illustration").length;
          if (giCount < p.length * 0.8) {
            clearInterval(poll);
            toast.success("Reclassification complete");
          }
        } catch {}
      }, 5000);
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to start reclassification");
    } finally {
      setReclassifying(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm("Delete this manual and all its data?")) return;
    try {
      await api.delete(`/api/manuals/${manualId}`);
      toast.success("Manual deleted");
      router.push("/manuals");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to delete manual");
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (!manual) return null;

  // Classification breakdown
  const classBreakdown: Record<string, number> = {};
  for (const p of pages) {
    const cls = p.classification || "text";
    classBreakdown[cls] = (classBreakdown[cls] || 0) + 1;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => router.push("/manuals")}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{manual.title}</h1>
          <p className="text-sm text-muted-foreground">
            {manual.make} {manual.model}
            {manual.total_pages && ` \u00B7 ${manual.total_pages} pages`}
            {" \u00B7 "}
            {formatDate(manual.created_at)}
          </p>
        </div>
        <Badge className={statusColors[manual.upload_status] || "bg-slate-400"}>
          {manual.upload_status}
        </Badge>
        {manual.upload_status === "ready" && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleReclassify}
            disabled={reclassifying}
          >
            {reclassifying ? (
              <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-3.5 w-3.5" />
            )}
            Reclassify
          </Button>
        )}
        <Button variant="ghost" size="icon" onClick={handleDelete}>
          <Trash2 className="h-4 w-4 text-red-500" />
        </Button>
      </div>

      {/* Processing banner */}
      {manual.upload_status === "processing" && (
        <Card>
          <CardContent className="flex items-center gap-4 p-4">
            <RefreshCw className="h-5 w-5 animate-spin text-amber-500" />
            <div className="flex-1">
              <p className="text-sm font-medium">Processing manual...</p>
              <p className="text-xs text-muted-foreground">
                {progressStage === "downloading" && "Downloading PDF..."}
                {progressStage === "ocr" &&
                  `${progressPage} of ${progressTotal || manual.total_pages || "?"} pages processed`}
                {progressStage === "chunking" && "Chunking pages..."}
                {progressStage === "embedding" && "Generating embeddings..."}
                {!progressStage &&
                  `${pages.length} of ${manual.total_pages || "?"} pages processed`}
              </p>
              {(progressTotal || manual.total_pages) && (progressTotal || (manual.total_pages ?? 0)) > 0 && (
                <Progress
                  value={
                    progressTotal > 0
                      ? (progressPage / progressTotal) * 100
                      : manual.total_pages
                        ? (pages.length / manual.total_pages) * 100
                        : 0
                  }
                  className="mt-2 h-1.5"
                />
              )}
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={handleRetry}
              disabled={retrying}
              title="Re-queue if processing appears stuck"
            >
              {retrying ? (
                <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-3.5 w-3.5" />
              )}
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {manual.upload_status === "failed" && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-center justify-between p-4">
            <span className="text-sm text-red-700">
              Processing failed.
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={handleRetry}
              disabled={retrying}
            >
              {retrying ? (
                <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-3.5 w-3.5" />
              )}
              Retry Processing
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Tabs */}
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="pages">Pages ({pages.length})</TabsTrigger>
          <TabsTrigger value="schematics">Schematics</TabsTrigger>
          <TabsTrigger value="analysis">Analysis</TabsTrigger>
          <TabsTrigger value="specs">Specs</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6">
          <div className="grid gap-6 md:grid-cols-2">
            {/* Metadata */}
            <Card>
              <CardContent className="space-y-3 p-4">
                <h3 className="font-semibold">Manual Info</h3>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <span className="text-muted-foreground">Type</span>
                  <span className="capitalize">{manual.manual_type}</span>
                  <span className="text-muted-foreground">Make</span>
                  <span>{manual.make || "—"}</span>
                  <span className="text-muted-foreground">Model</span>
                  <span>{manual.model || "—"}</span>
                  <span className="text-muted-foreground">Total Pages</span>
                  <span>{manual.total_pages || "—"}</span>
                  <span className="text-muted-foreground">Visibility</span>
                  <span className="capitalize">{manual.visibility || "private"}</span>
                </div>
              </CardContent>
            </Card>

            {/* Classification Breakdown */}
            <Card>
              <CardContent className="space-y-3 p-4">
                <h3 className="font-semibold">Page Classifications</h3>
                {Object.keys(classBreakdown).length > 0 ? (
                  <div className="space-y-2">
                    {Object.entries(classBreakdown)
                      .sort(([, a], [, b]) => b - a)
                      .map(([cls, count]) => (
                        <div key={cls} className="flex items-center justify-between text-sm">
                          <span>{classificationLabels[cls] || cls}</span>
                          <Badge variant="secondary">{count}</Badge>
                        </div>
                      ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    No pages processed yet.
                  </p>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="pages" className="mt-6">
          {pages.length > 0 ? (
            <div className="space-y-2">
              {pages.map((page) => (
                <Card key={page.id}>
                  <CardContent className="flex items-start gap-4 p-4">
                    {/* Page image thumbnail */}
                    <button
                      className="shrink-0 overflow-hidden rounded border bg-slate-100"
                      onClick={() =>
                        setExpandedImage(
                          expandedImage === page.page_number ? null : page.page_number
                        )
                      }
                      title="Click to expand"
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={`${apiBase}/api/manuals/${manualId}/pages/${page.page_number}/image`}
                        alt={`Page ${page.page_number + 1}`}
                        className="h-16 w-12 object-cover"
                        loading="lazy"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = "none";
                        }}
                      />
                    </button>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary" className="shrink-0">
                          p.{page.page_number + 1}
                        </Badge>
                        <FileText className="h-3.5 w-3.5 text-muted-foreground" />
                        <span className="text-xs text-muted-foreground">
                          {classificationLabels[page.classification] || page.classification}
                        </span>
                        {page.has_table && (
                          <Badge variant="outline" className="text-xs">
                            Table
                          </Badge>
                        )}
                        {page.has_diagram && (
                          <Badge variant="outline" className="text-xs">
                            Diagram
                          </Badge>
                        )}
                      </div>
                      {page.extracted_text && (
                        <p className="mt-1 line-clamp-3 text-xs text-slate-600">
                          {page.extracted_text}
                        </p>
                      )}
                    </div>
                  </CardContent>
                  {/* Expanded image view */}
                  {expandedImage === page.page_number && (
                    <div className="border-t p-4">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={`${apiBase}/api/manuals/${manualId}/pages/${page.page_number}/image`}
                        alt={`Page ${page.page_number + 1} full`}
                        className="mx-auto max-h-[70vh] rounded border shadow-sm"
                      />
                    </div>
                  )}
                </Card>
              ))}
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No pages processed yet.
            </p>
          )}
        </TabsContent>

        <TabsContent value="schematics" className="mt-6">
          {(() => {
            const diagramPages = pages.filter(
              (p) =>
                p.classification === "hydraulic_schematic" ||
                p.classification === "electrical_diagram" ||
                p.classification === "wiring_harness" ||
                p.classification === "diagnostic_flowchart"
            );
            if (diagramPages.length === 0) {
              return (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No schematics or diagrams detected in this manual.
                </p>
              );
            }
            return (
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  {diagramPages.length} schematic/diagram page{diagramPages.length !== 1 ? "s" : ""} detected.
                  Open in the <a href="/viewer" className="text-emerald-600 underline">Viewer</a> for interactive annotations.
                </p>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {diagramPages.map((page) => (
                    <Card key={page.id}>
                      <CardContent className="p-3">
                        <button
                          className="w-full overflow-hidden rounded border bg-slate-100"
                          onClick={() =>
                            setExpandedImage(
                              expandedImage === page.page_number ? null : page.page_number
                            )
                          }
                        >
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={`${apiBase}/api/manuals/${manualId}/pages/${page.page_number}/image`}
                            alt={`Page ${page.page_number + 1}`}
                            className="h-40 w-full object-contain"
                            loading="lazy"
                          />
                        </button>
                        <div className="mt-2 flex items-center gap-2">
                          <Badge variant="secondary" className="text-[10px]">
                            p.{page.page_number + 1}
                          </Badge>
                          <Badge variant="outline" className="text-[10px]">
                            {classificationLabels[page.classification] || page.classification}
                          </Badge>
                        </div>
                        {expandedImage === page.page_number && (
                          <div className="mt-2">
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                              src={`${apiBase}/api/manuals/${manualId}/pages/${page.page_number}/image`}
                              alt={`Page ${page.page_number + 1} full`}
                              className="max-h-[60vh] w-full rounded border object-contain"
                            />
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            );
          })()}
        </TabsContent>

        <TabsContent value="analysis" className="mt-6">
          <AnalysisTab manualId={manualId} manualReady={manual.upload_status === "ready"} />
        </TabsContent>

        <TabsContent value="specs" className="mt-6">
          <ComingSoon
            icon={BookOpen}
            feature="Extracted Specifications"
            description="Auto-extracted torque specs, pressures, and part numbers from this manual."
            phase={1}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

/* ---------- Analysis Tab Component ---------- */

const impactColors: Record<string, string> = {
  critical: "bg-red-100 text-red-800",
  high: "bg-orange-100 text-orange-800",
  medium: "bg-amber-100 text-amber-800",
  low: "bg-slate-100 text-slate-700",
};

function AnalysisTab({ manualId, manualReady }: { manualId: string; manualReady: boolean }) {
  const [coverage, setCoverage] = useState<CoverageAnalysis | null>(null);
  const [gaps, setGaps] = useState<GapAnalysis | null>(null);
  const [components, setComponents] = useState<InferredComponent[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeSection, setActiveSection] = useState<"coverage" | "gaps" | "components">("coverage");

  const runAnalysis = async (type: "coverage" | "gaps" | "components") => {
    setLoading(true);
    setActiveSection(type);
    try {
      if (type === "coverage") {
        const result = await api.post<CoverageAnalysis>("/api/analyze/coverage", {
          manual_id: manualId,
        });
        setCoverage(result);
      } else if (type === "gaps") {
        const result = await api.post<GapAnalysis>("/api/analyze/gaps", {
          manual_id: manualId,
        });
        setGaps(result);
      } else {
        const result = await api.post<{ components: InferredComponent[] }>("/api/analyze/components", {
          manual_id: manualId,
        });
        setComponents(result.components || []);
      }
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  if (!manualReady) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Manual must be fully processed before running analysis.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {/* Analysis action buttons */}
      <div className="flex flex-wrap gap-2">
        <Button
          variant={activeSection === "coverage" ? "default" : "outline"}
          size="sm"
          onClick={() => runAnalysis("coverage")}
          disabled={loading}
        >
          {loading && activeSection === "coverage" ? (
            <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
          ) : (
            <Search className="mr-2 h-3.5 w-3.5" />
          )}
          Coverage Analysis
        </Button>
        <Button
          variant={activeSection === "gaps" ? "default" : "outline"}
          size="sm"
          onClick={() => runAnalysis("gaps")}
          disabled={loading}
        >
          {loading && activeSection === "gaps" ? (
            <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
          ) : (
            <Zap className="mr-2 h-3.5 w-3.5" />
          )}
          Gap Detection
        </Button>
        <Button
          variant={activeSection === "components" ? "default" : "outline"}
          size="sm"
          onClick={() => runAnalysis("components")}
          disabled={loading}
        >
          {loading && activeSection === "components" ? (
            <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
          ) : (
            <FileText className="mr-2 h-3.5 w-3.5" />
          )}
          Infer Components
        </Button>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
          <span className="text-sm text-muted-foreground">Running AI analysis...</span>
        </div>
      )}

      {/* Coverage results */}
      {!loading && coverage && activeSection === "coverage" && (
        <div className="space-y-4">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold">Documentation Coverage</h3>
                <div className="flex items-center gap-2">
                  <span className="text-2xl font-bold">
                    {Math.round(coverage.coverage_score * 100)}%
                  </span>
                </div>
              </div>
              <Progress value={coverage.coverage_score * 100} className="mt-3 h-2" />
              <p className="mt-2 text-xs text-muted-foreground">
                {coverage.page_count} pages analyzed for {coverage.system_area || "all systems"}
              </p>
            </CardContent>
          </Card>

          <div className="grid gap-4 sm:grid-cols-2">
            {/* Doc type checklist */}
            <Card>
              <CardContent className="p-4">
                <h4 className="mb-2 text-sm font-semibold">Documentation Types</h4>
                <div className="space-y-1.5 text-sm">
                  {[
                    ["Service Manual", coverage.has_service_manual],
                    ["Operator Manual", coverage.has_operator_manual],
                    ["Parts Manual", coverage.has_parts_manual],
                    ["Hydraulic Schematic", coverage.has_hydraulic_schematic],
                    ["Electrical Schematic", coverage.has_electrical_schematic],
                    ["Wiring Diagram", coverage.has_wiring_diagram],
                    ["Diagnostic Flowchart", coverage.has_diagnostic_flowchart],
                  ].map(([label, has]) => (
                    <div key={label as string} className="flex items-center gap-2">
                      <div className={`h-2 w-2 rounded-full ${has ? "bg-emerald-500" : "bg-slate-300"}`} />
                      <span className={has ? "" : "text-muted-foreground"}>{label as string}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Gaps */}
            <Card>
              <CardContent className="p-4">
                <h4 className="mb-2 text-sm font-semibold">Identified Gaps ({coverage.gaps.length})</h4>
                {coverage.gaps.length > 0 ? (
                  <div className="space-y-2">
                    {coverage.gaps.map((gap, i) => (
                      <div key={i} className="text-xs">
                        <Badge className={`${impactColors[gap.impact] || impactColors.low} mr-1 text-[10px]`}>
                          {gap.impact}
                        </Badge>
                        {gap.description}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">No gaps detected.</p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Recommendations */}
          {coverage.recommendations && coverage.recommendations.length > 0 && (
            <Card>
              <CardContent className="p-4">
                <h4 className="mb-2 text-sm font-semibold">Recommendations</h4>
                <ul className="space-y-1 text-xs text-muted-foreground">
                  {coverage.recommendations.map((rec, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="text-emerald-500">-</span> {rec}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Gap detection results */}
      {!loading && gaps && activeSection === "gaps" && (
        <div className="space-y-4">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold">Documentation Quality</h3>
                <span className="text-2xl font-bold">
                  {Math.round(gaps.overall_quality * 100)}%
                </span>
              </div>
              <Progress value={gaps.overall_quality * 100} className="mt-3 h-2" />
            </CardContent>
          </Card>

          {/* Gaps list */}
          {gaps.gaps.length > 0 && (
            <Card>
              <CardContent className="p-4">
                <h4 className="mb-3 text-sm font-semibold">
                  Gaps Found ({gaps.gaps.length})
                </h4>
                <div className="space-y-3">
                  {gaps.gaps.map((gap, i) => (
                    <div key={i} className="rounded-lg border p-3">
                      <div className="flex items-center gap-2">
                        <Badge className={`${impactColors[gap.impact] || impactColors.low} text-[10px]`}>
                          {gap.impact}
                        </Badge>
                        <Badge variant="outline" className="text-[10px] capitalize">
                          {gap.category}
                        </Badge>
                      </div>
                      <p className="mt-1 text-sm">{gap.description}</p>
                      {gap.recommendation && (
                        <p className="mt-1 text-xs text-muted-foreground">
                          Fix: {gap.recommendation}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Coverage by area */}
          {gaps.coverage_by_area && gaps.coverage_by_area.length > 0 && (
            <Card>
              <CardContent className="p-4">
                <h4 className="mb-3 text-sm font-semibold">Coverage by System Area</h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b text-muted-foreground">
                        <th className="pb-2 text-left">System</th>
                        <th className="pb-2 text-center">Specs</th>
                        <th className="pb-2 text-center">Procedures</th>
                        <th className="pb-2 text-center">Diagrams</th>
                        <th className="pb-2 text-center">Troubleshooting</th>
                        <th className="pb-2 text-right">Score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {gaps.coverage_by_area.map((area, i) => (
                        <tr key={i} className="border-b last:border-0">
                          <td className="py-2 font-medium">{area.system_area}</td>
                          <td className="py-2 text-center">{area.has_specs ? "✓" : "—"}</td>
                          <td className="py-2 text-center">{area.has_procedures ? "✓" : "—"}</td>
                          <td className="py-2 text-center">{area.has_diagrams ? "✓" : "—"}</td>
                          <td className="py-2 text-center">{area.has_troubleshooting ? "✓" : "—"}</td>
                          <td className="py-2 text-right">{Math.round(area.coverage * 100)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Component inference results */}
      {!loading && components.length > 0 && activeSection === "components" && (
        <Card>
          <CardContent className="p-4">
            <h3 className="mb-3 font-semibold">
              Inferred Components ({components.length})
            </h3>
            <div className="space-y-2">
              {components.map((comp) => (
                <div key={comp.id} className="flex items-start gap-3 rounded-lg border p-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-slate-100 text-xs font-bold uppercase">
                    {comp.component_type.slice(0, 2)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{comp.component_name}</span>
                      {comp.designator && (
                        <Badge variant="secondary" className="text-[10px]">
                          {comp.designator}
                        </Badge>
                      )}
                    </div>
                    <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                      <Badge variant="outline" className="text-[10px] capitalize">
                        {comp.component_type}
                      </Badge>
                      <span>via {comp.inferred_from.replace("_", " ")}</span>
                      <span>{Math.round(comp.confidence * 100)}% confidence</span>
                    </div>
                    {Object.keys(comp.specs || {}).length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {Object.entries(comp.specs).map(([k, v]) => (
                          <span key={k} className="text-[10px] text-muted-foreground">
                            {k}: {v}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Empty state for components */}
      {!loading && components.length === 0 && activeSection === "components" && !coverage && !gaps && (
        <p className="py-8 text-center text-sm text-muted-foreground">
          Click "Infer Components" to extract components from this manual.
        </p>
      )}
    </div>
  );
}
