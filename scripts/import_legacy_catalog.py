#!/usr/bin/env python3
"""Convert a legacy catalog data file into Agent Skill Catalog curation."""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable


CJK = re.compile(r"[\u3400-\u9fff]")
GITHUB = re.compile(r"^https?://(?:www\.)?github\.com/[^\s]+$", re.I)


def legacy_payload(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    marker = "window.SKILL_ATLAS_DATA"
    if not text.startswith(marker) or "=" not in text:
        raise ValueError("Expected a legacy window.SKILL_ATLAS_DATA assignment")
    raw = text.split("=", 1)[1].strip().rstrip(";").strip()
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Legacy catalog payload must be a JSON object")
    return payload


def legacy_records(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for item in payload.get("items", []):
        if isinstance(item, dict):
            yield item
    for plugin in payload.get("plugins", []):
        if not isinstance(plugin, dict):
            continue
        yield plugin
        for item in plugin.get("skills", []):
            if isinstance(item, dict):
                yield item


def curation_from_payload(payload: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    descriptions: dict[str, str] = {}
    github: dict[str, str] = {}
    images: dict[str, str] = {}
    for record in legacy_records(payload):
        name = str(record.get("name") or "").strip()
        description = str(record.get("description") or "").strip()
        github_url = str(record.get("githubUrl") or "").strip()
        preview = record.get("preview") if isinstance(record.get("preview"), dict) else {}
        preview_url = str(preview.get("url") or "").strip()
        if name and description and CJK.search(description):
            descriptions.setdefault(name, description)
        if name and GITHUB.match(github_url) and "/sponsors/" not in github_url:
            github.setdefault(name, github_url.rstrip("/"))
        if name and preview_url and not re.match(r"^https?://", preview_url, re.I):
            preview_path = (base_dir / preview_url).resolve()
            if preview_path.is_file():
                images.setdefault(name, str(preview_path))
    return {
        "schema_version": "1.0",
        "description_overrides": descriptions,
        "github_overrides": github,
        "image_overrides": images,
        "family_overrides": {},
    }


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Chinese descriptions and observed GitHub URLs from a legacy catalog data file.")
    parser.add_argument("--legacy-catalog-data", required=True, help="Path to legacy catalog-data.js")
    parser.add_argument("--output", required=True, help="Standard curation JSON to write")
    args = parser.parse_args()
    payload = legacy_payload(Path(args.legacy_catalog_data).resolve())
    legacy_path = Path(args.legacy_catalog_data).resolve()
    curation = curation_from_payload(payload, legacy_path.parent)
    output = Path(args.output).resolve()
    atomic_write(output, json.dumps(curation, ensure_ascii=False, indent=2) + "\n")
    print(
        f"Imported {len(curation['description_overrides'])} Chinese descriptions and "
        f"{len(curation['github_overrides'])} GitHub URLs into {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
