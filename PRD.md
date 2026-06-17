Below is a build-ready PRD for a web application that automates the four uploaded workflows as one connected operational system.

# Product Requirements Document

## B&R Food Services Workflow Automation Web Application

**Version:** 1.0
**Prepared for:** AI coding / software build
**Primary goal:** Convert four spreadsheet/PDF/image-driven operational workflows into a functioning web application that ingests source files, validates them, automates reconciliation, generates QuickBooks-ready imports, produces office-ready exception reports, and preserves auditability.

---

# 1. Source Workflow Assimilation

The application must unify four workflows:

1. **Restaurant Depot / Jetro reconciliation and QuickBooks bill import**
   This weekly workflow converts the Night Shift Jetro source sheet plus Restaurant Depot invoices into a reconciliation workbook and QuickBooks-ready bill import. It handles CRV/surcharge folding, coupons, voids, returns, pound-based item logic, missing/extra/quantity mismatch issues, price updates, and coupon opportunity reporting. 

2. **Vendor bills to QuickBooks import using a QuickBooks PO Bank**
   This accumulating workday workflow loads a structured QuickBooks PO export as a reference bank, waits for vendor bill images, extracts bill data, matches only relevant PO rows, creates QuickBooks import rows, identifies vendor-facing discrepancies, records verified catch weights, updates cost comparisons, and removes processed PO rows from the active PO Bank. 

3. **Combined price changes from both sources**
   This consolidation workflow pulls cost changes from the Jetro workflow’s `Price Update` sheet and the vendor-bill workflow’s `Cost Comparison` sheet into one review sheet of changed costs only, using a unified `New Cost - Old Cost` difference convention. 

4. **Daily web-orders invoice check**
   This daily workflow enriches raw web orders from reference sheets, splits same-day orders from future orders, validates same-day lines, flags problematic items, and creates both a full problematic-items sheet and a customer-sorted review sheet. 

The full system is best understood as an **accounting-safe file processing and reconciliation platform**. It is not merely an upload-and-export tool. It must preserve strict business rules, prevent premature processing, require human review where images or OCR are involved, maintain an audit trail, and generate outputs that match the existing workbook formats closely enough for office and accounting teams to trust them.

---

# 2. Executive Summary

## 2.1 Product Vision

Build a web application that allows B&R Food Services staff to upload operational spreadsheets, invoice exports, invoice photos/scans, PO exports, and sales reports, then automatically produce:

* QuickBooks-ready bill import files.
* Vendor reconciliation sheets.
* Office-ready vendor email preparation summaries.
* Problematic web-order review lists.
* Combined cost-change review sheets.
* Persistent cumulative workbooks by period or workday.

The application should replace fragile manual Excel workflows with guided web-based workflows that enforce the SOP rules.

## 2.2 Primary Business Outcomes

The application must:

* Reduce manual spreadsheet preparation time.
* Prevent invoice lines from being posted incorrectly to QuickBooks.
* Detect vendor billing discrepancies.
* Detect web-order lines requiring office review.
* Preserve exact invoice-total integrity checks.
* Keep processed and unprocessed PO rows separated.
* Produce clean, office-ready output instead of raw discrepancy dumps.
* Maintain a historical audit trail of uploads, extracted lines, corrections, generated outputs, and exports.

---

# 3. Core Product Principles

## 3.1 Accuracy over speed

Accounting outputs must be correct. If an invoice photo is unclear, the app must require user review before applying the data.

## 3.2 Human-in-the-loop for image extraction

Whenever invoice data is extracted from a photo, scan, or PDF image, the application must show the extracted line items before processing. The user must confirm or edit the extraction.

## 3.3 No premature processing

For the vendor-bill workflow, the QuickBooks PO export is only a bank/reference. No working rows may be generated for a vendor until that vendor’s bill image is uploaded and processed.

## 3.4 Exact workbook semantics

The generated outputs must preserve the existing workflow structures, sheet names, columns, sort orders, formatting cues, and business logic.

## 3.5 Accumulating workflows must persist state

Some workflows are cumulative. The application must support adding multiple invoices or credits to an existing run/workbook without duplicating previously processed data.

## 3.6 Empty results should stay empty

The system must not add status rows saying “nothing missing,” “no discrepancies,” “no individual weights,” or similar. Absence of rows is the intended signal.

---

# 4. Product Scope

## 4.1 In Scope

The web application must support the following modules:

1. **File Intake and Run Management**

   * Upload Excel files, CSV files, PDFs, invoice photos/scans, and supporting reports.
   * Create named workflow runs.
   * Track run status.
   * Store source files and generated output files.
   * Allow reprocessing with version history.

2. **Daily Web Orders Check**

   * Upload `All Orders`, `Item list`, `Inventory`, and `Shopping History`.
   * Enrich order rows.
   * Split same-day and future orders.
   * Validate same-day rows.
   * Generate four-sheet output workbook.

3. **Restaurant Depot / Jetro Reconciliation**

   * Upload Jetro source sheet.
   * Upload one or more Restaurant Depot invoices as `.xlsx`, PDF, image, or manually transcribed line table.
   * Upload Sales-Per-Week report.
   * Process charges and credits.
   * Generate five-sheet workbook.
   * Maintain cumulative invoice blocks.

4. **Vendor Bills / PO Bank Processing**

   * Upload structured QuickBooks PO export.
   * Parse PO Bank and Office/Driver tasks.
   * Upload vendor bill images throughout the workday.
   * Extract and review bill data.
   * Match bill lines to PO Bank rows.
   * Generate/update accumulating workbook sheets.
   * Remove processed PO rows from active PO Bank.

5. **Combined Price Changes**

   * Pull from current Jetro `Price Update`.
   * Pull from current vendor-bills `Cost Comparison`.
   * Generate combined price change review sheet.

6. **Export Engine**

   * Export Excel workbooks in exact required structures.
   * Export selected sheets as CSV if needed for QuickBooks import.
   * Preserve formatting, highlights, sort order, and number formats.

7. **Audit and Validation**

   * Track source files, extracted records, edited fields, validation warnings, and export timestamps.
   * Show invoice total checks before export.
   * Block final export when critical checks fail unless an authorized user overrides with a reason.

## 4.2 Out of Scope for MVP

The MVP should not attempt to:

* Directly post bills into QuickBooks through the QuickBooks API.
* Automatically email vendors.
* Automatically update sell prices in QuickBooks or inventory systems.
* Fully trust OCR without review.
* Make purchasing decisions.
* Replace the office team’s judgment on vendor discrepancies.
* Process unrelated PO rows before a bill image is received.

These can be future enhancements.

---

# 5. Users and Personas

## 5.1 Accounting User

Responsible for importing bills into QuickBooks.

Needs:

* Clean QuickBooks import sheets.
* Invoice blocks separated by invoice number.
* Totals that tie to printed invoice totals.
* Credits represented correctly.
* No duplicate processing.

## 5.2 Office / Purchasing User

Responsible for reviewing vendor price changes, overcharges, undercharges, missing items, and customer-facing web-order problems.

Needs:

* Office-ready summaries.
* Vendor email preparation sections.
* Price change review sorted by largest impact.
* Problematic items sorted by customer.

## 5.3 Management User

Needs quick visibility into:

* Missing items.
* Extra billed items.
* Quantity mismatches.
* Price changes.
* Coupon savings opportunities.
* System status by workflow.

## 5.4 Admin User

Responsible for configuration.

Needs:

* Vendor matching rules.
* Keyword rules.
* Column mappings.
* User permissions.
* Run archive settings.
* Override permissions.

---

# 6. Recommended Technical Architecture

## 6.1 Frontend

Recommended stack:

* **Next.js / React**
* TypeScript
* Tailwind CSS or equivalent component framework
* Data grid component with editable cells, validation states, filters, and row grouping

Frontend responsibilities:

* Workflow dashboards.
* File upload.
* Extraction review screens.
* Reconciliation previews.
* Manual correction of extracted data.
* Validation result display.
* Export download controls.

## 6.2 Backend

Recommended stack:

* **Python FastAPI**
* Pandas for tabular processing.
* OpenPyXL or XlsxWriter for Excel generation.
* Pydantic models for validation.
* Decimal arithmetic for currency.
* Background job queue for larger files if needed.

Backend responsibilities:

* File parsing.
* Workflow rule execution.
* OCR/AI extraction orchestration.
* Data validation.
* Workbook generation.
* State persistence.
* Audit trail.

## 6.3 Database

Recommended:

* PostgreSQL

Use database tables for:

* Users
* Organizations
* Workflow runs
* Uploaded files
* Parsed records
* Invoices
* Invoice lines
* PO Bank rows
* Order lines
* Issues
* Cost changes
* Coupons
* Exports
* Audit events

