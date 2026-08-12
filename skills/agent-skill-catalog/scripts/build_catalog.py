#!/usr/bin/env python3
"""Build a deterministic Agent Skill Catalog and HTML view."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
DEFAULT_CONFIG = PACKAGE_ROOT / "references" / "catalog-config.json"
DEFAULT_SKIP_DIRS = {
    ".git", ".agents", ".codex", ".venv", "venv", "node_modules",
    "__pycache__", "tests", "test", "fixtures", "examples", "vendor",
    "site-packages", ".previews",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
ASCII_WORD = re.compile(r"[a-z0-9]")
GITHUB_URL = re.compile(r"https?://(?:www\.)?github\.com/[^\s'\")<>]+", re.I)
GITHUB_SSH_URL = re.compile(r"git@github\.com:([^\s'\")<>]+)", re.I)
SVG_NAMESPACE = "http:" + "//www.w3.org/2000/svg"
COVER_STYLES = {
    "visual": ("#164e63", "#f97316"),
    "video": ("#312e81", "#fbbf24"),
    "audio": ("#7c2d12", "#fb923c"),
    "content": ("#3f6212", "#facc15"),
    "internet_search": ("#075985", "#38bdf8"),
    "learning": ("#1d4ed8", "#93c5fd"),
    "securities": ("#14532d", "#86efac"),
    "data": ("#0f766e", "#5eead4"),
    "development": ("#1e3a8a", "#93c5fd"),
    "productivity": ("#713f12", "#fde68a"),
    "specialist": ("#7e1d44", "#f9a8d4"),
    "other": ("#334155", "#cbd5e1"),
}
FAVICON_SVG = f"""<svg xmlns="{SVG_NAMESPACE}" viewBox="0 0 64 64">
<rect width="64" height="64" rx="12" fill="#0f494d"/>
<path d="M16 20h32v8H16zm0 16h22v8H16z" fill="#fff"/>
</svg>
"""

from github_preview import (
    AllowedRedirectHandler,
    github_cache_key,
    github_preview_image,
    image_data_uri,
    image_data_uri_from_bytes,
)


def read_json(path: Path, fallback: Any, strict: bool = False) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fallback
    except (OSError, json.JSONDecodeError) as exc:
        if strict:
            raise ValueError(f"Cannot read JSON: {path}: {exc}") from exc
        return fallback


def expand_path(value: str) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(str(value)))
    # Support Windows-style %VAR% even when the host process uses a POSIX shell.
    expanded = re.sub(r"%([^%]+)%", lambda m: os.environ.get(m.group(1), m.group(0)), expanded)
    return Path(expanded).expanduser()


def load_config(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Config does not exist: {path}")
    payload = read_json(path, {}, strict=True)
    if not isinstance(payload, dict):
        raise ValueError(f"Config must be a JSON object: {path}")
    payload.setdefault("roots", [])
    if not isinstance(payload["roots"], list):
        raise ValueError("roots must be an array")
    payload.setdefault("categories", {})
    payload.setdefault("category_overrides", {})
    payload.setdefault("category_tie_break", list(payload["categories"]) or ["other"])
    payload.setdefault("classification", {})
    if not isinstance(payload["classification"], dict):
        raise ValueError("classification must be a JSON object")
    payload["classification"].setdefault("small_margin", 1.0)
    payload["classification"].setdefault("low_confidence", 0.5)
    payload.setdefault("locale", "zh-CN")
    payload.setdefault("include_absolute_paths", False)
    payload.setdefault("curation", {})
    if not isinstance(payload["curation"], dict):
        raise ValueError("curation must be a JSON object")
    payload["curation"].setdefault("description_overrides", {})
    payload["curation"].setdefault("category_overrides", [])
    payload["curation"].setdefault("github_overrides", {})
    payload["curation"].setdefault("family_overrides", {})
    payload["curation"].setdefault("image_overrides", {})
    payload.setdefault("scan", {})
    payload["scan"].setdefault("skip_dirs", sorted(DEFAULT_SKIP_DIRS))
    payload["scan"].setdefault("max_depth", 12)
    payload.setdefault("image", {})
    payload["image"].setdefault("frontmatter_keys", ["preview_image", "image", "cover", "preview"])
    payload["image"].setdefault("sidecar_names", [])
    payload["image"].setdefault("allow_remote_metadata", True)
    payload["image"].setdefault("category_cover_fallback", True)
    payload["image"].setdefault("github_repository_previews", True)
    payload["image"].setdefault("github_image_cache_ttl_hours", 168)
    payload["image"].setdefault("github_request_timeout_seconds", 6)
    payload["image"].setdefault("github_max_page_bytes", 1024 * 1024)
    payload["image"].setdefault("github_max_download_bytes", 2 * 1024 * 1024)
    payload["image"].setdefault("github_image_candidate_limit", 3)
    payload["image"].setdefault("github_fetch_workers", 8)
    invalid = validate_category_overrides(payload)
    if invalid:
        details = ", ".join(f"{entry['id']}={entry['category']}" for entry in invalid)
        raise ValueError(f"Invalid category override(s): {details}")
    payload["invalid_category_overrides"] = []
    return payload


def _override_entries(overrides: Any) -> List[Dict[str, Any]]:
    """Normalize legacy name maps and scoped override lists into one shape."""
    entries: List[Dict[str, Any]] = []
    if isinstance(overrides, list):
        for index, value in enumerate(overrides):
            if isinstance(value, dict):
                entry = dict(value)
                entry.setdefault("id", f"override[{index}]")
                entries.append(entry)
        return entries
    if isinstance(overrides, dict):
        for key, value in overrides.items():
            if isinstance(value, dict):
                entry = dict(value)
                entry.setdefault("name", key)
                entry.setdefault("id", str(key))
            else:
                entry = {"name": key, "category": value, "id": str(key)}
            entries.append(entry)
    return entries


def validate_category_overrides(config: Dict[str, Any]) -> List[Dict[str, str]]:
    categories = config.get("categories") if isinstance(config.get("categories"), dict) else {}
    invalid: List[Dict[str, str]] = []
    raw_category_overrides = config.get("category_overrides")
    if raw_category_overrides is not None and not isinstance(raw_category_overrides, (dict, list)):
        invalid.append({"id": "category_overrides", "category": "<invalid shape>"})
    for index, entry in enumerate(_override_entries(raw_category_overrides)):
        entry_id = str(entry.get("id") or entry.get("name") or f"override[{index}]")
        category = str(entry.get("category") or "").strip()
        if category and category not in categories:
            invalid.append({"id": entry_id, "category": category})
        selectors = [entry.get("root"), entry.get("path"), entry.get("relative_path"), entry.get("name")]
        if any(value is not None and not isinstance(value, str) for value in selectors):
            invalid.append({"id": entry_id, "category": "<invalid scope>"})
        if entry.get("path") and entry.get("relative_path"):
            path_value = normalize_for_match(str(entry.get("path")))
            relative_value = normalize_for_match(str(entry.get("relative_path")))
            if path_value != relative_value:
                invalid.append({"id": entry_id, "category": "<conflicting scope>"})
        if not any(str(value or "").strip() for value in selectors):
            invalid.append({"id": entry_id, "category": "<missing scope>"})
    curation = config.get("curation") if isinstance(config.get("curation"), dict) else {}
    family_overrides = curation.get("family_overrides") if isinstance(curation.get("family_overrides"), dict) else {}
    for key, entry in family_overrides.items():
        if not isinstance(entry, dict):
            invalid.append({"id": f"family:{key}", "category": "<invalid shape>"})
            continue
        category = str(entry.get("category") or "").strip()
        if category and category not in categories:
            invalid.append({"id": f"family:{key}", "category": category})
        if not str(key or "").strip():
            invalid.append({"id": "family:<empty>", "category": "<missing selector>"})
    return invalid


def load_curation(paths: Optional[Any], config: Dict[str, Any]) -> None:
    if not paths:
        return
    target = config.setdefault("curation", {})
    values = paths if isinstance(paths, list) else [paths]
    for path in values:
        curation_path = Path(path).resolve()
        payload = read_json(curation_path, {}, strict=True)
        if not isinstance(payload, dict):
            raise ValueError(f"Curation must be a JSON object: {curation_path}")
        for key in ("description_overrides", "category_overrides", "github_overrides", "family_overrides", "image_overrides"):
            value = payload.get(key, {})
            if value:
                if not isinstance(value, (dict, list)) or (key != "category_overrides" and not isinstance(value, dict)):
                    raise ValueError(f"Curation field must be an object: {key}")
                if key == "category_overrides":
                    existing = target.setdefault(key, [])
                    if isinstance(value, list):
                        existing.extend(value)
                    else:
                        existing.extend(_override_entries(value))
                else:
                    target.setdefault(key, {}).update(value)

        # Accept the two simple formats used by earlier local catalog versions:
        # {"skills": {"name": "Chinese description"}} and a flat name map.
        legacy_skills = payload.get("skills")
        if legacy_skills:
            if not isinstance(legacy_skills, dict):
                raise ValueError(f"Legacy skills must be an object: {curation_path}")
            target.setdefault("description_overrides", {}).update(legacy_skills)
        if not any(key in payload for key in ("description_overrides", "category_overrides", "github_overrides", "family_overrides", "image_overrides", "skills")):
            if not all(isinstance(value, str) for value in payload.values()):
                raise ValueError(f"Flat legacy curation must map names to strings: {curation_path}")
            target.setdefault("description_overrides", {}).update(payload)
    invalid = validate_category_overrides(config)
    if invalid:
        details = ", ".join(f"{entry['id']}={entry['category']}" for entry in invalid)
        raise ValueError(f"Invalid category override(s): {details}")


def default_curation_path(output_dir: Path) -> Path:
    return output_dir / "catalog-curation.json"


def ensure_output_curation(config: Dict[str, Any], output_dir: Path) -> Path:
    """Merge an output-owned curation file last so manual page edits always win."""
    path = default_curation_path(output_dir)
    if not path.exists():
        atomic_write_text(
            path,
            json.dumps(
                {
                    "description_overrides": {},
                    "category_overrides": [],
                    "github_overrides": {},
                    "family_overrides": {},
                    "image_overrides": {},
                },
                ensure_ascii=False,
                indent=2,
            ) + "\n",
        )
    load_curation([str(path)], config)
    return path


def parse_frontmatter(text: str) -> Dict[str, Any]:
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields: Dict[str, Any] = {}
    index = 1
    while index < len(lines):
        line = lines[index]
        if line.strip() == "---":
            break
        match = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", line)
        if not match:
            index += 1
            continue
        key, value = match.groups()
        value = value.strip()
        if value in {">", ">-", "|", "|-"}:
            folded = value.startswith(">")
            block_lines: List[str] = []
            index += 1
            while index < len(lines):
                child = lines[index]
                if child.strip() == "---":
                    break
                if child and not child[0].isspace():
                    break
                block_lines.append(child.strip())
                index += 1
            fields[key] = (" " if folded else "\n").join(part for part in block_lines if part).strip()
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        fields[key] = value
        index += 1
    return fields


def body_description(text: str) -> str:
    body = re.sub(r"^---[\s\S]*?---\s*", "", text, count=1)
    for line in body.splitlines():
        candidate = line.strip()
        if candidate and not candidate.startswith("#") and not candidate.startswith("-"):
            return re.sub(r"^>\s*", "", candidate)
    return "Open the skill instructions to learn its use case and procedure."


def skill_name(path: Path, frontmatter: Dict[str, Any]) -> str:
    value = str(frontmatter.get("name") or "").strip()
    return value or path.parent.name


def description_for(text: str, frontmatter: Dict[str, Any]) -> str:
    value = str(frontmatter.get("description") or "").strip()
    return value or body_description(text)


def curation_value(mapping: Any, name: str, relative_path: str) -> str:
    if not isinstance(mapping, dict):
        return ""
    normalized_name = normalize_for_match(name)
    normalized_path = normalize_for_match(relative_path)
    for key in (relative_path, normalized_path, name, normalized_name):
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            localized = value.get("zh-CN") or value.get("description") or value.get("value")
            if isinstance(localized, str) and localized.strip():
                return localized.strip()
    return ""


def github_from_values(values: Iterable[Any]) -> str:
    for value in values:
        if isinstance(value, dict):
            nested = github_from_values(value.values())
            if nested:
                return nested
            continue
        match = GITHUB_URL.search(str(value or ""))
        if match:
            return match.group(0).rstrip(".,;:)]}")
        ssh_match = GITHUB_SSH_URL.search(str(value or ""))
        if ssh_match:
            return "https://github.com/" + ssh_match.group(1).rstrip(".,;:)]}").removesuffix(".git")
    return ""


def github_from_git_config(skill_path: Path, root: Path) -> str:
    current = skill_path.parent
    resolved_root = root.resolve()
    for _ in range(8):
        try:
            current.resolve().relative_to(resolved_root)
        except ValueError:
            break
        config_path = current / ".git" / "config"
        if config_path.is_file():
            try:
                url = github_from_values([config_path.read_text(encoding="utf-8", errors="replace")])
            except OSError:
                url = ""
            if url:
                return url
        if current == resolved_root:
            break
        current = current.parent
    return ""


def github_for(frontmatter: Dict[str, Any], manifest: Dict[str, Any], curation: Dict[str, Any], name: str, relative_path: str, skill_path: Path, root: Path) -> Tuple[str, str]:
    override = curation_value(curation.get("github_overrides"), name, relative_path)
    if override:
        return override, "curation"
    frontmatter_url = github_from_values(frontmatter.values())
    if frontmatter_url:
        return frontmatter_url, "frontmatter"
    manifest_url = github_from_values(manifest.values())
    if manifest_url:
        return manifest_url, "manifest"
    git_url = github_from_git_config(skill_path, root)
    if git_url:
        return git_url, "git-config"
    return "", ""


def truncate_cover_text(value: str, limit: int = 58) -> str:
    compact = re.sub(r"\s+", " ", str(value or "")).strip()
    return compact if len(compact) <= limit else compact[: limit - 1].rstrip() + "…"


def generated_cover(name: str, description: str, category: str, category_label: str) -> str:
    background, accent = COVER_STYLES.get(category, COVER_STYLES["other"])
    title = html.escape(truncate_cover_text(name, 26))
    summary = html.escape(truncate_cover_text(description, 56))
    label = html.escape(category_label)
    svg = (
        f'<svg xmlns="{SVG_NAMESPACE}" width="1200" height="675" viewBox="0 0 1200 675" role="img">'
        f'<rect width="1200" height="675" fill="{background}"/>'
        '<path d="M0 0h1200v86H0z" fill="#ffffff" opacity=".08"/>'
        '<path d="M0 545h1200v130H0z" fill="#000000" opacity=".10"/>'
        f'<path d="M72 116h210" stroke="{accent}" stroke-width="12"/>'
        f'<text x="72" y="176" fill="{accent}" font-family="Segoe UI, Microsoft YaHei, sans-serif" font-size="24" font-weight="700">{label}</text>'
        '<text x="72" y="226" fill="#d7f0f2" font-family="Segoe UI, Microsoft YaHei, sans-serif" font-size="17">AGENT SKILL CATALOG</text>'
        f'<text x="72" y="320" fill="#ffffff" font-family="Segoe UI, Microsoft YaHei, sans-serif" font-size="48" font-weight="700">{title}</text>'
        f'<text x="76" y="452" fill="#d7f0f2" font-family="Segoe UI, Microsoft YaHei, sans-serif" font-size="22">{summary}</text>'
        f'<rect x="854" y="152" width="210" height="210" rx="16" fill="none" stroke="{accent}" stroke-width="14"/>'
        f'<path d="M885 316l61-75 49 47 35-43 48 71" fill="none" stroke="{accent}" stroke-width="14" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    )
    return "data:image/svg+xml;utf8," + quote(svg, safe="")


def normalize_for_match(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\\", "/").lower()).strip()


def is_absolute_text(value: Any) -> bool:
    text = str(value or "").strip().replace("\\", "/")
    return bool(re.match(r"^(?:[A-Za-z]:/|//|/)", text))


def public_label(value: Any, include_absolute_paths: bool) -> str:
    text = str(value or "")
    return text if include_absolute_paths or not is_absolute_text(text) else "<absolute path hidden>"


def keyword_match(haystack: str, keyword: str) -> bool:
    value = normalize_for_match(keyword)
    if not value:
        return False
    if ASCII_WORD.search(value):
        return bool(re.search(r"(?<![a-z0-9])" + re.escape(value) + r"(?![a-z0-9])", haystack, re.I))
    return value in haystack


def nearest_manifest(skill_path: Path, root: Path) -> Tuple[Dict[str, Any], str]:
    current = skill_path.parent
    root = root.resolve()
    for _ in range(8):
        if not current.resolve().is_relative_to(root):
            break
        for name in ("manifest.json", "plugin.json"):
            candidate = current / name
            if candidate.is_file():
                payload = read_json(candidate, {})
                return (payload if isinstance(payload, dict) else {}, str(candidate))
        if current == root:
            break
        current = current.parent
    return {}, ""


def root_specs(config: Dict[str, Any], cli_roots: Optional[List[str]]) -> List[Dict[str, str]]:
    raw = cli_roots if cli_roots else config.get("roots", [])
    if not raw:
        raw = ["."]
    specs: List[Dict[str, str]] = []
    for index, value in enumerate(raw):
        if isinstance(value, dict):
            path_value = str(value.get("path") or ".")
            label = str(value.get("label") or value.get("source") or f"Root {index + 1}")
            kind = str(value.get("kind") or "skill")
        else:
            path_value = str(value)
            label = f"Root {index + 1}"
            kind = "skill"
        specs.append({"path": str(expand_path(path_value).resolve()), "label": label, "kind": kind})
    return specs


def iter_skill_files(root: Path, skip_dirs: Iterable[str], max_depth: int) -> Iterable[Path]:
    skip = {str(item).lower() for item in skip_dirs}
    root = root.resolve()
    if not root.is_dir():
        return
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        try:
            depth = len(current_path.relative_to(root).parts)
        except ValueError:
            continue
        if depth >= max_depth:
            dirs[:] = []
        dirs[:] = sorted([name for name in dirs if name.lower() not in skip])
        for name in sorted(files):
            if name.lower() == "skill.md":
                skill_path = current_path / name
                if is_packaged_mirror_skill(skill_path):
                    continue
                yield skill_path


def is_packaged_mirror_skill(skill_path: Path) -> bool:
    """Skip the versioned package copy when a repository root exposes the same Skill."""
    package_dir = skill_path.parent
    skills_dir = package_dir.parent
    if skills_dir.name.casefold() != "skills":
        return False
    repository_root = skills_dir.parent
    root_skill = repository_root / "SKILL.md"
    if not root_skill.is_file():
        return False
    try:
        root_fields = parse_frontmatter(root_skill.read_text(encoding="utf-8", errors="replace"))
        package_fields = parse_frontmatter(skill_path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return False
    root_name = str(root_fields.get("name") or "").strip().casefold()
    package_name = str(package_fields.get("name") or "").strip().casefold()
    return bool(root_name and root_name == package_name == package_dir.name.casefold())


def category_override(
    name: str,
    relative_path: str,
    root_label: str,
    root_path: str,
    config: Dict[str, Any],
) -> Optional[Tuple[str, Dict[str, Any]]]:
    categories = config.get("categories") if isinstance(config.get("categories"), dict) else {}
    name_key = normalize_for_match(name)
    path_key = normalize_for_match(relative_path)
    root_label_key = normalize_for_match(root_label)
    root_path_key = normalize_for_match(root_path)
    matches: List[Tuple[int, int, Dict[str, Any], Dict[str, Any]]] = []
    curation = config.get("curation") if isinstance(config.get("curation"), dict) else {}
    raw_overrides = _override_entries(config.get("category_overrides"))
    raw_overrides.extend(_override_entries(curation.get("category_overrides")))
    for index, entry in enumerate(raw_overrides):
        category = str(entry.get("category") or "").strip()
        if category not in categories:
            continue
        selector_root = normalize_for_match(str(entry.get("root") or ""))
        selector_path = normalize_for_match(str(entry.get("path") or entry.get("relative_path") or ""))
        selector_name = normalize_for_match(str(entry.get("name") or ""))
        if selector_root and selector_root not in {root_label_key, root_path_key}:
            continue
        if selector_path:
            full_path_key = normalize_for_match(f"{root_path}/{relative_path}")
            if selector_path not in {path_key, full_path_key}:
                continue
        if selector_name and selector_name != name_key:
            continue
        # More specific selectors win; stable order breaks otherwise.
        specificity = bool(selector_root) + bool(selector_path) * 2 + bool(selector_name) * 4
        matches.append((specificity, index, entry, {
            "type": "override",
            "scope": {key: str(entry[key]) for key in ("root", "path", "relative_path", "name") if key in entry},
        }))
    if not matches:
        return None
    _, index, selected, evidence = sorted(matches, key=lambda value: (-value[0], value[1]))[0]
    evidence["key"] = str(selected.get("id") or selected.get("name") or index)
    return str(selected["category"]), evidence


def classify(
    name: str,
    description: str,
    relative_path: str,
    manifest: Dict[str, Any],
    config: Dict[str, Any],
    root_label: str = "",
    root_path: str = "",
) -> Tuple[str, List[Dict[str, Any]], float, Dict[str, Any]]:
    categories = config.get("categories") if isinstance(config.get("categories"), dict) else {}
    override = category_override(name, relative_path, root_label, root_path, config)
    if override and override[0] in categories:
        return override[0], [override[1]], 1.0, {
            "candidates": [{"category": override[0], "score": 1.0, "evidence": [override[1]]}],
            "winning_margin": 1.0,
            "tie_reason": "explicit-override",
            "low_confidence": False,
        }
    manifest_category = str(manifest.get("category") or "").strip()
    if manifest_category in categories:
        evidence = [{"type": "manifest", "field": "category", "value": manifest_category}]
        return manifest_category, evidence, 0.98, {
            "candidates": [{"category": manifest_category, "score": 1.0, "evidence": evidence}],
            "winning_margin": 1.0,
            "tie_reason": "manifest-category",
            "low_confidence": False,
        }

    identity = normalize_for_match(f"{name} {relative_path}")
    detail = normalize_for_match(description)
    scores: Dict[str, int] = {}
    evidence: Dict[str, List[Dict[str, Any]]] = {}
    for category_id, metadata in categories.items():
        keywords = metadata.get("keywords", []) if isinstance(metadata, dict) else []
        hits: List[Dict[str, Any]] = []
        score = 0
        for keyword in keywords if isinstance(keywords, list) else []:
            term = str(keyword)
            if keyword_match(identity, term):
                score += 3
                hits.append({"type": "identity-keyword", "value": term})
            elif keyword_match(detail, term):
                score += 1
                hits.append({"type": "description-keyword", "value": term})
        if hits:
            scores[category_id] = score
            evidence[category_id] = hits
    tie_break = [str(value) for value in (config.get("category_tie_break") or list(categories))]
    ranked = sorted(
        ((category_id, float(score)) for category_id, score in scores.items()),
        key=lambda value: (-value[1], tie_break.index(value[0]) if value[0] in tie_break else len(tie_break), value[0]),
    )
    best = ranked[0][0] if ranked else ("other" if "other" in categories else (next(iter(categories), "other")))
    best_score = ranked[0][1] if ranked else 0.0
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = round(best_score - second_score, 3)
    tied = bool(ranked and second_score == best_score)
    small_margin = bool(ranked and not tied and margin <= float(config.get("classification", {}).get("small_margin", 1.0)))
    if best_score == 0:
        fallback = [{"type": "fallback", "reason": "no configured keyword matched"}]
        return best, fallback, 0.2, {
            "candidates": [{"category": best, "score": 0.0, "evidence": fallback}],
            "winning_margin": 0.0, "tie_reason": "no-signal", "low_confidence": True,
        }
    confidence = min(0.95, 0.5 + best_score * 0.05)
    low_confidence = tied or small_margin or confidence < float(config.get("classification", {}).get("low_confidence", 0.5))
    tie_reason = "exact-tie" if tied else ("small-margin" if small_margin else "clear-winner")
    candidates = [{"category": category_id, "score": score, "evidence": evidence.get(category_id, [])} for category_id, score in ranked]
    return best, evidence.get(best, []), confidence if not low_confidence else min(confidence, 0.49), {
        "candidates": candidates,
        "winning_margin": margin,
        "tie_reason": tie_reason,
        "low_confidence": low_confidence,
    }


def local_path_value(value: str, skill_path: Path) -> str:
    candidate = expand_path(value)
    if not candidate.is_absolute():
        candidate = skill_path.parent / candidate
    return str(candidate.resolve())


def choose_image(
    skill_path: Path,
    frontmatter: Dict[str, Any],
    category: str,
    name: str,
    relative_path: str,
    description: str,
    config: Dict[str, Any],
    github_url: str = "",
    image_cache_dir: Optional[Path] = None,
    github_previews: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    image_config = config.get("image") if isinstance(config.get("image"), dict) else {}
    categories = config.get("categories") if isinstance(config.get("categories"), dict) else {}
    metadata = categories.get(category) if isinstance(categories.get(category), dict) else {}
    label = str(metadata.get("label") or category)
    fallback = generated_cover(name, description, category, label)
    max_bytes = int(image_config.get("max_embedded_bytes", 512 * 1024) or 0)
    curation = config.get("curation") if isinstance(config.get("curation"), dict) else {}
    curated_image = curation_value(curation.get("image_overrides"), name, relative_path)
    if curated_image:
        local = Path(local_path_value(curated_image, skill_path))
        data_uri = image_data_uri(local, max_bytes) if local.is_file() else ""
        if data_uri:
            return {"status": "curated-local", "source": "curation:image_overrides", "value": data_uri, "missing_evidence": False}
    if github_url and image_cache_dir is not None:
        if github_previews is not None and github_url not in github_previews:
            github_previews[github_url] = github_preview_image(github_url, image_config, image_cache_dir)
        github_image = github_previews.get(github_url, {}) if github_previews is not None else github_preview_image(github_url, image_config, image_cache_dir)
        if github_image:
            return dict(github_image)
    keys = image_config.get("frontmatter_keys", [])
    for key in keys if isinstance(keys, list) else []:
        raw = str(frontmatter.get(key) or "").strip()
        if not raw:
            continue
        if re.match(r"^https?://", raw, re.I):
            if image_config.get("allow_remote_metadata", True):
                return {
                    "status": "remote-metadata",
                    "source": f"frontmatter:{key}",
                    "value": fallback,
                    "remote_metadata": raw,
                    "missing_evidence": True,
                }
            continue
        local = Path(local_path_value(raw, skill_path))
        data_uri = image_data_uri(local, max_bytes) if local.is_file() else ""
        if data_uri:
            return {"status": "verified-local", "source": f"frontmatter:{key}", "value": data_uri, "missing_evidence": False}
        return {"status": "generated-fallback", "source": f"invalid-frontmatter:{key}", "value": fallback, "missing_evidence": True}

    sidecars = image_config.get("sidecar_names", [])
    for name in sidecars if isinstance(sidecars, list) else []:
        candidate = skill_path.parent / str(name)
        data_uri = image_data_uri(candidate, max_bytes) if candidate.is_file() and candidate.suffix.lower() in IMAGE_EXTENSIONS else ""
        if data_uri:
            return {"status": "verified-local", "source": f"sidecar:{name}", "value": data_uri, "missing_evidence": False}

    cover = str(metadata.get("cover") or "").strip()
    if cover and image_config.get("category_cover_fallback", True):
        if re.match(r"^https?://", cover, re.I):
            return {
                "status": "remote-metadata",
                "source": f"category:{category}",
                "value": fallback,
                "remote_metadata": cover,
                "missing_evidence": True,
            }
        data_uri = image_data_uri(Path(cover), max_bytes)
        if data_uri:
            return {"status": "category-cover", "source": f"category:{category}", "value": data_uri, "missing_evidence": True}
    return {"status": "generated-fallback", "source": "generated", "value": fallback, "missing_evidence": True}


def stable_id(root: Path, relative_path: str) -> str:
    value = f"{root.resolve()}::{relative_path}".encode("utf-8")
    return "skill:" + hashlib.sha1(value).hexdigest()[:16]


def plugin_info(spec: Dict[str, str], relative_path: str, skill_path: Path) -> Optional[Dict[str, str]]:
    if spec.get("kind") != "plugin":
        return None
    parts = Path(relative_path).parts
    provider = parts[0] if parts else "unknown"
    name = parts[1] if len(parts) > 1 else skill_path.parent.name
    version = parts[2] if len(parts) > 2 else ""
    return {
        "id": f"plugin:{provider}:{name}",
        "name": name,
        "version": version,
        "provider": provider,
        "provider_source": "structural-path",
        "provider_evidence": {"type": "relative-path", "value": provider},
        "location": "/".join(parts[:3]),
    }


def scan(
    config: Dict[str, Any],
    specs: List[Dict[str, str]],
    include_absolute_paths: bool,
    image_cache_dir: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, str]]]:
    items: List[Dict[str, Any]] = []
    plugins: Dict[str, Dict[str, Any]] = {}
    github_previews: Dict[str, Dict[str, Any]] = {}
    image_contexts: List[Tuple[Dict[str, Any], Path, Dict[str, Any], str, str, str, str, str]] = []
    unresolved: List[Dict[str, str]] = []
    seen: set[str] = set()
    skip_dirs = config.get("scan", {}).get("skip_dirs", sorted(DEFAULT_SKIP_DIRS))
    max_depth = int(config.get("scan", {}).get("max_depth", 12) or 12)
    for spec in specs:
        root = Path(spec["path"])
        if not root.is_dir():
            unresolved.append({"path": str(root), "label": spec["label"], "reason": "root does not exist or is not a directory"})
            continue
        for skill_path in iter_skill_files(root, skip_dirs, max_depth):
            resolved = str(skill_path.resolve()).casefold()
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                relative = skill_path.resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                relative = skill_path.name
            text = skill_path.read_text(encoding="utf-8", errors="replace")
            frontmatter = parse_frontmatter(text)
            name = skill_name(skill_path, frontmatter)
            source_description = description_for(text, frontmatter)
            manifest, manifest_path = nearest_manifest(skill_path, root)
            curation = config.get("curation", {})
            curated_description = curation_value(curation.get("description_overrides"), name, relative)
            description = curated_description or source_description
            category, evidence, confidence, classification = classify(
                name,
                source_description,
                relative,
                manifest,
                config,
                root_label=spec["label"],
                root_path=str(root),
            )
            github_url, github_source = github_for(frontmatter, manifest, curation, name, relative, skill_path, root)
            item: Dict[str, Any] = {
                "id": stable_id(root, relative),
                "name": name,
                "description": description,
                "description_source": "curation" if curated_description else "source",
                "source_description": source_description,
                "category": category,
                "category_evidence": evidence,
                "confidence": round(confidence, 3),
                "category_candidates": classification["candidates"],
                "category_winner_margin": classification["winning_margin"],
                "category_tie_reason": classification["tie_reason"],
                "low_confidence": bool(classification["low_confidence"]),
                "source": public_label(spec["label"], include_absolute_paths),
                "kind": "plugin" if spec.get("kind") == "plugin" else "skill",
                "relative_path": relative,
                "invocation": f"在你的 Agent 中明确说明任务，并要求它按 {relative} 的 SKILL.md 执行。",
                "image": {},
                "root_basename": root.name,
            }
            if github_url:
                item["github"] = {"url": github_url, "source": github_source, "verification": "observed-local"}
            if include_absolute_paths:
                item["path"] = str(skill_path.resolve())
            if manifest_path and include_absolute_paths:
                item["manifest_path"] = manifest_path
            plugin = plugin_info(spec, relative, skill_path)
            if plugin:
                item["plugin_id"] = plugin["id"]
                bucket = plugins.setdefault(plugin["id"], {**plugin, "skills": []})
                bucket.setdefault("locations", [])
                if plugin.get("location") and plugin["location"] not in bucket["locations"]:
                    bucket["locations"].append(plugin["location"])
                if include_absolute_paths:
                    bucket.setdefault("paths", [])
                    plugin_path = str((root / Path(*Path(relative).parts[:3])).resolve())
                    if plugin_path not in bucket["paths"]:
                        bucket["paths"].append(plugin_path)
                bucket["skills"].append(item["id"])
            items.append(item)
            image_contexts.append((item, skill_path, frontmatter, category, name, relative, description, github_url))

    image_config = config.get("image") if isinstance(config.get("image"), dict) else {}
    repositories = sorted({context[-1] for context in image_contexts if context[-1]})
    if image_cache_dir is not None and image_config.get("github_repository_previews", True) and repositories:
        worker_count = min(len(repositories), max(1, int(image_config.get("github_fetch_workers", 8) or 8)))

        def fetch_repository(repository_url: str) -> Tuple[str, Dict[str, Any]]:
            try:
                return repository_url, github_preview_image(repository_url, image_config, image_cache_dir)
            except (OSError, ValueError, UnicodeError):
                return repository_url, {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
            for repository_url, preview in executor.map(fetch_repository, repositories):
                github_previews[repository_url] = preview

    for item, skill_path, frontmatter, category, name, relative, description, github_url in image_contexts:
        image = choose_image(
            skill_path,
            frontmatter,
            category,
            name,
            relative,
            description,
            config,
            github_url=github_url,
            image_cache_dir=image_cache_dir,
            github_previews=github_previews,
        )
        image["evidence"] = "missing" if image.get("missing_evidence", True) else "verified"
        item["image"] = image
    items.sort(key=lambda item: (str(item["category"]), str(item["name"]).casefold(), str(item["relative_path"]).casefold()))
    return items, sorted(plugins.values(), key=lambda item: str(item["name"]).casefold()), unresolved


def family_override(mapping: Any, item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(mapping, dict):
        return {}
    name = normalize_for_match(item.get("name", ""))
    relative = normalize_for_match(item.get("relative_path", ""))
    for key in (item.get("relative_path", ""), relative, item.get("name", ""), name):
        value = mapping.get(key)
        if isinstance(value, dict):
            return value
    return {}


def structural_family_root(item: Dict[str, Any]) -> str:
    parts = Path(str(item.get("relative_path") or "")).parts
    # A root SKILL.md is its own family; nested skills use their first directory.
    return str(item.get("root_basename") or item.get("name") or "skill") if len(parts) <= 1 else str(parts[0])


def family_override_for_structure(mapping: Any, item: Dict[str, Any]) -> Dict[str, Any]:
    """Apply an explicit family id to structurally related paths only.

    A curation entry such as ``tailwind -> ecosystem:hyperframes`` can cover
    the root ``hyperframes`` and its ``hyperframes-*`` siblings.  This is still
    path-derived and never inspects descriptions.
    """
    if not isinstance(mapping, dict):
        return {}
    root_name = normalize_for_match(structural_family_root(item))
    relative = normalize_for_match(item.get("relative_path", ""))
    for key, value in mapping.items():
        if not isinstance(value, dict):
            continue
        family_id = str(value.get("id") or value.get("family") or "").strip()
        if not family_id:
            continue
        slug = normalize_for_match(family_id.rsplit(":", 1)[-1])
        if not slug:
            continue
        if root_name == slug or root_name.startswith(slug + "-"):
            # Do not let an unrelated root-level entry inherit a sibling's
            # family merely because its name happens to share a token.
            selector = normalize_for_match(str(key))
            if selector and (selector in relative or root_name == slug or root_name.startswith(slug + "-")):
                return value
    return {}


def direct_skill_folder(item: Dict[str, Any]) -> str:
    """Return the direct folder name for a root-level ``SKILL.md`` item."""
    parts = Path(str(item.get("relative_path") or "")).parts
    if len(parts) != 2 or parts[-1].casefold() != "skill.md":
        return ""
    folder = normalize_for_match(parts[0])
    name = normalize_for_match(str(item.get("name") or ""))
    return folder if folder and folder == name else ""


def github_key(item: Dict[str, Any]) -> str:
    github = item.get("github")
    url = github.get("url") if isinstance(github, dict) else ""
    value = normalize_for_match(str(url or "")).rstrip("/")
    return re.sub(r"\.git$", "", value)


def rooted_sibling_families(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Infer families installed as sibling root folders, conservatively.

    A prefix is considered a family only when a same-named root Skill exists and
    at least two sibling root Skills use that prefix. This catches repositories
    installed as ``research``, ``research-deep`` and ``research-report`` while
    avoiding loose prefix or description-based merges. Conflicting observed
    GitHub repositories are kept separate.
    """
    buckets: Dict[Tuple[str, str], Dict[str, List[Dict[str, Any]]]] = {}
    for item in items:
        if item.get("kind") != "skill":
            continue
        folder = direct_skill_folder(item)
        if not folder:
            continue
        bucket_key = (
            normalize_for_match(str(item.get("source") or "skill")),
            normalize_for_match(str(item.get("root_basename") or "")),
        )
        bucket = buckets.setdefault(bucket_key, {})
        bucket.setdefault(folder, []).append(item)

    inferred: Dict[str, Dict[str, Any]] = {}
    assigned: set[str] = set()
    for bucket in buckets.values():
        for parent_name in sorted(bucket, key=lambda value: (-len(value), value)):
            parents = bucket[parent_name]
            if len(parents) != 1:
                continue
            parent = parents[0]
            parent_id = str(parent.get("id") or "")
            if not parent_id or parent_id in assigned:
                continue
            children: List[Dict[str, Any]] = []
            prefix = parent_name + "-"
            for child_name, candidates in bucket.items():
                if not child_name.startswith(prefix) or len(candidates) != 1:
                    continue
                child = candidates[0]
                child_id = str(child.get("id") or "")
                if child_id and child_id not in assigned:
                    children.append(child)
            if len(children) < 2:
                continue

            members = [parent, *children]
            observed_repositories = {github_key(member) for member in members if github_key(member)}
            parent_repository = github_key(parent)
            if len(observed_repositories) > 1:
                if not parent_repository:
                    continue
                members = [member for member in members if not github_key(member) or github_key(member) == parent_repository]
                if len(members) < 3:
                    continue

            source = normalize_for_match(str(parent.get("source") or "skill")) or "skill"
            family_id = f"family:{source}:{parent_name}"
            family = {
                "id": family_id,
                "name": str(parent.get("name") or parent_name),
                "category": str(parent.get("category") or "other"),
            }
            for member in members:
                member_id = str(member.get("id") or "")
                if member_id:
                    inferred[member_id] = family
                    assigned.add(member_id)
    return inferred


