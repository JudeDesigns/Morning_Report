import hashlib
import re
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from app.core.auth import get_current_user
from app.store import files_meta as file_store, runs as run_store, audit as audit_store
from app.services.storage import save_upload, detect_mime_type

router = APIRouter(prefix="/files", tags=["files"])

ALLOWED_FILE_TYPES = [
    # Web Orders — single multi-sheet workbook (preferred) or legacy 4-file layout
    "web_orders_spreadsheet",
    "web_orders_all_orders", "web_orders_item_list", "web_orders_inventory",
    "web_orders_shopping_history",
    # Jetro / Restaurant Depot
    "jetro_source", "restaurant_depot_invoice_xlsx",
    "restaurant_depot_invoice_image", "sales_per_week",
    # Vendor Bills
    "quickbooks_po_export", "vendor_bill_image", "vendor_bill_pdf",
    # Combined Price
    "combined_price_jetro_workbook", "combined_price_vendor_bill_workbook",
]

# Allowed MIME types — block executables and dangerous types
ALLOWED_MIMES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel", "text/csv", "application/pdf",
    "image/png", "image/jpeg", "image/webp", "image/tiff",
    "application/octet-stream",  # xlsx fallback
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

# Characters that are illegal across Windows/macOS/Linux filesystems or that
# could break HTTP Content-Disposition / shell handling. Everything else
# (apostrophes, parens, commas, ampersands, accented letters, etc.) is kept
# verbatim so the displayed name matches what the user uploaded.
_FORBIDDEN_FILENAME_CHARS = re.compile(r'[\x00-\x1f<>:"/\\|?*]')


def _safe_filename(name: str) -> str:
    name = Path(name).name.strip()           # strip any directory component
    name = _FORBIDDEN_FILENAME_CHARS.sub("_", name)  # neutralise illegal chars
    name = name.lstrip(".")                  # no leading dots (hidden / traversal)
    if not name:
        return "upload"
    return name[:255]                        # filesystem name length cap


@router.post("/upload/{run_id}", status_code=201)
async def upload_file(
    run_id: str,
    file_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    if file_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(400, f"Invalid file_type. Must be one of: {ALLOWED_FILE_TYPES}")

    run = run_store.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if current_user.get("role") != "admin" and run.get("created_by") != current_user["id"]:
        raise HTTPException(403, "Access denied")

    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"File too large (max {MAX_FILE_SIZE // 1024 // 1024} MB)")

    # Hash the bytes before writing anything to disk so we can dedupe early.
    # Same sha256 already present in this run ⇒ refuse; the user must delete
    # the existing copy first. Prevents duplicate vendor bills from going
    # through extraction + matching and double-counting in the export.
    content_sha256 = hashlib.sha256(content).hexdigest()
    existing_dup = next(
        (f for f in file_store.list_files(run_id) if f.get("sha256") == content_sha256),
        None,
    )
    if existing_dup:
        raise HTTPException(
            409,
            f"This exact file was already uploaded as "
            f"'{existing_dup.get('original_filename')}'. Delete that file first "
            "if you need to re-upload it.",
        )

    safe_name = _safe_filename(file.filename or "upload")
    mime_type = detect_mime_type(safe_name, content)

    if mime_type not in ALLOWED_MIMES:
        raise HTTPException(415, f"File type not allowed: {mime_type}")

    storage_path, sha256 = await save_upload(content, safe_name, run_id, file_type)

    record = file_store.add_file(
        run_id=run_id,
        file_type=file_type,
        original_filename=safe_name,
        storage_path=storage_path,
        mime_type=mime_type,
        sha256=sha256,
        uploaded_by=current_user["id"],
    )
    run_store.increment_file_count(run_id, 1)
    audit_store.log(run_id, "file_uploaded", f"{file_type}: {safe_name}", current_user["id"])
    return record


@router.get("/run/{run_id}", response_model=List[dict])
async def list_run_files(
    run_id: str,
    current_user: dict = Depends(get_current_user),
):
    run = run_store.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if current_user.get("role") != "admin" and run.get("created_by") != current_user["id"]:
        raise HTTPException(403, "Access denied")
    return file_store.list_files(run_id)


@router.delete("/{run_id}/{file_id}", status_code=204)
async def delete_file(
    run_id: str,
    file_id: str,
    current_user: dict = Depends(get_current_user),
):
    run = run_store.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if current_user.get("role") != "admin" and run.get("created_by") != current_user["id"]:
        raise HTTPException(403, "Access denied")

    rec = file_store.get_file(run_id, file_id)
    if not rec:
        raise HTTPException(404, "File record not found")

    # Remove physical file
    p = Path(rec["storage_path"])
    if p.exists():
        p.unlink()

    file_store.delete_file(run_id, file_id)
    run_store.increment_file_count(run_id, -1)
    audit_store.log(run_id, "file_deleted", rec["original_filename"], current_user["id"])


@router.get("/{run_id}/{file_id}/download")
async def download_file(
    run_id: str,
    file_id: str,
    current_user: dict = Depends(get_current_user),
):
    run = run_store.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if current_user.get("role") != "admin" and run.get("created_by") != current_user["id"]:
        raise HTTPException(403, "Access denied")

    rec = file_store.get_file(run_id, file_id)
    if not rec:
        raise HTTPException(404, "File not found")

    p = Path(rec["storage_path"])
    if not p.exists():
        raise HTTPException(404, "File not found on disk")

    return FileResponse(
        path=str(p),
        filename=rec["original_filename"],
        media_type=rec.get("mime_type") or "application/octet-stream",
    )
