"use client";

import { useEffect, useState } from "react";
import {
  BookOpen,
  CreditCard,
  GraduationCap,
  Image,
  MessageSquare,
  Users,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api-client";
import type { Manual } from "@/types";

interface DashboardStats {
  manuals: number;
  manuals_ready: number;
  manuals_processing: number;
}

export default function DashboardPage() {
  const { user, tenant } = useAuth();
  const [stats, setStats] = useState<DashboardStats>({
    manuals: 0,
    manuals_ready: 0,
    manuals_processing: 0,
  });

  useEffect(() => {
    api
      .get<Manual[]>("/api/manuals")
      .then((data) => {
        setStats({
          manuals: data.length,
          manuals_ready: data.filter((m) => m.upload_status === "ready").length,
          manuals_processing: data.filter(
            (m) => m.upload_status === "processing" || m.upload_status === "pending"
          ).length,
        });
      })
      .catch((e: Error) => toast.error(e.message || "Failed to load dashboard stats"));
  }, []);

  if (!user || !tenant) return null;

  const skillColors: Record<string, string> = {
    green: "bg-emerald-100 text-emerald-700",
    apprentice: "bg-amber-100 text-amber-700",
    journeyman: "bg-blue-100 text-blue-700",
  };

  return (
    <div className="space-y-8">
      {/* Welcome */}
      <div>
        <h1 className="text-2xl font-bold">Welcome back, {user.name}</h1>
        <div className="mt-1 flex items-center gap-2">
          <Badge
            className={skillColors[user.skill_level] || ""}
            variant="outline"
          >
            {user.skill_level}
          </Badge>
          <span className="text-sm text-muted-foreground">{tenant.name}</span>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={BookOpen}
          title="Manuals"
          value={String(stats.manuals)}
          subtitle={
            stats.manuals_processing > 0
              ? `${stats.manuals_ready} ready, ${stats.manuals_processing} processing`
              : "uploaded"
          }
          color="text-emerald-600"
        />
        <StatCard
          icon={MessageSquare}
          title="Queries"
          value={`0 / ${tenant.query_limit_monthly}`}
          subtitle="this month"
          color="text-blue-600"
        />
        <StatCard
          icon={Users}
          title="Team"
          value={tenant.type === "shop" ? "—" : "Solo"}
          subtitle={tenant.type === "shop" ? "members" : "individual account"}
          color="text-amber-500"
        />
        <StatCard
          icon={CreditCard}
          title="Plan"
          value={tenant.subscription_plan.toUpperCase()}
          subtitle={
            tenant.subscription_plan === "free" ? (
              <Link href="/billing" className="text-emerald-600 hover:underline">
                Upgrade
              </Link>
            ) : (
              "active"
            )
          }
          color="text-slate-600"
        />
      </div>

      {/* Quick actions */}
      <div>
        <h2 className="mb-4 text-lg font-semibold">Quick Actions</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <QuickAction
            icon={BookOpen}
            title="Upload Manual"
            description="Add a service manual to your library"
            href="/manuals"
          />
          <QuickAction
            icon={MessageSquare}
            title="Ask a Question"
            description="Query your manuals with AI"
            href="/query"
          />
          <QuickAction
            icon={Image}
            title="View Schematics"
            description="Interactive hydraulic and electrical diagrams"
            href="/viewer"
          />
          <QuickAction
            icon={GraduationCap}
            title="Start Training"
            description="Learn equipment systems step by step"
            href="/teach"
          />
        </div>
      </div>
    </div>
  );
}

function StatCard({
  icon: Icon,
  title,
  value,
  subtitle,
  color,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  value: string;
  subtitle: React.ReactNode;
  color: string;
}) {
  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{title}</p>
            <p className="mt-1 text-2xl font-bold">{value}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>
          </div>
          <Icon className={`h-8 w-8 ${color} opacity-70`} />
        </div>
      </CardContent>
    </Card>
  );
}

function QuickAction({
  icon: Icon,
  title,
  description,
  href,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  href: string;
}) {
  return (
    <Link href={href}>
      <Card className="transition-shadow hover:shadow-md">
        <CardContent className="flex items-center gap-4 p-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50">
            <Icon className="h-5 w-5 text-emerald-600" />
          </div>
          <div>
            <h3 className="font-medium">{title}</h3>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
