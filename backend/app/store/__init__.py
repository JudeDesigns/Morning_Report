"""File-based store layer (JSON + XLSX).  No database required.

Sub-modules:
  runs        — WorkflowRun CRUD
  users       — User CRUD (users.json)
  files_meta  — UploadedFile metadata CRUD (per-run files.json)
  results     — Intermediate processing results (per-run results/*.json)
  audit       — Append-only audit log (per-run audit.json)
"""
from app.store import runs, users, files_meta, results, audit

__all__ = ["runs", "users", "files_meta", "results", "audit"]
