const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

function detailToMessage(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((d) => (typeof d === "string" ? d : typeof d === "object" && d && "msg" in d ? String((d as { msg: unknown }).msg) : ""))
      .filter(Boolean);
    if (parts.length) return parts.join("; ");
  }
  if (detail && typeof detail === "object") {
    const d = detail as Record<string, unknown>;
    if (typeof d.message === "string") return d.message;
    if (typeof d.error === "string") return d.error;
  }
  return "Request failed";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = (body as { detail?: unknown }).detail ?? body;
    throw new ApiError(detailToMessage(detail), res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

async function upload(path: string, formData: FormData): Promise<unknown> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = (body as { detail?: unknown }).detail ?? body;
    throw new ApiError(detailToMessage(detail), res.status, detail);
  }
  return res.json();
}

async function downloadBlob(path: string, init: RequestInit = {}): Promise<Blob> {
  const token = getToken();
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", ...init, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = (body as { detail?: unknown }).detail ?? body;
    throw new ApiError(detailToMessage(detail), res.status, detail);
  }
  return res.blob();
}

// ── Auth ──────────────────────────────────────────────────────────────────────
export const auth = {
  // Backend uses OAuth2PasswordRequestForm → must send as form-encoded, not JSON
  login: async (email: string, password: string) => {
    const body = new URLSearchParams({ username: email, password });
    const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? "Login failed");
    }
    return res.json() as Promise<{ access_token: string; token_type: string; user: { id: string; email: string; name: string; role: string } }>;
  },
  me: () => request<{ id: string; email: string; name: string; role: string }>("/api/v1/auth/me"),
  register: (data: { email: string; password: string; name: string; role?: string }) =>
    request("/api/v1/auth/register", { method: "POST", body: JSON.stringify(data) }),
};

