#!/usr/bin/env python3
"""Merge install/.env.example into .env without overwriting existing values."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def parse_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = KEY_RE.match(stripped)
        if match:
            values[match.group(1)] = match.group(2)
    return values


def merge_env(example_path: Path, env_path: Path, dry_run: bool = False) -> list[str]:
    example_values = parse_values(example_path)
    current_values = parse_values(env_path)

    if env_path.exists() and not dry_run:
        backup = env_path.with_suffix(env_path.suffix + ".bak")
        backup.write_text(env_path.read_text(encoding="utf-8"), encoding="utf-8")

    merged = dict(example_values)
    merged.update(current_values)

    added = sorted(set(example_values) - set(current_values))
    kept = sorted(set(current_values) & set(example_values))
    extra = sorted(set(current_values) - set(example_values))

    lines: list[str] = []
    for raw in example_path.read_text(encoding="utf-8").splitlines():
        match = KEY_RE.match(raw.strip())
        if match:
            lines.append(f"{match.group(1)}={merged[match.group(1)]}")
        else:
            lines.append(raw)
    for key in extra:
        lines.append(f"{key}={current_values[key]}")

    output = "\n".join(lines).rstrip() + "\n"
    report = []
    report.append(f"Added keys: {', '.join(added)}" if added else "No new keys to add.")
    if extra:
        report.append(f"Kept extra keys (not in example): {', '.join(extra)}")
    report.append(f"Preserved {len(kept)} existing value(s).")

    if not dry_run:
        env_path.write_text(output, encoding="utf-8")
        report.append(f"Wrote {env_path}")
        if env_path.exists():
            report.append(f"Backup: {env_path}.bak")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge .env.example into .env")
    parser.add_argument("--example", type=Path, default=Path(".env.example"))
    parser.add_argument("--env", type=Path, default=Path(".env"))
    parser.add_argument("-n", "--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.example.exists():
        raise SystemExit(f"Missing {args.example}")
    for line in merge_env(args.example, args.env, dry_run=args.dry_run):
        print(line)


if __name__ == "__main__":
    main()
