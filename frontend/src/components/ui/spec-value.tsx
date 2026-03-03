import { cn } from "@/lib/utils";
import { ConfidenceLevel } from "@/types";

interface SpecValueProps {
  value: string;
  confidence?: ConfidenceLevel;
  source?: string;
  className?: string;
}

const borderColors: Record<ConfidenceLevel, string> = {
  [ConfidenceLevel.HIGH]: "border-emerald-600",
  [ConfidenceLevel.MODERATE]: "border-amber-500",
  [ConfidenceLevel.LOW]: "border-red-600",
  [ConfidenceLevel.INFERENCE]: "border-slate-400",
};

export function SpecValue({
  value,
  confidence,
  source,
  className,
}: SpecValueProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border bg-slate-50 px-2 py-0.5 font-mono text-sm font-medium",
        confidence ? borderColors[confidence] : "border-slate-300",
        className
      )}
      title={source ? `Source: ${source}` : undefined}
    >
      {value}
    </span>
  );
}
