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
import { Input } from "@/components/ui/input";
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
          <PagesTab
            pages={pages}
            manualId={manualId}
            apiBase={apiBase}
            expandedImage={expandedImage}
            setExpandedImage={setExpandedImage}
          />
        </TabsContent>

        <TabsContent value="schematics" className="mt-6">
          <SchematicsTab manualId={manualId} apiBase={apiBase} />
        </TabsContent>

        <TabsContent value="analysis" className="mt-6">
          <AnalysisTab manualId={manualId} manualReady={manual.upload_status === "ready"} />
        </TabsContent>

        <TabsContent value="specs" className="mt-6">
          <SpecsTab manualId={manualId} manualReady={manual.upload_status === "ready"} />
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
          Click &quot;Infer Components&quot; to extract components from this manual.
        </p>
      )}
    </div>
  );
}

/* ---------- Pages Tab with Search ---------- */

interface SearchResult {
  page_id: string;
  page_number: number;
  classification: string;
  has_table: boolean;
  has_diagram: boolean;
  rank: number;
  snippet: string;
}

function PagesTab({
  pages,
  manualId,
  apiBase,
  expandedImage,
  setExpandedImage,
}: {
  pages: Page[];
  manualId: string;
  apiBase: string;
  expandedImage: number | null;
  setExpandedImage: (v: number | null) => void;
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const searchTimeout = useRef<NodeJS.Timeout | null>(null);

  const handleSearch = useCallback(
    (query: string) => {
      setSearchQuery(query);
      if (searchTimeout.current) clearTimeout(searchTimeout.current);
      if (!query.trim()) {
        setSearchResults(null);
        return;
      }
      searchTimeout.current = setTimeout(async () => {
        setSearching(true);
        try {
          const result = await api.get<{ results: SearchResult[] }>(
            `/api/manuals/${manualId}/search?q=${encodeURIComponent(query.trim())}&limit=50`
          );
          setSearchResults(result.results);
        } catch {
          setSearchResults(null);
        } finally {
          setSearching(false);
        }
      }, 300);
    },
    [manualId]
  );

  const displayPages = searchResults
    ? searchResults.map((sr) => {
        const page = pages.find((p) => p.id === sr.page_id);
        return { ...sr, page };
      })
    : null;

  return (
    <div className="space-y-3">
      {/* Search bar */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search all pages..."
          value={searchQuery}
          onChange={(e) => handleSearch(e.target.value)}
          className="pl-10"
        />
        {searching && (
          <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted-foreground" />
        )}
      </div>

      {searchResults !== null && (
        <p className="text-xs text-muted-foreground">
          {searchResults.length} page{searchResults.length !== 1 ? "s" : ""} matching &quot;{searchQuery}&quot;
        </p>
      )}

      {/* Search results or all pages */}
      {displayPages ? (
        displayPages.length > 0 ? (
          <div className="space-y-2">
            {displayPages.map((sr) => (
              <Card key={sr.page_id}>
                <CardContent className="flex items-start gap-4 p-4">
                  <button
                    className="shrink-0 overflow-hidden rounded border bg-slate-100"
                    onClick={() =>
                      setExpandedImage(expandedImage === sr.page_number ? null : sr.page_number)
                    }
                    title="Click to expand"
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={`${apiBase}/api/manuals/${manualId}/pages/${sr.page_number}/image`}
                      alt={`Page ${sr.page_number + 1}`}
                      className="h-16 w-12 object-cover"
                      loading="lazy"
                      onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                    />
                  </button>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary" className="shrink-0">p.{sr.page_number + 1}</Badge>
                      <span className="text-xs text-muted-foreground">
                        {classificationLabels[sr.classification] || sr.classification}
                      </span>
                      <Badge variant="outline" className="text-[10px]">
                        relevance: {(sr.rank * 100).toFixed(0)}%
                      </Badge>
                    </div>
                    <p
                      className="mt-1 text-xs text-slate-600"
                      dangerouslySetInnerHTML={{ __html: sr.snippet }}
                    />
                  </div>
                </CardContent>
                {expandedImage === sr.page_number && (
                  <div className="border-t p-4">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={`${apiBase}/api/manuals/${manualId}/pages/${sr.page_number}/image`}
                      alt={`Page ${sr.page_number + 1} full`}
                      className="mx-auto max-h-[70vh] rounded border shadow-sm"
                    />
                  </div>
                )}
              </Card>
            ))}
          </div>
        ) : (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No pages match your search.
          </p>
        )
      ) : pages.length > 0 ? (
        <div className="space-y-2">
          {pages.map((page) => (
            <Card key={page.id}>
              <CardContent className="flex items-start gap-4 p-4">
                <button
                  className="shrink-0 overflow-hidden rounded border bg-slate-100"
                  onClick={() =>
                    setExpandedImage(expandedImage === page.page_number ? null : page.page_number)
                  }
                  title="Click to expand"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`${apiBase}/api/manuals/${manualId}/pages/${page.page_number}/image`}
                    alt={`Page ${page.page_number + 1}`}
                    className="h-16 w-12 object-cover"
                    loading="lazy"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                  />
                </button>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="shrink-0">p.{page.page_number + 1}</Badge>
                    <FileText className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground">
                      {classificationLabels[page.classification] || page.classification}
                    </span>
                    {page.has_table && <Badge variant="outline" className="text-xs">Table</Badge>}
                    {page.has_diagram && <Badge variant="outline" className="text-xs">Diagram</Badge>}
                  </div>
                  {page.extracted_text && (
                    <p className="mt-1 line-clamp-3 text-xs text-slate-600">{page.extracted_text}</p>
                  )}
                </div>
              </CardContent>
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
        <p className="py-8 text-center text-sm text-muted-foreground">No pages processed yet.</p>
      )}
    </div>
  );
}

/* ---------- Schematics Tab with AI Annotations ---------- */

interface SchematicEntry {
  page_id: string;
  page_number: number;
  classification: string;
  annotated: boolean;
  diagram_type?: string;
  component_count?: number;
  connection_count?: number;
  confidence?: number | null;
  components?: { id: string; designator: string; name: string; type: string }[];
  connections?: { from_id: string; to_id: string; line_type: string; label?: string }[];
  operating_states?: { id: string; name: string; description: string }[];
  annotated_at?: string | null;
}

function SchematicsTab({ manualId, apiBase }: { manualId: string; apiBase: string }) {
  const [schematics, setSchematics] = useState<SchematicEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedSchematic, setExpandedSchematic] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await api.get<{ schematics: SchematicEntry[] }>(
          `/api/manuals/${manualId}/schematics`
        );
        setSchematics(data.schematics);
      } catch {
        setSchematics([]);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [manualId]);

  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  if (schematics.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No schematics or diagrams detected in this manual.
      </p>
    );
  }

  const annotatedCount = schematics.filter((s) => s.annotated).length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {schematics.length} schematic page{schematics.length !== 1 ? "s" : ""} detected
          {annotatedCount > 0 && ` — ${annotatedCount} AI-annotated`}.
          Open in the <a href="/viewer" className="text-emerald-600 underline">Viewer</a> for interactive mode.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {schematics.map((s) => (
          <Card key={s.page_id} className={s.annotated ? "border-emerald-200" : ""}>
            <CardContent className="p-3">
              {/* Thumbnail */}
              <button
                className="w-full overflow-hidden rounded border bg-slate-100"
                onClick={() => setExpandedSchematic(expandedSchematic === s.page_id ? null : s.page_id)}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`${apiBase}/api/manuals/${manualId}/pages/${s.page_number}/image`}
                  alt={`Page ${s.page_number + 1}`}
                  className="h-40 w-full object-contain"
                  loading="lazy"
                />
              </button>

              {/* Badges */}
              <div className="mt-2 flex flex-wrap items-center gap-1">
                <Badge variant="secondary" className="text-[10px]">p.{s.page_number + 1}</Badge>
                <Badge variant="outline" className="text-[10px]">
                  {classificationLabels[s.classification] || s.classification}
                </Badge>
                {s.annotated && (
                  <Badge className="bg-emerald-100 text-emerald-800 text-[10px]">
                    AI Annotated
                  </Badge>
                )}
              </div>

              {/* Annotation summary */}
              {s.annotated && (
                <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                  <div className="flex justify-between">
                    <span>Components</span>
                    <span className="font-medium text-foreground">{s.component_count}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Connections</span>
                    <span className="font-medium text-foreground">{s.connection_count}</span>
                  </div>
                  {s.confidence != null && (
                    <div className="flex justify-between">
                      <span>Confidence</span>
                      <span className="font-medium text-foreground">{Math.round(s.confidence * 100)}%</span>
                    </div>
                  )}
                </div>
              )}

              {/* Expanded: component list */}
              {expandedSchematic === s.page_id && s.annotated && (
                <div className="mt-3 space-y-2 border-t pt-3">
                  {/* Full image */}
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`${apiBase}/api/manuals/${manualId}/pages/${s.page_number}/image`}
                    alt={`Page ${s.page_number + 1} full`}
                    className="max-h-[50vh] w-full rounded border object-contain"
                  />

                  {/* Components table */}
                  {s.components && s.components.length > 0 && (
                    <div>
                      <h4 className="mb-1 text-xs font-semibold">Components</h4>
                      <div className="max-h-40 overflow-y-auto rounded border text-xs">
                        <table className="w-full">
                          <thead className="bg-slate-50">
                            <tr>
                              <th className="p-1.5 text-left font-medium">ID</th>
                              <th className="p-1.5 text-left font-medium">Name</th>
                              <th className="p-1.5 text-left font-medium">Type</th>
                            </tr>
                          </thead>
                          <tbody>
                            {s.components.map((c, i) => (
                              <tr key={i} className="border-t">
                                <td className="p-1.5 font-mono">{c.designator}</td>
                                <td className="p-1.5">{c.name}</td>
                                <td className="p-1.5 text-muted-foreground">{c.type}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Operating states */}
                  {s.operating_states && s.operating_states.length > 0 && (
                    <div>
                      <h4 className="mb-1 text-xs font-semibold">Operating States</h4>
                      <div className="space-y-1">
                        {s.operating_states.map((os, i) => (
                          <div key={i} className="rounded border p-2 text-xs">
                            <span className="font-medium">{os.name}:</span>{" "}
                            <span className="text-muted-foreground">{os.description}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Expand prompt for non-annotated */}
              {expandedSchematic === s.page_id && !s.annotated && (
                <div className="mt-3 border-t pt-3">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`${apiBase}/api/manuals/${manualId}/pages/${s.page_number}/image`}
                    alt={`Page ${s.page_number + 1} full`}
                    className="max-h-[50vh] w-full rounded border object-contain"
                  />
                  <p className="mt-2 text-center text-xs text-muted-foreground">
                    AI annotation pending — use the Viewer for interactive analysis.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

/* ---------- Specs Tab ---------- */

interface ExtractedSpec {
  category: string;
  component: string;
  spec: string;
  conditions?: string;
  page?: number;
}

const specCategoryColors: Record<string, string> = {
  torque: "bg-blue-100 text-blue-800",
  pressure: "bg-red-100 text-red-800",
  clearance: "bg-amber-100 text-amber-800",
  capacity: "bg-purple-100 text-purple-800",
  electrical: "bg-yellow-100 text-yellow-800",
  general: "bg-slate-100 text-slate-800",
};

function SpecsTab({ manualId, manualReady }: { manualId: string; manualReady: boolean }) {
  const [specs, setSpecs] = useState<ExtractedSpec[]>([]);
  const [loading, setLoading] = useState(false);
  const [extracted, setExtracted] = useState(false);
  const [filterCategory, setFilterCategory] = useState<string>("all");

  const extractSpecs = async () => {
    setLoading(true);
    try {
      const result = await api.post<{ specs: ExtractedSpec[]; total: number }>(
        `/api/manuals/${manualId}/extract-specs`
      );
      setSpecs(result.specs || []);
      setExtracted(true);
      if (result.total === 0) {
        toast.info("No specifications found in this manual");
      } else {
        toast.success(`Extracted ${result.total} specifications`);
      }
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to extract specifications");
    } finally {
      setLoading(false);
    }
  };

  const categories = ["all", ...Array.from(new Set(specs.map((s) => s.category)))];
  const filtered = filterCategory === "all" ? specs : specs.filter((s) => s.category === filterCategory);

  if (!extracted) {
    return (
      <div className="flex flex-col items-center gap-4 py-12">
        <BookOpen className="h-12 w-12 text-muted-foreground" />
        <div className="text-center">
          <h3 className="font-semibold">Extract Specifications</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            AI will scan torque specs, pressures, clearances, and capacities from this manual.
          </p>
        </div>
        <Button onClick={extractSpecs} disabled={loading || !manualReady}>
          {loading ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Zap className="mr-2 h-4 w-4" />
          )}
          {loading ? "Extracting..." : "Extract Specs"}
        </Button>
      </div>
    );
  }

  if (specs.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No specifications found in this manual.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {/* Category filter */}
      <div className="flex flex-wrap gap-2">
        {categories.map((cat) => (
          <Button
            key={cat}
            variant={filterCategory === cat ? "default" : "outline"}
            size="sm"
            onClick={() => setFilterCategory(cat)}
          >
            {cat === "all" ? `All (${specs.length})` : `${cat} (${specs.filter((s) => s.category === cat).length})`}
          </Button>
        ))}
      </div>

      {/* Specs table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b bg-slate-50">
                <tr>
                  <th className="p-3 text-left font-medium">Category</th>
                  <th className="p-3 text-left font-medium">Component</th>
                  <th className="p-3 text-left font-medium">Specification</th>
                  <th className="p-3 text-left font-medium">Conditions</th>
                  <th className="p-3 text-right font-medium">Page</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((spec, i) => (
                  <tr key={i} className="border-b last:border-0">
                    <td className="p-3">
                      <Badge className={specCategoryColors[spec.category] || specCategoryColors.general}>
                        {spec.category}
                      </Badge>
                    </td>
                    <td className="p-3 font-medium">{spec.component}</td>
                    <td className="p-3 font-mono text-xs">{spec.spec}</td>
                    <td className="p-3 text-xs text-muted-foreground">{spec.conditions || "—"}</td>
                    <td className="p-3 text-right text-xs text-muted-foreground">
                      {spec.page != null ? `p.${spec.page}` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
