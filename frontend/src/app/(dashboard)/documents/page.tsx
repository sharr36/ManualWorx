"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Download,
  FileText,
  Loader2,
  Trash2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { api } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";

interface DocItem {
  id: string;
  query_id: string | null;
  doc_type: string;
  format: string;
  file_url: string | null;
  query_text: string | null;
  created_at: string | null;
}

const DOC_TYPE_LABELS: Record<string, string> = {
  troubleshooting_guide: "Troubleshooting Guide",
  service_procedure: "Service Procedure",
  parts_reference: "Parts Reference",
  quick_reference: "Quick Reference",
  training_lesson: "Training Lesson",
  quiz_assessment: "Quiz Assessment",
  progress_report: "Progress Report",
  system_analysis: "System Analysis",
  gap_report: "Gap Report",
};

const DOC_TYPE_COLORS: Record<string, string> = {
  troubleshooting_guide: "bg-amber-100 text-amber-800",
  service_procedure: "bg-blue-100 text-blue-800",
  parts_reference: "bg-slate-100 text-slate-800",
  quick_reference: "bg-emerald-100 text-emerald-800",
  training_lesson: "bg-purple-100 text-purple-800",
  quiz_assessment: "bg-pink-100 text-pink-800",
  progress_report: "bg-cyan-100 text-cyan-800",
  system_analysis: "bg-orange-100 text-orange-800",
  gap_report: "bg-red-100 text-red-800",
};

const FILTER_TABS = [
  { label: "All", value: "" },
  { label: "Troubleshooting", value: "troubleshooting_guide" },
  { label: "Procedures", value: "service_procedure" },
  { label: "Quick Ref", value: "quick_reference" },
  { label: "Parts", value: "parts_reference" },
];

const apiBase = process.env.NEXT_PUBLIC_API_URL || "";

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [deleting, setDeleting] = useState<string | null>(null);

  const loadDocs = useCallback(async () => {
    try {
      const params = filter ? `?doc_type=${filter}` : "";
      const data = await api.get<DocItem[]>(`/api/documents${params}`);
      setDocs(data);
    } catch {
      setDocs([]);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    setLoading(true);
    loadDocs();
  }, [loadDocs]);

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this document?")) return;
    setDeleting(id);
    try {
      await api.delete(`/api/documents/${id}`);
      setDocs((prev) => prev.filter((d) => d.id !== id));
    } catch {
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Generated Documents</h1>
        <p className="text-sm text-muted-foreground">
          {docs.length} document{docs.length !== 1 ? "s" : ""}
        </p>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2">
        {FILTER_TABS.map((tab) => (
          <Button
            key={tab.value}
            variant={filter === tab.value ? "default" : "outline"}
            size="sm"
            onClick={() => setFilter(tab.value)}
          >
            {tab.label}
          </Button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : docs.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No documents yet"
          description="Generate your first document from any query result. Use the query page to ask a question, then click 'Generate Document' on the response."
        />
      ) : (
        <div className="space-y-3">
          {docs.map((doc) => (
            <Card key={doc.id}>
              <CardContent className="flex items-center gap-4 p-4">
                <FileText className="h-8 w-8 shrink-0 text-slate-400" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <Badge
                      className={
                        DOC_TYPE_COLORS[doc.doc_type] ||
                        "bg-slate-100 text-slate-800"
                      }
                    >
                      {DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type}
                    </Badge>
                    <Badge variant="outline" className="text-[10px] uppercase">
                      {doc.format}
                    </Badge>
                  </div>
                  {doc.query_text && (
                    <p className="mt-1 line-clamp-1 text-sm text-slate-600">
                      {doc.query_text}
                    </p>
                  )}
                  {doc.created_at && (
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {formatDate(doc.created_at)}
                    </p>
                  )}
                </div>
                <div className="flex shrink-0 gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    asChild
                  >
                    <a
                      href={`${apiBase}/api/documents/${doc.id}/download`}
                      target="_blank"
                      rel="noopener noreferrer"
                      title="Download"
                    >
                      <Download className="h-4 w-4" />
                    </a>
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    disabled={deleting === doc.id}
                    onClick={() => handleDelete(doc.id)}
                  >
                    {deleting === doc.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4 text-red-500" />
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