## 6.4 File Storage

Recommended:

* Local storage for development.
* S3-compatible object storage for production.

Store:

* Original uploaded files.
* Normalized parsed versions.
* OCR/extraction JSON.
* Generated Excel workbooks.
* Exported CSV files.
* Audit snapshots.

## 6.5 OCR / AI Extraction Layer

The app should support a pluggable extraction interface.

Possible extraction sources:

* OCR provider.
* LLM vision extraction.
* Manual user entry.
* Direct Excel parsing.

All extracted invoice lines from images must enter an **Extraction Review** state before processing.

---

# 7. Global System Concepts

## 7.1 Workflow Run

A workflow run is a processing container.

Examples:

* Daily Web Orders Run for `2026-06-11`.
* Weekly Jetro Run for week ending `2026-06-14`.
* Vendor Bills Workday Run for `2026-06-11`.
* Combined Price Changes Run for `2026-06-11`.

Fields:

* `id`
* `workflow_type`
* `name`
* `run_date`
* `status`
* `created_by`
* `created_at`
* `updated_at`
* `locked_at`
* `archived_at`

Statuses:

* `draft`
* `files_uploaded`
* `extraction_pending`
* `extraction_review`
* `ready_to_process`
* `processing`
* `validation_failed`
* `processed`
* `exported`
* `archived`

## 7.2 Uploaded File

Fields:

* `id`
* `run_id`
* `file_type`
* `original_filename`
* `storage_path`
* `mime_type`
* `uploaded_by`
* `uploaded_at`
* `parse_status`
* `parse_errors`

File types:

* `web_orders_all_orders`
* `web_orders_item_list`
* `web_orders_inventory`
* `web_orders_shopping_history`
* `jetro_source`
* `restaurant_depot_invoice_xlsx`
* `restaurant_depot_invoice_image`
* `sales_per_week`
* `quickbooks_po_export`
* `vendor_bill_image`
* `vendor_bill_pdf`
* `combined_price_jetro_workbook`
* `combined_price_vendor_bill_workbook`

## 7.3 Critical Validation Types

The app must distinguish:

* **Blocking errors**: prevent export.
* **Warnings**: allow export after acknowledgement.
* **Informational messages**: visible but not blocking.

Blocking examples:

* Invoice Grand Total does not equal processed line total.
* Required sheet missing.
* Required column missing.
* OCR extraction has unconfirmed invoice lines.
* PO export cannot be parsed into product rows.
* Duplicate invoice number in same run without explicit override.

Warning examples:

* Unmatched bill item.
* Missing Sales-Per-Week usage for coupon.
* Price change above configurable threshold.
* Weight mismatch close to tolerance.

---

# 8. Module A — Daily Web Orders Check

## 8.1 Purpose

Automate the daily invoice finalization check by enriching raw web-order lines, splitting future-dated orders, and moving only review-required same-day lines into office-facing problem sheets.

## 8.2 Inputs

The module must accept the following sheets, whether they are in one workbook or split across multiple workbooks:

1. `All Orders`
2. `Item list`
3. `Inventory`
4. `Shopping History`

The run must also have a **Run Date**. Default should be the current local date, but the user must be able to override it before processing.

## 8.3 Input Sheet Mapping

### All Orders

Important source columns:

| Field                      | Column |
| -------------------------- | -----: |
| Product Name               |      A |
| Code                       |      B |
| Qty                        |      G |
| Weight                     |      H |
| Individual Weight / Status |      I |
| Price / Selling            |      J |
| Customer Name              |      L |
| Transaction Date           |      O |
| Route                      |      Q |
| Remark                     |      S |

### Item List

| Source Field          | Source Column | Target All Orders Column |
| --------------------- | ------------: | -----------------------: |
| SKU CODE              |             B |                Match key |
| Category Name         |             — |                        T |
| Current Cost Price    |             — |                        U |
| Current Selling Price |             — |                        V |
| Unit                  |             — |                       AF |

### Shopping History

| Source Field | Source Column | Target All Orders Column |
| ------------ | ------------: | -----------------------: |
| Item         |             B |                Match key |
| Product      |             — |                        W |
| Bin          |             — |                        X |
| Unit Price   |             — |                        Y |
| Case Price   |             — |                        Z |

### Inventory

| Source Field     | Source Column | Target All Orders Column |
| ---------------- | ------------: | -----------------------: |
| Item             |             A |                Match key |
| Quantity On Hand |             — |                       AA |
| Cost             |             — |                       AB |
| Case Avg Weight  |             — |                       AC |
| Unit Avg Weight  |             — |                       AD |
| BIN Internal     |             — |                       AE |

## 8.4 Enrichment Rules

Functional requirements:

* The system must normalize item codes as text.
* Trim leading and trailing whitespace.
* Numeric `24514` and text `"24514"` must match.
* Spacer rows without item codes must be left untouched.
* Shopping History matching must allow a one-letter trailing `U` or `C` difference.

  * Example: `24514U` may match `24514`.
  * Example: `24514C` may match `24514`.
* Enriched columns must be written into columns `T` through `AF`.
* Decimal precision must be preserved.
* Columns `U`, `V`, `Y`, `Z`, `AB`, `AC`, and `AD` must use number format `0.####`.

## 8.5 Same-Day vs Future Split

Functional requirements:

* Read Transaction Date from All Orders column `O`.
* Same-day rows remain in `All Orders`.
* Future rows move to `Future Orders`.
* Future Orders must keep the same header and column layout as All Orders.
* Future Orders are enriched but not checked.
* Future Orders must never feed `Problematic Items`.
* Spacer rows inherit the date of the block above them.
* Past-dated rows should trigger a warning because they are not expected in a same-day batch.

## 8.6 Status Handling

Column `I` drives special handling.

| Status        | Meaning                               | Handling                  |
| ------------- | ------------------------------------- | ------------------------- |
| `MISSING`     | Missing item with no substitute       | Move to Problematic Items |
| `SUBSTITUTED` | Original ordered item was substituted | Keep; do not run checks   |
| `WITH`        | Substitute item actually delivered    | Validate like normal line |
| Blank         | Normal line                           | Run all checks            |

## 8.7 Problem Checks

The system must build a `problem_reasons` array per same-day line. If the array is not empty, move the row to `Problematic Items`.

### 8.7.1 Remark and Status Checks

Check `Remark` column `S`.

Rules:

* If remark contains `Sub` or `substitute` and status is `SUBSTITUTED`, keep.
* If remark contains `Sub` or `substitute` and status is not `SUBSTITUTED`, flag as problematic.
* If remark contains `pending` and status is blank, flag as problematic.
* If remark indicates office mistake, entry error, or change of mind:

  * If Qty `G = 0`, keep.
  * If Qty `G ≠ 0`, flag as problematic.

Configurable keyword groups:

* `substitution_keywords`
* `pending_keywords`
* `office_mistake_keywords`

Default office mistake keywords:

* `entry error`
* `change of mind`
* `office mistake`

### 8.7.2 Weight Check for LBS Items

Only run when enriched Unit column `AF = LBS`.

Inputs:

* Qty Ordered: column `G`
* Weight: column `H`
* Product Name: column `A`
* Case Avg Weight: column `AC`
* Unit Avg Weight: column `AD`

Cascade:

1. If `Qty × CASE AVG WEIGHT = Weight`, pass.
2. Else, if Product Name starts with `Unit` and `Qty × UNIT AVG WEIGHT = Weight`, pass.
3. Else, if Product Name contains `AVG` or `A.V.G`, re-check applicable expected weight within ±15%.
4. Else, flag as problematic.

The implementation should use Decimal arithmetic and a configurable small arithmetic tolerance only to avoid floating point issues.

### 8.7.3 Price vs Cost Check

Inputs:

* Current Cost Price: column `U`
* Selling Price / Price: column `J`

Rules:

* If cost is blank, leave line in place.
* If `U < J`, pass.
* If `U = J`, flag: no margin.
* If `J < U`, flag: selling below cost.
* If `U = 0` or `J = 0`, flag: zero price.
* Remark containing `SP` means a special customer price, but it must still be flagged if it falls below cost.

## 8.8 Output Workbook

Final sheet order:

1. `All Orders`
2. `Future Orders`
3. `Problematic Items`
4. `By Customer Problematic`

The reference sheets must be removed from the delivered workbook.

## 8.9 Problematic Items Sheet

Columns:

| Output Column | Field                        | Source                |
| ------------: | ---------------------------- | --------------------- |
|             A | Customer Name                | All Orders L          |
|             B | Problem                      | Generated reason text |
|             C | Qty Ordered                  | All Orders G          |
|             D | Weight                       | All Orders H          |
|             E | Individual Weight            | All Orders I          |
|             F | Remark                       | All Orders S          |
|             G | Product Name                 | All Orders A          |
|            H+ | Remaining All Orders columns | Original order        |

