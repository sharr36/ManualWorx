"use client";

import { FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

export default function DocumentsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Generated Documents</h1>
        <Button disabled>Generate New</Button>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2">
        {[
          "All",
          "Troubleshooting",
          "Procedures",
          "Training",
          "Analysis",
        ].map((tab) => (
          <Button key={tab} variant="outline" size="sm" disabled>
            {tab}
          </Button>
        ))}
      </div>

      <EmptyState
        icon={FileText}
        title="No documents yet"
        description="Generate your first document from any query result. Supports troubleshooting guides, service procedures, training lessons, and more."
        action={{
          label: "Generate Document",
          onClick: () => {},
          disabled: true,
        }}
      />
    </div>
  );
}
