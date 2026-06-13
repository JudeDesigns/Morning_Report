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
}

type UploadState = "idle" | "uploading" | "done" | "error";

export function FileUpload({ runId, fileType, onUploaded, accept }: FileUploadProps) {
  const [state, setState] = useState<UploadState>("idle");
  const [fileName, setFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    setFileName(file.name);
    setState("uploading");
    setError(null);
    try {
      await filesApi.upload(runId, fileType, file);
      setState("done");
      onUploaded?.();
    } catch (err) {
      setState("error");
      setError(err instanceof Error ? err.message : "Upload failed");
    }
  }

  function onInputChange(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) handleFile(f);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) handleFile(f);
  }

  function reset() {
    setState("idle");
    setFileName(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  const label = FILE_TYPE_LABELS[fileType] ?? fileType;

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
              Click or drag &amp; drop
            </p>
          </>
        )}
        {state === "uploading" && (
          <>
            <Loader2 className="size-5 animate-spin text-primary" aria-hidden />
            <p className="max-w-full truncate text-xs text-muted-foreground">{fileName}</p>
          </>
        )}
        {state === "done" && (
          <>
            <CheckCircle2 className="size-5 text-emerald-600" aria-hidden />
            <p className="max-w-full truncate text-xs font-medium text-emerald-700 dark:text-emerald-300">
              {fileName}
            </p>
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
          onChange={onInputChange}
        />
      </div>
    </div>
  );
}
