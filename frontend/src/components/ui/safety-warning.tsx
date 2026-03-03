import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

interface SafetyWarningProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
}

export function SafetyWarning({
  title = "SAFETY WARNING",
  children,
  className,
}: SafetyWarningProps) {
  return (
    <div
      className={cn(
        "rounded-lg border-2 border-red-600 bg-red-50 p-4",
        className
      )}
    >
      <div className="flex items-center gap-2 mb-1">
        <AlertTriangle className="h-5 w-5 text-red-600 shrink-0" />
        <span className="text-sm font-bold text-red-600">{title}</span>
      </div>
      <div className="text-sm text-slate-900">{children}</div>
    </div>
  );
}
