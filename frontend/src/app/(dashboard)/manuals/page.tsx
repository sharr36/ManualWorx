"use client";

import { BookOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/empty-state";

export default function ManualsPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Manual Library</h1>
        <Button
          disabled
          onClick={() => {
            // TODO: Phase 1
          }}
        >
          Upload Manual
        </Button>
      </div>

      {/* Search & filters */}
      <div className="flex gap-3">
        <Input
          placeholder="Search manuals by name, make, or model..."
          className="max-w-md"
          disabled
        />
        <div className="flex gap-2">
          {["All", "Service", "Operator", "Parts"].map((filter) => (
            <Button key={filter} variant="outline" size="sm" disabled>
              {filter}
            </Button>
          ))}
        </div>
      </div>

      {/* Empty state */}
      <EmptyState
        icon={BookOpen}
        title="No manuals yet"
        description="Upload your first service manual to start querying with AI. Supports PDFs up to 5,000+ pages."
        action={{
          label: "Upload Manual",
          onClick: () => {},
          disabled: true,
        }}
      />
    </div>
  );
}
