"""Intermediate processing results — stored per-run in storage/runs/{run_id}/results/{key}.json.

Keys used:
  web_orders_lines, jetro_invoices, jetro_import_rows, jetro_issues,
  jetro_price_updates, jetro_coupons, vendor_bills, po_bank, office_tasks,
  bill_import_rows, vendor_summary_blocks, po_not_charged, weight_rows,
  cost_comparison, combined_price_rows
"""
from pathlib import Path
from typing import Any

from app.store._base import read_json, write_json
from app.store.runs import run_dir


def _results_dir(run_id: str) -> Path:
    d = run_dir(run_id) / "results"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(run_id: str, key: str) -> Path:
    return _results_dir(run_id) / f"{key}.json"


# ── Public API ────────────────────────────────────────────────────────────────

def save(run_id: str, key: str, data: Any) -> None:
    """Overwrite results for this key (list or dict)."""
    write_json(_path(run_id, key), data)


def load(run_id: str, key: str, default: Any = None) -> Any:
    """Load results for this key; returns default if not found."""
    return read_json(_path(run_id, key), default if default is not None else [])


def append(run_id: str, key: str, items: list) -> None:
    """Append items to an existing list result (create if absent)."""
    existing: list = load(run_id, key, [])
    existing.extend(items)
    save(run_id, key, existing)


def exists(run_id: str, key: str) -> bool:
    return _path(run_id, key).exists()
