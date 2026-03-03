"use client";

import { GraduationCap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ComingSoon } from "@/components/ui/coming-soon";
import { EmptyState } from "@/components/ui/empty-state";

export default function TeachPage() {
  return (
    <div className="flex h-[calc(100vh-8rem)] gap-6">
      {/* Left panel — Learning paths */}
      <div className="w-72 shrink-0 space-y-4 overflow-y-auto border-r pr-4">
        <h2 className="font-semibold">Learning Paths</h2>
        <EmptyState
          icon={GraduationCap}
          title="No learning paths yet"
          description="Upload a manual to auto-generate learning paths."
        />

        <div className="border-t pt-4">
          <p className="text-xs text-muted-foreground">Skill Level</p>
          <Badge variant="secondary" className="mt-1">
            Green
          </Badge>
        </div>
      </div>

      {/* Right panel — Content */}
      <div className="flex-1 space-y-6">
        <ComingSoon
          icon={GraduationCap}
          feature="Teach-Then-Troubleshoot Mode"
          description="When you describe a problem, ManualWorx first teaches you how the system works, then walks you through diagnostics. Choose: Teach Me First (5-min lesson), Quick Overview (60-sec brief), or Skip to Fix."
          phase={8}
        />

        {/* UX preview */}
        <div className="rounded-lg border bg-white p-6">
          <h3 className="mb-4 font-semibold">How it works</h3>
          <div className="space-y-4 text-sm text-slate-600">
            <div className="rounded-lg border-l-4 border-emerald-600 bg-emerald-50 p-4">
              <p className="font-medium text-emerald-800">
                1. Describe your problem
              </p>
              <p className="mt-1 text-emerald-700">
                &ldquo;The auxiliary hydraulics on my CAT 236B are running
                slow&rdquo;
              </p>
            </div>
            <div className="rounded-lg border-l-4 border-blue-600 bg-blue-50 p-4">
              <p className="font-medium text-blue-800">
                2. ManualWorx identifies the system
              </p>
              <p className="mt-1 text-blue-700">
                Finds the auxiliary hydraulic system in your manual library and
                offers to teach you how it works first.
              </p>
            </div>
            <div className="rounded-lg border-l-4 border-amber-500 bg-amber-50 p-4">
              <p className="font-medium text-amber-800">
                3. Choose your path
              </p>
              <ul className="mt-1 space-y-1 text-amber-700">
                <li>
                  <strong>Teach Me First</strong> — 5-min interactive lesson
                </li>
                <li>
                  <strong>Quick Overview</strong> — 60-second system brief
                </li>
                <li>
                  <strong>Skip to Fix</strong> — Jump straight to diagnostics
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
