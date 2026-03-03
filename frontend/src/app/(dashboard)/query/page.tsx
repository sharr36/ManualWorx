"use client";

import { MessageSquare, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

const EXAMPLE_QUERIES = [
  "What's the torque spec for the main relief valve?",
  "Trace the hydraulic flow from pump to cylinder",
  "How do I replace the fuel injectors?",
  "What causes low hydraulic pressure?",
];

export default function QueryPage() {
  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      {/* Chat area */}
      <div className="flex flex-1 flex-col">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          <EmptyState
            icon={MessageSquare}
            title="Ask anything about your equipment manuals"
            description="Get answers with page references, confidence scores, and spec values — all backed by your actual service manuals."
          />

          {/* Example query chips */}
          <div className="flex flex-wrap justify-center gap-2 px-4">
            {EXAMPLE_QUERIES.map((q) => (
              <button
                key={q}
                className="rounded-full border bg-white px-3 py-1.5 text-xs text-slate-600 transition hover:bg-slate-50"
                disabled
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        {/* Input bar */}
        <div className="border-t p-4">
          <div className="flex gap-2">
            {/* Mode tabs */}
            <div className="hidden gap-1 sm:flex">
              {["Q&A", "Troubleshoot", "Diagram", "Procedure"].map((mode) => (
                <Button
                  key={mode}
                  variant="ghost"
                  size="sm"
                  disabled
                  className="text-xs"
                >
                  {mode}
                </Button>
              ))}
            </div>
            <div className="flex flex-1 gap-2">
              <textarea
                placeholder="AI queries coming in Phase 1..."
                className="flex-1 resize-none rounded-lg border bg-white px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-emerald-600"
                rows={1}
                disabled
              />
              <Button size="icon" disabled>
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Context panel */}
      <div className="hidden w-72 flex-col border-l pl-4 lg:flex">
        <h3 className="mb-3 text-sm font-semibold">Context</h3>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-muted-foreground">Manual</label>
            <select
              className="mt-1 w-full rounded-md border bg-white px-2 py-1.5 text-sm"
              disabled
            >
              <option>All manuals</option>
            </select>
          </div>
          <div>
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <input type="checkbox" disabled className="accent-emerald-600" />
              Explain Like I&apos;m New
            </label>
          </div>
          <div className="border-t pt-3">
            <p className="text-xs text-muted-foreground">
              Source pages will appear here after querying.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
