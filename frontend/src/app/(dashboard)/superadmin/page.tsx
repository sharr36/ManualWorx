"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Database,
  FileText,
  HardDrive,
  Loader2,
  Play,
  RefreshCw,
  RotateCw,
  ScanLine,
  Server,
  Shield,
  Terminal,
  Users,
  XCircle,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";

/* ---------- Types ---------- */

interface SystemOverview {
  totals: {
    tenants: number;
    users: number;
    manuals: number;
    pages: number;
    chunks: number;
    queries: number;
    documents: number;
  };
  recent_7d: { manuals: number; queries: number; active_users: number };
  processing: { in_progress: number; failed: number };
}

interface TenantInfo {
  id: string;
  name: string;
  slug: string;
  type: string;
  subscription_plan: string;
  subscription_status: string;
  manual_limit: number;
  user_limit: number;
  query_limit_monthly: number;
  created_at: string | null;
  owner_email: string | null;
  user_count: number;
  manual_count: number;
  ready_count: number;
  query_count: number;
}

interface UserInfo {
  id: string;
  email: string;
  name: string;
  role: string;
  skill_level: string;
  last_login_at: string | null;
  created_at: string | null;
  tenant_name: string;
  tenant_slug: string;
}

interface Migration {
  filename: string;
  applied: boolean;
  applied_at: string | null;
  line_count: number;
  sql: string;
}

interface HealthChecks {
  healthy: boolean;
  checks: Record<string, Record<string, unknown>>;
}

interface ManualInfo {
  id: string;
  title: string;
  make: string | null;
  model: string | null;
  manual_type: string | null;
  total_pages: number | null;
  upload_status: string;
  created_at: string | null;
  tenant_name: string;
  tenant_slug: string;
  page_count: number;
  chunk_count: number;
  annotation_count: number;
}

/* ---------- Main Page ---------- */

