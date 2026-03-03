"use client";

import { Image } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ComingSoon } from "@/components/ui/coming-soon";

export default function ViewerPage() {
  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-3 rounded-lg border bg-white p-3">
        <div className="flex items-center gap-2">
          <label className="text-xs text-muted-foreground">Zoom</label>
          <input
            type="range"
            min="50"
            max="200"
            defaultValue="100"
            className="w-24"
            disabled
          />
        </div>

        <Button variant="outline" size="sm" disabled>
          Pan
        </Button>

        <select
          className="rounded-md border px-2 py-1 text-sm"
          disabled
        >
          <option>Layers...</option>
          <option>Pressure</option>
          <option>Return</option>
          <option>Pilot</option>
          <option>Drain</option>
        </select>

        <select
          className="rounded-md border px-2 py-1 text-sm"
          disabled
        >
          <option>Select operating state...</option>
        </select>

        <div className="flex-1" />

        <input
          placeholder="Find component..."
          className="rounded-md border px-2 py-1 text-sm"
          disabled
        />
      </div>

      <div className="flex gap-4">
        {/* Canvas area */}
        <div className="flex-1">
          <div
            className="rounded-lg border-2 border-dashed border-slate-200"
            style={{
              backgroundImage:
                "linear-gradient(45deg, #f1f5f9 25%, transparent 25%), linear-gradient(-45deg, #f1f5f9 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #f1f5f9 75%), linear-gradient(-45deg, transparent 75%, #f1f5f9 75%)",
              backgroundSize: "20px 20px",
              backgroundPosition: "0 0, 0 10px, 10px -10px, -10px 0px",
            }}
          >
            <ComingSoon
              icon={Image}
              feature="Interactive Schematic Viewer"
              description="Hydraulic and electrical diagrams with clickable components, flow tracing, and AI-annotated operating states. Pan, zoom, and layer controls."
              phase={5}
            />
          </div>
        </div>

        {/* Side panel */}
        <div className="hidden w-64 rounded-lg border bg-white p-4 xl:block">
          <h3 className="mb-3 font-semibold">Component Info</h3>
          <div className="space-y-2">
            {["Details", "Specs", "Procedures", "History"].map((tab) => (
              <Button
                key={tab}
                variant="ghost"
                size="sm"
                className="w-full justify-start"
                disabled
              >
                {tab}
              </Button>
            ))}
          </div>
          <p className="mt-4 text-xs text-muted-foreground">
            Click a component on the diagram to see its details.
          </p>
        </div>
      </div>
    </div>
  );
}