Requirements:

* Problem column must be highlighted.
* Multiple reasons must be separated by semicolons.
* Rows should preserve full original order data after the leading office-facing columns.

## 8.10 By Customer Problematic Sheet

Columns:

| Output Column | Field                 | Source |
| ------------: | --------------------- | ------ |
|             A | Customer Name         | L      |
|             B | Qty Ordered           | G      |
|             C | Product Name          | A      |
|             D | Code                  | B      |
|             E | Notes                 | S      |
|             F | Price                 | J      |
|             G | Weight                | H      |
|             H | Status                | I      |
|             I | Current Selling Price | V      |
|             J | Unit Avg Weight       | AD     |
|             K | Case Avg Weight       | AC     |

Requirements:

* Sort ascending by Customer Name.
* Keep each customer’s problem lines together.

## 8.11 Acceptance Criteria

* Given valid input sheets, the system generates a four-sheet workbook.
* Future-dated lines appear only in `Future Orders`.
* Future-dated lines do not appear in `Problematic Items`.
* Same-day lines with `MISSING` status are flagged.
* `SUBSTITUTED` original rows are not checked.
* `WITH` rows are checked normally.
* LBS lines follow the exact cascade.
* Cost/selling checks flag zero, equal, or below-cost selling prices.
* Reference sheets do not appear in final output.
* Number formats preserve up to four decimals.

---

# 9. Module B — Restaurant Depot / Jetro Reconciliation

## 9.1 Purpose

Automate weekly Restaurant Depot invoice reconciliation against the Night Shift Jetro source and produce:

1. Management reconciliation.
2. QuickBooks bill import.
3. Issue reporting.
4. Price update reporting.
5. Coupon opportunity reporting.

## 9.2 Inputs

Required:

1. Jetro source sheet from Night Shift Stage 2 extraction.
2. One or more Restaurant Depot invoices.
3. Sales-Per-Week report for 8-week coupon usage projection.

Invoice upload formats:

* `.xlsx` export
* PDF
* Photo
* Scan
* Manual line entry table

For photos/scans/PDF images, extracted lines must be displayed to the user for confirmation before processing.

## 9.3 Jetro Source Columns

| Column | Field                 | Purpose                            |
| -----: | --------------------- | ---------------------------------- |
|      C | Qty                   | Ordered quantity in cases          |
|      D | Product Name          | Display name                       |
|      E | Code                  | Item code; trailing `U` means unit |
|      O | Name                  | Customer                           |
|      X | Current Cost Price    | Old cost                           |
|      Y | Current Selling Price | Recorded sell                      |
|     AF | Case Avg Weight       | Cases-to-pounds conversion         |
|     AI | Unit                  | `CASE`, `Unit`, or `LBS`           |

Rows where customer/name is exactly `Warehouse INVENTORY Order` must be excluded from reconciliation.

## 9.4 Restaurant Depot Invoice Columns

The `.xlsx` invoice export has a preamble. Header is at row 17, data begins row 18 and continues until the first `Sub-Total` row.

| Column | Field       | Purpose                                         |
| -----: | ----------- | ----------------------------------------------- |
|      A | Line        | Line number                                     |
|      B | UPC         | Barcode or `Coupon` flag                        |
|      C | Item        | Numeric code or `Surcharge` flag                |
|      D | Description | Item description; may contain `CRV`             |
|      E | Price       | Unit/case price; negative on coupon rows        |
|      F | C/U         | `U`, `C`, optional `(T)` taxable                |
|      G | Qty         | Quantity; `V` or `R` indicators for void/return |
|      H | Total       | Line total                                      |

Invoice number must come from the row labeled `Invoice`, not from `Convert From Quote`.

## 9.5 Matching Key

Both Jetro source and invoice lines must normalize to:

```text
(base_code, kind)
```

Jetro source:

* If column `E` ends in `U`:

  * `kind = U`
  * `base_code = code without trailing U`
* Otherwise:

  * `kind = C`
  * `base_code = code`

Invoice:

* `base_code = numeric item code from column C`
* `kind = U` if C/U column starts with `U`
* Otherwise `kind = C`
* `(T)` only means taxable and must not affect matching.

## 9.6 Invoice Preprocessing

The processor must walk invoice lines top-to-bottom.

### 9.6.1 Real Item Row

A real item row has:

* Numeric item code.
* Non-coupon UPC.
* Non-surcharge item value.
* Description that is not a standalone CRV/surcharge row.

Real item rows become bill candidate lines.

### 9.6.2 CRV / Surcharge Rows

Detect when:

* Item column `C = Surcharge`, or
* Description contains `CRV`.

Handling:

* Attach the surcharge total to the immediately preceding real item.
* Drop the surcharge row from import output.
* Preserve audit link showing which surcharge was folded into which item.

### 9.6.3 Coupon Rows

Detect when:

* UPC column `B = Coupon`, or
* Price column `E` is negative.

Handling:

* Deduct coupon amount from the immediately preceding real item.
* Add coupon record to `Coupons – Take Advantage`.
* Drop coupon row from import output.
* Preserve item code of discounted item.

An item may have both CRV and coupon rows beneath it. Both must fold into the item above.

### 9.6.4 Voids and Returns

Detect negative-quantity line carrying positive price, often indicated by `V` or `R`.

Handling:

* Treat as a negative item line, not a coupon.
* Net it into the same item code.
* If entire invoice contains return lines and printed Grand Total is negative, classify invoice as credit/return invoice.

## 9.7 LBS Logic

For Jetro source items where column `AI = LBS`:

* Expected pounds = ordered case qty × Case Avg Weight from column `AF`.
* Compare source to invoice in pounds.
* Use the `LBS` flag to determine whether to show individual weight breakdown in the import description.
* Do not guess LBS status from invoice quantity.

## 9.8 Jetro Import Sheet

Sheet name:

```text
Jetro import
```

This sheet must be a flat table:

* Header row.
* Data rows only.
* No invoice banners.
* No subtotal rows.
* Multiple invoices remain separated by the `Invoice #` column.

Columns:

| Column | Field       | Build Rule                                                      |
| -----: | ----------- | --------------------------------------------------------------- |
|      A | Line        | Sequential within each invoice; restart at 1 per invoice        |
|      B | UPC         | Invoice UPC from first occurrence                               |
|      C | Item Code   | Invoice code plus `U` when C/U is unit; case items stay numeric |
|      D | Description | Invoice description; LBS items may include weight breakdown     |
|      E | Cost        | Net effective unit cost = Total ÷ Qty                           |
|      F | Qty         | Invoice qty, summed after voids/returns                         |
|      G | Total       | Invoice total, with CRV/coupon/returns folded                   |
|      H | Invoice #   | Source invoice number                                           |
|      I | Type        | Always `Inventory Part`                                         |

Deduplication:

* Deduplicate by final Item Code.
* Sum Qty.
* Sum Total.
* Recalculate Cost = Total ÷ Qty.
* Drop rows that net to zero.
* Line numbers are assigned after deduplication.

Integrity check:

* For each invoice number, sum column `G`.
* It must equal that invoice’s printed Grand Total to the penny.
* Credits must sum to negative Grand Total.

## 9.9 All Issues Sheet

Sheet name:

```text
All Issues
```

Columns:

| Column | Field            | Contents                                                   |
| -----: | ---------------- | ---------------------------------------------------------- |
|      A | Type             | `Missing`, `Extra`, or `Qty mismatch`                      |
|      B | Item Code        | Full code with `U` suffix for units                        |
|      C | Quantity         | Ordered qty for Missing/Qty mismatch; billed qty for Extra |
|      D | Item Description | Product name                                               |
|      E | Used by:         | Customers and quantities for Missing/Qty mismatch          |
|      F | Detail           | Plain-language reason naming source invoice                |

Issue definitions:

* `Missing`: ordered by customer but not billed.
* `Extra`: billed but not found in Jetro source or has no customer.
* `Qty mismatch`: billed quantity differs from ordered quantity.
* LBS mismatch must compare pounds, not cases.

Sorting:

1. Missing
2. Extra
3. Qty mismatch

Within each group, sort by dollar size when available.

## 9.10 Price Update Sheet

Sheet name:

```text
Price Update
```

Include every matched item.

Columns:

| Column | Field            | Contents                         |
| -----: | ---------------- | -------------------------------- |
|      A | Item Code        | Full code                        |
|      B | Qty Charged      | Invoice quantity; pounds for LBS |
|      C | Item Description | Product name                     |
|      D | Old Cost         | Jetro source current cost        |
|      E | New Cost         | Invoice cost = Total ÷ Qty       |
|      F | Cost Change      | Old Cost − New Cost              |
|      G | Used by:         | Customers and quantities ordered |

