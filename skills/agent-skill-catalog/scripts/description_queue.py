#!/usr/bin/env python3
"""Prepare and apply resumable Agent-owned description batches."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import time
from http.client import HTTPException, IncompleteRead
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_catalog import (  # noqa: E402
    DEFAULT_CONFIG,
    atomic_write_text,
    curation_value,
    description_review,
    load_config,
    read_json,
    root_specs,
    stable_id,
)
from github_preview import github_repository, open_allowed  # noqa: E402


DEFAULT_BATCH_SIZE = 12
MAX_BATCH_SIZE = 50
MAX_SOURCE_CHARS = 5000
MAX_README_BYTES = 256 * 1024
MAX_README_CHARS = 5000
README_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
README_HOSTS = {"raw.githubusercontent.com"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_object(path: Path, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = read_json(path, fallback or {}, strict=True)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return payload


def output_paths(output_dir: Path) -> tuple[Path, Path]:
    queue_path = output_dir / "description-enrichment.json"
    curation_path = output_dir / "catalog-curation.json"
    if not queue_path.is_file():
        raise ValueError(f"Description queue does not exist: {queue_path}")
    if not curation_path.is_file():
        raise ValueError(f"Catalog curation does not exist: {curation_path}")
    return queue_path, curation_path


def pending_items(queue: dict[str, Any], curation: dict[str, Any]) -> list[dict[str, Any]]:
    raw_items = queue.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("description-enrichment.json items must be an array")
    overrides = curation.get("description_overrides")
    if not isinstance(overrides, dict):
        raise ValueError("catalog-curation.json description_overrides must be an object")
    pending: list[dict[str, Any]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        key = str(item.get("curation_key") or item.get("id") or "").strip()
        name = str(item.get("name") or "")
        relative_path = str(item.get("relative_path") or "")
        if not key:
            raise ValueError(f"Description queue item has no curation key: {name or relative_path}")
        if curation_value(overrides, name, relative_path, key):
            continue
        item["curation_key"] = key
        pending.append(item)
    return pending


def resolve_source(item: dict[str, Any], specs: list[dict[str, str]]) -> Path | None:
    relative_path = str(item.get("relative_path") or "")
    item_id = str(item.get("id") or "")
    candidates: list[Path] = []
    for spec in specs:
        root = Path(spec["path"])
        root_resolved = root.resolve()
        candidate = (root_resolved / Path(relative_path)).resolve()
        if not candidate.is_relative_to(root_resolved):
            continue
        if not candidate.is_file():
            continue
        if item_id and stable_id(root, relative_path) == item_id:
            return candidate
        candidates.append(candidate)
    return candidates[0] if len(candidates) == 1 else None


def bounded_excerpt(text: str, max_chars: int) -> tuple[str, bool]:
    normalized = text.replace("\x00", "").strip()
    return normalized[:max_chars], len(normalized) > max_chars


def read_source_evidence(item: dict[str, Any], specs: list[dict[str, str]]) -> dict[str, Any]:
    path = resolve_source(item, specs)
    if path is None:
        return {"status": "missing-evidence", "excerpt": "", "truncated": False}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"status": "missing-evidence", "excerpt": "", "truncated": False}
    excerpt, truncated = bounded_excerpt(text, MAX_SOURCE_CHARS)
    return {"status": "local-skill", "excerpt": excerpt, "truncated": truncated}


def clean_markdown_excerpt(text: str) -> tuple[str, bool]:
    cleaned = re.sub(r"```[\s\S]*?```", " ", text)
    cleaned = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", cleaned)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return bounded_excerpt(cleaned, MAX_README_CHARS)


def readme_cache_path(cache_dir: Path, repository_url: str) -> Path:
    digest = hashlib.sha256(repository_url.rstrip("/").encode("utf-8")).hexdigest()[:20]
    return cache_dir / f"{digest}.json"


def cached_readme(cache_dir: Path, repository_url: str) -> dict[str, Any] | None:
    path = readme_cache_path(cache_dir, repository_url)
    try:
        if time.time() - path.stat().st_mtime > README_CACHE_TTL_SECONDS:
            return None
        payload = load_object(path)
    except (OSError, ValueError):
        return None
    if payload.get("repository_url") != repository_url:
        return None
    return payload


def fetch_github_readme(repository_url: str, cache_dir: Path, timeout: int = 8) -> dict[str, Any]:
    owner, repository = github_repository(repository_url)
    if not owner or not repository:
        return {"status": "missing-evidence", "repository_url": repository_url, "excerpt": "", "truncated": False}
    cached = cached_readme(cache_dir, repository_url)
    if cached is not None:
        cached["source"] = "github-readme-cache"
        return cached

    result: dict[str, Any] = {
        "status": "missing-evidence",
        "repository_url": repository_url,
        "excerpt": "",
        "truncated": False,
        "source": "github-raw",
    }
    for filename in ("README.md", "readme.md", "README.rst", "README.txt"):
        url = f"https://raw.githubusercontent.com/{owner}/{repository}/HEAD/{filename}"
        request = Request(url, headers={"Accept": "text/plain", "User-Agent": "agent-skill-catalog/0.3"})
        try:
            with open_allowed(request, timeout, README_HOSTS) as response:
                try:
                    body = response.read(MAX_README_BYTES + 1)
                except IncompleteRead as exc:
                    body = exc.partial
        except (OSError, HTTPError, HTTPException):
            continue
        if len(body) > MAX_README_BYTES:
            result["status"] = "oversize"
            break
        text = body.decode("utf-8", errors="replace")
        excerpt, truncated = clean_markdown_excerpt(text)
        if not excerpt:
            continue
        result.update(
            {
                "status": "github-readme",
                "source_url": url,
                "excerpt": excerpt,
                "truncated": truncated,
            }
        )
        break

    cache_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(readme_cache_path(cache_dir, repository_url), json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def prepare_batch(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).expanduser().resolve()
    queue_path, curation_path = output_paths(output_dir)
    queue = load_object(queue_path)
    curation = load_object(curation_path)
    config_path = Path(args.config).expanduser().resolve() if args.config else DEFAULT_CONFIG
    config = load_config(config_path)
    specs = root_specs(config, args.root or None)
    pending = pending_items(queue, curation)
    batch_size = max(1, min(int(args.batch_size), MAX_BATCH_SIZE))
    selected = pending[:batch_size]
    items: list[dict[str, Any]] = []
    readme_cache = output_dir / "github-readme-cache"
    for item in selected:
        github_url = str(item.get("github_url") or "")
        github_evidence = (
            {"status": "disabled", "repository_url": github_url, "excerpt": "", "truncated": False}
            if args.no_github_readmes
            else fetch_github_readme(github_url, readme_cache) if github_url else {
                "status": "missing-evidence",
                "repository_url": "",
                "excerpt": "",
                "truncated": False,
            }
        )
        items.append(
            {
                "curation_key": item["curation_key"],
                "name": item.get("name"),
                "source": item.get("source"),
                "relative_path": item.get("relative_path"),
                "current_description": item.get("current_description"),
                "reasons": item.get("reasons", []),
                "local_skill": read_source_evidence(item, specs),
                "github": github_evidence,
            }
        )
    batch_path = Path(args.output).expanduser().resolve() if args.output else output_dir / "description-batch.json"
    payload = {
        "schema_version": "1.0",
        "generated_at": utc_now(),
        "pending_before": len(pending),
        "batch_count": len(items),
        "pending_after_batch": max(0, len(pending) - len(items)),
        "items": items,
        "response_contract": {
            "path": str((output_dir / "description-batch.responses.json").name),
            "shape": {"items": [{"curation_key": "copy from batch", "description": "natural Chinese description"}]},
            "requirements": [
                "Use only the supplied local Skill and GitHub README evidence.",
                "Write natural Chinese covering purpose, typical use, and important output or limits.",
                "Do not invent unsupported capabilities; keep missing evidence explicit.",
            ],
        },
    }
    atomic_write_text(batch_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(f"Prepared {len(items)} description item(s); {payload['pending_after_batch']} remain after this batch.")
    print(batch_path)
    return 0


def apply_batch(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).expanduser().resolve()
    queue_path, curation_path = output_paths(output_dir)
    queue = load_object(queue_path)
    curation = load_object(curation_path)
    responses = load_object(Path(args.input).expanduser().resolve())
    raw_items = responses.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("Response file must contain a non-empty items array")

    queue_items = queue.get("items") if isinstance(queue.get("items"), list) else []
    allowed = {
        str(item.get("curation_key") or item.get("id") or ""): item
        for item in queue_items
        if isinstance(item, dict)
    }
    updates: dict[str, str] = {}
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise ValueError("Every response item must be an object")
        key = str(raw.get("curation_key") or "").strip()
        description = re.sub(r"\s+", " ", str(raw.get("description") or "")).strip()
        if not key or key not in allowed:
            raise ValueError(f"Response curation_key is not in the current queue: {key or '<empty>'}")
        if key in updates:
            raise ValueError(f"Duplicate response curation_key: {key}")
        review = description_review(description, "curation", str(queue.get("locale") or "zh-CN"))
        if review["needed"]:
            raise ValueError(f"Description for {key} failed review: {', '.join(review['reasons'])}")
        updates[key] = description

    overrides = curation.setdefault("description_overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError("catalog-curation.json description_overrides must be an object")
    overrides.update(updates)
    atomic_write_text(curation_path, json.dumps(curation, ensure_ascii=False, indent=2) + "\n")
    remaining = pending_items(queue, curation)
    print(f"Applied {len(updates)} description(s); {len(remaining)} queued item(s) remain before rebuild.")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Prepare and apply resumable Agent-owned description batches.")
    subparsers = result.add_subparsers(dest="command", required=True)

    next_parser = subparsers.add_parser("next", help="Prepare the next evidence batch")
    next_parser.add_argument("--output-dir", required=True)
    next_parser.add_argument("--config", help="Use the same catalog config as the builder")
    next_parser.add_argument("--root", action="append", help="Use the same root arguments as the builder")
    next_parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    next_parser.add_argument("--output", help="Batch JSON path; defaults inside the catalog output directory")
    next_parser.add_argument("--no-github-readmes", action="store_true", help="Do not retrieve public GitHub README evidence")
    next_parser.set_defaults(handler=prepare_batch)

    apply_parser = subparsers.add_parser("apply", help="Validate and merge Agent-written Chinese descriptions")
    apply_parser.add_argument("--output-dir", required=True)
    apply_parser.add_argument("--input", required=True, help="JSON response file matching the batch response contract")
    apply_parser.set_defaults(handler=apply_batch)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        return int(args.handler(args))
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"Description queue failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
