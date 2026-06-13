# B&R Food Services — Workflow Automation: System Overview

> Plain-language guide to what the system does, how each workflow works, and what the recent v3 logic changes mean.

---

## What the System Is (One Paragraph)

The app replaces four manual Excel-based office workflows with a guided web platform. Staff upload their daily/weekly source files, the system parses and cross-checks them, flags anything that needs a human decision, and then exports clean, QuickBooks-ready workbooks. Nothing is posted automatically — every export requires a deliberate human sign-off. The whole thing is file-based (no live QuickBooks connection), so there is zero risk of accidentally writing bad data into accounting.

---

## Workflow A — Daily Web Orders Check

**When:** Every morning before invoices go out.

**What it does:**
1. Staff upload four files: All Orders, Item List, Inventory, Shopping History.
2. The system enriches each order line — pulling the cost, selling price, bin location, and case weight from the reference sheets — so reviewers see the full picture on one row.
3. It splits the orders into **Same-Day** (needs action today) and **Future** (keep for later).
4. It flags same-day lines that have problems: zero quantity, missing weight for a catch-weight item, price discrepancy, out-of-stock, etc.
5. Output: a four-sheet workbook — enriched All Orders, Future Orders, Problematic Items, and a customer-sorted review list.

**Key rule:** Only same-day lines are validated. Future orders are enriched but not flagged.

---

## Workflow B — Jetro / Restaurant Depot Reconciliation

**When:** Weekly, after the Restaurant Depot delivery.

**What it does:**
1. Staff upload the Jetro night-shift source sheet and one or more Restaurant Depot invoices (Excel, PDF, or photo).
2. The system folds returns, voids, CRV charges, and coupons into each item's net quantity and total.
3. It compares what Jetro says was ordered/credited against what Restaurant Depot actually charged.
4. Discrepancies (missing items, extra charges, quantity mismatches, price changes) are collected per invoice block.
5. Coupon savings opportunities are identified from Sales-Per-Week data.
6. Output: a five-sheet workbook — QuickBooks Bill Import, Summary, Price Updates, Coupon Opportunities, Individual Weights.

**Key rule:** Multiple Restaurant Depot invoices accumulate into the same run — you can add invoices one at a time and the workbook grows each time.

---

## Workflow C — Vendor Bills / PO Bank

**When:** Throughout the workday as vendor invoices arrive.

**What it does — step by step:**

| Step | Who does it | What happens |
|---|---|---|
| 1. Upload PO Export | Staff | QuickBooks PO export loaded as a "PO Bank" — a reference list of everything ordered |
| 2. Upload bill image | Staff | Photo or scan of a vendor invoice |
| 3. AI extraction | System (Claude) | Reads the bill image, pulls out vendor, invoice number, line items, quantities, and rates |
| 4. Human review | Staff | Review extracted lines, fix anything the AI missed, confirm |
| 5. Match to POs | System | Each confirmed bill line is matched to its PO row using smart name-matching (see below) |
| 6. Discrepancy check | System | Flags overcharges, undercharges, quantity mismatches, and items not on any PO |
| 7. Repeat 2–6 | Staff | More bills arrive → upload → extract → match → flag |
| 8. "Done" | Staff | Click "Done — Ready to Export" when all expected bills are in |
| 9. Finalize | System | Any PO rows that were never billed are collected into "PO Items Not Charged" |
| 10. Export | Staff | Download the full workbook |

**Output sheets (in order):**
1. Original PO – PO Bank
2. Office and Driver's Tasks
3. Bill Import *(QuickBooks-ready)*
4. Summary Vendor & Warehouse
5. **All Issues** *(new — see below)*
6. PO Items Not Charged
7. Individual Weights
8. Cost Comparison

**Smart matching logic:** Vendor item descriptions never match POs word-for-word. The matcher strips noise words ("Los Angeles Produce", "PD", quantity prefixes like "6 CS"), expands abbreviations ("Med" → "Medium"), splits compound words ("Springmix" → "spring mix"), and scores every candidate PO row using token overlap. The highest-scoring PO above the acceptance threshold is auto-selected. Staff can override any match with one click.

---

## Workflow D — Combined Price Changes

**When:** After running Workflow B and/or Workflow C on the same day.

**What it does:**
1. Pulls price changes from Workflow B's "Price Update" sheet.
2. Pulls cost changes from Workflow C's "Cost Comparison" sheet.
3. Merges them into a single review list — one row per changed item, sorted by largest dollar impact.
4. Uses the convention: **New Cost − Old Cost** (positive = price went up, negative = price went down).

**Why it matters:** Gives management one consolidated place to approve or question every cost change before it is applied, regardless of which vendor it came from.

---

## What We Just Added — Workflow v3 Logic (Plain English)

### The Problem It Solves
Before v3, discrepancies were scattered across multiple sheets. A manager or vendor contact had to flip between "Bill Import", "Summary", and "PO Items Not Charged" to get the full picture. That wastes time and causes things to get missed.

### The Solution: "All Issues" Sheet
A new sheet called **All Issues** is inserted between Summary and PO Items Not Charged. It is a single scannable table of every problem in the run, across all invoices, in one place.

**Three issue types and what they mean:**

| Type | Colour | Meaning |
|---|---|---|
| **Missing** | Blue | Item was on the PO (we ordered it) but the vendor never charged us — could mean it wasn't delivered |
| **Extra** | Orange | Vendor charged us for something that was not on any PO — needs explanation or a PO raised |
| **Qty Mismatch** | Yellow | Vendor billed a different quantity than the PO says we ordered |

**Sorting rule:** Missing issues first (highest dollar value first within the group), then Extra, then Qty Mismatch. Biggest financial exposure is always at the top.

**Detail column:** Every row has a plain-English sentence explaining exactly what happened and what action is needed, using a standard template — e.g.:
- *"Ordered on PO PO-101 but not charged on invoice INV-7. PO value ~$37.50 (3 @ $12.50)."*
- *"Billed on invoice INV-7 but not on PO. $11.00 (2 @ $5.50). Confirm intended / provide PO."*
- *"Invoice INV-7 billed 4; PO ordered 6 (−2). See Cost Comparison for rate move."*

### Office & Driver's Tasks — Column Realignment
The task sheet was also updated to match the v3 column spec: **Vendor · Ref # · Type · Item · Need Review · Task / Instructions**. "Order header" tasks show the vendor name in "Need Review" and the order note in "Task". "Item task" rows show the product name in "Need Review" and the specific task instruction in "Task".

### Quantity Mismatch Flag
Previously the system only flagged items as "overcharged" or "undercharged" based on rate (price per unit). Now it separately tracks whether the *quantity* also differs, even when the rate also changed. This means a line that has both a price change and a quantity difference will correctly appear in *both* the Summary (for the rate issue) and the All Issues sheet (for the qty issue).

---

## How the Tests Protect All of This

Every rule above has an automated test. When anyone changes the code in the future, the tests will immediately catch regressions — for example:
- If the sort order breaks (Extra appearing before Missing), the test fails.
- If the detail template wording changes, the test fails.
- If the sheet is placed in the wrong position in the workbook, the test fails.
- If the quantity-mismatch flag stops being set on lines that also have a rate move, the test fails.

This gives confidence that the logic is correct today and stays correct as the system grows.
