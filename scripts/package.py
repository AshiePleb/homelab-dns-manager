#!/usr/bin/env python3
"""
Create a deployment zip for HomeLab DNS Manager.

Excludes local dev artifacts (venv, node_modules, .env, build output).
Docker on the server installs Python/npm dependencies during `docker compose build`.

Usage (from project root):
    python3 scripts/package.py
    python3 scripts/package.py -o /tmp/homelab-dns-manager.zip
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_NAME = "homelab-dns-manager"

# Directories to skip entirely (matched against any path component)
EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".idea",
    ".vscode",
    "data",
    "dist",
    ".cursor",
}

# File names to skip
EXCLUDE_FILES = {
    ".env",
    ".DS_Store",
    "Thumbs.db",
}

# Glob patterns for files to skip (matched on filename)
EXCLUDE_FILE_PATTERNS = (
    "*.pyc",
    "*.pyo",
    "*.log",
    "*.db",
    "*.zip",
    ".env.*",
    "!.env.example",
)

# Only include .env.example from .env.* pattern
def should_exclude_file(name: str, rel_path: str) -> bool:
    if name in EXCLUDE_FILES:
        return True
    if name == ".env.example":
        return False
    for pattern in EXCLUDE_FILE_PATTERNS:
        if pattern.startswith("!"):
            continue
        if fnmatch.fnmatch(name, pattern):
            return True
    return False


def should_exclude_dir(name: str) -> bool:
    return name in EXCLUDE_DIRS


def collect_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded directories in-place so os.walk skips them
        dirnames[:] = [d for d in dirnames if not should_exclude_dir(d)]

        for filename in filenames:
            if should_exclude_file(filename, dirpath):
                continue
            full = Path(dirpath) / filename
            files.append(full)
    return sorted(files)


def create_zip(root: Path, output: Path) -> tuple[Path, int, int]:
    files = collect_files(root)
    output.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in files:
            arcname = file_path.relative_to(root).as_posix()
            zf.write(file_path, arcname)

    total_bytes = output.stat().st_size
    return output, len(files), total_bytes


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def main() -> int:
    parser = argparse.ArgumentParser(description="Package HomeLab DNS Manager for server deploy")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output zip path (default: dist/homelab-dns-manager-YYYYMMDD-HHMMSS.zip)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Project root (default: parent of scripts/)",
    )
    args = parser.parse_args()

    root = (args.root or Path(__file__).resolve().parent.parent).resolve()
    if not (root / "docker-compose.yml").is_file():
        print(f"Error: {root} does not look like the project root (no docker-compose.yml)", file=sys.stderr)
        return 1

    if args.output:
        output = args.output.resolve()
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        output = root / "dist" / f"{PROJECT_NAME}-{stamp}.zip"

    print(f"Packaging from: {root}")
    print("Excluding: .venv, node_modules, .env, data/, frontend/dist/, __pycache__, .git")
    print()

    out_path, file_count, size = create_zip(root, output)

    print(f"Created: {out_path}")
    print(f"Files:   {file_count}")
    print(f"Size:    {human_size(size)}")
    print()
    print("Upload to your server, then:")
    print()
    print("  sudo mkdir -p /opt/homelab-dns-manager")
    print("  sudo chown $USER:$USER /opt/homelab-dns-manager")
    print(f"  unzip {out_path.name} -d /opt/homelab-dns-manager")
    print("  cd /opt/homelab-dns-manager")
    print("  cp .env.example .env && chmod 600 .env && nano .env")
    print("  docker compose up -d --build")
    print()
    print("Docker installs Python + npm dependencies inside the image — no venv or node_modules on the server.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
