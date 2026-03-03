"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  BookOpen,
  CreditCard,
  FileText,
  GraduationCap,
  Image,
  LayoutDashboard,
  MessageSquare,
  Settings,
  Users,
  Wrench,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { User, Tenant } from "@/types";

interface SidebarProps {
  user: User;
  tenant: Tenant;
  isOpen: boolean;
  onClose: () => void;
}

const mainNav = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/manuals", label: "Manuals", icon: BookOpen },
  { href: "/query", label: "Query", icon: MessageSquare },
  { href: "/viewer", label: "Viewer", icon: Image },
  { href: "/teach", label: "Teach", icon: GraduationCap },
  { href: "/documents", label: "Documents", icon: FileText },
];

const accountNav = [
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/billing", label: "Billing", icon: CreditCard },
];

const adminNav = [
  { href: "/admin", label: "Team", icon: Users },
];

export function Sidebar({ user, tenant, isOpen, onClose }: SidebarProps) {
  const pathname = usePathname();
  const isOwnerOrManager = user.role === "owner" || user.role === "manager";

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-slate-900 text-white transition-transform lg:static lg:translate-x-0",
          isOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Logo */}
        <div className="flex h-16 items-center justify-between px-4">
          <Link href="/dashboard" className="flex items-center gap-2">
            <Wrench className="h-6 w-6 text-emerald-500" />
            <span className="text-lg font-bold">ManualWorx</span>
          </Link>
          <button onClick={onClose} className="lg:hidden">
            <X className="h-5 w-5 text-slate-400" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 px-3 py-4">
          {mainNav.map((item) => (
            <NavLink key={item.href} item={item} pathname={pathname} />
          ))}

          <div className="my-4 border-t border-slate-700" />

          {accountNav.map((item) => (
            <NavLink key={item.href} item={item} pathname={pathname} />
          ))}

          {isOwnerOrManager && (
            <>
              <div className="my-4 border-t border-slate-700" />
              {adminNav.map((item) => (
                <NavLink key={item.href} item={item} pathname={pathname} />
              ))}
            </>
          )}
        </nav>

        {/* Tenant info */}
        <div className="border-t border-slate-700 p-4">
          <p className="truncate text-sm font-medium">{tenant.name}</p>
          <Badge
            variant="secondary"
            className="mt-1 bg-slate-700 text-slate-300"
          >
            {tenant.subscription_plan.toUpperCase()}
          </Badge>
        </div>
      </aside>
    </>
  );
}

function NavLink({
  item,
  pathname,
}: {
  item: { href: string; label: string; icon: React.ComponentType<{ className?: string }> };
  pathname: string;
}) {
  const isActive = pathname === item.href || pathname.startsWith(item.href + "/");

  return (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
        isActive
          ? "border-l-2 border-emerald-500 bg-emerald-500/10 text-white"
          : "text-slate-400 hover:bg-slate-800 hover:text-white"
      )}
    >
      <item.icon className="h-5 w-5 shrink-0" />
      {item.label}
    </Link>
  );
}
