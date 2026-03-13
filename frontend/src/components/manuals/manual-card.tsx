import { BookOpen, Loader2, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { formatDate } from "@/lib/utils";
import type { Manual } from "@/types";

export interface ProcessingProgress {
  stage: string;
  page: number;
  total: number;
}

interface ManualCardProps {
  manual: Manual;
  progress?: ProcessingProgress | null;
  onRetry?: (manualId: string) => void;
}

const statusColors: Record<string, string> = {
  pending: "bg-slate-400",
  processing: "bg-amber-500",
  ready: "bg-emerald-600",
  failed: "bg-red-600",
};

const STAGE_LABELS: Record<string, string> = {
  pending: "Queued…",
  downloading: "Preparing PDF…",
  ocr: "Extracting text",
  chunking: "Chunking pages…",
  embedding: "Generating embeddings…",
  ready: "Complete!",
  failed: "Failed",
};

function computeProgressPercent(p: ProcessingProgress): number {
  const { stage, page, total } = p;
  if (stage === "downloading") return 5;
  if (stage === "ocr" && total > 0) return 10 + Math.round((page / total) * 60);
  if (stage === "chunking") return 75;
  if (stage === "embedding") return 90;
  if (stage === "ready") return 100;
  return 0;
}

export function ManualCard({ manual, progress, onRetry }: ManualCardProps) {
  const isProcessing =
    manual.upload_status === "processing" || manual.upload_status === "pending";

  const pct = progress ? computeProgressPercent(progress) : 0;
  const stageLabel = progress
    ? STAGE_LABELS[progress.stage] || "Processing…"
    : isProcessing
      ? "Queued…"
      : null;

  return (
    <Card className="cursor-pointer transition-shadow hover:shadow-md">
      <CardContent className="p-0">
        {/* Thumbnail area */}
        <div className="relative flex h-32 items-center justify-center bg-slate-100">
          <BookOpen className="h-12 w-12 text-slate-300" />
          {isProcessing && (
            <div className="absolute inset-0 flex items-center justify-center bg-white/60">
              <Loader2 className="h-8 w-8 animate-spin text-amber-500" />
            </div>
          )}
        </div>

        <div className="p-4">
          <h3 className="truncate font-semibold">{manual.title}</h3>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {manual.make} {manual.model}
            {manual.total_pages && ` \u00B7 ${manual.total_pages} pages`}
          </p>

          {/* Processing progress */}
          {isProcessing && (
            <div className="mt-2 space-y-1">
              <Progress value={pct} className="h-1.5" />
              <div className="flex items-center justify-between">
                <p className="text-xs text-muted-foreground">{stageLabel}</p>
                {progress?.stage === "ocr" && progress.total > 0 && (
                  <p className="text-xs text-muted-foreground">
                    {progress.page}/{progress.total} pages
                  </p>
                )}
              </div>
            </div>
          )}

          {!isProcessing && (
            <div className="mt-3 flex items-center justify-between">
              <Badge
                className={statusColors[manual.upload_status] || "bg-slate-400"}
              >
                {manual.upload_status}
              </Badge>
              {manual.upload_status === "failed" && onRetry ? (
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-6 px-2 text-xs"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    onRetry(manual.id);
                  }}
                >
                  <RefreshCw className="mr-1 h-3 w-3" />
                  Retry
                </Button>
              ) : (
                <span className="text-xs text-muted-foreground">
                  {formatDate(manual.created_at)}
                </span>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
