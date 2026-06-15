"use client";

import { useState, useRef, DragEvent, ChangeEvent } from "react";
import { UploadCloud, X, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { files as filesApi } from "@/lib/api";
import { FILE_TYPE_LABELS } from "@/lib/types";

interface FileUploadProps {
  runId: string;
  fileType: string;
  onUploaded?: () => void;
  accept?: string;
  multiple?: boolean;
}

type UploadState = "idle" | "uploading" | "done" | "error";
interface FailedItem { name: string; message: string; }

export function FileUpload({ runId, fileType, onUploaded, accept, multiple }: FileUploadProps) {
  const [state, setState] = useState<UploadState>("idle");
  const [fileName, setFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<{ done: number; total: number }>({ done: 0, total: 0 });
  const [okCount, setOkCount] = useState(0);
  const [failed, setFailed] = useState<FailedItem[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFiles(fileList: File[]) {
    if (fileList.length === 0) return;
    setState("uploading");
    setError(null);
    setFailed([]);
    setOkCount(0);
    setProgress({ done: 0, total: fileList.length });

    // Upload one file at a time. Backend sha256 dedupe + Anthropic rate
    // guarantees are easier to reason about when requests are serialized.
    let ok = 0;
    const errs: FailedItem[] = [];
    for (let i = 0; i < fileList.length; i++) {
      const f = fileList[i];
      setFileName(f.name);
      setProgress({ done: i, total: fileList.length });
      try {
        await filesApi.upload(runId, fileType, f);
        ok++;
        onUploaded?.();
      } catch (err) {
        errs.push({ name: f.name, message: err instanceof Error ? err.message : "Upload failed" });
      }
    }

    setOkCount(ok);
    setFailed(errs);
    setProgress({ done: fileList.length, total: fileList.length });
    if (ok === 0) {
      setState("error");
      setError(errs[0]?.message ?? "Upload failed");
    } else {
      setState("done");
    }
  }

  function onInputChange(e: ChangeEvent<HTMLInputElement>) {
    const list = e.target.files;
    if (list && list.length > 0) handleFiles(Array.from(list));
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    const list = e.dataTransfer.files;
    if (list && list.length > 0) handleFiles(Array.from(list));
  }

  function reset() {
    setState("idle");
    setFileName(null);
    setError(null);
    setFailed([]);
    setOkCount(0);
    setProgress({ done: 0, total: 0 });
    if (inputRef.current) inputRef.current.value = "";
  }

  const label = FILE_TYPE_LABELS[fileType] ?? fileType;
  const isMulti = progress.total > 1;

  return (
    <div className="space-y-1.5">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <div
        role="button"
        tabIndex={0}
        onClick={() => state === "idle" && inputRef.current?.click()}
        onKeyDown={(e) => e.key === "Enter" && state === "idle" && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "relative flex flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed px-3 py-4 text-center transition-all duration-150 outline-none",
          state === "idle" && !dragging && "border-border bg-muted/20 hover:border-primary/50 hover:bg-primary/[0.04] cursor-pointer focus-visible:ring-2 focus-visible:ring-ring/40",
          dragging && "border-primary bg-primary/[0.06] scale-[1.01]",
          state === "uploading" && "border-border bg-muted/40 cursor-wait",
          state === "done" && "border-emerald-300 bg-emerald-50/60 dark:border-emerald-900/60 dark:bg-emerald-950/20",
          state === "error" && "border-rose-300 bg-rose-50/60 dark:border-rose-900/60 dark:bg-rose-950/20",
        )}
      >
        {state === "idle" && (
          <>
            <UploadCloud className="size-5 text-muted-foreground" aria-hidden />
            <p className="text-xs text-muted-foreground">
              Click or drag &amp; drop{multiple ? " (one or more)" : ""}
            </p>
          </>
        )}
        {state === "uploading" && (
          <>
            <Loader2 className="size-5 animate-spin text-primary" aria-hidden />
            {isMulti ? (
              <p className="text-xs text-muted-foreground">
                Uploading {Math.min(progress.done + 1, progress.total)} of {progress.total}
                {fileName ? <span className="block max-w-full truncate text-[11px] opacity-80">{fileName}</span> : null}
              </p>
            ) : (
              <p className="max-w-full truncate text-xs text-muted-foreground">{fileName}</p>
            )}
          </>
        )}
        {state === "done" && (
          <>
            <CheckCircle2 className="size-5 text-emerald-600" aria-hidden />
            {isMulti ? (
              <p className="text-xs font-medium text-emerald-700 dark:text-emerald-300">
                Uploaded {okCount} of {progress.total}
                {failed.length > 0 && (
                  <span className="mt-1 block text-[10px] font-normal text-rose-600 dark:text-rose-400">
                    {failed.length} failed: {failed.map((f) => f.name).join(", ")}
                  </span>
                )}
              </p>
            ) : (
              <p className="max-w-full truncate text-xs font-medium text-emerald-700 dark:text-emerald-300">
                {fileName}
              </p>
            )}
            <button
              onClick={(e) => { e.stopPropagation(); reset(); }}
              aria-label="Reset upload"
              className="absolute top-1 right-1 rounded p-0.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground cursor-pointer"
            >
              <X className="size-3.5" />
            </button>
          </>
        )}
        {state === "error" && (
          <>
            <AlertCircle className="size-5 text-destructive" aria-hidden />
            <p className="text-[11px] text-destructive line-clamp-2">{error}</p>
            <button
              onClick={(e) => { e.stopPropagation(); reset(); }}
              aria-label="Retry upload"
              className="absolute top-1 right-1 rounded p-0.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground cursor-pointer"
            >
              <X className="size-3.5" />
            </button>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          className="sr-only"
          accept={accept}
          multiple={multiple}
          onChange={onInputChange}
        />
      </div>
    </div>
  );
}
