#!/usr/bin/env python3
"""Validate the repository and its GitHub-discoverable Agent Skill."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


NAME = "agent-skill-catalog"
SKILL_RELATIVE = Path("skills") / NAME
REQUIRED_SKILL_FILES = (
    "SKILL.md",
    "LICENSE",
    "requirements.txt",
    "manifest.json",
    "agents/interface.yaml",
    "agents/openai.yaml",
    "scripts/build_catalog.py",
    "scripts/github_preview.py",
    "scripts/serve_catalog.py",
    "scripts/import_legacy_catalog.py",
    "references/catalog-config.json",
    "references/catalog-config.windows.example.json",
    "references/catalog-config.posix.example.json",
    "security/network_policy.json",
    "security/permission_policy.json",
    "reports/output_quality_scorecard.md",
    "reports/security_trust_report.md",
)
PORTABLE_REPORTS = {
    "reports/architecture_maintainability.md",
    "reports/compiled_targets.md",
    "reports/conformance_matrix.md",
    "reports/output_quality_scorecard.md",
    "reports/python_compatibility.md",
    "reports/review_annotations.md",
    "reports/review_waivers.md",
    "reports/runtime_permission_probes.md",
    "reports/security_trust_report.md",
}
PRIVATE_PATH = re.compile(r"(?:[A-Za-z]:\\(?:Users|Object)\\|/(?:Users|home)/)", re.I)


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


def frontmatter_text(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\r?\n([\s\S]*?)\r?\n---(?:\r?\n|\Z)", content)
    return match.group(1) if match else ""


def text_files(root: Path):
    allowed = {".md", ".json", ".py", ".yaml", ".yml", ".txt"}
    ignored = {".git", "dist", "reports", "__pycache__", ".pytest_cache", ".venv", "venv"}
    for path in root.rglob("*"):
        if not path.is_file() or any(part in ignored for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() in allowed:
            yield path


def portable_report_files(skill: Path):
    for relative in sorted(PORTABLE_REPORTS):
        path = skill / relative
        if path.is_file():
            yield path


def validate(root: Path) -> list[str]:
    failures: list[str] = []
    skill = root / SKILL_RELATIVE

    if not skill.is_dir():
        failures.append(f"Missing GitHub-discoverable skill directory: {SKILL_RELATIVE}")
        return failures

    if skill.name != NAME:
        failures.append(f"Skill directory must be named {NAME}")
    for relative in REQUIRED_SKILL_FILES:
        if not (skill / relative).is_file():
            failures.append(f"Missing required Skill file: {SKILL_RELATIVE / relative}")

    skill_md = skill / "SKILL.md"
    if skill_md.is_file():
        fields = frontmatter(skill_md)
        if fields.get("name") != NAME:
            failures.append(f"SKILL.md name must be {NAME}")
        if not fields.get("description"):
            failures.append("SKILL.md requires a description")
        if fields.get("license") != "MIT":
            failures.append("SKILL.md must declare license: MIT")
        if re.search(r"^\s*(?:metadata\.)?github-[A-Za-z0-9_-]+\s*:", frontmatter_text(skill_md), re.MULTILINE):
            failures.append("Published SKILL.md must not contain metadata.github-* install fields")
    manifest = skill / "manifest.json"
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
            if data.get("license") != "MIT":
                failures.append("manifest.json license must be MIT")

    config = skill / "references/catalog-config.json"
    if config.is_file():
        try:
            data = json.loads(config.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"Invalid default config: {exc}")
        else:
            if data.get("roots") != []:
                failures.append("Default catalog config must not contain machine-specific roots")

    interface = skill / "agents/interface.yaml"
    if interface.is_file() and 'display_name: "Agent Skill Catalog"' not in interface.read_text(encoding="utf-8"):
        failures.append("agents/interface.yaml must use the public display name")

    openai = skill / "agents/openai.yaml"
    if openai.is_file():
        content = openai.read_text(encoding="utf-8")
        if 'display_name: "Agent Skill Catalog"' not in content:
            failures.append("agents/openai.yaml must use the public display name")
        short = re.search(r"^\s+short_description:\s*\"(.*)\"$", content, re.MULTILINE)
        if not short or not 25 <= len(short.group(1)) <= 64:
            failures.append("agents/openai.yaml short_description must be 25-64 characters")
        if "$agent-skill-catalog" not in content:
            failures.append("agents/openai.yaml default_prompt must mention $agent-skill-catalog")

    for forbidden in ("catalog.json", "index.html", "catalog-data.js"):
        if (skill / forbidden).exists():
            failures.append(f"Generated output must not be committed inside the Skill: {forbidden}")

    for path in [*text_files(root), *portable_report_files(skill)]:
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if PRIVATE_PATH.search(content):
            failures.append(f"Machine-specific absolute path found: {path.relative_to(root)}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the GitHub Agent Skill repository.")
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
