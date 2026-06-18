"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { runs as runsApi, exports as exportsApi, ApiError } from "@/lib/api";
import { WorkflowRun, WorkflowType, WORKFLOW_LABELS } from "@/lib/types";
import { RunCard } from "@/components/ui/run-card";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toast";
import { Plus, Loader2, Search, X, Archive } from "lucide-react";
import { cn } from "@/lib/utils";

const WORKFLOW_FILTERS: { label: string; value: string }[] = [
  { label: "All", value: "" },
  { label: "Web Orders", value: "web_orders_check" },
  { label: "Jetro / RD", value: "jetro_reconciliation" },
  { label: "Vendor Bills", value: "vendor_bill_po_bank" },
  { label: "Price Changes", value: "combined_price_changes" },
];

type DateRange = "all" | "today" | "7d" | "30d";

const DATE_FILTERS: { label: string; value: DateRange }[] = [
  { label: "All time", value: "all" },
  { label: "Today", value: "today" },
  { label: "Last 7 days", value: "7d" },
  { label: "Last 30 days", value: "30d" },
];

function toDayKey(iso: string): string {
  // YYYY-MM-DD in local time; tolerates either date-only or full ISO strings
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function formatDayHeader(key: string): string {
  const today = toDayKey(new Date().toISOString());
  const yest = new Date();
  yest.setDate(yest.getDate() - 1);
  const yKey = toDayKey(yest.toISOString());
  if (key === today) return "Today";
  if (key === yKey) return "Yesterday";
  const d = new Date(`${key}T00:00:00`);
  return d.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: d.getFullYear() === new Date().getFullYear() ? undefined : "numeric",
  });
}

export default function RunsPage() {
  const searchParams = useSearchParams();
  const [type, setType] = useState(searchParams.get("type") ?? "");
  const [dateRange, setDateRange] = useState<DateRange>("all");
  const [query, setQuery] = useState("");
  const [allRuns, setAllRuns] = useState<WorkflowRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [archivingDay, setArchivingDay] = useState<string | null>(null);

  const downloadDayArchive = async (dayKey: string) => {
    setArchivingDay(dayKey);
    try {
      await exportsApi.downloadDayArchive(dayKey);
      toast.success(`Archive for ${dayKey} downloaded`);
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : "Failed to download archive";
      toast.error(msg);
    } finally {
      setArchivingDay(null);
    }
  };

  useEffect(() => {
    setLoading(true);
    setError(null);
    runsApi
      .list(type ? { workflow_type: type } : {})
      .then((r) => setAllRuns(r as WorkflowRun[]))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [type]);

  const title = type
    ? WORKFLOW_LABELS[type as WorkflowType] ?? type
    : "All Runs";

  const filtered = useMemo(() => {
    let out = allRuns;
    if (dateRange !== "all") {
      const now = new Date();
      const cutoff = new Date(now);
      if (dateRange === "today") cutoff.setHours(0, 0, 0, 0);
      else if (dateRange === "7d") cutoff.setDate(cutoff.getDate() - 7);
      else if (dateRange === "30d") cutoff.setDate(cutoff.getDate() - 30);
      out = out.filter((r) => new Date(r.run_date).getTime() >= cutoff.getTime());
    }
    if (query.trim()) {
      const q = query.trim().toLowerCase();
      out = out.filter(
        (r) =>
          r.name.toLowerCase().includes(q) ||
          (r.notes ?? "").toLowerCase().includes(q) ||
          r.id.toLowerCase().includes(q),
      );
    }
    return out;
  }, [allRuns, query, dateRange]);

  const grouped = useMemo(() => {
    const groups = new Map<string, WorkflowRun[]>();
    for (const r of filtered) {
      const key = toDayKey(r.run_date);
      const arr = groups.get(key) ?? [];
      arr.push(r);
      groups.set(key, arr);
    }
    return Array.from(groups.entries())
      .sort((a, b) => (a[0] < b[0] ? 1 : -1))
      .map(([key, runs]) => ({
        key,
        label: formatDayHeader(key),
        runs: runs.sort(
          (a, b) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
        ),
      }));
  }, [filtered]);

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6 lg:p-8">
      <header className="flex items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Runs</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {loading ? "Loading…" : `${filtered.length} of ${allRuns.length} runs`}
          </p>
        </div>
        <Link href={`/runs/new${type ? `?type=${type}` : ""}`}>
          <Button size="lg">
            <Plus className="size-3.5" />
            New Run
          </Button>
        </Link>
      </header>

      {/* Filters */}
      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap gap-1.5">
            {WORKFLOW_FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => setType(f.value)}
                className={cn(
                  "rounded-full px-3 py-1.5 text-xs font-medium transition-all duration-150 cursor-pointer",
                  type === f.value
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "border border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground",
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search runs…"
              className="w-full rounded-lg border border-input bg-card pl-8 pr-8 py-1.5 text-sm outline-none transition-colors focus:border-ring focus:ring-2 focus:ring-ring/30"
            />
            {query && (
              <button
                onClick={() => setQuery("")}
                aria-label="Clear search"
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-muted-foreground hover:text-foreground cursor-pointer"
              >
                <X className="size-3.5" />
              </button>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {DATE_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setDateRange(f.value)}
              className={cn(
                "rounded-full px-3 py-1.5 text-[11px] font-medium transition-all duration-150 cursor-pointer",
                dateRange === f.value
                  ? "bg-foreground text-background shadow-sm"
                  : "border border-border bg-card text-muted-foreground hover:border-foreground/40 hover:text-foreground",
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="flex justify-center py-16">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        </div>
      )}
      {error && (
        <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </p>
      )}
      {!loading && !error && filtered.length === 0 && (
        <div className="rounded-xl border border-dashed border-border bg-card/50 py-14 text-center">
          <p className="text-sm text-muted-foreground">
            {query ? `No runs match "${query}".` : "No runs found."}
          </p>
          {!query && (
            <Link href={`/runs/new${type ? `?type=${type}` : ""}`} className="mt-2 inline-block text-sm font-medium text-primary hover:underline">
              Create your first run →
            </Link>
          )}
        </div>
      )}
      {!loading && !error && grouped.length > 0 && (
        <div className="space-y-6">
          {grouped.map((group) => (
            <section key={group.key} className="space-y-3">
              <div className="flex items-center gap-3">
                <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-foreground">
                  {group.label}
                </h2>
                <span className="text-[11px] text-muted-foreground">
                  {group.runs.length} {group.runs.length === 1 ? "run" : "runs"}
                </span>
                <div className="h-px flex-1 bg-border" />
                {group.runs.some((r) => r.status === "exported") && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={archivingDay === group.key}
                    onClick={() => downloadDayArchive(group.key)}
                    className="h-7 gap-1.5 text-[11px]"
                  >
                    {archivingDay === group.key ? (
                      <Loader2 className="size-3 animate-spin" />
                    ) : (
                      <Archive className="size-3" />
                    )}
                    Download Day ZIP
                  </Button>
                )}
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {group.runs.map((run) => (
                  <RunCard
                    key={run.id}
                    run={run}
                    onDeleted={() => setAllRuns((prev) => prev.filter((r) => r.id !== run.id))}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
