"""Backup and restore application data."""

from __future__ import annotations

import io
import os
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

DATA_ROOT = Path(os.environ.get("DATA_ROOT", "/app/data"))


def create_backup_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in DATA_ROOT.rglob("*"):
            if path.is_file():
                arcname = path.relative_to(DATA_ROOT).as_posix()
                zf.write(path, arcname)
        zf.writestr(
            "backup-meta.txt",
            f"created_at={datetime.now(timezone.utc).isoformat()}\nsource=homelab-dns-manager\n",
        )
    buffer.seek(0)
    return buffer.getvalue()


def restore_backup_zip(data: bytes) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        extract_dir = Path(tmp) / "restore"
        extract_dir.mkdir()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for name in zf.namelist():
                if name.endswith("/") or name.startswith("/") or ".." in name:
                    continue
                zf.extract(name, extract_dir)

        for item in extract_dir.iterdir():
            if item.name == "backup-meta.txt":
                continue
            dest = DATA_ROOT / item.name
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)