Sorting:

* Highest positive cost changes first.
* Then negative changes.
* Then no-change items at bottom.

Formatting:

* Cost drops: green.
* Cost rises: pink.
* Largest changes should be visually easy to review.

Note: Jetro’s native sign convention is `Old - New`. The combined price-change module will later normalize to `New - Old`.

## 9.11 Coupons – Take Advantage Sheet

Sheet name:

```text
Coupons – Take Advantage
```

Columns:

| Column | Field                   | Contents                          |
| -----: | ----------------------- | --------------------------------- |
|      A | Item Code               | Discounted item full code         |
|      B | Description             | Invoice item description          |
|      C | Coupon Amount           | Per-unit discount, shown positive |
|      D | Qty                     | Coupon quantity                   |
|      E | Total Savings (invoice) | Savings realized on invoice       |
|      F | Invoice #               | Source invoice                    |
|      G | 8 Weeks Usage           | Sales/Week × 8                    |
|      H | 8wk Usage × Coupon $    | Projected savings                 |

Rules:

* Match coupon item code to Sales-Per-Week report by full code.
* If not found, leave columns G and H blank.
* Sort by projected 8-week savings descending.

## 9.12 Summary Sheet

Sheet name:

```text
Summary
```

The Summary sheet should provide:

* Run name.
* Run date.
* Invoice numbers.
* Invoice dates if available.
* Grand totals.
* Processed line totals.
* Integrity check status.
* Count of Missing, Extra, Qty mismatch.
* Count of coupons.
* Total coupon savings.
* Number of price changes.
* Warnings and overrides.

This sheet should be scannable in under one minute.

## 9.13 Multiple Invoices and Credits

Requirements:

* The Jetro workbook is cumulative.
* Additional invoices or credits must append into the same run.
* Do not create a new workbook for every invoice unless user explicitly starts a new run.
* Charge invoices:

  * Add rows to `Jetro import`.
  * Compare to Jetro source.
  * Feed `All Issues`, `Price Update`, and `Coupons`.
* Credit invoices:

  * Add rows to `Jetro import` with negative Qty and Total.
  * Post as negative bills.
  * Do not run credit invoice through customer order comparison.
  * Do not create Missing/Extra/Qty mismatch rows from a credit alone.

## 9.14 Acceptance Criteria

* The app accepts multiple Restaurant Depot invoices in one weekly run.
* CRV rows fold into the correct item above.
* Coupon rows deduct from the correct item above and appear in Coupons.
* Voids/returns net into the item and are not treated as coupons.
* Internal warehouse Jetro rows are excluded.
* LBS items compare pounds using case average weight.
* Import rows sum to printed invoice Grand Total.
* Credits produce negative invoice blocks.
* Each invoice has line numbers restarting at 1.
* Duplicate item codes are collapsed after folding.
* Output workbook contains exactly:

  * `Summary`
  * `Jetro import`
  * `All Issues`
  * `Price Update`
  * `Coupons – Take Advantage`

---

# 10. Module C — Vendor Bills / QuickBooks PO Bank

## 10.1 Purpose

Automate vendor bill image processing against one structured QuickBooks PO export.

The PO file acts as a bank/reference. Working sheets are populated only after a matching vendor bill image is received.

## 10.2 Inputs

Required at workday start:

* QuickBooks PO export in the new structured format.

Uploaded throughout workday:

* Vendor bill images.
* Vendor bill PDFs.
* Credit memo images.
* Optional manual corrections after extraction.

## 10.3 QuickBooks PO Export Format

Columns:

| Column | Field               | Use                                   |
| -----: | ------------------- | ------------------------------------- |
|      A | Terms               | Vendor payment terms                  |
|      B | RefNumber           | PO number                             |
|      C | TxnDate             | PO date                               |
|      D | Vendor              | QB vendor name                        |
|      E | Memo                | PO memo                               |
|      F | Total Amount        | PO total                              |
|      G | TxnLine Cost        | PO unit cost                          |
|      H | TxnLine Description | Product description and possible task |
|      I | TxnLine Item        | QB item code                          |
|      J | TxnLine Quantity    | Qty or total lbs shipped              |
|      K | Name                | QB class/category                     |
|      L | CASE AVG WEIGHT     | Avg lbs per case                      |
|      M | UNIT AVG WEIGHT     | Avg lbs per unit                      |

## 10.4 PO Row Type Detection

The PO parser must classify each row as:

### 10.4.1 Order Header

Detect when:

* Description begins with `ORDER PLACED BY`, or
* Description is a print/availability note such as `***...***`, or
* Description includes `NEED TO CHECK AVAILABILITY`, and
* Item code is blank or equals vendor name, and
* Cost is zero.

Handling:

* Do not load into PO Bank.
* Extract once per PO into `Office and Driver’s tasks`.

### 10.4.2 Spacer

Detect when:

* Description is blank.
* Item code is blank.

Handling:

* Ignore.

### 10.4.3 Product Line

Detect when:

* Real item code exists in column `I`.
* Item code is not equal to vendor name.
* Cost is in column `G`.
* Quantity is in column `J`.

Handling:

* Load into `Original PO / PO Bank`.

## 10.5 Embedded Driver / Office Tasks

Column `H` may contain product description plus a task below a blank line.

Rule:

* Split at first blank line.
* Text above blank line = product description.
* Text below blank line = task/instruction.

Handling:

* Product description goes to PO Bank and Bill Import.
* Task goes to `Office and Driver’s tasks`.
* Product/compliance notes with no blank line remain with product description.

## 10.6 Workbook Sheets

The accumulating workbook must contain:

1. `Original PO / PO Bank`
2. `Office and Driver’s tasks`
3. `Bill Import`
4. `Summary Vendor & Warehouse`
5. `PO Items Not Charged`
6. `Individual Weights`
7. `Cost Comparison`

## 10.7 Core Processing State Rule

No vendor bill image, no working rows.

The system must:

* Load PO Bank at intake.
* Wait for bill image.
* Process only the vendor/items connected to that bill.
* Leave unrelated PO rows untouched.
* Remove matched/processed PO rows from the active PO Bank after processing.
* Keep historical processed PO row records in the database for audit.

## 10.8 Vendor Bill Extraction

For each uploaded vendor bill image/PDF, extract:

* Vendor name.
* Invoice number.
* Invoice date.
* Item code if printed.
* Item description.
* Quantity.
* Unit rate.
* Line total.
* Credits/returns.
* Individual weights if shown.
* Relevant handwritten driver notes.

The extracted bill must be shown to the user in an editable review table.

Required review table columns:

| Field              |
| ------------------ |
| Vendor             |
| Invoice #          |
| Invoice Date       |
| Bill Item Code     |
| Bill Description   |
| Qty                |
| Rate               |
| Total              |
| Credit/Return Flag |
| Individual Weights |
| Notes              |
| Confidence         |
| User Confirmed     |

Processing cannot continue until all required fields are confirmed.

## 10.9 Vendor Matching Rules

Default matching should use:

* Vendor name.
* Item code when available.
* Description similarity.
* Quantity/weight context.
* Configured vendor aliases.
* Configured item mapping table.

Vendor-specific rules:

| Vendor                     | Matching Rule                                                                                          |
| -------------------------- | ------------------------------------------------------------------------------------------------------ |
| D&N Produce Inc.           | Usually no invoice item code; match by vendor and product description                                  |
| Jalisco Fresh Produce Inc. | Match by Jalisco short code and/or product description to QB PO code mapping                           |
| Maui Fresh                 | Invoice may show Maui Fresh International; QB vendor name must remain Maui Fresh; match by description |
| Glen Rose Meat Company     | Use invoice product code when possible; weight-based items use total lbs in Bill Import qty            |
| La Palma Foods             | Match by description; if no PO match, enter as billed not on PO with blank item code                   |

The matching engine must show:

* Matched PO row.
* Match confidence.
* Reason for match.
* Ability to manually select/override a match.
* Ability to mark bill item as not on PO.

## 10.10 Bill Import Sheet

Exact 11-column format:

|  # | Column      | Rule                                                                                                                |
| -: | ----------- | ------------------------------------------------------------------------------------------------------------------- |
|  1 | Line        | Sequential line number; restart at 1 per invoice                                                                    |
|  2 | UPC         | UPC from vendor bill if printed; otherwise blank                                                                    |
|  3 | Item Code   | Use QB PO item code when matched; blank if not on PO                                                                |
|  4 | Description | PO description, blank line, vendor description; add analysis only when required                                     |
|  5 | Price       | Vendor billed unit rate exactly as shown                                                                            |
|  6 | Qty         | Vendor billed qty; for weight-based items use total lbs shipped; use 0 only for actual PO items not billed/provided |
|  7 | Total       | Vendor billed line total exactly as shown                                                                           |
|  8 | Ref         | Vendor invoice or credit memo number                                                                                |
|  9 | Date        | Vendor bill date                                                                                                    |
| 10 | Vendor      | Vendor name exactly as it appears in QB PO when matched                                                             |
| 11 | Type        | Always `Inventory Part`                                                                                             |

Description rules:

* PO notes may appear only in Bill Import description and only if relevant to that item.
* Do not copy PO notes into Summary.
* Do not copy PO notes into Cost Comparison.
* Dollar impact belongs in Description only when there is a rate difference.
* Do not add dollar impact for quantity-only differences, substitutions, promos, or credits unless explicitly requested.
* If verified individual weights are shown, add final line:

  * `weights: xx.xx+xx.xx+xx.xx`

## 10.11 Summary Vendor & Warehouse Sheet

This sheet is not a raw discrepancy table. It must be office-ready vendor email content.

Do not create a vendor summary block if there is nothing to report.

Required sections:

1. Header
2. Copy/Paste Email Body
3. Overcharged Items
4. Undercharged / Price Decrease Items
5. Quantity Issues
6. Missing / Not Billed Items
7. Optional Office Note

### 10.11.1 Header

Must include:

* Vendor name.
* Invoice number.
* Invoice date.
* Email subject.
* Summary type.
* Prepared-for note.

### 10.11.2 Copy/Paste Email Body

Must include:

* Short greeting.
* Clear request to review invoice.
* Confirmation request for overcharges.
* Confirmation request for undercharges / price decreases.
* Closing.

### 10.11.3 Overcharged Items

Grouped first.

Include:

* Item code.
* Item.
* PO rate.
* Invoice rate.
* Qty.
* Difference per unit.
* Total impact.
* Action needed.

### 10.11.4 Undercharged / Price Decrease Items

Grouped second.

Include same fields as overcharged items.

Ask vendor to confirm whether lower price is correct.

### 10.11.5 Quantity Issues

Grouped third.

Include only when actual quantity shortage or extra exists.

Do not include dollar impact unless there is also a rate difference.

### 10.11.6 Missing / Not Billed Items

Grouped last.

Include actual PO items ordered but not charged/provided.

Include ETA request when applicable.

### 10.11.7 Not Allowed

The system must not add:

* “Nothing missing.”
* “No discrepancies.”
* Internal PO notes.
* Buyer reminders.
* Quality-review notes.
* “Contact Barak” or similar instructions unless explicitly requested.
* Raw repeated rows without email context.
* Interpretive paragraphs.

## 10.12 PO Items Not Charged Sheet

This sheet contains only actual PO items ordered but not charged/provided after the related bill has been processed.

Rules:

* If nothing is missing, add nothing.
* Do not add vendor status notes.
* Do not use for billed-not-on-PO items.
* Billed-not-on-PO items belong in Bill Import with blank item code and red highlight.

## 10.13 Individual Weights Sheet

Rules:

* Create block only when verified individual weights exist.
* Use merged block header:

  * `Vendor Name - Invoice # - Invoice Date`
* Headers:

  * `Item Code (PO)`
  * `Item Code (Bill)`
  * `Product Name (PO)`
  * `W1`
  * `W2`
  * `W3`
  * More weight columns as needed
  * `Total`
* One row per item.
* Each individual weight goes in separate cell.
* Final total cell must equal billed weight.
* Do not create notes saying no weights were shown.

## 10.14 Cost Comparison Sheet

Columns:

| Column           | Rule                                                 |
| ---------------- | ---------------------------------------------------- |
| Item Code        | QB PO item code                                      |
| Description      | Short PO item description only                       |
| Vendor           | QB PO vendor name                                    |
| PO Cost          | Cost from matched PO row                             |
| Vendor Bill Cost | Actual vendor bill unit rate                         |
| Difference       | Vendor Bill Cost − PO Cost                           |
| % Change         | Difference ÷ PO Cost; blank if PO cost zero/unusable |

Rules:

* Include matched PO-vs-bill items only.
* Sort by Vendor, then Item Code or Description.
* No paragraph-style notes.
* No internal PO notes.
* No interpretation.
* If rate is unreadable, mark `VERIFY`.

## 10.15 Credits and Returns

Requirements:

* Process credit only when credit image is received.
* Use credit memo number as Ref.
* Use negative qty, negative total, or exact credit structure required by the QuickBooks import method.
* If credited item is not found in processed PO Bank, enter in Bill Import as credit not on PO.
* Item code should be blank.
* Row should be light red.
* Do not create unrelated PO Items Not Charged from a credit memo alone.

## 10.16 Row Highlighting

| Situation                               | Sheet                                | Handling                                                         |
| --------------------------------------- | ------------------------------------ | ---------------------------------------------------------------- |
| Matched normal bill item                | Bill Import / Cost Comparison        | No red highlight unless rate rules require color                 |
| Vendor billed item not on PO            | Bill Import                          | Light red row; item code blank; description identifies not on PO |
| PO item ordered but not billed/provided | Bill Import and PO Items Not Charged | Light red row; Bill Import qty 0                                 |
| Verified individual weights             | Bill Import and Individual Weights   | Add weights line and weights detail block                        |
| No missing/no weights/no discrepancies  | Any sheet                            | Add nothing                                                      |

## 10.17 PO Bank Row Lifecycle

Each PO Bank product row should have internal status:

* `unprocessed`
* `matched_pending_review`
* `processed`
* `removed_from_active_bank`
* `manually_excluded`
* `reopened`

The exported `Original PO / PO Bank` sheet should show only unprocessed active rows.

The database must retain processed rows for audit.

## 10.18 Acceptance Criteria

* PO export parses product lines into PO Bank.
* Order headers and embedded item tasks go only to Office/Driver tasks.
* No working sheet is populated before a bill image is processed.
* Bill image extraction must be reviewed before processing.
* Bill Import uses exact 11-column structure.
* Processed PO rows disappear from active PO Bank.
* Summary Vendor & Warehouse is email-prep content, not raw discrepancy rows.
* Empty results do not produce status notes.
* Individual Weights appears only for verified weights.
* Cost Comparison is factual and sorted.
* Vendor-specific matching rules are applied.
* Credits do not create unrelated missing PO rows.

---

# 11. Module D — Combined Price Changes

## 11.1 Purpose

Create one consolidated review sheet showing cost changes from both Jetro/Restaurant Depot and vendor-bill workflows.

## 11.2 Inputs

The module should support two input modes.

### Preferred internal mode

Pull from completed workflow runs:

* Jetro run: `Price Update` records.
* Vendor-bill run: `Cost Comparison` records.

### Upload mode

Allow user to upload:

* Jetro workflow output workbook.
* Vendor-bill import output workbook.

Then parse:

* Jetro `Price Update`.
* Vendor-bills `Cost Comparison`.

## 11.3 Output Sheet

Sheet name:

```text
Price changes from both sources
```

Columns:

| Column | Field            | Rule                                                       |
| -----: | ---------------- | ---------------------------------------------------------- |
|      A | Item Code        | Full code exactly as source                                |
|      B | Item Description | Source description                                         |
|      C | Old Cost         | Jetro Old Cost or Vendor PO Cost                           |
|      D | New Cost         | Jetro New Cost or Vendor Bill Cost                         |
|      E | Difference       | New Cost − Old Cost                                        |
|      F | Used by:         | Jetro customer usage; blank for vendor bills               |
|      G | Source           | `Jetro / Restaurant Depot` or `Vendor bills (vendor name)` |

## 11.4 Transformation Rules

Jetro source mapping:

| Output Field     | Jetro Price Update Field   |
| ---------------- | -------------------------- |
| Item Code        | A                          |
| Item Description | C                          |
| Old Cost         | D                          |
| New Cost         | E                          |
| Used by          | G                          |
| Source           | `Jetro / Restaurant Depot` |

Vendor-bill source mapping:

| Output Field     | Cost Comparison Field                    |
| ---------------- | ---------------------------------------- |
| Item Code        | A                                        |
| Item Description | B                                        |
| Old Cost         | D                                        |
| New Cost         | E                                        |
| Used by          | Blank                                    |
| Source           | `Vendor bills ({Vendor})` using column C |

Difference rule:

```text
Difference = New Cost - Old Cost
```

Filtering:

* Exclude no-change rows.
* Drop rows where `abs(Difference) <= 0.005`.

Sorting:

* Sort by absolute Difference descending.
* Largest movement first.

Formatting:

