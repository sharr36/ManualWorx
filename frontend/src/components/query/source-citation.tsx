import { FileText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

interface SourceCitationProps {
  pageNumber: number;
  classification: string;
  textPreview: string;
  onClick?: () => void;
}

export function SourceCitation({
  pageNumber,
  classification,
  textPreview,
  onClick,
}: SourceCitationProps) {
  return (
    <Card
      className="cursor-pointer transition-shadow hover:shadow-sm"
      onClick={onClick}
    >
      <CardContent className="flex items-start gap-3 p-3">
        <Badge variant="secondary" className="shrink-0">
          p.{pageNumber}
        </Badge>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <FileText className="h-3 w-3" />
            {classification.replace(/_/g, " ")}
          </div>
          <p className="mt-0.5 line-clamp-2 text-xs">{textPreview}</p>
        </div>
      </CardContent>
    </Card>
  );
}