// ── Runs ──────────────────────────────────────────────────────────────────────
export const runs = {
  list: (params?: { workflow_type?: string; status?: string; limit?: number }) => {
    const qs = new URLSearchParams(params as Record<string, string>).toString();
    return request<unknown[]>(`/api/v1/runs${qs ? `?${qs}` : ""}`);
  },
  get: (id: string) => request<unknown>(`/api/v1/runs/${id}`),
  create: (data: { workflow_type: string; name: string; run_date: string; notes?: string }) =>
    request<unknown>("/api/v1/runs", { method: "POST", body: JSON.stringify(data) }),
  update: (id: string, data: Partial<{ name: string; notes: string; status: string }>) =>
    request<unknown>(`/api/v1/runs/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (id: string) => request<void>(`/api/v1/runs/${id}`, { method: "DELETE" }),
  override: (
    id: string,
    data: { check: string; reason: string; original_value?: string; affected_rows?: string[] },
  ) =>
    request<{ success: boolean; overrides: unknown[] }>(`/api/v1/runs/${id}/override`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

// ── Files ─────────────────────────────────────────────────────────────────────
export const files = {
  upload: (runId: string, fileType: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("file_type", fileType);
    return upload(`/api/v1/files/upload/${runId}`, fd);
  },
  list: (runId: string) => request<unknown[]>(`/api/v1/files/run/${runId}`),
  delete: (runId: string, fileId: string) =>
    request<void>(`/api/v1/files/${runId}/${fileId}`, { method: "DELETE" }),
};

// ── Workflow processors ───────────────────────────────────────────────────────
export const webOrders = {
  process: (runId: string) =>
    request<unknown>(`/api/v1/web-orders/${runId}/process`, { method: "POST" }),
  lines: (runId: string) => request<unknown[]>(`/api/v1/web-orders/${runId}/lines`),
  summary: (runId: string) =>
    request<{ total: number; same_day: number; future: number; problematic: number }>(
      `/api/v1/web-orders/${runId}/summary`,
    ),
};

export const jetro = {
  process: (runId: string) =>
    request<unknown>(`/api/v1/jetro/${runId}/process`, { method: "POST" }),
  invoices: (runId: string) => request<unknown[]>(`/api/v1/jetro/${runId}/invoices`),
  issues: (runId: string) => request<unknown[]>(`/api/v1/jetro/${runId}/issues`),
  priceUpdates: (runId: string) => request<unknown[]>(`/api/v1/jetro/${runId}/price-updates`),
  coupons: (runId: string) => request<unknown[]>(`/api/v1/jetro/${runId}/coupons`),
  summary: (runId: string) => request<Record<string, unknown>>(`/api/v1/jetro/${runId}/summary`),
};

export const vendorBills = {
  loadPo: (runId: string) =>
    request<unknown>(`/api/v1/vendor-bills/${runId}/load-po`, { method: "POST" }),
  poBank: (runId: string) => request<unknown[]>(`/api/v1/vendor-bills/${runId}/po-bank`),
  extractBill: (runId: string, fileId: string) =>
    request<unknown>(`/api/v1/vendor-bills/${runId}/extract-bill/${fileId}`, { method: "POST" }),
  bills: (runId: string) => request<unknown[]>(`/api/v1/vendor-bills/${runId}/bills`),
  billLines: (runId: string, billId: string) =>
    request<unknown[]>(`/api/v1/vendor-bills/${runId}/bills/${billId}/lines`),
  updateLine: (
    runId: string,
    billId: string,
    lineId: string,
    data: Record<string, unknown>,
  ) =>
    request<unknown>(`/api/v1/vendor-bills/${runId}/bills/${billId}/lines/${lineId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  confirmBill: (
    runId: string,
    billId: string,
    data: { vendor_confirmed?: string; invoice_number?: string; invoice_date?: string },
  ) =>
    request<unknown>(`/api/v1/vendor-bills/${runId}/bills/${billId}/confirm`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  processBill: (runId: string, billId: string) =>
    request<unknown>(`/api/v1/vendor-bills/${runId}/bills/${billId}/process`, {
      method: "POST",
    }),
  importRows: (runId: string) =>
    request<unknown[]>(`/api/v1/vendor-bills/${runId}/import-rows`),
  finalize: (runId: string) =>
    request<{ processed_bills: number }>(`/api/v1/vendor-bills/${runId}/finalize`, {
      method: "POST",
    }),
  reopen: (runId: string) =>
    request<{ reverted_pos: number }>(`/api/v1/vendor-bills/${runId}/reopen`, {
      method: "POST",
    }),
  deleteBill: (runId: string, billId: string) =>
    request<void>(`/api/v1/vendor-bills/${runId}/bills/${billId}`, { method: "DELETE" }),
  deleteLine: (runId: string, billId: string, lineId: string) =>
    request<{ success: boolean }>(`/api/v1/vendor-bills/${runId}/bills/${billId}/lines/${lineId}`, { method: "DELETE" }),
  aiMatch: (runId: string, billId: string) =>
    request<{ success: boolean; matches: { line_id: string; po_id: string | null; confidence: number; reason: string }[] }>(
      `/api/v1/vendor-bills/${runId}/bills/${billId}/ai-match`,
      { method: "POST" },
    ),
};

export const combinedPrice = {
  process: (runId: string, jetroRunId?: string, vendorRunId?: string) =>
    request<unknown>(`/api/v1/combined-price/${runId}/process`, {
      method: "POST",
      body: JSON.stringify({ jetro_run_id: jetroRunId, vendor_run_id: vendorRunId }),
    }),
  rows: (runId: string) => request<unknown[]>(`/api/v1/combined-price/${runId}/rows`),
};

const EXPORT_PATHS: Record<string, string> = {
  web_orders_check: "web-orders",
  jetro_reconciliation: "jetro",
  vendor_bill_po_bank: "vendor-bills",
  combined_price_changes: "combined-price",
};

export const exports = {
  /**
   * Triggers the per-workflow export endpoint and streams the .xlsx
   * back to the browser as a download. Throws ApiError (status 409 with
   * detail.error === "integrity_mismatch") if the run has unresolved
   * grand-total mismatches and no override on record.
   */
  download: async (runId: string, workflowType: string, suggestedName?: string) => {
    const seg = EXPORT_PATHS[workflowType];
    if (!seg) throw new Error(`Unknown workflow type: ${workflowType}`);
    const blob = await downloadBlob(`/api/v1/exports/${seg}/${runId}`);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = suggestedName ?? `export_${runId}.xlsx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },

  /**
   * Vendor-bills only: download a draft Bill Import workbook WITHOUT running
   * the missing-PO sweep and WITHOUT marking the run as exported. Used while
   * additional bills are still expected so vendors aren't prematurely flagged.
   */
  downloadVendorBillsDraft: async (runId: string, suggestedName?: string) => {
    const blob = await downloadBlob(`/api/v1/exports/vendor-bills/${runId}/draft`);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = suggestedName ?? `export_${runId}_draft.xlsx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },

  /**
   * Download a zip archive of the most recent finalized workbook for each
   * workflow run on the given calendar day (YYYY-MM-DD). The archive is
   * named `<date>.zip`.
   */
  downloadDayArchive: async (date: string) => {
    const blob = await downloadBlob(
      `/api/v1/exports/day-archive/${encodeURIComponent(date)}`,
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Morning Report ${date}.zip`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
};

export const audit = {
  forRun: (runId: string) => request<unknown[]>(`/api/v1/audit/run/${runId}`),
};

// Templates — keyed by file_type, value is the template slug on the backend
export const SAMPLE_TEMPLATE_KEYS: Record<string, string> = {
  quickbooks_po_export: "qb-po-export",
  web_orders_spreadsheet: "web-orders-master",
  jetro_source: "jetro-source",
};

export async function downloadSampleTemplate(templateKey: string): Promise<void> {
  const blob = await downloadBlob(
    `/api/v1/exports/sample-template/${encodeURIComponent(templateKey)}`,
    { method: "GET" },
  );
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  // Use the filename from Content-Disposition if possible, otherwise guess
  a.download = `${templateKey}_template.xlsx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