* Cost increase: pink.
* Cost decrease: green.

Deduplication:

* No deduplication required.
* If the same item appears in both sources, keep both rows with different Source values.

## 11.5 Acceptance Criteria

* Combined sheet includes changed items only.
* Jetro sign convention is correctly converted to `New - Old`.
* Vendor-bill sign convention remains `Vendor Bill Cost - PO Cost`.
* No-change items are excluded.
* Rows are sorted by largest absolute movement.
* Source field clearly distinguishes channels.

---

# 12. Cross-Workflow Data Model

Below is a practical relational data model for the AI coder.

## 12.1 Core Tables

### users

```sql
users (
  id uuid primary key,
  email text unique not null,
  name text not null,
  role text not null,
  created_at timestamptz not null
)
```

Roles:

* `admin`
* `accounting`
* `office`
* `management`
* `viewer`

### workflow_runs

```sql
workflow_runs (
  id uuid primary key,
  workflow_type text not null,
  name text not null,
  run_date date not null,
  status text not null,
  created_by uuid references users(id),
  created_at timestamptz not null,
  updated_at timestamptz not null,
  locked_at timestamptz,
  archived_at timestamptz
)
```

Workflow types:

* `web_orders_check`
* `jetro_reconciliation`
* `vendor_bill_po_bank`
* `combined_price_changes`

### uploaded_files

```sql
uploaded_files (
  id uuid primary key,
  run_id uuid references workflow_runs(id),
  file_type text not null,
  original_filename text not null,
  storage_path text not null,
  mime_type text,
  sha256 text,
  uploaded_by uuid references users(id),
  uploaded_at timestamptz not null,
  parse_status text not null,
  parse_errors jsonb
)
```

### audit_events

```sql
audit_events (
  id uuid primary key,
  run_id uuid references workflow_runs(id),
  user_id uuid references users(id),
  event_type text not null,
  entity_type text,
  entity_id uuid,
  before_value jsonb,
  after_value jsonb,
  message text,
  created_at timestamptz not null
)
```

## 12.2 Web Orders Tables

### web_order_lines

```sql
web_order_lines (
  id uuid primary key,
  run_id uuid references workflow_runs(id),
  source_row_number int,
  product_name text,
  code text,
  qty numeric,
  weight numeric,
  individual_weight_status text,
  price numeric,
  customer_name text,
  transaction_date date,
  route text,
  remark text,
  category_name text,
  current_cost_price numeric,
  current_selling_price numeric,
  shopping_product text,
  new_bin text,
  unit_price numeric,
  case_price numeric,
  quantity_on_hand numeric,
  inventory_cost numeric,
  case_avg_weight numeric,
  unit_avg_weight numeric,
  bin_internal text,
  unit text,
  is_future boolean default false,
  is_problematic boolean default false,
  problem_reasons text[],
  raw_row jsonb
)
```

## 12.3 Jetro Tables

### jetro_source_lines

```sql
jetro_source_lines (
  id uuid primary key,
  run_id uuid references workflow_runs(id),
  source_row_number int,
  qty numeric,
  product_name text,
  raw_code text,
  base_code text,
  kind text,
  full_code text,
  customer_name text,
  current_cost_price numeric,
  current_selling_price numeric,
  case_avg_weight numeric,
  unit text,
  is_internal_inventory boolean,
  raw_row jsonb
)
```

### restaurant_depot_invoices

```sql
restaurant_depot_invoices (
  id uuid primary key,
  run_id uuid references workflow_runs(id),
  invoice_number text not null,
  invoice_date date,
  invoice_type text not null,
  printed_grand_total numeric,
  processed_total numeric,
  integrity_status text,
  source_file_id uuid references uploaded_files(id),
  extraction_status text,
  user_confirmed_at timestamptz,
  created_at timestamptz not null
)
```

Invoice types:

* `charge`
* `credit`

### restaurant_depot_invoice_lines

```sql
restaurant_depot_invoice_lines (
  id uuid primary key,
  invoice_id uuid references restaurant_depot_invoices(id),
  source_row_number int,
  line_number text,
  upc text,
  item_raw text,
  description text,
  price numeric,
  cu text,
  qty numeric,
  total numeric,
  base_code text,
  kind text,
  full_code text,
  row_type text,
  folded_into_line_id uuid,
  raw_row jsonb
)
```

Row types:

* `item`
* `coupon`
* `surcharge`
* `void`
* `return`

### jetro_import_rows

```sql
jetro_import_rows (
  id uuid primary key,
  run_id uuid references workflow_runs(id),
  invoice_id uuid references restaurant_depot_invoices(id),
  line int,
  upc text,
  item_code text,
  description text,
  cost numeric,
  qty numeric,
  total numeric,
  invoice_number text,
  type text default 'Inventory Part'
)
```

### jetro_issues

```sql
jetro_issues (
  id uuid primary key,
  run_id uuid references workflow_runs(id),
  invoice_id uuid references restaurant_depot_invoices(id),
  issue_type text,
  item_code text,
  quantity numeric,
  item_description text,
  used_by text,
  detail text,
  dollar_size numeric
)
```

### jetro_price_updates

```sql
jetro_price_updates (
  id uuid primary key,
  run_id uuid references workflow_runs(id),
  item_code text,
  qty_charged numeric,
  item_description text,
  old_cost numeric,
  new_cost numeric,
  cost_change_old_minus_new numeric,
  used_by text
)
```

### jetro_coupons

```sql
jetro_coupons (
  id uuid primary key,
  run_id uuid references workflow_runs(id),
  invoice_id uuid references restaurant_depot_invoices(id),
  item_code text,
  description text,
  coupon_amount numeric,
  qty numeric,
  invoice_total_savings numeric,
  invoice_number text,
  eight_week_usage numeric,
  projected_savings numeric
)
```

## 12.4 Vendor Bill / PO Bank Tables

### po_bank_rows

```sql
po_bank_rows (
  id uuid primary key,
  run_id uuid references workflow_runs(id),
  source_row_number int,
  terms text,
  ref_number text,
  txn_date date,
  vendor text,
  memo text,
  total_amount numeric,
  po_cost numeric,
  description text,
  item_code text,
  quantity numeric,
  class_name text,
  case_avg_weight numeric,
  unit_avg_weight numeric,
  status text,
  processed_bill_id uuid,
  raw_row jsonb
)
```

### office_driver_tasks

```sql
office_driver_tasks (
  id uuid primary key,
  run_id uuid references workflow_runs(id),
  vendor_name text,
  ref_number text,
  task_type text,
  item text,
  need_review text,
  task_instructions text
)
```

### vendor_bills

```sql
vendor_bills (
  id uuid primary key,
  run_id uuid references workflow_runs(id),
  source_file_id uuid references uploaded_files(id),
  vendor_extracted text,
  vendor_confirmed text,
  invoice_number text,
  invoice_date date,
  bill_type text,
  extraction_status text,
  user_confirmed_at timestamptz,
  created_at timestamptz not null
)
```

Bill types:

* `invoice`
* `credit_memo`

### vendor_bill_lines

```sql
vendor_bill_lines (
  id uuid primary key,
  bill_id uuid references vendor_bills(id),
  source_line_number int,
  bill_item_code text,
  description text,
  qty numeric,
  rate numeric,
  total numeric,
  is_credit boolean,
  individual_weights numeric[],
  notes text,
  confidence numeric,
  matched_po_bank_row_id uuid references po_bank_rows(id),
  match_status text,
  user_confirmed boolean default false,
  raw_extraction jsonb
)
```

### bill_import_rows

```sql
bill_import_rows (
  id uuid primary key,
  run_id uuid references workflow_runs(id),
  bill_id uuid references vendor_bills(id),
  line int,
  upc text,
  item_code text,
  description text,
  price numeric,
  qty numeric,
  total numeric,
  ref text,
  date date,
  vendor text,
  type text default 'Inventory Part',
  highlight_status text
)
```

### vendor_summary_blocks

```sql
vendor_summary_blocks (
  id uuid primary key,
  run_id uuid references workflow_runs(id),
  bill_id uuid references vendor_bills(id),
  vendor text,
  invoice_number text,
  invoice_date date,
  email_subject text,
  email_body text,
  office_note text,
  has_reportable_issue boolean
)
```

### vendor_summary_items

```sql
vendor_summary_items (
  id uuid primary key,
  summary_block_id uuid references vendor_summary_blocks(id),
  section text,
  item_code text,
  item_description text,
  po_rate numeric,
  invoice_rate numeric,
  qty numeric,
  difference_per_unit numeric,
  total_impact numeric,
  action_needed text
)
```

### po_items_not_charged

