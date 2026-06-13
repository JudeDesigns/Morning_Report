export type WorkflowType =
  | "web_orders_check"
  | "jetro_reconciliation"
  | "vendor_bill_po_bank"
  | "combined_price_changes";

export type RunStatus =
  | "draft"
  | "files_uploaded"
  | "extraction_pending"
  | "extraction_review"
  | "ready_to_process"
  | "processing"
  | "validation_failed"
  | "processed"
  | "exported"
  | "archived";

export interface RunOverride {
  check: string;
  reason: string;
  user_id: string;
  original_value?: string | null;
  affected_rows?: string[] | null;
  created_at: string;
}

export interface WorkflowRun {
  id: string;
  workflow_type: WorkflowType;
  name: string;
  run_date: string;
  status: RunStatus;
  notes?: string;
  created_by?: string;
  created_at: string;
  updated_at: string;
  file_count: number;
  overrides?: RunOverride[];
}

export interface IntegrityMismatchDetail {
  error: "integrity_mismatch";
  message: string;
  invoices: (string | number)[];
}

export interface UploadedFile {
  id: string;
  run_id: string;
  file_type: string;
  original_filename: string;
  mime_type?: string;
  sha256?: string;
  uploaded_at: string;
  parse_status: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
}

export interface AuditEvent {
  id: string;
  run_id?: string;
  user_id?: string;
  event_type: string;
  entity_type?: string;
  message?: string;
  created_at: string;
}

export interface VendorBill {
  id: string;
  source_file_id?: string;
  vendor_extracted?: string;
  vendor_confirmed?: string;
  invoice_number?: string;
  invoice_date?: string;
  bill_type: string;
  extraction_status: string;
  header_confidence?: number;
  header_needs_review?: string[];
}

export interface VendorBillLine {
  id: string;
  bill_item_code?: string;
  description?: string;
  qty?: number;
  rate?: number;
  total?: number;
  is_credit: boolean;
  individual_weights?: number[];
  notes?: string;
  confidence?: number;
  field_confidence?: Record<string, number>;
  field_needs_review?: string[];
  user_confirmed: boolean;
  match_status?: string;
  matched_po_id?: string | null;
  forced_po_id?: string | null;
}

export interface PoRow {
  id: string;
  item_code?: string;
  description?: string;
  vendor?: string;
  ref_number?: string;
  quantity?: number;
  po_cost?: number;
  status: string;
}

export const WORKFLOW_LABELS: Record<WorkflowType, string> = {
  web_orders_check: "Daily Web Orders Check",
  jetro_reconciliation: "Jetro / Restaurant Depot",
  vendor_bill_po_bank: "Vendor Bills / PO Bank",
  combined_price_changes: "Combined Price Changes",
};

export const STATUS_LABELS: Record<RunStatus, string> = {
  draft: "Draft",
  files_uploaded: "Files Uploaded",
  extraction_pending: "Extraction Pending",
  extraction_review: "Extraction Review",
  ready_to_process: "Ready to Process",
  processing: "Processing",
  validation_failed: "Validation Failed",
  processed: "Processed",
  exported: "Exported",
  archived: "Archived",
};

export const FILE_TYPE_LABELS: Record<string, string> = {
  web_orders_spreadsheet: "Master Spreadsheet (All Orders, Item List, Inventory, Shopping History)",
  web_orders_all_orders: "All Orders",
  web_orders_item_list: "Item List",
  web_orders_inventory: "Inventory",
  web_orders_shopping_history: "Shopping History",
  jetro_source: "Jetro Source Sheet",
  restaurant_depot_invoice_xlsx: "RD Invoice (.xlsx)",
  restaurant_depot_invoice_image: "RD Invoice (Image)",
  sales_per_week: "Sales Per Week",
  quickbooks_po_export: "QuickBooks PO Export",
  vendor_bill_image: "Vendor Bill Image",
  vendor_bill_pdf: "Vendor Bill PDF",
  combined_price_jetro_workbook: "Jetro Workbook",
  combined_price_vendor_bill_workbook: "Vendor Bill Workbook",
};

export const WORKFLOW_FILE_TYPES: Record<WorkflowType, string[]> = {
  web_orders_check: ["web_orders_spreadsheet"],
  jetro_reconciliation: [
    "jetro_source",
    "restaurant_depot_invoice_xlsx",
    "restaurant_depot_invoice_image",
    "sales_per_week",
  ],
  vendor_bill_po_bank: [
    "quickbooks_po_export",
    "vendor_bill_image",
    "vendor_bill_pdf",
  ],
  combined_price_changes: [
    "combined_price_jetro_workbook",
    "combined_price_vendor_bill_workbook",
  ],
};
