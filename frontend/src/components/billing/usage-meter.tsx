import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface UsageMeterProps {
  label: string;
  used: number;
  limit: number;
  resetDate?: string;
}

export function UsageMeter({ label, used, limit, resetDate }: UsageMeterProps) {
  const percentage = limit > 0 ? Math.min((used / limit) * 100, 100) : 0;

  const colorClass =
    percentage > 85
      ? "[&>div]:bg-red-600"
      : percentage > 60
        ? "[&>div]:bg-amber-500"
        : "[&>div]:bg-emerald-600";

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-medium">{label}</span>
        <span className="text-sm text-muted-foreground">
          {used.toLocaleString()} of {limit.toLocaleString()}
        </span>
      </div>
      <Progress value={percentage} className={cn("h-2", colorClass)} />
      {resetDate && (
        <p className="text-xs text-muted-foreground">Resets {resetDate}</p>
      )}
    </div>
  );
}
