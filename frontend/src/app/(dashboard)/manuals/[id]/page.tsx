"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  BookOpen,
  FileText,
  Image as ImageIcon,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ComingSoon } from "@/components/ui/coming-soon";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import type { Manual, Page } from "@/types";

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
  const eventSourceRef = useRef<EventSource | null>(null);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "";

  useEffect(() => {
    async function load() {
      try {
        const [m, p] = await Promise.all([
          api.get<ManualDetail>(`/api/manuals/${manualId}`),
          api.get<Page[]>(`/api/manuals/${manualId}/pages`).catch(() => []),
        ]);
        setManual(m);
        setPages(p);
      } catch {
        router.push("/manuals");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [manualId, router]);

  // SSE progress stream while processing
  useEffect(() => {
    if (
      !manual ||
      (manual.upload_status !== "processing" && manual.upload_status !== "pending")
    )
      return;

    const es = new EventSource(
      `${apiBase}/api/manuals/${manualId}/progress`,
      { withCredentials: true }
    );
    eventSourceRef.current = es;

    es.onmessage = async (event) => {
      try {
        const data = JSON.parse(event.data);
        setProgressStage(data.stage || "");
        setProgressPage(data.page || 0);
        setProgressTotal(data.total || 0);

        if (data.stage === "ready" || data.stage === "failed") {
          es.close();
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
      // Fallback to polling if SSE fails
      es.close();
      const interval = setInterval(async () => {
        try {
          const [m, p] = await Promise.all([
            api.get<ManualDetail>(`/api/manuals/${manualId}`),
            api.get<Page[]>(`/api/manuals/${manualId}/pages`).catch(() => []),
          ]);
          setManual(m);
          setPages(p);
          if (m.upload_status === "ready" || m.upload_status === "failed") {
            clearInterval(interval);
          }
        } catch {}
      }, 3000);
    };

    return () => {
      es.close();
    };
  }, [manual?.upload_status, manualId, apiBase]);

  const handleDelete = async () => {
    if (!confirm("Delete this manual and all its data?")) return;
    try {
      await api.delete(`/api/manuals/${manualId}`);
      router.push("/manuals");
    } catch {}
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
                {progressStage
                  ? `Stage: ${progressStage} — page ${progressPage} of ${progressTotal || manual.total_pages || "?"}`
                  : `${pages.length} of ${manual.total_pages || "?"} pages processed`}
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
          </CardContent>
        </Card>
      )}

      {manual.upload_status === "failed" && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-4 text-sm text-red-700">
            Processing failed. Try re-uploading the manual.
          </CardContent>
        </Card>
      )}

      {/* Tabs */}
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="pages">Pages ({pages.length})</TabsTrigger>
          <TabsTrigger value="schematics">Schematics</TabsTrigger>
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
