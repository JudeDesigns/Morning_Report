"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  runs as runsApi,
  files as filesApi,
  webOrders,
  jetro,
  vendorBills,
  combinedPrice,
  exports as exportsApi,
  ApiError,
} from "@/lib/api";
import { VendorBillsPanel } from "@/components/vendor-bills/vendor-bills-panel";
import { ExportConfirmDialog } from "@/components/vendor-bills/export-confirm-dialog";
import { CombinedPricePanel } from "@/components/combined-price/combined-price-panel";
import {
  WorkflowRun,
  UploadedFile,
  VendorBill,
  WORKFLOW_LABELS,
  WORKFLOW_FILE_TYPES,
  FILE_TYPE_LABELS,
  IntegrityMismatchDetail,
} from "@/lib/types";
import { StatusBadge } from "@/components/ui/status-badge";
import { FileUpload } from "@/components/ui/file-upload";
import { Button } from "@/components/ui/button";
import { WorkflowIcon } from "@/components/ui/workflow-icon";
import { OverrideDialog } from "@/components/ui/override-dialog";
import { useAuth } from "@/contexts/auth-context";
import { cn } from "@/lib/utils";
import {
  ArrowLeft,
  Play,
  Download,
  Trash2,
  Loader2,
  FileText,
  RefreshCw,
  Check,
  Upload,
  Cog,
  PackageCheck,
  ShieldCheck,
  RotateCcw,
} from "lucide-react";

const BILL_FILE_TYPES = new Set(["vendor_bill_image", "vendor_bill_pdf"]);

interface OverrideState {
  open: boolean;
  check: string;
  message: string;
  invoices?: (string | number)[];
}

const PHASE_ORDER = ["upload", "process", "export"] as const;
type Phase = (typeof PHASE_ORDER)[number];

