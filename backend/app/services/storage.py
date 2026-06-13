import hashlib
import os
import uuid
import aiofiles
from pathlib import Path
from app.config import settings


def get_storage_root() -> Path:
    path = Path(settings.STORAGE_PATH)
    path.mkdir(parents=True, exist_ok=True)
    return path


async def save_upload(file_content: bytes, original_filename: str, run_id: uuid.UUID, file_type: str) -> tuple[str, str]:
    """Save uploaded file, return (storage_path, sha256)."""
    storage_root = get_storage_root()
    run_dir = storage_root / str(run_id) / file_type
    run_dir.mkdir(parents=True, exist_ok=True)

    # Compute sha256
    sha256 = hashlib.sha256(file_content).hexdigest()

    # Generate unique filename
    ext = Path(original_filename).suffix
    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = run_dir / unique_name

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(file_content)

    return str(file_path), sha256


async def read_file(storage_path: str) -> bytes:
    async with aiofiles.open(storage_path, "rb") as f:
        return await f.read()


def get_file_path(storage_path: str) -> Path:
    return Path(storage_path)


def detect_mime_type(filename: str, content: bytes) -> str:
    """Simple mime type detection based on file extension and magic bytes."""
    ext = Path(filename).suffix.lower()
    mime_map = {
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".csv": "text/csv",
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }
    # Check magic bytes
    if content[:4] == b'%PDF':
        return "application/pdf"
    if content[:8] == b'\x89PNG\r\n\x1a\n':
        return "image/png"
    if content[:2] in (b'\xff\xd8', b'\xff\xe0', b'\xff\xe1'):
        return "image/jpeg"
    return mime_map.get(ext, "application/octet-stream")
