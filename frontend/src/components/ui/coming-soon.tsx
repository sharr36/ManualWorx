import { cn } from "@/lib/utils";
import { type LucideIcon, Construction } from "lucide-react";
import { Badge } from "./badge";

interface ComingSoonProps {
  icon?: LucideIcon;
  feature: string;
  description: string;
  phase: number;
  className?: string;
}

export function ComingSoon({
  icon: Icon = Construction,
  feature,
  description,
  phase,
  className,
}: ComingSoonProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 py-16 text-center",
        className
      )}
    >
      <Icon className="mb-4 h-12 w-12 text-slate-400" />
      <h3 className="mb-1 text-lg font-semibold text-slate-700">{feature}</h3>
      <p className="mb-4 max-w-md text-sm text-slate-500">{description}</p>
      <Badge variant="secondary">Planned for Phase {phase}</Badge>
    </div>
  );
}
