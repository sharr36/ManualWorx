import { BookOpen } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";
import type { Manual, ManualStatus } from "@/types";

interface ManualCardProps {
  manual: Manual;
}

const statusColors: Record<string, string> = {
  pending: "bg-slate-400",
  processing: "bg-amber-500",
  ready: "bg-emerald-600",
  failed: "bg-red-600",
};

export function ManualCard({ manual }: ManualCardProps) {
  return (
    <Card className="cursor-pointer transition-shadow hover:shadow-md">
      <CardContent className="p-0">
        {/* Thumbnail area */}
        <div className="flex h-32 items-center justify-center bg-slate-100">
          <BookOpen className="h-12 w-12 text-slate-300" />
        </div>

        <div className="p-4">
          <h3 className="truncate font-semibold">{manual.title}</h3>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {manual.make} {manual.model}
            {manual.total_pages && ` \u00B7 ${manual.total_pages} pages`}
          </p>

          <div className="mt-3 flex items-center justify-between">
            <Badge
              className={statusColors[manual.upload_status] || "bg-slate-400"}
            >
              {manual.upload_status}
            </Badge>
            <span className="text-xs text-muted-foreground">
              {formatDate(manual.created_at)}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