function statusToPhase(status: string): { phase: Phase; complete: boolean } {
  if (["draft"].includes(status)) return { phase: "upload", complete: false };
  if (["files_uploaded", "extraction_pending", "extraction_review", "ready_to_process"].includes(status))
    return { phase: "process", complete: false };
  if (["processing"].includes(status)) return { phase: "process", complete: false };
  if (["processed"].includes(status)) return { phase: "export", complete: false };
  if (["exported", "archived"].includes(status)) return { phase: "export", complete: true };
  if (status === "validation_failed") return { phase: "process", complete: false };
  return { phase: "upload", complete: false };
}

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<null | "process" | "export" | "reopen">(null);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [override, setOverride] = useState<OverrideState>({ open: false, check: "", message: "" });
  const [vendorBillsList, setVendorBillsList] = useState<VendorBill[]>([]);
  const [exportConfirm, setExportConfirm] = useState(false);

  const refresh = useCallback(async () => {
    try {
      // Fetch the run first — a files error must never hide the run
      const r = await runsApi.get(id);
      const runData = r as WorkflowRun;
      setRun(runData);
      setError(null);
      // Files are secondary — failure is non-fatal
      try {
        const f = await filesApi.list(id);
        setUploadedFiles(f as UploadedFile[]);
      } catch {
        setUploadedFiles([]);
      }
      // Vendor-bill summary drives the pre-export confirmation gate
      if (runData.workflow_type === "vendor_bill_po_bank") {
        try {
          const b = (await vendorBills.bills(id)) as VendorBill[];
          setVendorBillsList(b);
        } catch {
          setVendorBillsList([]);
        }
      } else {
        setVendorBillsList([]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Run not found");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleProcess() {
    if (!run) return;
    setActionLoading("process");
    setError(null);
    setWarnings([]);
    try {
      let outcome: unknown = null;
      if (run.workflow_type === "web_orders_check") outcome = await webOrders.process(id);
      else if (run.workflow_type === "jetro_reconciliation") outcome = await jetro.process(id);
      else if (run.workflow_type === "vendor_bill_po_bank") outcome = await vendorBills.loadPo(id);
      // Combined-price runs are processed from <CombinedPricePanel>
      const w = (outcome as { warnings?: string[] } | null)?.warnings;
      if (Array.isArray(w) && w.length) setWarnings(w);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Processing failed");
    } finally {
      setActionLoading(null);
    }
  }

  function handleExportClick() {
    if (!run) return;
    if (run.workflow_type === "vendor_bill_po_bank") {
      setExportConfirm(true);
      return;
    }
    void doExport();
  }

  async function doExport() {
    if (!run) return;
    setExportConfirm(false);
    setActionLoading("export");
    setError(null);
    try {
      const fileName = `${run.name.replace(/[^A-Za-z0-9_-]+/g, "_")}.xlsx`;
      await exportsApi.download(id, run.workflow_type, fileName);
      await refresh();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && e.detail && typeof e.detail === "object") {
        const detail = e.detail as IntegrityMismatchDetail;
        if (detail.error === "integrity_mismatch") {
          setOverride({
            open: true,
            check: "jetro_integrity_mismatch",
            message: detail.message,
            invoices: detail.invoices,
          });
          return;
        }
      }
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleReopen() {
    if (!run) return;
    setActionLoading("reopen");
    setError(null);
    try {
      await vendorBills.reopen(id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reopen failed");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleDeleteFile(fileId: string) {
    setUploadedFiles((prev) => prev.filter((f) => f.id !== fileId));
    await filesApi.delete(id, fileId);
    await refresh();
  }

  async function handleDeleteRun() {
    if (!confirm("Delete this run? This cannot be undone.")) return;
    await runsApi.delete(id);
    router.push("/runs");
  }

  const currentPhase = useMemo(() => (run ? statusToPhase(run.status) : null), [run]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!run) {
    return (
      <div className="mx-auto max-w-4xl p-6">
        <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error ?? "Run not found"}
        </p>
        <Link href="/runs" className="mt-2 inline-block text-sm font-medium text-primary hover:underline">
          ← Back to runs
        </Link>
      </div>
    );
  }

  const fileTypes = WORKFLOW_FILE_TYPES[run.workflow_type] ?? [];
  const canProcess = ["files_uploaded", "ready_to_process", "validation_failed"].includes(run.status);
  const canExport = ["processed", "exported"].includes(run.status);
  const canOverride = ["admin", "accounting"].includes(user?.role ?? "");
  const canReopen =
    run.workflow_type === "vendor_bill_po_bank" &&
    run.status === "exported" &&
    canOverride;

  // Jetro runs can be reprocessed after export (new invoice files added to the same run)
  const canReprocessJetro =
    run.workflow_type === "jetro_reconciliation" &&
    ["processed", "exported"].includes(run.status);

  // Pre-export confirmation counts (vendor-bill only)
  const billFiles = uploadedFiles.filter((f) => BILL_FILE_TYPES.has(f.file_type));
  const extractedFileIds = new Set(vendorBillsList.map((b) => b.source_file_id).filter(Boolean));
  const pendingExtractions = billFiles.filter((f) => !extractedFileIds.has(f.id)).length;
  const pendingProcessing = vendorBillsList.filter(
    (b) => b.extraction_status !== "processed",
  ).length;
  const runDate = new Date(run.run_date).toLocaleDateString("en-US", {
    weekday: "long", month: "long", day: "numeric", year: "numeric",
  });
  const uploadCount = uploadedFiles.length;
  const required = fileTypes.length;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6 lg:p-8">
      {/* Header */}
      <header className="flex items-start gap-4">
        <Link
          href="/runs"
          className="mt-1 inline-flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label="Back to runs"
        >
          <ArrowLeft className="size-4" />
        </Link>
        <WorkflowIcon workflow={run.workflow_type} size="lg" className="mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
            {WORKFLOW_LABELS[run.workflow_type]}
          </p>
          <div className="mt-1 flex items-center gap-3 flex-wrap">
            <h1 className="text-xl font-semibold tracking-tight text-foreground truncate">
              {run.name}
            </h1>
            <StatusBadge status={run.status} />
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{runDate}</p>
          {run.notes && (
            <p className="mt-1 text-sm text-muted-foreground italic line-clamp-2">{run.notes}</p>
          )}
        </div>
        <div className="flex gap-1 shrink-0">
          <Button variant="ghost" size="icon" onClick={refresh} title="Refresh">
            <RefreshCw className="size-4" />
          </Button>
          {canOverride && (
            <Button variant="destructive" size="icon" onClick={handleDeleteRun} title="Delete run">
              <Trash2 className="size-4" />
            </Button>
          )}
        </div>
      </header>

      {/* Phase stepper */}
      <PhaseStepper phase={currentPhase?.phase ?? "upload"} status={run.status} />

      {error && (
        <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </p>
      )}

      {warnings.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50/60 px-4 py-3 dark:border-amber-900/60 dark:bg-amber-950/30">
          <p className="text-xs font-semibold uppercase tracking-wider text-amber-800 dark:text-amber-300">
            Processed with {warnings.length} warning{warnings.length === 1 ? "" : "s"}
          </p>
          <ul className="mt-1.5 list-disc space-y-0.5 pl-5 text-xs text-amber-900 dark:text-amber-200">
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Override banner if recorded */}
      {run.overrides && run.overrides.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50/60 px-4 py-3 dark:border-amber-900/60 dark:bg-amber-950/30">
          <div className="flex items-start gap-2.5">
            <ShieldCheck className="mt-0.5 size-4 shrink-0 text-amber-700 dark:text-amber-300" />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold uppercase tracking-wider text-amber-800 dark:text-amber-300">
                {run.overrides.length} override{run.overrides.length === 1 ? "" : "s"} on record
              </p>
              <ul className="mt-1 space-y-0.5 text-xs text-amber-900 dark:text-amber-200">
                {run.overrides.slice(0, 3).map((o, i) => (
                  <li key={i} className="truncate">
                    <span className="font-mono">{o.check}</span> — {o.reason}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* File Uploads */}
      <section className="rounded-xl border border-border bg-card p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-foreground">Required Files</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {uploadCount} of {required} expected file type{required === 1 ? "" : "s"} uploaded
            </p>
          </div>
          {uploadCount >= required && (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 ring-1 ring-inset ring-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:ring-emerald-900/60">
              <Check className="size-3" /> Ready
            </span>
          )}
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {fileTypes.map((ft) => (
            <FileUpload
              key={ft}
              runId={id}
              fileType={ft}
              onUploaded={refresh}
              accept={ft.includes("image") ? "image/*" : ft.includes("pdf") ? ".pdf" : ".xlsx,.xls,.csv"}
              multiple={BILL_FILE_TYPES.has(ft)}
            />
          ))}
        </div>
      </section>

      {/* Uploaded files list */}
      {uploadedFiles.length > 0 && (
        <section className="rounded-xl border border-border bg-card p-5">
          <h2 className="mb-3 text-sm font-semibold text-foreground">
            Uploaded Files <span className="text-muted-foreground font-normal">({uploadedFiles.length})</span>
          </h2>
          <ul className="space-y-1.5">
            {uploadedFiles.map((f) => (
              <li
                key={f.id}
                className="flex items-center gap-3 rounded-lg border border-border/60 bg-muted/30 px-3 py-2 transition-colors hover:bg-muted/50"
              >
                <FileText className="size-4 shrink-0 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-foreground">{f.original_filename}</p>
                  <p className="text-[11px] text-muted-foreground">
                    {FILE_TYPE_LABELS[f.file_type] ?? f.file_type} · {f.parse_status}
                  </p>
                </div>
                <button
                  onClick={() => handleDeleteFile(f.id)}
                  aria-label="Delete file"
                  className="rounded p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive cursor-pointer"
                >
                  <Trash2 className="size-3.5" />
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Workflow-specific review panel */}
      {run.workflow_type === "vendor_bill_po_bank" && uploadedFiles.length > 0 && (
        <VendorBillsPanel runId={id} uploadedFiles={uploadedFiles} onChange={refresh} />
      )}
      {run.workflow_type === "combined_price_changes" && (
        <CombinedPricePanel runId={id} disabled={canExport} onProcessed={refresh} />
      )}

      {/* Actions */}
      <section className="flex flex-wrap items-center gap-3 border-t border-border pt-5">
        {canProcess && run.workflow_type !== "combined_price_changes" && run.workflow_type !== "vendor_bill_po_bank" && (
          <Button onClick={handleProcess} disabled={actionLoading !== null} size="lg">
            {actionLoading === "process" ? (
              <><Loader2 className="size-3.5 animate-spin" />Processing…</>
            ) : (
              <><Play className="size-3.5" />Run Processing</>
            )}
          </Button>
        )}
        {canReprocessJetro && (
          <Button variant="outline" onClick={handleProcess} disabled={actionLoading !== null} size="lg"
            title="Upload additional RD invoice files above, then click to re-reconcile with all files in this run">
            {actionLoading === "process" ? (
              <><Loader2 className="size-3.5 animate-spin" />Reprocessing…</>
            ) : (
              <><RefreshCw className="size-3.5" />Reprocess with New Files</>
            )}
          </Button>
        )}
        {canExport && (
          <Button variant="secondary" onClick={handleExportClick} disabled={actionLoading !== null} size="lg">
            {actionLoading === "export" ? (
              <><Loader2 className="size-3.5 animate-spin" />Preparing…</>
            ) : (
              <><Download className="size-3.5" />Download Workbook</>
            )}
          </Button>
        )}
        {canReopen && (
          <Button variant="outline" onClick={handleReopen} disabled={actionLoading !== null} size="lg">
            {actionLoading === "reopen" ? (
              <><Loader2 className="size-3.5 animate-spin" />Reopening…</>
            ) : (
              <><RotateCcw className="size-3.5" />Reopen Run</>
            )}
          </Button>
        )}
        {run.status === "processing" && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Processing in progress — refresh to check status.
          </div>
        )}
      </section>

      <OverrideDialog
        open={override.open}
        onOpenChange={(open) => setOverride((s) => ({ ...s, open }))}
        runId={id}
        check={override.check}
        message={override.message}
        affectedInvoices={override.invoices}
        onSuccess={() => {
          // After recording the override, refresh and immediately retry the export
          refresh().then(() => doExport());
        }}
      />

      <ExportConfirmDialog
        open={exportConfirm}
        onOpenChange={setExportConfirm}
        pendingExtractions={pendingExtractions}
        pendingProcessing={pendingProcessing}
        totalBills={vendorBillsList.length}
        onConfirm={doExport}
        loading={actionLoading === "export"}
      />
    </div>
  );
}

function PhaseStepper({ phase, status }: { phase: Phase; status: string }) {
  const steps: { id: Phase; label: string; icon: typeof Upload }[] = [
    { id: "upload", label: "Upload", icon: Upload },
    { id: "process", label: "Process", icon: Cog },
    { id: "export", label: "Export", icon: PackageCheck },
  ];
  const idx = PHASE_ORDER.indexOf(phase);
  const isFailed = status === "validation_failed";
  return (
    <ol className="flex items-center gap-2 rounded-xl border border-border bg-card p-3">
      {steps.map((s, i) => {
        const Icon = s.icon;
        const isActive = i === idx;
        const isDone = i < idx || (i === idx && status === "exported");
        const failed = isActive && isFailed;
        return (
          <li key={s.id} className="flex flex-1 items-center gap-2">
            <div
              className={cn(
                "flex flex-1 items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition-colors",
                isDone && "bg-emerald-50 text-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300",
                isActive && !isDone && !failed && "bg-primary/[0.08] text-primary",
                failed && "bg-rose-50 text-rose-700 dark:bg-rose-950/30 dark:text-rose-300",
                !isActive && !isDone && "text-muted-foreground",
              )}
            >
              <span
                className={cn(
                  "inline-flex size-6 items-center justify-center rounded-full text-[11px] font-semibold",
                  isDone && "bg-emerald-600 text-white",
                  isActive && !isDone && !failed && "bg-primary text-primary-foreground",
                  failed && "bg-rose-600 text-white",
                  !isActive && !isDone && "bg-muted text-muted-foreground",
                )}
              >
                {isDone ? <Check className="size-3" strokeWidth={3} /> : <Icon className="size-3" />}
              </span>
              <span className="text-xs font-medium">{s.label}</span>
            </div>
            {i < steps.length - 1 && (
              <span className={cn("h-px w-3 shrink-0", i < idx ? "bg-emerald-400" : "bg-border")} aria-hidden />
            )}
          </li>
        );
      })}
    </ol>
  );
}