```sql
po_items_not_charged (
  id uuid primary key,
  run_id uuid references workflow_runs(id),
  bill_id uuid references vendor_bills(id),
  po_bank_row_id uuid references po_bank_rows(id),
  item_code text,
  description text,
  vendor text,
  ref_number text,
  qty_ordered numeric,
  po_cost numeric,
  eta_request boolean
)
```

### individual_weight_rows

```sql
individual_weight_rows (
  id uuid primary key,
  run_id uuid references workflow_runs(id),
  bill_id uuid references vendor_bills(id),
  item_code_po text,
  item_code_bill text,
  product_name_po text,
  weights numeric[],
  total numeric
)
```

### cost_comparison_rows

```sql
cost_comparison_rows (
  id uuid primary key,
  run_id uuid references workflow_runs(id),
  item_code text,
  description text,
  vendor text,
  po_cost numeric,
  vendor_bill_cost numeric,
  difference numeric,
  percent_change numeric
)
```

## 12.5 Combined Price Changes Table

```sql
combined_price_change_rows (
  id uuid primary key,
  run_id uuid references workflow_runs(id),
  item_code text,
  item_description text,
  old_cost numeric,
  new_cost numeric,
  difference numeric,
  used_by text,
  source text
)
```

---

# 13. User Experience Requirements

## 13.1 Main Dashboard

The dashboard must show:

* Active workflow runs.
* Run type.
* Run date.
* Status.
* Last updated.
* Validation status.
* Export availability.
* Number of uploaded files.
* Number of issues/warnings.
* Quick action buttons:

  * Continue
  * Review extraction
  * Process
  * Export
  * Archive

## 13.2 Workflow Creation

User chooses workflow type:

1. Daily Web Orders Check
2. Jetro / Restaurant Depot Reconciliation
3. Vendor Bills / PO Bank
4. Combined Price Changes

Then app asks for:

* Run name.
* Run date.
* Optional notes.
* Whether to start fresh or continue existing accumulating run.

## 13.3 File Upload Screen

Requirements:

* Drag-and-drop upload.
* File type detection.
* Required file checklist.
* Sheet detection preview.
* Column validation.
* Missing required column errors.
* Duplicate file warning.
* Replacement flow with versioning.

## 13.4 Extraction Review Screen

For invoice images/PDFs:

* Show original image/PDF side-by-side with extracted data grid.
* Allow zoom.
* Allow row add/delete.
* Allow field edit.
* Show confidence per row/field.
* Highlight required missing values.
* Require user confirmation.

## 13.5 Matching Review Screen

For Jetro and vendor-bill workflows:

* Show source item.
* Show matched item.
* Show match key.
* Show quantity comparison.
* Show cost comparison.
* Show confidence.
* Allow manual override.
* Allow mark as unmatched.
* Allow add note.

## 13.6 Validation Screen

Before export, show:

* Blocking errors.
* Warnings.
* Invoice total checks.
* Rows not matched.
* Price changes above threshold.
* Missing expected sheets.
* OCR fields not confirmed.
* Override controls for authorized users.

## 13.7 Export Screen

Show export options:

* Full workbook.
* QuickBooks import only.
* Reconciliation only.
* Problematic items only.
* Combined price changes only.

Each export should show:

* File name.
* Generated timestamp.
* Source run.
* Version number.
* Download button.

---

# 14. File Naming Requirements

Default generated file names:

## 14.1 Web Orders

```text
Web_Orders_Check_MMDDYYYY.xlsx
```

## 14.2 Jetro / Restaurant Depot

```text
Jetro_Restaurant_Depot_Reconciliation_MMDDYYYY.xlsx
```

## 14.3 Vendor Bills

```text
QB_Vendor_Bill_Import_MMDDYYYY_Accumulating.xlsx
```

## 14.4 Combined Price Changes

```text
Price_Changes_Both_Sources_MMDDYYYY.xlsx
```

The user should be allowed to rename exports before download, but the default names should follow these conventions.

---

# 15. Shared Normalization and Calculation Rules

## 15.1 Currency

Use Decimal, not binary floating point.

Currency display:

* Two decimals for dollar totals.
* Unit costs may preserve more precision when source requires it.
* Invoice integrity should compare rounded-to-cent totals.

## 15.2 Quantity

Quantities may be:

* Cases.
* Units.
* Pounds.
* Negative returns.
* Zero for actual PO missing items in vendor Bill Import only.

## 15.3 Item Code Normalization

General normalization:

```text
trim whitespace
convert numeric-looking strings to canonical text
remove trailing .0 from spreadsheet numeric strings
preserve meaningful U/C suffixes
```

Jetro matching:

```text
base_code = numeric portion
kind = U if full code ends U or invoice C/U starts U
kind = C otherwise
matching key = (base_code, kind)
```

Web Orders enrichment:

```text
normal_code = text-normalized code
Shopping History may match if only difference is one trailing U or C
```

Vendor bills:

```text
use configured vendor-specific matching rules
prefer PO item code when bill code is reliable
fall back to description similarity where vendor requires it
```

## 15.4 Date Handling

* User timezone: Europe/Athens unless organization setting says otherwise.
* Web Orders run date controls same-day/future split.
* Invoice dates must come from invoice/bill source when available.
* If invoice date is unreadable, require user confirmation.

## 15.5 Sorting

Sorting must be deterministic.

When two rows have equal primary sort values, sort by:

1. Vendor if available.
2. Item code.
3. Description.
4. Original source row number.

---

# 16. Validation and Error Handling

## 16.1 Blocking Errors

The app must block export for:

* Missing required input file.
* Missing required sheet.
* Missing required column.
* Unconfirmed image extraction.
* Invoice line total not matching printed Grand Total.
* Restaurant Depot invoice number missing.
* Vendor bill invoice number missing.
* Invalid run date.
* PO export cannot identify product rows.
* Generated QuickBooks import has invalid required columns.

## 16.2 Warnings

The app should warn but allow authorized continuation for:

* Unmatched invoice item.
* Billed item not on PO.
* Coupon item not found in Sales-Per-Week report.
* Past-dated web order line.
* Price change above configured threshold.
* Weight mismatch close to tolerance.
* Duplicate item description with different item codes.
* Vendor alias detected but not configured.

## 16.3 Overrides

When an authorized user overrides a blocking or warning condition, record:

* User.
* Timestamp.
* Issue type.
* Original value.
* Override value or reason.
* Affected workflow run.
* Affected row IDs.

---

# 17. Security and Permissions

## 17.1 Authentication

Required for all users.

Acceptable MVP options:

* Email/password.
* Google Workspace login.
* SSO later.

## 17.2 Authorization

Permissions by role:

| Capability                    | Admin | Accounting |      Office | Management | Viewer |
| ----------------------------- | ----: | ---------: | ----------: | ---------: | -----: |
| Upload files                  |   Yes |        Yes |         Yes |   Optional |     No |
| Process workflows             |   Yes |        Yes |         Yes |         No |     No |
| Confirm OCR extraction        |   Yes |        Yes |         Yes |         No |     No |
| Override blocking validations |   Yes |   Optional |          No |         No |     No |
| Export QuickBooks import      |   Yes |        Yes | No/Optional |         No |     No |
| View summaries                |   Yes |        Yes |         Yes |        Yes |    Yes |
| Edit configuration            |   Yes |         No |          No |         No |     No |
| Archive/delete runs           |   Yes |   Optional |          No |         No |     No |

## 17.3 Data Protection

* Store uploaded files securely.
* Restrict access by organization.
* Log file downloads.
* Keep source files immutable.
* Store generated outputs as versioned artifacts.
* Do not overwrite exports silently.

---

# 18. Reporting and Observability

## 18.1 Run Summary Metrics

Each run should calculate:

### Web Orders

* Total rows.
* Same-day rows.
* Future rows.
* Problematic rows.
* Missing status rows.
* Below-cost rows.
* Weight issue rows.

### Jetro

* Number of invoices.
* Number of credit invoices.
* Invoice totals.
* Import totals.
* Total missing items.
* Total extra items.
* Total qty mismatches.
* Number of coupons.
* Total invoice coupon savings.
* Total projected 8-week savings.
* Number of price changes.

### Vendor Bills

* PO Bank starting rows.
* PO Bank remaining rows.
* Bills processed.
* Bill Import rows.
* Billed-not-on-PO rows.
* PO items not charged.
* Cost comparison rows.
* Vendor summary blocks created.
* Individual weight items.

### Combined Price Changes

* Jetro changes.
* Vendor bill changes.
* Total changes.
* Cost increases.
* Cost decreases.
* Largest increase.
* Largest decrease.

## 18.2 Processing Logs

For each run, log:

* File uploaded.
* File parsed.
* Extraction completed.
* User confirmed extraction.
* Matching completed.
* Validation failed/passed.
* Export generated.
* Override created.
* Run archived.

