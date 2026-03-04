"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { BookOpen, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/empty-state";
import { ManualCard } from "@/components/manuals/manual-card";
import { UploadDialog } from "@/components/manuals/upload-dialog";
import { api } from "@/lib/api-client";
import type { Manual } from "@/types";

type FilterType = "All" | "service" | "operator" | "parts";

export default function ManualsPage() {
  const [manuals, setManuals] = useState<Manual[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<FilterType>("All");

  const fetchManuals = useCallback(async () => {
    try {
      const data = await api.get<Manual[]>("/api/manuals");
      setManuals(data);
    } catch {
      // Silently handle — empty state shown
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchManuals();
  }, [fetchManuals]);

  // Poll for processing status updates
  useEffect(() => {
    const hasProcessing = manuals.some((m) => m.upload_status === "processing" || m.upload_status === "pending");
    if (!hasProcessing) return;

    const interval = setInterval(fetchManuals, 3000);
    return () => clearInterval(interval);
  }, [manuals, fetchManuals]);

  const filtered = useMemo(() => {
    let result = manuals;
    if (filter !== "All") {
      result = result.filter((m) => m.manual_type === filter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (m) =>
          m.title.toLowerCase().includes(q) ||
          m.make?.toLowerCase().includes(q) ||
          m.model?.toLowerCase().includes(q)
      );
    }
    return result;
  }, [manuals, filter, search]);

  const handleUploadSuccess = useCallback(
    (manual: Manual) => {
      setManuals((prev) => [manual, ...prev]);
      setUploadOpen(false);
    },
    []
  );

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <RefreshCw className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Manual Library</h1>
        <Button onClick={() => setUploadOpen(true)}>Upload Manual</Button>
      </div>

      {/* Search & filters */}
      <div className="flex gap-3">
        <Input
          placeholder="Search manuals by name, make, or model..."
          className="max-w-md"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="flex gap-2">
          {(["All", "service", "operator", "parts"] as FilterType[]).map(
            (f) => (
              <Button
                key={f}
                variant={filter === f ? "default" : "outline"}
                size="sm"
                onClick={() => setFilter(f)}
              >
                {f === "All" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
              </Button>
            )
          )}
        </div>
      </div>

      {/* Manual grid */}
      {filtered.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filtered.map((manual) => (
            <Link key={manual.id} href={`/manuals/${manual.id}`}>
              <ManualCard manual={manual} />
            </Link>
          ))}
        </div>
      ) : manuals.length > 0 ? (
        <div className="py-12 text-center text-sm text-muted-foreground">
          No manuals match your search.
        </div>
      ) : (
        <EmptyState
          icon={BookOpen}
          title="No manuals yet"
          description="Upload your first service manual to start querying with AI. Supports PDFs up to 5,000+ pages."
          action={{
            label: "Upload Manual",
            onClick: () => setUploadOpen(true),
          }}
        />
      )}

      {/* Upload dialog */}
      <UploadDialog
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onSuccess={handleUploadSuccess}
      />
    </div>
  );
}