export default function SuperAdminPage() {
  const router = useRouter();
  const { user, isLoading: authLoading } = useAuth();

  useEffect(() => {
    if (!authLoading && (!user || !user.is_superadmin)) {
      router.push("/dashboard");
    }
  }, [user, authLoading, router]);

  if (authLoading || !user?.is_superadmin) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid gap-4 md:grid-cols-4">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Shield className="h-6 w-6 text-red-500" />
        <h1 className="text-2xl font-bold">Super Admin</h1>
        <Badge variant="destructive">System</Badge>
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="tenants">Tenants</TabsTrigger>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="manuals">Manuals</TabsTrigger>
          <TabsTrigger value="migrations">Migrations</TabsTrigger>
          <TabsTrigger value="health">System Health</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6">
          <OverviewTab />
        </TabsContent>
        <TabsContent value="tenants" className="mt-6">
          <TenantsTab />
        </TabsContent>
        <TabsContent value="users" className="mt-6">
          <UsersTab />
        </TabsContent>
        <TabsContent value="manuals" className="mt-6">
          <ManualsTab />
        </TabsContent>
        <TabsContent value="migrations" className="mt-6">
          <MigrationsTab />
        </TabsContent>
        <TabsContent value="health" className="mt-6">
          <HealthTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

/* ---------- Overview Tab ---------- */

function OverviewTab() {
  const [data, setData] = useState<SystemOverview | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<SystemOverview>("/api/superadmin/overview");
      setData(res);
    } catch {
      toast.error("Failed to load overview");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading || !data) {
    return (
      <div className="grid gap-4 md:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
    );
  }

  const stats = [
    { label: "Tenants", value: data.totals.tenants, icon: Users },
    { label: "Users", value: data.totals.users, icon: Users },
    { label: "Manuals", value: data.totals.manuals, icon: FileText },
    { label: "Pages", value: data.totals.pages, icon: FileText },
    { label: "Chunks", value: data.totals.chunks, icon: Database },
    { label: "Queries", value: data.totals.queries, icon: Zap },
    { label: "Documents", value: data.totals.documents, icon: FileText },
  ];

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-4">
        {stats.map((s) => (
          <Card key={s.label}>
            <CardContent className="flex items-center gap-3 p-4">
              <s.icon className="h-5 w-5 text-muted-foreground" />
              <div>
                <p className="text-2xl font-bold">{s.value.toLocaleString()}</p>
                <p className="text-xs text-muted-foreground">{s.label}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Recent activity */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardContent className="p-4">
            <h3 className="text-sm font-semibold text-muted-foreground">Last 7 Days</h3>
            <div className="mt-2 space-y-2 text-sm">
              <div className="flex justify-between">
                <span>New Manuals</span>
                <Badge variant="secondary">{data.recent_7d.manuals}</Badge>
              </div>
              <div className="flex justify-between">
                <span>Queries</span>
                <Badge variant="secondary">{data.recent_7d.queries}</Badge>
              </div>
              <div className="flex justify-between">
                <span>Active Users</span>
                <Badge variant="secondary">{data.recent_7d.active_users}</Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <h3 className="text-sm font-semibold text-muted-foreground">Processing Queue</h3>
            <div className="mt-2 space-y-2 text-sm">
              <div className="flex justify-between">
                <span>In Progress</span>
                <Badge variant={data.processing.in_progress > 0 ? "default" : "secondary"}>
                  {data.processing.in_progress}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span>Failed</span>
                <Badge variant={data.processing.failed > 0 ? "destructive" : "secondary"}>
                  {data.processing.failed}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <h3 className="text-sm font-semibold text-muted-foreground">Actions</h3>
            <div className="mt-2">
              <Button variant="outline" size="sm" onClick={load}>
                <RefreshCw className="mr-2 h-3.5 w-3.5" />
                Refresh Stats
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

/* ---------- Tenants Tab ---------- */

function TenantsTab() {
  const [tenants, setTenants] = useState<TenantInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get<{ tenants: TenantInfo[] }>("/api/superadmin/tenants");
        setTenants(res.tenants);
      } catch {
        toast.error("Failed to load tenants");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <Skeleton className="h-64" />;

  const planColors: Record<string, string> = {
    free: "bg-slate-100 text-slate-800",
    starter: "bg-blue-100 text-blue-800",
    pro: "bg-purple-100 text-purple-800",
    shop: "bg-emerald-100 text-emerald-800",
  };

  return (
    <Card>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b bg-slate-50">
              <tr>
                <th className="p-3 text-left font-medium">Tenant</th>
                <th className="p-3 text-left font-medium">Owner</th>
                <th className="p-3 text-left font-medium">Plan</th>
                <th className="p-3 text-center font-medium">Users</th>
                <th className="p-3 text-center font-medium">Manuals</th>
                <th className="p-3 text-center font-medium">Queries</th>
                <th className="p-3 text-left font-medium">Created</th>
              </tr>
            </thead>
            <tbody>
              {tenants.map((t) => (
                <tr key={t.id} className="border-b last:border-0 hover:bg-slate-50">
                  <td className="p-3">
                    <div className="font-medium">{t.name}</div>
                    <div className="text-xs text-muted-foreground">{t.slug} ({t.type})</div>
                  </td>
                  <td className="p-3 text-xs">{t.owner_email || "—"}</td>
                  <td className="p-3">
                    <Badge className={planColors[t.subscription_plan] || planColors.free}>
                      {t.subscription_plan}
                    </Badge>
                    {t.subscription_status !== "active" && (
                      <Badge variant="outline" className="ml-1 text-[10px]">
                        {t.subscription_status}
                      </Badge>
                    )}
                  </td>
                  <td className="p-3 text-center">
                    {t.user_count}/{t.user_limit}
                  </td>
                  <td className="p-3 text-center">
                    {t.ready_count}/{t.manual_count}
                    <span className="text-xs text-muted-foreground"> (lim {t.manual_limit})</span>
                  </td>
                  <td className="p-3 text-center">{t.query_count}</td>
                  <td className="p-3 text-xs text-muted-foreground">
                    {t.created_at ? new Date(t.created_at).toLocaleDateString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

/* ---------- Users Tab ---------- */

function UsersTab() {
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get<{ users: UserInfo[] }>("/api/superadmin/users");
        setUsers(res.users);
      } catch {
        toast.error("Failed to load users");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <Skeleton className="h-64" />;

  const roleColors: Record<string, string> = {
    owner: "bg-amber-100 text-amber-800",
    manager: "bg-blue-100 text-blue-800",
    technician: "bg-slate-100 text-slate-800",
  };

  return (
    <Card>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b bg-slate-50">
              <tr>
                <th className="p-3 text-left font-medium">Name</th>
                <th className="p-3 text-left font-medium">Email</th>
                <th className="p-3 text-left font-medium">Role</th>
                <th className="p-3 text-left font-medium">Tenant</th>
                <th className="p-3 text-left font-medium">Last Login</th>
                <th className="p-3 text-left font-medium">Created</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b last:border-0 hover:bg-slate-50">
                  <td className="p-3 font-medium">{u.name}</td>
                  <td className="p-3 text-xs">{u.email}</td>
                  <td className="p-3">
                    <Badge className={roleColors[u.role] || roleColors.technician}>{u.role}</Badge>
                  </td>
                  <td className="p-3 text-xs">{u.tenant_name}</td>
                  <td className="p-3 text-xs text-muted-foreground">
                    {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "Never"}
                  </td>
                  <td className="p-3 text-xs text-muted-foreground">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

/* ---------- Manuals Tab ---------- */

function ManualsTab() {
  const [manuals, setManuals] = useState<ManualInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [reprocessing, setReprocessing] = useState<string | null>(null);
  const [reembedding, setReembedding] = useState<string | null>(null);
  const [reclassifying, setReclassifying] = useState<string | null>(null);
  const [rechunking, setRechunking] = useState<string | null>(null);
  const [reocring, setReocring] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<{ manuals: ManualInfo[] }>("/api/superadmin/manuals");
      setManuals(res.manuals);
    } catch {
      toast.error("Failed to load manuals");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleReprocess = async (id: string) => {
    setReprocessing(id);
    try {
      await api.post(`/api/superadmin/manuals/${id}/reprocess`);
      toast.success("Reprocessing started");
      await load();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Reprocess failed");
    } finally {
      setReprocessing(null);
    }
  };

  const handleReembed = async (id: string) => {
    setReembedding(id);
    try {
      await api.post(`/api/superadmin/manuals/${id}/re-embed`);
      toast.success("Re-embedding started");
      await load();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Re-embed failed");
    } finally {
      setReembedding(null);
    }
  };

  const handleReclassify = async (id: string) => {
    setReclassifying(id);
    try {
      await api.post(`/api/superadmin/manuals/${id}/reclassify`);
      toast.success("Reclassification started");
      await load();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Reclassify failed");
    } finally {
      setReclassifying(null);
    }
  };

  const handleRechunk = async (id: string) => {
    setRechunking(id);
    try {
      await api.post(`/api/superadmin/manuals/${id}/rechunk`);
      toast.success("Re-chunking started — will delete old chunks, re-chunk, and embed");
      await load();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Re-chunk failed");
    } finally {
      setRechunking(null);
    }
  };

  const handleReocr = async (id: string) => {
    setReocring(id);
    try {
      const res = await api.post<{ empty_pages: number }>(`/api/superadmin/manuals/${id}/reocr`);
      toast.success(`Re-OCR started for ${res.empty_pages} empty pages — will rechunk + embed after`);
      await load();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Re-OCR failed");
    } finally {
      setReocring(null);
    }
  };

  if (loading) return <Skeleton className="h-64" />;

  const statusColors: Record<string, string> = {
    ready: "bg-emerald-100 text-emerald-800",
    processing: "bg-amber-100 text-amber-800",
    failed: "bg-red-100 text-red-800",
    pending: "bg-slate-100 text-slate-800",
  };

  return (
    <Card>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b bg-slate-50">
              <tr>
                <th className="p-3 text-left font-medium">Title</th>
                <th className="p-3 text-left font-medium">Make/Model</th>
                <th className="p-3 text-left font-medium">Tenant</th>
                <th className="p-3 text-left font-medium">Status</th>
                <th className="p-3 text-center font-medium">Pages</th>
                <th className="p-3 text-center font-medium">Chunks</th>
                <th className="p-3 text-center font-medium">Annotations</th>
                <th className="p-3 text-left font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {manuals.map((m) => (
                <tr key={m.id} className="border-b last:border-0 hover:bg-slate-50">
                  <td className="max-w-[200px] truncate p-3 font-medium">{m.title}</td>
                  <td className="p-3 text-xs">
                    {m.make || "—"} {m.model || ""}
                  </td>
                  <td className="p-3 text-xs">{m.tenant_name}</td>
                  <td className="p-3">
                    <Badge className={statusColors[m.upload_status] || statusColors.pending}>
                      {m.upload_status}
                    </Badge>
                  </td>
                  <td className="p-3 text-center">{m.page_count}</td>
                  <td className="p-3 text-center">{m.chunk_count}</td>
                  <td className="p-3 text-center">{m.annotation_count}</td>
                  <td className="p-3">
                    <div className="flex gap-1">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={reprocessing === m.id}
                        onClick={() => handleReprocess(m.id)}
                      >
                        {reprocessing === m.id ? (
                          <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                        ) : (
                          <Play className="mr-1 h-3 w-3" />
                        )}
                        Reprocess
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={reembedding === m.id}
                        onClick={() => handleReembed(m.id)}
                      >
                        {reembedding === m.id ? (
                          <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                        ) : (
                          <Database className="mr-1 h-3 w-3" />
                        )}
                        Re-embed
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={reclassifying === m.id}
                        onClick={() => handleReclassify(m.id)}
                      >
                        {reclassifying === m.id ? (
                          <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                        ) : (
                          <RefreshCw className="mr-1 h-3 w-3" />
                        )}
                        Reclassify
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={rechunking === m.id}
                        onClick={() => handleRechunk(m.id)}
                      >
                        {rechunking === m.id ? (
                          <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                        ) : (
                          <RotateCw className="mr-1 h-3 w-3" />
                        )}
                        Re-chunk
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={reocring === m.id}
                        onClick={() => handleReocr(m.id)}
                      >
                        {reocring === m.id ? (
                          <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                        ) : (
                          <ScanLine className="mr-1 h-3 w-3" />
                        )}
                        Re-OCR
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

/* ---------- Migrations Tab ---------- */

function MigrationsTab() {
  const [migrations, setMigrations] = useState<Migration[]>([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [repairSql, setRepairSql] = useState("");
  const [repairDesc, setRepairDesc] = useState("");
  const [repairRunning, setRepairRunning] = useState(false);
  const [repairResult, setRepairResult] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<{ migrations: Migration[]; pending: number }>(
        "/api/superadmin/migrations"
      );
      setMigrations(res.migrations);
      setPendingCount(res.pending);
    } catch {
      toast.error("Failed to load migrations");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const runAllPending = async () => {
    setRunning(true);
    try {
      const res = await api.post<{
        applied: { filename: string; status: string }[];
        errors: { filename: string; error: string }[];
      }>("/api/superadmin/migrations/run");

      if (res.errors.length > 0) {
        toast.error(`Migration failed: ${res.errors[0].filename} — ${res.errors[0].error}`);
      } else if (res.applied.length > 0) {
        toast.success(`Applied ${res.applied.length} migration(s)`);
      } else {
        toast.info("No pending migrations to apply");
      }
      await load();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to run migrations");
    } finally {
      setRunning(false);
    }
  };

  const applySingle = async (filename: string) => {
    setActionLoading(filename);
    try {
      await api.post(`/api/superadmin/migrations/apply/${encodeURIComponent(filename)}`);
      toast.success(`Applied: ${filename}`);
      await load();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : `Failed to apply ${filename}`);
    } finally {
      setActionLoading(null);
    }
  };

  const repairMigration = async (filename: string) => {
    if (!confirm(`Re-run migration "${filename}"?\n\nThis will delete the tracking record and re-execute the SQL. Only safe if the migration uses IF NOT EXISTS / CREATE OR REPLACE patterns.`)) {
      return;
    }
    setActionLoading(filename);
    try {
      await api.post(`/api/superadmin/migrations/repair/${encodeURIComponent(filename)}`);
      toast.success(`Repaired: ${filename}`);
      await load();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : `Failed to repair ${filename}`);
    } finally {
      setActionLoading(null);
    }
  };

  const executeRepairSql = async () => {
    if (!repairSql.trim()) return;
    if (!confirm("Execute this SQL against the production database?\n\nThis action cannot be undone.")) {
      return;
    }
    setRepairRunning(true);
    setRepairResult(null);
    try {
      const res = await api.post<{ status: string; result: string; description: string }>(
        "/api/superadmin/migrations/execute-sql",
        { sql: repairSql, description: repairDesc }
      );
      setRepairResult(`Success: ${res.result}`);
      toast.success("SQL executed successfully");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "SQL execution failed";
      setRepairResult(`Error: ${msg}`);
      toast.error(msg);
    } finally {
      setRepairRunning(false);
    }
  };

  if (loading) return <Skeleton className="h-64" />;

  return (
    <div className="space-y-6">
      {/* Header + run all */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {migrations.length} migration files — {migrations.filter((m) => m.applied).length} applied,{" "}
          {pendingCount} pending
        </p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={load}>
            <RefreshCw className="mr-2 h-3.5 w-3.5" />
            Refresh
          </Button>
          {pendingCount > 0 && (
            <Button size="sm" onClick={runAllPending} disabled={running} variant="destructive">
              {running ? (
                <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
              ) : (
                <Play className="mr-2 h-3.5 w-3.5" />
              )}
              Run All {pendingCount} Pending
            </Button>
          )}
        </div>
      </div>

      {/* Migration list */}
      <div className="space-y-2">
        {migrations.map((m) => {
          const isExpanded = expanded === m.filename;
          const isLoading = actionLoading === m.filename;

          return (
            <Card key={m.filename} className={!m.applied ? "border-amber-200 bg-amber-50/50" : ""}>
              <CardContent className="p-0">
                {/* Header row */}
                <div className="flex items-center gap-3 p-4">
                  <button
                    className="flex min-w-0 flex-1 items-center gap-3 text-left"
                    onClick={() => setExpanded(isExpanded ? null : m.filename)}
                  >
                    {m.applied ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
                    ) : (
                      <AlertTriangle className="h-4 w-4 shrink-0 text-amber-500" />
                    )}
                    <div className="min-w-0 flex-1">
                      <span className="text-sm font-mono font-medium">{m.filename}</span>
                      <span className="ml-2 text-xs text-muted-foreground">
                        ({m.line_count} lines)
                      </span>
                    </div>
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    )}
                  </button>

                  {/* Status + action buttons */}
                  <div className="flex items-center gap-2">
                    {m.applied ? (
                      <>
                        <Badge className="bg-emerald-100 text-emerald-800 text-[10px]">
                          Applied {m.applied_at ? new Date(m.applied_at).toLocaleDateString() : ""}
                        </Badge>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={isLoading}
                          onClick={() => repairMigration(m.filename)}
                          title="Re-run this migration (repair)"
                        >
                          {isLoading ? (
                            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                          ) : (
                            <RotateCw className="mr-1 h-3 w-3" />
                          )}
                          Repair
                        </Button>
                      </>
                    ) : (
                      <>
                        <Badge className="bg-amber-100 text-amber-800 text-[10px]">Pending</Badge>
                        <Button
                          size="sm"
                          disabled={isLoading}
                          onClick={() => applySingle(m.filename)}
                        >
                          {isLoading ? (
                            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                          ) : (
                            <Play className="mr-1 h-3 w-3" />
                          )}
                          Apply
                        </Button>
                      </>
                    )}
                  </div>
                </div>

                {/* Expanded SQL view */}
                {isExpanded && (
                  <div className="border-t bg-slate-950 p-4">
                    <pre className="max-h-[400px] overflow-auto text-xs text-slate-300">
                      <code>{m.sql}</code>
                    </pre>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Repair SQL Console */}
      <Card className="border-red-200">
        <CardContent className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <Terminal className="h-4 w-4 text-red-500" />
            <h3 className="font-semibold text-sm">Repair SQL Console</h3>
            <Badge variant="destructive" className="text-[10px]">Caution</Badge>
          </div>
          <p className="text-xs text-muted-foreground mb-3">
            Execute ad-hoc SQL for emergency repairs. Blocks DROP DATABASE, schema drops,
            and _migrations table manipulation.
          </p>
          <div className="space-y-3">
            <input
              type="text"
              placeholder="Description (what this fix does)"
              value={repairDesc}
              onChange={(e) => setRepairDesc(e.target.value)}
              className="w-full rounded border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <textarea
              placeholder="-- Enter repair SQL here&#10;ALTER TABLE pages ADD COLUMN IF NOT EXISTS new_col TEXT;"
              value={repairSql}
              onChange={(e) => setRepairSql(e.target.value)}
              rows={6}
              className="w-full rounded border bg-slate-950 px-3 py-2 font-mono text-xs text-slate-300 placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-red-500"
            />
            <div className="flex items-center justify-between">
              <Button
                variant="destructive"
                size="sm"
                disabled={repairRunning || !repairSql.trim()}
                onClick={executeRepairSql}
              >
                {repairRunning ? (
                  <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Zap className="mr-2 h-3.5 w-3.5" />
                )}
                Execute SQL
              </Button>
              {repairResult && (
                <span className={`text-xs font-mono ${repairResult.startsWith("Error") ? "text-red-500" : "text-emerald-500"}`}>
                  {repairResult}
                </span>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

/* ---------- Health Tab ---------- */

function HealthTab() {
  const [health, setHealth] = useState<HealthChecks | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<HealthChecks>("/api/superadmin/health");
      setHealth(res);
    } catch {
      toast.error("Failed to load health status");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading || !health) {
    return (
      <div className="grid gap-4 md:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-40" />
        ))}
      </div>
    );
  }

  const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
    postgres: Database,
    redis: Server,
    qdrant: Activity,
    storage: HardDrive,
    config: Zap,
  };

  const statusIcon = (status: string) => {
    if (status === "healthy") return <CheckCircle2 className="h-5 w-5 text-emerald-500" />;
    if (status === "unhealthy") return <XCircle className="h-5 w-5 text-red-500" />;
    return <AlertTriangle className="h-5 w-5 text-amber-500" />;
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {health.healthy ? (
            <CheckCircle2 className="h-5 w-5 text-emerald-500" />
          ) : (
            <XCircle className="h-5 w-5 text-red-500" />
          )}
          <span className="font-semibold">
            System {health.healthy ? "Healthy" : "Degraded"}
          </span>
        </div>
        <Button variant="outline" size="sm" onClick={load}>
          <RefreshCw className="mr-2 h-3.5 w-3.5" />
          Refresh
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {Object.entries(health.checks).map(([key, check]) => {
          const Icon = iconMap[key] || Server;
          const status = (check.status as string) || "unknown";

          return (
            <Card key={key} className={status === "unhealthy" ? "border-red-200" : ""}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Icon className="h-5 w-5 text-muted-foreground" />
                    <h3 className="font-semibold capitalize">{key}</h3>
                  </div>
                  {key !== "config" && statusIcon(status)}
                </div>
                <div className="mt-3 space-y-1 text-xs">
                  {Object.entries(check)
                    .filter(([k]) => k !== "status")
                    .map(([k, v]) => (
                      <div key={k} className="flex justify-between">
                        <span className="text-muted-foreground">{k.replace(/_/g, " ")}</span>
                        <span className="font-mono">
                          {typeof v === "boolean" ? (v ? "Yes" : "No") : String(v)}
                        </span>
                      </div>
                    ))}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
