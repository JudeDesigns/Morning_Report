"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  ClipboardList,
  ShoppingCart,
  Receipt,
  TrendingUp,
  LogOut,
  Plus,
} from "lucide-react";
import { Button } from "@/components/ui/button";

interface NavItem {
  label: string;
  href: string;
  icon: typeof LayoutDashboard;
  type?: string;
}

const PRIMARY: NavItem[] = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard },
  { label: "All Runs", href: "/runs", icon: ClipboardList },
];

const WORKFLOWS: NavItem[] = [
  { label: "Web Orders", href: "/runs?type=web_orders_check", icon: ShoppingCart, type: "web_orders_check" },
  { label: "Jetro / RD", href: "/runs?type=jetro_reconciliation", icon: ClipboardList, type: "jetro_reconciliation" },
  { label: "Vendor Bills", href: "/runs?type=vendor_bill_po_bank", icon: Receipt, type: "vendor_bill_po_bank" },
  { label: "Price Changes", href: "/runs?type=combined_price_changes", icon: TrendingUp, type: "combined_price_changes" },
];

export function Sidebar() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { user, logout } = useAuth();
  const activeType = searchParams.get("type");

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  function isActive(item: NavItem): boolean {
    const base = item.href.split("?")[0];
    if (item.type) {
      // Workflow link is active iff we're on /runs with matching ?type
      return pathname === "/runs" && activeType === item.type;
    }
    if (base === "/") return pathname === "/";
    if (base === "/runs") return pathname.startsWith("/runs") && !activeType;
    return pathname === base;
  }

  function renderItem(item: NavItem) {
    const Icon = item.icon;
    const active = isActive(item);
    return (
      <Link
        key={item.href}
        href={item.href}
        className={cn(
          "group/nav flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-all duration-150",
          active
            ? "bg-primary/10 text-primary font-medium ring-1 ring-inset ring-primary/15"
            : "text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
        )}
      >
        <Icon className={cn("size-4 shrink-0 transition-colors", active ? "text-primary" : "text-muted-foreground group-hover/nav:text-foreground")} />
        <span className="truncate">{item.label}</span>
      </Link>
    );
  }

  const initials = (user?.name || user?.email || "?")
    .split(/[\s@]/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0]?.toUpperCase())
    .join("");

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
      {/* Brand */}
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-sidebar-border">
        <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
          <span className="text-[11px] font-bold tracking-tight">B&amp;R</span>
        </span>
        <div className="min-w-0 flex-1">
          <h1 className="text-[13px] font-semibold leading-tight text-sidebar-foreground">
            B&amp;R Food Services
          </h1>
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Operations Portal
          </p>
        </div>
      </div>

      {/* New Run CTA */}
      <div className="px-3 pt-3">
        <Link href="/runs/new" className="block">
          <Button className="w-full justify-center" size="lg">
            <Plus className="size-3.5" />
            New Run
          </Button>
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-4">
        <div className="space-y-0.5">
          <p className="px-2.5 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Overview
          </p>
          {PRIMARY.map(renderItem)}
        </div>
        <div className="space-y-0.5">
          <p className="px-2.5 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Workflows
          </p>
          {WORKFLOWS.map(renderItem)}
        </div>
      </nav>

      {/* User */}
      <div className="border-t border-sidebar-border px-3 py-3">
        <div className="flex items-center gap-2.5 rounded-lg px-2 py-1.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-xs font-semibold ring-1 ring-inset ring-primary/20">
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-sidebar-foreground">
              {user?.name ?? user?.email ?? "—"}
            </p>
            <p className="truncate text-[10px] uppercase tracking-wider text-muted-foreground">
              {user?.role ?? ""}
            </p>
          </div>
          <button
            onClick={handleLogout}
            title="Sign out"
            aria-label="Sign out"
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-foreground cursor-pointer"
          >
            <LogOut className="size-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
