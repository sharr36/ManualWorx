"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ArrowLeft,
  BookOpen,
  Eye,
  Loader2,
  MessageSquare,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api-client";
import type { Manual } from "@/types";

const statusColors: Record<string, string> = {
  pending: "bg-slate-400",
  processing: "bg-amber-500",
  ready: "bg-emerald-600",
  failed: "bg-red-600",
};

const tabs = [
  { href: "", label: "Details", icon: BookOpen },
  { href: "/viewer", label: "Viewer", icon: Eye },
  { href: "/query", label: "Query", icon: MessageSquare },
];

export default function ManualLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const params = useParams();
  const pathname = usePathname();
  const manualId = params.id as string;
  const [manual, setManual] = useState<Manual | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<Manual>(`/api/manuals/${manualId}`)
      .then(setManual)
      .catch(() => setManual(null))
      .finally(() => setLoading(false));
  }, [manualId]);

  const basePath = `/manuals/${manualId}`;

  return (
    <div className="space-y-4">
      {/* Manual header */}
      <div className="flex items-center gap-4">
        <Link
          href="/manuals"
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Manuals
        </Link>

        {loading ? (
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        ) : manual ? (
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-bold">{manual.title}</h1>
            {manual.make && (
              <span className="text-sm text-muted-foreground">
                {manual.make} {manual.model || ""}
              </span>
            )}
            <Badge
              className={`${statusColors[manual.upload_status] || "bg-slate-400"} text-white text-[10px]`}
            >
              {manual.upload_status}
            </Badge>
            {manual.total_pages && (
              <span className="text-xs text-muted-foreground">
                {manual.total_pages} pages
              </span>
            )}
          </div>
        ) : (
          <span className="text-sm text-muted-foreground">Manual not found</span>
        )}
      </div>

      {/* Tab navigation */}
      <div className="flex gap-1 border-b">
        {tabs.map((tab) => {
          const tabPath = `${basePath}${tab.href}`;
          const isActive =
            tab.href === ""
              ? pathname === basePath || pathname === basePath + "/"
              : pathname.startsWith(tabPath);

          return (
            <Link
              key={tab.href}
              href={tabPath}
              className={`flex items-center gap-1.5 border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? "border-emerald-600 text-emerald-700"
                  : "border-transparent text-muted-foreground hover:text-foreground hover:border-slate-300"
              }`}
            >
              <tab.icon className="h-4 w-4" />
              {tab.label}
            </Link>
          );
        })}
      </div>

      {/* Tab content */}
      {children}
    </div>
  );
}
