"""Shared JSON read/write helpers with atomic write (tmp + rename)."""
import json
from datetime import datetime, date, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class _Encoder(json.JSONEncoder):
    """Convert Decimal → float, date/datetime → ISO string, fallback → str."""
    def default(self, obj):  # noqa: D102
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return str(obj)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def write_json(path: Path, data: Any) -> None:
    """Atomic write: serialise → .tmp → rename (crash-safe)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, cls=_Encoder), encoding="utf-8")
    tmp.replace(path)