def family_identity(
    item: Dict[str, Any],
    config: Dict[str, Any],
    inferred: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Tuple[str, str, str]:
    mapping = config.get("curation", {}).get("family_overrides")
    override = (
        family_override(mapping, item)
        or family_override_for_structure(mapping, item)
        or (inferred or {}).get(str(item.get("id") or ""), {})
    )
    if override:
        family_id = str(override.get("id") or override.get("family") or item["name"])
        family_name = str(override.get("name") or family_id)
        category = str(override.get("category") or item["category"])
        return family_id, family_name, category
    source = normalize_for_match(item.get("source", "skill")) or "skill"
    root_name = structural_family_root(item)
    family_slug = normalize_for_match(root_name).replace(" ", "-") or "skill"
    return f"family:{source}:{family_slug}", root_name, str(item["category"])


def assign_families(items: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    inferred = rooted_sibling_families(items)
    for item in items:
        if item["kind"] != "skill":
            continue
        family_id, family_name, family_category = family_identity(item, config, inferred)
        item["family_id"] = family_id
        item["family_name"] = family_name
        item["family_category"] = family_category
        buckets.setdefault(family_id, []).append(item)

    families: List[Dict[str, Any]] = []
    for family_id, members in buckets.items():
        members.sort(key=lambda item: (
            0 if str(item["relative_path"]).casefold().endswith("/skill.md") else 1,
            len(Path(str(item["relative_path"])).parts),
            str(item["name"]).casefold(),
        ))
        expected_name = normalize_for_match(str(members[0].get("family_name") or ""))
        primary = sorted(
            members,
            key=lambda item: (
                0 if normalize_for_match(str(item.get("name") or "")) == expected_name else 1,
                0 if str(item["relative_path"]).casefold().endswith("/skill.md") else 1,
                len(Path(str(item["relative_path"])).parts),
                str(item["name"]).casefold(),
            ),
        )[0]
        for member in members:
            member["family_size"] = len(members)
            member["is_family_primary"] = member["id"] == primary["id"]
        category = str(primary.get("family_category") or primary["category"])
        families.append({
            "id": family_id,
            "name": str(primary.get("family_name") or primary["name"]),
            "category": category,
            "description": primary["description"],
            "description_source": primary.get("description_source", "source"),
            "source": primary.get("source", "unknown"),
            "image": primary["image"],
            "github": primary.get("github", {}),
            "invocation": primary["invocation"],
            "category_evidence": primary.get("category_evidence", []),
            "category_candidates": primary.get("category_candidates", []),
            "category_winner_margin": primary.get("category_winner_margin", 0),
            "category_tie_reason": primary.get("category_tie_reason", "unknown"),
            "confidence": primary.get("confidence", 0),
            "low_confidence": primary.get("low_confidence", False),
            "primary_id": primary["id"],
            "skill_ids": [member["id"] for member in members],
            "locations": [member["relative_path"] for member in members],
        })
    return sorted(families, key=lambda family: str(family["name"]).casefold())


def merge_plugins(raw_plugins: List[Dict[str, Any]], items: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    by_id = {item["id"]: item for item in items}
    buckets: Dict[str, Dict[str, Any]] = {}
    curation = config.get("curation", {})
    for plugin in raw_plugins:
        key = normalize_for_match(f"{plugin.get('provider') or 'unknown'}:{plugin['name']}")
        bucket = buckets.setdefault(key, {
            "id": f"plugin:{key}",
            "name": plugin["name"],
            "provider": plugin.get("provider") or "unknown",
            "provider_source": plugin.get("provider_source") or "unknown",
            "provider_evidence": plugin.get("provider_evidence") or {"type": "unknown"},
            "providers": [],
            "versions": [],
            "locations": [],
            "paths": [],
            "skill_ids": [],
        })
        for field, target in (("provider", "providers"), ("version", "versions"), ("location", "locations"), ("path", "paths")):
            value = plugin.get(field)
            if value and value not in bucket[target]:
                bucket[target].append(value)
        for skill_id in plugin.get("skills", []):
            if skill_id not in bucket["skill_ids"]:
                bucket["skill_ids"].append(skill_id)

    result: List[Dict[str, Any]] = []
    for plugin in buckets.values():
        skills = [by_id[skill_id] for skill_id in plugin["skill_ids"] if skill_id in by_id]
        if not skills:
            continue
        counts: Dict[str, int] = {}
        confidence_by_category: Dict[str, float] = {}
        for skill in skills:
            counts[skill["category"]] = counts.get(skill["category"], 0) + 1
            confidence_by_category[skill["category"]] = confidence_by_category.get(skill["category"], 0.0) + float(skill.get("confidence", 0.0))
        tie_break = [str(value) for value in (config.get("category_tie_break") or [])]
        category = sorted(
            counts,
            key=lambda value: (-counts[value], -confidence_by_category[value], tie_break.index(value) if value in tie_break else len(tie_break), value),
        )[0]
        candidate_rows = [
            {
                "category": value,
                "count": counts[value],
                "confidence_sum": round(confidence_by_category[value], 3),
                "evidence": [
                    json.loads(encoded)
                    for encoded in sorted({
                        json.dumps(evidence, ensure_ascii=False, sort_keys=True)
                        for skill in skills if skill["category"] == value
                        for evidence in skill.get("category_evidence", [])
                    })
                ],
            }
            for value in sorted(
                counts,
                key=lambda value: (
                    -counts[value],
                    -confidence_by_category[value],
                    tie_break.index(value) if value in tie_break else len(tie_break),
                    value,
                ),
            )
        ]
        best_count = counts[category]
        second_count = sorted(counts.values(), reverse=True)[1] if len(counts) > 1 else 0
        plugin_margin = best_count - second_count
        plugin_low_confidence = len(counts) > 1 and plugin_margin <= 1
        explicit = curation_value(curation.get("description_overrides"), str(plugin["name"]), str(plugin["name"]))
        primary = sorted(skills, key=lambda skill: (-float(skill["confidence"]), str(skill["name"]).casefold()))[0]
        description = explicit or primary["description"]
        github = next((skill.get("github") for skill in skills if skill.get("github", {}).get("url")), {})
        image = primary["image"]
        plugin.update({
            "category": category,
            "description": description,
            "description_source": "curation" if explicit else primary.get("description_source", "source"),
            "image": image,
            "github": github,
            "invocation": f"在你的 Agent 中直接说明任务；插件 {plugin['name']} 会路由到它携带的技能。",
            "category_candidates": candidate_rows,
            "category_evidence": [{"type": "plugin-member-category", "value": value, "count": counts[value]} for value in sorted(counts)],
            "category_winner_margin": plugin_margin,
            "category_tie_reason": "small-margin" if plugin_low_confidence else "member-majority",
            "confidence": round(sum(float(skill.get("confidence", 0.0)) for skill in skills) / len(skills), 3),
            "low_confidence": plugin_low_confidence or any(bool(skill.get("low_confidence")) for skill in skills),
        })
        plugin["providers"].sort(key=str.casefold)
        plugin["versions"].sort(key=str.casefold)
        plugin["locations"].sort(key=str.casefold)
        if plugin.get("paths"):
            plugin["paths"].sort(key=str.casefold)
        else:
            plugin.pop("paths", None)
        result.append(plugin)
    return sorted(result, key=lambda plugin: (str(plugin["name"]).casefold(), str(plugin.get("provider") or "").casefold()))


def coverage(items: List[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
    categories = config.get("categories") if isinstance(config.get("categories"), dict) else {}
    rows = []
    for category_id, metadata in categories.items():
        members = [item for item in items if item["category"] == category_id]
        confidence = sum(float(item["confidence"]) for item in members) / len(members) if members else 0.0
        rows.append({
            "id": category_id,
            "label": str(metadata.get("label") or category_id) if isinstance(metadata, dict) else category_id,
            "count": len(members),
            "covered": bool(members),
            "image_count": sum(1 for item in members if not item["image"].get("missing_evidence", True)),
            "average_confidence": round(confidence, 3),
        })
    covered_count = sum(1 for row in rows if row["covered"])
    category_count = len(rows)
    return {
        "schema_version": "1.0",
        "categories": rows,
        "covered_count": covered_count,
        "category_count": category_count,
        "coverage_ratio": round(covered_count / category_count, 3) if category_count else 1.0,
        "uncovered": [row["id"] for row in rows if not row["covered"]],
    }


def public_root_specs(specs: List[Dict[str, str]], include_absolute_paths: bool) -> List[Dict[str, str]]:
    if include_absolute_paths:
        return [dict(spec) for spec in specs]
    return [
        {**spec, "path": "<absolute path hidden>", "label": public_label(spec.get("label"), False)}
        for spec in specs
    ]


def public_unresolved(roots: List[Dict[str, str]], include_absolute_paths: bool) -> List[Dict[str, str]]:
    if include_absolute_paths:
        return [dict(root) for root in roots]
    return [
        {**root, "path": "<absolute path hidden>", "label": public_label(root.get("label"), False)}
        for root in roots
    ]


def image_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    statuses: Dict[str, int] = {}
    missing_evidence_count = 0
    for item in items:
        image = item.get("image", {}) if isinstance(item.get("image"), dict) else {}
        status = str(image.get("status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
        if bool(image.get("missing_evidence", True)):
            missing_evidence_count += 1
    return {
        "status_counts": dict(sorted(statuses.items())),
        "verified_count": len(items) - missing_evidence_count,
        "missing_evidence_count": missing_evidence_count,
    }


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def file_fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def root_fingerprints(specs: List[Dict[str, str]]) -> List[str]:
    return [fingerprint("\x1f".join((str(spec.get("path") or ""), str(spec.get("label") or ""), str(spec.get("kind") or "")))) for spec in specs]


def root_path_fingerprints(specs: List[Dict[str, str]]) -> List[str]:
    return [fingerprint(str(spec.get("path") or "")) for spec in specs]


def public_startup_specs(specs: List[Dict[str, str]], include_absolute_paths: bool) -> List[Dict[str, str]]:
    """Expose the effective startup contract without leaking local paths."""
    return public_root_specs(specs, include_absolute_paths)


def render_html(catalog: Dict[str, Any]) -> str:
    data = json.dumps(catalog, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent Skill Catalog</title><link rel="icon" href="favicon.svg"><style>
:root{font-family:"Segoe UI","Microsoft YaHei",system-ui,sans-serif;color:#142127;background:#f5f7f5}*{box-sizing:border-box}body{min-width:1080px;margin:0}.shell{width:min(1440px,calc(100% - 64px));margin:auto;padding:28px 0 56px}header{display:flex;align-items:center;justify-content:space-between;padding-bottom:22px;border-bottom:1px solid #d9e1dd}.brand{font-size:21px;font-weight:760}.brand span{display:inline-grid;width:36px;height:36px;place-items:center;margin-right:10px;border-radius:6px;color:#fff;background:#0f494d}.refresh{padding:10px 15px;border:0;border-radius:5px;color:#fff;background:#0f494d;font:inherit;font-weight:700;cursor:pointer}.intro{display:grid;grid-template-columns:1fr auto;gap:42px;align-items:end;padding:44px 0 30px}.intro h1{max-width:720px;margin:0;font-size:44px;line-height:1.12;letter-spacing:0}.intro p{max-width:720px;margin:13px 0 0;color:#587076;font-size:16px;line-height:1.7}.stat{padding-left:25px;border-left:3px solid #f05a35}.stat strong{display:block;font-size:42px;line-height:1;color:#0f494d}.stat span{color:#587076}.tabs{display:inline-flex;overflow:hidden;border:1px solid #c9d5d0;border-radius:5px;background:#fff}.tabs button{min-width:92px;padding:10px 18px;border:0;border-right:1px solid #c9d5d0;color:#395055;background:transparent;font:inherit;font-weight:700;cursor:pointer}.tabs button:last-child{border-right:0}.tabs button.active{color:#fff;background:#0f494d}.toolbar{display:grid;grid-template-columns:1fr auto;gap:14px;margin:22px 0}.search{width:100%;padding:13px 15px;border:1px solid #c9d5d0;border-radius:5px;background:#fff;font:inherit;font-size:15px}.filters{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 24px}.filter{padding:8px 12px;border:1px solid #c9d5d0;border-radius:999px;color:#4b6267;background:#fff;font:inherit;cursor:pointer}.filter.active{border-color:#0f494d;color:#fff;background:#0f494d}.overview{display:grid;grid-template-columns:repeat(6,1fr);gap:11px;margin:0 0 34px}.category{min-height:108px;padding:15px;border:0;border-radius:6px;color:#fff;text-align:left;background:#235258;cursor:pointer}.category:nth-child(3n){background:#3d5160}.category:nth-child(3n+2){background:#5b492f}.category strong{display:block;margin-top:30px;font-size:16px}.category span{display:block;margin-top:4px;color:#d7e8e5;font-size:13px}.results-head{display:flex;justify-content:space-between;align-items:baseline;margin:0 0 15px}.results-head h2{margin:0;font-size:23px}.results-head span{color:#667b80}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.card{display:grid;grid-template-rows:auto 1fr;border:1px solid #d7e1dc;border-radius:6px;overflow:hidden;background:#fff;box-shadow:0 8px 22px rgba(29,52,54,.06)}.thumb{position:relative;aspect-ratio:16/9;overflow:hidden;background:#173f45}.thumb img{width:100%;height:100%;object-fit:cover}.thumb-link{display:block;color:inherit}.badge{position:absolute;right:10px;bottom:10px;padding:5px 8px;border-radius:4px;color:#dcefed;background:rgba(10,38,42,.82);font-size:12px}.body{display:flex;min-width:0;flex-direction:column;padding:16px}.card-top{display:flex;gap:10px;align-items:start;justify-content:space-between}.card h3{min-width:0;margin:0;font-size:18px;overflow-wrap:anywhere}.tag{flex:none;padding:4px 7px;border-radius:999px;color:#426167;background:#edf3f0;font-size:12px}.body p{display:-webkit-box;overflow:hidden;margin:10px 0 14px;color:#526b70;line-height:1.55;-webkit-line-clamp:3;-webkit-box-orient:vertical}.meta{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:auto;color:#667b80;font-size:13px}.open{width:34px;height:34px;border:1px solid #b9cac4;border-radius:4px;color:#0f494d;background:#fff;font-size:18px;cursor:pointer}.empty{padding:48px;color:#667b80;text-align:center;border:1px dashed #b8c9c3;background:#fff}dialog{width:min(1050px,calc(100% - 64px));max-height:calc(100% - 64px);padding:0;border:0;border-radius:7px;box-shadow:0 30px 100px rgba(10,27,30,.38)}dialog::backdrop{background:rgba(8,25,28,.58)}.dialog{position:relative;display:grid;grid-template-columns:390px 1fr}.detail-media{min-height:360px;background:#173f45}.detail-media img{width:100%;height:100%;object-fit:cover;object-position:left center}.detail{padding:30px 34px}.close{position:absolute;top:15px;right:16px;width:32px;height:32px;border:0;border-radius:4px;color:#567076;background:transparent;font-size:26px;cursor:pointer}.detail h2{margin:8px 40px 10px 0;font-size:28px}.detail-summary{margin:0 0 22px;color:#536a70;line-height:1.7}.label{margin:20px 0 8px;color:#0f494d;font-size:13px;font-weight:760}.code{padding:12px 14px;border-left:3px solid #f05a35;background:#eef3f0;color:#273f43;line-height:1.55;white-space:pre-wrap}.subskills{display:grid;gap:0;border-top:1px solid #dbe5e0}.subskill{display:grid;grid-template-columns:1fr auto;gap:9px;padding:12px 0;border-bottom:1px solid #dbe5e0}.subskill strong{overflow-wrap:anywhere}.subskill p{grid-column:1/-1;margin:0;color:#647b80;font-size:13px;line-height:1.5}.github{display:inline-block;color:#0b6570;font-weight:700;overflow-wrap:anywhere}.status{min-height:20px;margin-top:8px;color:#647b80;font-size:13px}
</style></head><body><div class="shell"><header><div class="brand"><span>AC</span>Agent Skill Catalog</div><div><button class="refresh" id="refresh" type="button">刷新索引</button><div class="status" id="status" role="status" aria-live="polite"></div></div></header><section class="intro"><div><h1>按分类查找 Skill，打开就能看调用方式。</h1><p>将本机 Skill 与插件按用途、来源、调用方式和预览整理为可检索目录。独立技能按家族聚合；插件只在插件视图中展示。</p></div><div class="stat"><strong id="total"></strong><span id="stat-label"></span></div></section><nav class="tabs" aria-label="目录视图"><button class="mode active" data-mode="skills" type="button">技能</button><button class="mode" data-mode="plugins" type="button">插件</button></nav><section class="toolbar"><label class="sr-only" for="search">搜索技能与插件</label><input class="search" id="search" type="search" placeholder="搜索名称、用途、GitHub 或本地相对路径"><span></span></section><section class="filters" id="filters" aria-label="分类筛选"></section><section class="overview" id="overview" aria-label="分类概览"></section><section><div class="results-head"><h2 id="result-title"></h2><span id="count"></span></div><div class="grid" id="list"></div></section></div><dialog id="detail" aria-labelledby="detail-name"><article class="dialog"><button class="close" id="close" type="button" title="关闭详情" aria-label="关闭详情">×</button><div class="detail-media"><img id="detail-image" alt=""></div><div class="detail"><span class="tag" id="detail-tag"></span><h2 id="detail-name"></h2><p class="detail-summary" id="detail-description"></p><section id="github-panel" hidden><div class="label">GitHub 仓库</div><a class="github" id="detail-github" target="_blank" rel="noreferrer"></a></section><section class="image-editor"><div class="label">更换预览图</div><p id="image-editor-help">选择一张本地图片作为这个 Skill 的预览图。图片只保存在目录输出中，不会修改原 Skill。</p><label class="image-upload" for="image-file">选择图片<input id="image-file" type="file" accept="image/png,image/jpeg,image/gif,image/webp,image/svg+xml"></label><button class="image-save" id="image-save" type="button" disabled>保存预览图</button><button class="image-remove" id="image-remove" type="button" hidden>恢复自动图</button><span class="image-editor-status" id="image-editor-status" role="status" aria-live="polite"></span></section><div class="label">调用方式</div><div class="code" id="detail-invocation"></div><section id="subskills-panel"><div class="label" id="subskills-label"></div><div class="subskills" id="detail-subskills"></div></section><div class="label">来源位置</div><div class="code" id="detail-locations"></div></div></article></dialog><script>
const data=__CATALOG__;
const $=selector=>document.querySelector(selector);
const escapeHtml=value=>String(value??'').replace(/[&<>'\"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
const labels=Object.fromEntries(Object.entries(data.categories||{}).map(([id,meta])=>[id,meta.label||id]));
const byId=new Map((data.items||[]).map(item=>[item.id,item]));
const state={mode:'skills',category:'all',query:''};let lastFocus=null;
const records=()=>state.mode==='plugins'?(data.plugins||[]):(data.families||[]);
const recordSkills=record=>(record.skill_ids||[]).map(id=>byId.get(id)).filter(Boolean);
const recordText=record=>[record.name,record.description,record.invocation,...(record.locations||[]),record.github?.url,...recordSkills(record).flatMap(item=>[item.name,item.description,item.relative_path,item.github?.url])].join(' ').toLowerCase();
const filtered=()=>records().filter(record=>(state.category==='all'||record.category===state.category)&&(!state.query||recordText(record).includes(state.query)));
function preview(record){const image=record.image||{};const status=image.status==='curated-local'?'人工预览图':image.status==='verified-local'?'Skill 自带图片':image.status==='github-repository'?'GitHub 仓库图片':image.status==='github-social-preview'?'GitHub 仓库预览':image.status==='remote-metadata'?'远程元数据（缺证据）':image.status==='category-cover'?'分类封面（缺证据）':'生成封面（缺证据）';const picture=`<div class="thumb"><img src="${escapeHtml(image.value||'')}" alt="${escapeHtml(record.name)} 的预览图"><span class="badge">${escapeHtml(status)}</span></div>`;return record.github?.url?`<a class="thumb-link" href="${escapeHtml(record.github.url)}" target="_blank" rel="noreferrer" title="打开 GitHub 仓库">${picture}</a>`:picture}
function evidence(record){const winner=record.category_winner_margin??0;const confidence=Math.round(Number(record.confidence||0)*100);const image=record.image||{};return `<div class="evidence"><span>证据：${escapeHtml(record.category_tie_reason||'未说明')}</span><span>置信度：${confidence}%</span><span>图片：${escapeHtml(image.status||'unknown')}</span><span class="source">来源：${escapeHtml(record.source||record.provider||'unknown')}</span><span>边际：${escapeHtml(winner)}</span></div>`}
function card(record){const skillCount=(record.skill_ids||[]).length;const countText=state.mode==='plugins'?`携带 ${skillCount} 个技能`:(skillCount>1?`包含 ${skillCount} 个子技能`:'独立技能');return `<article class="card">${preview(record)}<div class="body"><div class="card-top"><h3>${escapeHtml(record.name)}</h3><span class="tag">${escapeHtml(labels[record.category]||record.category)}</span></div><p>${escapeHtml(record.description)}</p>${evidence(record)}<div class="meta"><span>${countText}</span><div class="meta-actions"><button class="open" type="button" data-record="${escapeHtml(record.id)}" title="查看详情">查看详情</button><button class="edit-image" type="button" data-image-record="${escapeHtml(record.id)}" title="更换此 Skill 的预览图">更换预览图</button></div></div></div></article>`}
function renderFilters(){const counts=records().reduce((out,item)=>(out[item.category]=(out[item.category]||0)+1,out),{});const entries=[['all','全部',records().length],...Object.keys(labels).filter(id=>counts[id]).map(id=>[id,labels[id],counts[id]])];$('#filters').innerHTML=entries.map(([id,label,count])=>`<button class="filter ${state.category===id?'active':''}" data-category="${escapeHtml(id)}" type="button">${escapeHtml(label)} ${count}</button>`).join('')}
function renderOverview(){const counts=records().reduce((out,item)=>(out[item.category]=(out[item.category]||0)+1,out),{});$('#overview').innerHTML=Object.keys(labels).filter(id=>counts[id]).map(id=>`<button class="category" data-category="${escapeHtml(id)}" type="button"><strong>${escapeHtml(labels[id])}</strong><span>${counts[id]} ${state.mode==='plugins'?'个插件':'个主技能'}</span></button>`).join('')}
function render(){const items=filtered();$('#total').textContent=records().length;$('#stat-label').textContent=state.mode==='plugins'?'已整理插件':'已整理主技能';$('#result-title').textContent=state.category==='all'?(state.mode==='plugins'?'全部插件':'全部技能'):(labels[state.category]||state.category);$('#count').textContent=`${items.length} 项结果 · 索引更新于 ${data.generated_at||'未生成'}`;renderFilters();renderOverview();$('#list').innerHTML=items.length?items.map(card).join(''):'<div class="empty">没有找到匹配的 Skill 或插件。请更换关键词或分类。</div>';document.querySelectorAll('[data-category]').forEach(button=>button.addEventListener('click',()=>{state.category=button.dataset.category;render()}));document.querySelectorAll('[data-record]').forEach(button=>button.addEventListener('click',()=>openRecord(button.dataset.record)));document.querySelectorAll('[data-image-record]').forEach(button=>button.addEventListener('click',()=>openRecord(button.dataset.imageRecord,true)))}
let activeRecord=null;let selectedImage=null;function primaryRelativePath(record){const skills=recordSkills(record);const primary=record.primary_id?(skills.find(item=>item.id===record.primary_id)||skills[0]):(skills[0]||record);return primary?.relative_path||''}function openRecord(id,focusImage=false){const record=records().find(entry=>entry.id===id);if(!record)return;const pageScroll=window.scrollY;const skills=recordSkills(record);activeRecord=record;selectedImage=null;$('#image-file').value='';$('#image-save').disabled=true;$('#image-remove').hidden=(record.image||{}).status!=='curated-local';$('#image-editor-status').textContent='';$('#detail-image').src=(record.image||{}).value||'';$('#detail-image').alt=`${record.name} 的预览图`;$('#detail-tag').textContent=labels[record.category]||record.category;$('#detail-name').textContent=state.mode==='plugins'?`${record.name} 插件`:record.name;$('#detail-description').textContent=record.description;$('#detail-invocation').textContent=record.invocation;$('#detail-locations').textContent=(record.locations||[]).join('\\n');const github=record.github?.url;$('#github-panel').hidden=!github;if(github){$('#detail-github').href=github;$('#detail-github').textContent=github}$('#subskills-label').textContent=state.mode==='plugins'?`插件携带技能（${skills.length}）`:(skills.length>1?`包含的子技能（${skills.length}）`:'技能详情');$('#detail-subskills').innerHTML=skills.map(item=>`<article class="subskill"><strong>${escapeHtml(item.name)}</strong><span class="tag">${escapeHtml(labels[item.category]||item.category)}</span><p>${escapeHtml(item.description)}</p><p>调用：${escapeHtml(item.invocation)}</p></article>`).join('');const imageSource=(record.image||{}).source||'unknown';const evidenceHtml=`<section class="detail-evidence" aria-label="分类与来源证据"><div><strong>分类证据</strong>${escapeHtml(record.category_tie_reason||'未说明')}</div><div><strong>置信度</strong>${Math.round(Number(record.confidence||0)*100)}%</div><div><strong>图片状态</strong>${escapeHtml((record.image||{}).status||'unknown')} · ${(record.image||{}).missing_evidence?'missing evidence':'verified evidence'}</div><div><strong>图片来源</strong><span class="source">${escapeHtml(imageSource)}</span></div></section>`;document.querySelectorAll('.detail-evidence').forEach(node=>node.remove());$('.detail').insertAdjacentHTML('beforeend',evidenceHtml);$('#detail').showModal();window.scrollTo({top:pageScroll,behavior:'auto'});$('#close').focus({preventScroll:true});if(focusImage){requestAnimationFrame(()=>{window.scrollTo({top:pageScroll,behavior:'auto'});const editor=$('.image-editor');editor.classList.add('focus-target');editor.focus({preventScroll:true});setTimeout(()=>editor.classList.remove('focus-target'),1400)})}}
document.querySelectorAll('[data-mode]').forEach(button=>button.addEventListener('click',()=>{state.mode=button.dataset.mode;state.category='all';state.query='';$('#search').value='';document.querySelectorAll('[data-mode]').forEach(tab=>tab.classList.toggle('active',tab.dataset.mode===state.mode));render()}));$('#search').addEventListener('input',event=>{state.query=event.target.value.trim().toLowerCase();render()});$('#close').addEventListener('click',()=>$('#detail').close());$('#detail').addEventListener('close',()=>{if(lastFocus&&typeof lastFocus.focus==='function')lastFocus.focus()});document.addEventListener('keydown',event=>{if(event.key==='Escape'&&$('#detail').open){event.preventDefault();$('#detail').close()}});$('#refresh').addEventListener('click',async()=>{const status=$('#status');status.textContent='正在刷新索引…';try{const response=await fetch('/api/refresh',{method:'POST'});if(!response.ok)throw new Error('refresh failed');location.reload()}catch{status.textContent='当前为静态页面。请运行 build_catalog.py --refresh，或通过 serve_catalog.py 打开页面。'}});render();
</script></body></html>""".replace("__CATALOG__", data).replace(
        "</style>",
        ".sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}:focus-visible{outline:3px solid #f05a35;outline-offset:3px}.evidence{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px;color:#526b70;font-size:12px}.evidence span{padding:3px 6px;border:1px solid #d3dfda;border-radius:4px;background:#f5f8f6}.detail-evidence{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:18px}.detail-evidence div{padding:8px 10px;background:#f5f8f6;color:#526b70;font-size:13px;line-height:1.4}.detail-evidence strong{display:block;color:#0f494d;font-size:12px}.source{overflow-wrap:anywhere}.image-editor{margin:20px 0 4px}.image-editor .label{margin-bottom:8px}.image-editor p{margin:0 0 10px;color:#647b80;font-size:13px;line-height:1.5}.image-upload,.image-save,.image-remove{display:inline-flex;align-items:center;justify-content:center;min-height:35px;margin:0 8px 0 0;padding:8px 11px;border:1px solid #b9cac4;border-radius:4px;color:#0f494d;background:#fff;font:inherit;font-size:13px;font-weight:700;cursor:pointer}.image-upload input{position:absolute;width:1px;height:1px;opacity:0;pointer-events:none}.image-save{border-color:#0f494d;color:#fff;background:#0f494d}.image-remove{border-color:#c7674d;color:#9f3e27}.image-save:disabled{cursor:not-allowed;opacity:.5}.image-editor-status{display:inline-block;color:#526b70;font-size:12px}</style>",
    ).replace(
        "</style>",
        ":root{--ease-spring:cubic-bezier(.32,.72,0,1);--ease-out-quart:cubic-bezier(.25,1,.5,1)}.shell>header{position:sticky;top:0;z-index:10;background:rgba(245,247,245,.82);backdrop-filter:blur(16px) saturate(150%);-webkit-backdrop-filter:blur(16px) saturate(150%);box-shadow:0 8px 22px rgba(29,52,54,.04);transition:background .22s var(--ease-out-quart),box-shadow .22s var(--ease-out-quart)}.refresh,.tabs button,.filter,.category,.open,.close{transition:transform .16s var(--ease-out-quart),box-shadow .16s var(--ease-out-quart),background-color .16s var(--ease-out-quart),border-color .16s var(--ease-out-quart),color .16s var(--ease-out-quart)}.refresh:hover{transform:translateY(-1px);box-shadow:0 6px 14px rgba(15,73,77,.2)}.refresh:active,.tabs button:active,.filter:active,.category:active,.open:active,.close:active{transform:scale(.97)}.refresh:disabled{cursor:wait;opacity:.72;transform:none}.tabs button:hover,.filter:hover{border-color:#9eb9b2;color:#0f494d}.tabs button.active:hover,.filter.active:hover{color:#fff;background:#0c4144}.category:hover{transform:translateY(-3px) scale(1.01);box-shadow:0 12px 24px rgba(22,53,57,.18)}.open:hover{transform:scale(1.06);border-color:#0f494d;background:#eef7f4;box-shadow:0 5px 12px rgba(15,73,77,.16)}.close:hover{color:#0f494d;background:#eef3f0}.search{transition:border-color .16s var(--ease-out-quart),box-shadow .16s var(--ease-out-quart)}.search:focus{border-color:#0f494d;box-shadow:0 0 0 4px rgba(15,73,77,.12);outline:0}.card{transition:transform .22s var(--ease-out-quart),box-shadow .22s var(--ease-out-quart),border-color .22s var(--ease-out-quart)}.card:hover{transform:translateY(-3px) scale(1.01);border-color:#b2c8c0;box-shadow:0 16px 34px rgba(29,52,54,.14)}.card:focus-within{border-color:#8eb3aa;box-shadow:0 12px 28px rgba(29,52,54,.12)}.thumb img{transition:transform .35s var(--ease-out-quart),filter .35s var(--ease-out-quart)}.card:hover .thumb img{transform:scale(1.035);filter:saturate(1.04)}dialog{background:rgba(255,255,255,.86);backdrop-filter:blur(20px) saturate(145%);-webkit-backdrop-filter:blur(20px) saturate(145%);overflow:hidden;isolation:isolate}dialog::backdrop{background:rgba(8,25,28,0);transition:background .25s var(--ease-out-quart)}dialog.is-visible::backdrop{background:rgba(8,25,28,.58)}dialog .dialog{opacity:0;transform:translateY(14px) scale(.98);transform-origin:50% 12%;transition:opacity .28s var(--ease-spring),transform .28s var(--ease-spring)}dialog.is-visible .dialog{opacity:1;transform:none;transition-duration:.4s}.detail{background:rgba(255,255,255,.78)}@media (prefers-reduced-motion:reduce){.card:hover,.category:hover{transform:none}.card:hover .thumb img{transform:none}.card,.thumb img,.refresh,.tabs button,.filter,.category,.open,.close,dialog .dialog{transition-duration:.01ms!important}dialog .dialog,dialog.is-visible .dialog{transform:none;transition:opacity .2s var(--ease-out-quart)}}@media (prefers-reduced-transparency:reduce){.shell>header,dialog,.detail{background:#fff;backdrop-filter:none;-webkit-backdrop-filter:none}}@media (prefers-contrast:more){.shell>header,dialog{background:#fff;border:1px solid rgba(0,0,0,.35)}} </style>",
    ).replace(
        "</script>",
         "const originalOpenRecord=openRecord;let closeTimer=null;let closing=false;function closeDetail(){const detail=$('#detail');if(!detail.open||closing)return;closing=true;detail.classList.remove('is-visible');const panel=detail.querySelector('.dialog');let finished=false;const finish=()=>{if(finished)return;finished=true;panel.removeEventListener('transitionend',onEnd);clearTimeout(closeTimer);closing=false;detail.close()};const onEnd=event=>{if(event.target===panel&&event.propertyName==='opacity')finish()};panel.addEventListener('transitionend',onEnd);closeTimer=setTimeout(finish,320)}openRecord=(id,focusImage=false)=>{originalOpenRecord(id,focusImage);requestAnimationFrame(()=>$('#detail').classList.add('is-visible'))};$('#close').addEventListener('click',event=>{event.preventDefault();event.stopImmediatePropagation();closeDetail()},true);document.addEventListener('keydown',event=>{if(event.key==='Escape'&&$('#detail').open){event.preventDefault();event.stopImmediatePropagation();closeDetail()}},true);$('#detail').addEventListener('close',()=>$('#detail').classList.remove('is-visible'));</script>",
    ).replace(
        "</script>",
        "const refreshButton=$('#refresh');const refreshStatus=$('#status');new MutationObserver(()=>{if(refreshStatus.textContent&&!refreshStatus.textContent.startsWith('正在')){refreshButton.disabled=false;refreshButton.removeAttribute('aria-busy')}}).observe(refreshStatus,{childList:true});refreshButton.addEventListener('click',()=>{refreshButton.disabled=true;refreshButton.setAttribute('aria-busy','true')});$('#image-file').addEventListener('change',event=>{const file=event.target.files?.[0]||null;selectedImage=file;const status=$('#image-editor-status');if(!file){status.textContent='';$('#image-save').disabled=true;return}if(file.size>2*1024*1024){selectedImage=null;status.textContent='图片不能超过 2 MiB。';$('#image-save').disabled=true;return}status.textContent=`已选择：${file.name}`;$('#image-save').disabled=false});$('#image-save').addEventListener('click',async()=>{const status=$('#image-editor-status');if(!activeRecord||!selectedImage)return;const save=$('#image-save');save.disabled=true;status.textContent='正在保存预览图…';try{const response=await fetch('/api/image',{method:'POST',headers:{'Content-Type':selectedImage.type||'application/octet-stream','X-Catalog-Skill-Name':activeRecord.name,'X-Catalog-Relative-Path':primaryRelativePath(activeRecord)},body:selectedImage});const payload=await response.json().catch(()=>({}));if(!response.ok)throw new Error(payload.error||'保存失败');status.textContent='已保存，正在重载目录…';location.reload()}catch(error){status.textContent=`无法保存：${error.message||'请通过本地服务打开页面'}`;save.disabled=false}});$('#image-remove').addEventListener('click',async()=>{const status=$('#image-editor-status');if(!activeRecord)return;const remove=$('#image-remove');remove.disabled=true;status.textContent='正在恢复自动图…';try{const response=await fetch('/api/image',{method:'DELETE',headers:{'X-Catalog-Relative-Path':primaryRelativePath(activeRecord)}});const payload=await response.json().catch(()=>({}));if(!response.ok)throw new Error(payload.error||'恢复失败');location.reload()}catch(error){status.textContent=`无法恢复：${error.message||'请通过本地服务打开页面'}`;remove.disabled=false}});$('#detail').addEventListener('cancel',event=>{event.preventDefault();closeDetail()});</script>",
    ).replace(
        "</style>",
        ".meta-actions{display:flex;align-items:center;justify-content:flex-end;gap:8px;flex-wrap:wrap}.open,.edit-image{width:auto;min-height:34px;padding:8px 11px;border:1px solid #b9cac4;border-radius:4px;color:#0f494d;background:#fff;font:inherit;font-size:13px;font-weight:700;cursor:pointer}.edit-image{border-color:#f05a35;color:#9f3e27}.meta-actions button:hover{transform:translateY(-1px);box-shadow:0 5px 12px rgba(15,73,77,.12)}.image-editor.focus-target{outline:3px solid rgba(240,90,53,.35);outline-offset:8px}</style>",
    ).replace(
        "</script>",
        "$('.image-editor').setAttribute('tabindex','-1');</script>",
    )


def has_link_ancestor(path: Path) -> bool:
    current = path
    while True:
        is_junction = getattr(current, "is_junction", lambda: False)
        if current.exists() and (current.is_symlink() or is_junction()):
            return True
        if current.parent == current:
            return False
        current = current.parent


def validate_output_dir(output_dir: Path, specs: List[Dict[str, str]], refresh: bool) -> None:
    if has_link_ancestor(output_dir):
        raise ValueError(f"Output directory cannot be a symlink or junction: {output_dir}")
    resolved_output = output_dir.resolve()
    for spec in specs:
        root = Path(spec["path"]).resolve()
        if resolved_output == root or resolved_output.is_relative_to(root):
            raise ValueError(f"Output directory must stay outside scanned roots: {output_dir}")
    if (output_dir / "catalog.json").exists() and not refresh:
        raise ValueError("Output already contains catalog.json; rerun with --refresh to replace it intentionally")


def replace_with_retry(temporary: Path, path: Path) -> None:
    for attempt in range(40):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 39:
                raise
            time.sleep(min(0.1 * (attempt + 1), 1.0))


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as handle:
        handle.write(content)
        temporary = Path(handle.name)
    replace_with_retry(temporary, path)


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False, suffix=".tmp") as handle:
        handle.write(content)
        temporary = Path(handle.name)
    replace_with_retry(temporary, path)


def build(args: argparse.Namespace) -> Dict[str, Any]:
    config_path = Path(args.config).resolve() if args.config else DEFAULT_CONFIG
    config = load_config(config_path)
    if getattr(args, "no_github_images", False):
        config.setdefault("image", {})["github_repository_previews"] = False
    load_curation(getattr(args, "curation", None), config)
    cli_roots = args.root if args.root else None
    specs = root_specs(config, cli_roots)
    explicit_roots = bool(args.root)
    include_absolute = bool(args.include_absolute_paths or config.get("include_absolute_paths", False))
    output_dir = Path(os.path.abspath(expand_path(args.output_dir or str(config.get("output_dir") or "agent-skill-catalog-output"))))
    validate_output_dir(output_dir, specs, args.refresh)
    output_dir = output_dir.resolve()
    output_curation = ensure_output_curation(config, output_dir)
    curation_files = [str(Path(path).resolve()) for path in (args.curation or [])] + [str(output_curation)]
    items, raw_plugins, unresolved = scan(config, specs, include_absolute, output_dir / "github-image-cache")
    families = assign_families(items, config)
    plugins = merge_plugins(raw_plugins, items, config)
    previous = read_json(output_dir / "catalog.json", {}) if output_dir.is_dir() else {}
    images = image_summary(items)
    startup_curation_fingerprints = [file_fingerprint(Path(path)) for path in curation_files]
    catalog: Dict[str, Any] = {
        "schema_version": "1.1",
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "mode": "refresh" if args.refresh else "initial",
        "roots": public_root_specs(specs, include_absolute),
        "root_source": "cli" if explicit_roots else "config",
        "items": items,
        "families": families,
        "plugins": plugins,
        "categories": config.get("categories", {}),
        "category_coverage": coverage(items, config),
        "unresolved_roots": public_unresolved(unresolved, include_absolute),
        "warnings": [
            {"type": "invalid-category-override", **entry}
            for entry in config.get("invalid_category_overrides", [])
        ],
        "refresh_policy": {
            "requires_explicit_roots": True,
            "curation_count": len(args.curation or []),
            "output_curation_file": output_curation.name,
            "absolute_paths_included": include_absolute,
            "startup_root_source": "cli" if explicit_roots else "config",
            "startup_root_specs": public_startup_specs(specs, include_absolute),
            "startup_root_fingerprints": root_fingerprints(specs),
            "startup_root_path_fingerprints": root_path_fingerprints(specs),
            "startup_config_fingerprint": file_fingerprint(config_path),
            "startup_curation_fingerprints": startup_curation_fingerprints[:-1],
        },
        "summary": {
            "skill_count": len([item for item in items if item["kind"] == "skill"]),
            "plugin_skill_count": len([item for item in items if item["kind"] == "plugin"]),
            "plugin_count": len(plugins),
            "family_count": len(families),
            "category_count": len(config.get("categories", {})),
            "low_confidence_count": sum(1 for item in items if float(item["confidence"]) < 0.5),
            "missing_image_count": sum(1 for item in items if item["image"].get("missing_evidence", True)),
            "image_evidence": images,
        },
    }
    if isinstance(previous, dict) and previous.get("generated_at"):
        catalog["previous_generated_at"] = previous["generated_at"]
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output_dir / "catalog.json", json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")
    if not args.no_html:
        atomic_write_text(output_dir / "index.html", render_html(catalog))
        atomic_write_text(output_dir / "favicon.svg", FAVICON_SVG)
    return catalog


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Build a local-only, deterministic Agent Skill Catalog.")
    result.add_argument("--config", help="Path to catalog-config.json")
    result.add_argument("--curation", action="append", help="Optional JSON curation; repeat for Chinese descriptions, GitHub links, and family overrides")
    result.add_argument("--root", action="append", help="Skill or plugin root; repeat for multiple roots")
    result.add_argument("--output-dir", help="Directory for catalog.json and index.html")
    result.add_argument("--refresh", action="store_true", help="Intentional overwrite of the selected output directory")
    result.add_argument("--no-html", action="store_true", help="Write catalog.json without index.html")
    result.add_argument("--include-absolute-paths", action="store_true", help="Include absolute source paths in catalog items")
    result.add_argument("--no-github-images", action="store_true", help="Do not fetch or reuse GitHub repository preview images for this build")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        catalog = build(args)
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"Agent Skill Catalog generation failed: {exc}", file=sys.stderr)
        return 2
    summary = catalog["summary"]
    coverage_ratio = catalog["category_coverage"]["coverage_ratio"]
    print(
        f"Generated {summary['skill_count']} skills and {summary['plugin_count']} plugins; "
        f"category coverage={coverage_ratio:.3f}; output roots={len(catalog['roots'])}"
    )
    if catalog.get("unresolved_roots"):
        print(f"Unresolved roots: {len(catalog['unresolved_roots'])}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
