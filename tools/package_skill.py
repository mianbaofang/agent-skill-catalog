#!/usr/bin/env python3
"""Create an optional deterministic ZIP of the installable Skill directory."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validate_package import PRIVATE_PATH, SKILL_RELATIVE, validate


PACKAGE_NAME = "agent-skill-catalog"
EXCLUDED_DIRS = {
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "build",
    "dist",
    "node_modules",
    "evals",
    "reports",
}
EXCLUDED_FILES = {"catalog.json", "index.html", "catalog-data.js", ".env"}
EXCLUDED_SUFFIXES = {".log", ".pyc", ".pyo", ".tmp"}


def package_paths(skill_root: Path):
    for path in sorted(skill_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(skill_root)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if relative.name in EXCLUDED_FILES or relative.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        yield path, relative


def validate_package_text(path: Path, relative: Path) -> None:
    if path.suffix.lower() not in {".md", ".json", ".py", ".yaml", ".yml", ".txt"}:
        return
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if PRIVATE_PATH.search(content):
        raise ValueError(f"Machine-specific absolute path found in packaged file: {relative.as_posix()}")


def source_timestamp() -> tuple[int, int, int, int, int, int]:
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "315532800"))
    import datetime as dt

    value = dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc)
    return value.year, value.month, value.day, value.hour, value.minute, value.second


def write_package(skill_root: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    timestamp = source_timestamp()
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, relative in package_paths(skill_root):
            validate_package_text(path, relative)
            info = zipfile.ZipInfo(f"{PACKAGE_NAME}/{relative.as_posix()}", date_time=timestamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    return hashlib.sha256(destination.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Package the installable Agent Skill without local data.")
    parser.add_argument("source_dir", nargs="?", default=".")
    parser.add_argument("--output", default="dist/agent-skill-catalog-skill.zip")
    args = parser.parse_args()
    root = Path(args.source_dir).resolve()
    failures = validate(root)
    if failures:
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    skill_root = root / SKILL_RELATIVE
    destination = Path(args.output)
    if not destination.is_absolute():
        destination = (root / destination).resolve()
    try:
        digest = write_package(skill_root, destination)
    except ValueError as exc:
        print(f"- {exc}", file=sys.stderr)
        return 1
    checksum = destination.with_suffix(destination.suffix + ".sha256")
    checksum.write_text(f"{digest}  {destination.name}\n", encoding="ascii")
    print(f"Created {destination}")
    print(f"SHA256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
