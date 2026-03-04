"use client";

import { useState } from "react";
import { FileText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

const apiBase = process.env.NEXT_PUBLIC_API_URL || "";

interface SourceCitationProps {
  pageNumber: number;
  classification: string;
  textPreview: string;
  manualId?: string;
  relevanceScore?: number;
  manualTitle?: string;
  onClick?: () => void;
}

export function SourceCitation({
  pageNumber,
  classification,
  textPreview,
  manualId,
  relevanceScore,
  manualTitle,
  onClick,
}: SourceCitationProps) {
  const [imageError, setImageError] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const imageUrl = manualId
    ? `${apiBase}/api/manuals/${manualId}/pages/${pageNumber - 1}/image`
    : null;

  return (
    <Card
      className="cursor-pointer transition-shadow hover:shadow-sm"
      onClick={() => {
        if (onClick) onClick();
        else setExpanded(!expanded);
      }}
    >
      <CardContent className="flex items-start gap-3 p-3">
        {/* Page image thumbnail */}
        {imageUrl && !imageError ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imageUrl}
            alt={`Page ${pageNumber}`}
            className="h-12 w-9 shrink-0 rounded border object-cover"
            loading="lazy"
            onError={() => setImageError(true)}
          />
        ) : (
          <Badge variant="secondary" className="shrink-0">
            p.{pageNumber}
          </Badge>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <FileText className="h-3 w-3" />
            {classification.replace(/_/g, " ")}
            {relevanceScore !== undefined && (
              <span className="ml-auto text-[10px]">
                {Math.round(relevanceScore * 100)}%
              </span>
            )}
          </div>
          {manualTitle && (
            <p className="text-[10px] text-muted-foreground truncate">
              {manualTitle}
            </p>
          )}
          <p className="mt-0.5 line-clamp-2 text-xs">{textPreview}</p>
        </div>
      </CardContent>
      {/* Expanded image */}
      {expanded && imageUrl && !imageError && (
        <div className="border-t p-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imageUrl}
            alt={`Page ${pageNumber} full`}
            className="mx-auto max-h-64 rounded border"
          />
        </div>
      )}
    </Card>
  );
}
