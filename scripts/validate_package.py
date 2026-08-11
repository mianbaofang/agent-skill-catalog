#!/usr/bin/env python3
"""Validate the portable Agent Skill Catalog source package."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


NAME = "agent-skill-catalog"
REQUIRED_FILES = (
    "SKILL.md",
    "README.md",
    "LICENSE",
    "VERSION",
    "manifest.json",
    "agents/interface.yaml",
    "scripts/build_catalog.py",
    "scripts/serve_catalog.py",
    "scripts/import_legacy_catalog.py",
    "references/catalog-config.json",
    "references/catalog-config.windows.example.json",
    "references/catalog-config.posix.example.json",
    "tests/test_build_catalog.py",
)
FORBIDDEN_ROOT_OUTPUTS = ("catalog.json", "index.html", "catalog-data.js")
PRIVATE_PATH = re.compile(r"(?:[A-Za-z]:\\(?:Users|home)\\|/(?:Users|home)/)", re.I)


def frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    values: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if match:
            values[match.group(1)] = match.group(2).strip().strip('"')
    return values


def text_files(root: Path):
    allowed = {".md", ".json", ".py", ".yaml", ".yml", ".txt"}
    ignored = {".git", "dist", "reports", "__pycache__", ".pytest_cache", ".venv", "venv"}
    for path in root.rglob("*"):
        if not path.is_file() or any(part in ignored for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() in allowed:
            yield path


def validate(root: Path) -> list[str]:
    failures: list[str] = []
    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            failures.append(f"Missing required file: {relative}")

    skill = root / "SKILL.md"
    if skill.is_file():
        fields = frontmatter(skill)
        if fields.get("name") != NAME:
            failures.append(f"SKILL.md name must be {NAME}")
        if not fields.get("description"):
            failures.append("SKILL.md requires a description")

    manifest = root / "manifest.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"Invalid manifest.json: {exc}")
        else:
            for field in ("name", "version", "owner", "updated_at"):
                if not data.get(field):
                    failures.append(f"manifest.json missing {field}")
            if data.get("name") != NAME:
                failures.append(f"manifest.json name must be {NAME}")

    config = root / "references/catalog-config.json"
    if config.is_file():
        try:
            data = json.loads(config.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"Invalid default config: {exc}")
        else:
            if data.get("roots") != []:
                failures.append("Default catalog config must not contain machine-specific roots")

    interface = root / "agents/interface.yaml"
    if interface.is_file() and 'display_name: "Agent Skill Catalog"' not in interface.read_text(encoding="utf-8"):
        failures.append("agents/interface.yaml must use the public display name")

    for output in FORBIDDEN_ROOT_OUTPUTS:
        if (root / output).exists():
            failures.append(f"Local generated output must not be committed: {output}")

    for path in text_files(root):
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if PRIVATE_PATH.search(content):
            failures.append(f"Machine-specific absolute path found: {path.relative_to(root)}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Agent Skill Catalog for public packaging.")
    parser.add_argument("source_dir", nargs="?", default=".")
    args = parser.parse_args()
    root = Path(args.source_dir).resolve()
    failures = validate(root)
    if failures:
        print("Package validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"Package validation passed: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
