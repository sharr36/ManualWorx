"use client";

import { cn } from "@/lib/utils";
import { ConfidenceLevel } from "@/types";

interface ConfidenceBarProps {
  score: number;
  level?: ConfidenceLevel;
  sources?: string[];
  className?: string;
}

const levelColors: Record<ConfidenceLevel, string> = {
  [ConfidenceLevel.HIGH]: "bg-emerald-600",
  [ConfidenceLevel.MODERATE]: "bg-amber-500",
  [ConfidenceLevel.LOW]: "bg-red-600",
  [ConfidenceLevel.INFERENCE]: "bg-slate-400",
};

const levelLabels: Record<ConfidenceLevel, string> = {
  [ConfidenceLevel.HIGH]: "HIGH",
  [ConfidenceLevel.MODERATE]: "MODERATE",
  [ConfidenceLevel.LOW]: "LOW",
  [ConfidenceLevel.INFERENCE]: "INFERENCE",
};

function getLevel(score: number): ConfidenceLevel {
  if (score >= 80) return ConfidenceLevel.HIGH;
  if (score >= 60) return ConfidenceLevel.MODERATE;
  if (score >= 40) return ConfidenceLevel.LOW;
  return ConfidenceLevel.INFERENCE;
}

export function ConfidenceBar({
  score,
  level,
  sources,
  className,
}: ConfidenceBarProps) {
  const resolvedLevel = level || getLevel(score);

  return (
    <div className={cn("space-y-1", className)}>
      <div className="flex items-center gap-3">
        <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
          <div
            className={cn("h-full rounded-full transition-all", levelColors[resolvedLevel])}
            style={{ width: `${score}%` }}
          />
        </div>
        <span className="font-mono text-xs font-semibold">{score}%</span>
        <span
          className={cn(
            "rounded-sm px-1.5 py-0.5 text-xs font-semibold text-white",
            levelColors[resolvedLevel]
          )}
        >
          {levelLabels[resolvedLevel]}
        </span>
      </div>
      {sources && sources.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Sources: {sources.join(", ")}
        </p>
      )}
    </div>
  );
}