---

# 19. Workbook Generation Requirements

## 19.1 Excel Formatting

Use consistent formatting:

* Header row bold.
* Freeze top row.
* Auto-filter enabled.
* Auto-fit or reasonable column widths.
* Currency columns formatted consistently.
* Weight/price precision preserved where required.
* Highlight problem/review rows.
* Highlight green/pink cost movements.
* Light red for billed-not-on-PO or missing PO items.
* Merged block headers only where required, such as Individual Weights.

## 19.2 Export Fidelity

Generated workbooks must be stable enough for:

* Office review.
* Accounting import preparation.
* QuickBooks upload preparation.
* Archival.

The app should generate workbooks server-side to avoid browser inconsistencies.

---

# 20. MVP Implementation Plan

## Phase 1 — Foundation

Build:

* Authentication.
* Workflow run dashboard.
* File upload/storage.
* Excel parser.
* Workbook export engine.
* Audit logging.
* Basic validation framework.

Deliverable:

* Users can create runs, upload files, parse sheets, and download generated test workbook.

## Phase 2 — Web Orders Check

Build:

* Reference sheet enrichment.
* Same-day/future split.
* Problem checks.
* Problematic Items.
* By Customer Problematic.
* Final workbook export.

This is a strong first workflow because it is deterministic and mostly spreadsheet-based.

## Phase 3 — Jetro / Restaurant Depot

Build:

* Jetro source parser.
* Restaurant Depot `.xlsx` invoice parser.
* Manual invoice line entry table.
* CRV/coupon/void/return folding.
* Matching by `(base_code, kind)`.
* All Issues.
* Price Update.
* Coupons.
* Summary.
* Multi-invoice cumulative run.
* Credit invoice support.

Add image extraction after deterministic `.xlsx` flow works.

## Phase 4 — Vendor Bills / PO Bank

Build:

* PO export parser.
* PO Bank.
* Office/Driver tasks extraction.
* Vendor bill extraction review screen.
* Matching engine.
* Bill Import.
* Summary Vendor & Warehouse.
* PO Items Not Charged.
* Individual Weights.
* Cost Comparison.
* PO Bank row removal.

## Phase 5 — Combined Price Changes

Build:

* Pull from internal Jetro and Vendor Bill run data.
* Workbook upload fallback.
* Difference normalization.
* Changes-only filtering.
* Sorted output sheet.

## Phase 6 — Hardening

Build:

* Advanced validation.
* Override flows.
* Role permissions.
* Vendor matching configuration UI.
* Regression test suite.
* Golden workbook comparisons.
* Export version history.

---

# 21. Testing Strategy

## 21.1 Unit Tests

Required test groups:

### Normalization

* Numeric/text item codes.
* Trailing `U`.
* Trailing `C`.
* `(T)` taxable invoice markers.
* Whitespace trimming.
* `.0` spreadsheet artifacts.

### Web Orders

* Enrichment from all three reference sheets.
* Shopping History suffix exception.
* Future split.
* Spacer row behavior.
* MISSING/SUBSTITUTED/WITH statuses.
* LBS cascade.
* AVG ±15% allowance.
* Cost-vs-price logic.
* Blank cost behavior.

### Jetro

* CRV folding.
* Coupon folding.
* CRV plus coupon under same item.
* Void netting.
* Return netting.
* Full credit invoice.
* Internal warehouse exclusion.
* LBS expected pounds.
* Deduplication.
* Grand Total integrity.

### Vendor Bills

* PO row classification.
* Embedded task splitting.
* Vendor-specific matching.
* Bill item not on PO.
* PO item not charged.
* Individual weights exact sum.
* Credit memo handling.
* No empty status rows.
* Summary block only when issues exist.

### Combined Price Changes

* Jetro sign conversion.
* Vendor sign usage.
* No-change threshold.
* Absolute difference sorting.
* Source labeling.

## 21.2 Golden Workbook Tests

For each workflow, maintain sample input files and expected output workbooks.

Automated tests should:

* Generate output workbook.
* Compare sheet names.
* Compare header rows.
* Compare row counts.
* Compare key cell values.
* Compare totals.
* Compare issue counts.
* Compare formatting flags where important.

## 21.3 End-to-End Tests

Scenarios:

1. Daily web orders run with same-day, future, problematic, and clean rows.
2. Jetro run with one charge invoice, coupons, CRV, one return line, and Sales-Per-Week report.
3. Jetro run with multiple invoices and one credit.
4. Vendor bills run with one PO export and three bill images from different vendors.
5. Vendor bill with billed-not-on-PO item.
6. Vendor bill with missing PO item.
7. Vendor bill with individual weights.
8. Combined price run after Jetro and vendor bills have been processed.

---

# 22. AI Extraction Requirements

## 22.1 Extraction JSON Contract

For invoice images, the extraction service should return structured JSON.

### Restaurant Depot invoice extraction

```json
{
  "invoice_number": "230543",
  "invoice_date": "2026-06-01",
  "grand_total": 1234.56,
  "lines": [
    {
      "line": "1",
      "upc": "123456789",
      "item": "24514",
      "description": "PRODUCT NAME",
      "price": 10.5,
      "cu": "C",
      "qty": 3,
      "total": 31.5,
      "confidence": 0.98
    }
  ]
}
```

### Vendor bill extraction

```json
{
  "vendor": "Maui Fresh International",
  "invoice_number": "INV-123",
  "invoice_date": "2026-06-01",
  "bill_type": "invoice",
  "lines": [
    {
      "bill_item_code": "ABC123",
      "description": "PRODUCT NAME",
      "qty": 10,
      "rate": 12.34,
      "total": 123.4,
      "individual_weights": [12.1, 11.9],
      "notes": "",
      "confidence": 0.92
    }
  ]
}
```

## 22.2 Review Requirement

Any extracted field below confidence threshold should be highlighted.

Default confidence threshold:

```text
0.90
```

The user must confirm:

* Invoice number.
* Invoice date.
* Vendor when applicable.
* Each line’s item/description.
* Quantity.
* Rate/price.
* Total.
* Grand Total when applicable.

---

# 23. Configuration Requirements

Admin should be able to configure:

## 23.1 Vendor Aliases

Example:

```json
{
  "Maui Fresh International": "Maui Fresh"
}
```

## 23.2 Vendor Matching Rules

For each vendor:

* Match by code.
* Match by description.
* Match by short code.
* Require manual review.
* Allow fuzzy match threshold.

## 23.3 Keyword Rules

For Web Orders:

* Substitution keywords.
* Pending keywords.
* Office mistake keywords.
* AVG product keywords.

For Jetro:

* CRV keywords.
* Surcharge keywords.
* Coupon indicators.
* Internal warehouse customer name.

## 23.4 Tolerances

* Currency penny tolerance.
* Weight tolerance.
* AVG ±15% allowance.
* No-change price threshold: default `0.005`.

## 23.5 Column Mappings

Although the SOPs define exact columns, the app should allow admin-level mapping overrides for future file changes.

---

# 24. Open Implementation Questions

These should not block MVP, but the AI coder should design with them in mind:

1. Should QuickBooks import be exported as `.xlsx`, `.csv`, or both?
2. Does QuickBooks require a specific date format for import?
3. Should invoice images be stored permanently or purged after a retention period?
4. Should vendor email drafts eventually be sent through email integration?
5. Should sell-price updates eventually generate a QuickBooks item update file?
6. Should multiple users be allowed to edit the same extraction review at once?
7. Should Management users be allowed to see source invoices, or only summaries?

For MVP, assume:

* Export `.xlsx` first.
* Add CSV export for import sheets where useful.
* Keep all source files unless admin archives/deletes.
* Do not send emails automatically.
* Do not post directly to QuickBooks.

---

# 25. Final Build Definition

The application is complete for MVP when a user can:

1. Create a Daily Web Orders run, upload required files, process them, and download the four-sheet checked workbook.
2. Create a Jetro weekly run, upload Jetro source, upload Restaurant Depot invoices, review extracted image lines when needed, process invoices, and download the five-sheet reconciliation/import workbook.
3. Create a Vendor Bills workday run, upload the QuickBooks PO export, process bill images one by one, maintain the active PO Bank, and download the accumulating vendor-bill workbook.
4. Create a Combined Price Changes run from completed Jetro and Vendor Bill runs, then download the combined price-change workbook.
5. Review validation results before export.
6. Correct extraction and matching issues manually.
7. See an audit trail of what files were uploaded, what data was extracted, what was edited, and what outputs were generated.

This product should be built as a **workflow-controlled accounting operations platform**, with strict validation, human review for image-derived data, exact spreadsheet output formats, and persistent run state.
