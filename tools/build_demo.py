#!/usr/bin/env python3
"""Build or verify the public, reproducible demo catalog.

This drives the real scanner (``skills/agent-skill-catalog/scripts/build_catalog.py``)
against the original synthetic fixtures in ``examples/demo-library`` and writes a
self-contained static catalog to ``docs/demo``.  The demo is offline, uses no
GitHub discovery or images, and is labelled as synthetic demo data.

Determinism and portability: the scanner stamps ``generated_at`` with the wall
clock and derives item ids, root ids and fingerprints from absolute root paths,
which differ per machine and per temp dir.  After the real build, this wrapper
pins the timestamp to a documented build epoch and re-maps every identity onto
stable *logical* roots (``<demo-root>/<label>``), so the committed output is
byte-stable and free of machine-specific paths while grouping/results are
unchanged.  The HTML is rendered from the same normalized public catalog.

Usage:
    python tools/build_demo.py            # rebuild docs/demo from fixtures
    python tools/build_demo.py --check    # verify tracked docs/demo matches (read-only)
    python tools/build_demo.py --refresh  # remove this tool's generated files first

Standard library only; runs offline from a fresh clone.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "examples" / "demo-library"
OUTPUT_DIR = REPO_ROOT / "docs" / "demo"
BUILDER_PATH = REPO_ROOT / "skills" / "agent-skill-catalog" / "scripts" / "build_catalog.py"

# Documented fixed build epoch for the synthetic demo (see docs/DEMO.md).
DEMO_EPOCH = "2026-08-18T00:00:00Z"
# Logical, portable stand-in for the absolute fixtures root.
LOGICAL_ROOT = "<demo-root>"
# Fingerprint stand-ins for machine-specific config/curation file hashes.
CONFIG_FINGERPRINT = "demo-config"
CURATION_FINGERPRINT = "demo-curation"

# Generated files this tool owns in docs/demo.  Refresh removes only these.
GENERATED_FILES = (
    "catalog.json",
    "description-enrichment.json",
    "catalog-curation.json",
    "index.html",
    "favicon.svg",
)

# Portable, synthetic curation state shipped with the demo (no machine paths).
DEMO_CURATION_JSON = (
    "{\n"
    '  "description_overrides": {},\n'
    '  "category_overrides": [],\n'
    '  "github_overrides": {},\n'
    '  "family_overrides": {},\n'
    '  "image_overrides": {}\n'
    "}\n"
)

BANNER_MARK = '<meta charset="utf-8">'
BANNER_HTML = (
    '<meta name="robots" content="noindex">'
    '<div class="demo-banner" role="note" '
    'style="margin:0;padding:10px 16px;background:#123b3a;color:#e6f2f0;'
    'font:14px/1.5 system-ui,sans-serif;text-align:center">'
    "演示数据 · Demo data — 合成示例目录，仅展示功能，不扫描访客设备，不提供真实服务。"
    " Synthetic example catalog; limited functionality, nothing is executed or fetched."
    "</div>"
)


def load_builder():
    """Import the real build_catalog module from the installed skill layout."""
    spec = importlib.util.spec_from_file_location("demo_build_catalog", BUILDER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load builder at {BUILDER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def stage_fixtures(temp_path: Path) -> Path:
    """Copy synthetic fixtures into an isolated tree and materialize real SKILL.md.

    Committed fixtures use ``SKILL.md.example`` so they are visibly non-installable
    templates and never pollute repository skill discovery.  The real scanner needs
    actual ``SKILL.md`` files, so this stages a private copy and restores the real
    names there; the repository tree is never modified.
    """
    staged = temp_path / "fixtures"
    shutil.copytree(FIXTURES, staged)
    for template in staged.rglob("SKILL.md.example"):
        template.replace(template.with_name("SKILL.md"))
    return staged


def write_runtime_config(builder, staged: Path, temp_path: Path) -> Path:
    """Write a temp config: inherited default categories + labeled synthetic roots.

    Labels each fixture root ``skill`` vs ``plugin`` (plain ``--root`` strings would
    force kind=skill and drop the plugin view) and inherits the builder's default
    categories so the demo exposes real category filters.
    """
    default = builder.load_config(builder.DEFAULT_CONFIG)
    config = {
        "locale": default.get("locale", "zh-CN"),
        "categories": default.get("categories", {}),
        "category_tie_break": default.get("category_tie_break", []),
        "classification": default.get("classification", {}),
        "image": default.get("image", {}),
        "scan": default.get("scan", {}),
        "roots": [
            {
                "path": str((staged / "roots" / "community-skills").resolve()),
                "label": "社区技能示例",
                "kind": "skill",
            },
            {
                "path": str((staged / "roots" / "personal-skills").resolve()),
                "label": "个人技能示例",
                "kind": "skill",
            },
            {
                "path": str((staged / "plugins").resolve()),
                "label": "插件缓存示例",
                "kind": "plugin",
            },
        ],
    }
    path = temp_path / "catalog-config.json"
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def build_real(builder) -> Dict[str, Any]:
    """Run the real scanner offline in a temp dir; return the built catalog."""
    import argparse

    with tempfile.TemporaryDirectory(prefix="agent-skill-catalog-demo-") as temp:
        temp_path = Path(temp)
        staged = stage_fixtures(temp_path)
        config_path = write_runtime_config(builder, staged, temp_path)
        output_dir = temp_path / "output"
        args = argparse.Namespace(
            config=str(config_path),
            curation=[str(FIXTURES / "catalog-curation.json")],
            root=None,
            output_dir=str(output_dir),
            refresh=True,
            no_html=True,
            include_absolute_paths=False,
            no_github_images=True,
            no_github_discovery=True,
            require_complete_descriptions=False,
        )
        catalog = builder.build(args)
    return catalog


def logical_roots(catalog: Dict[str, Any]) -> List[Dict[str, str]]:
    """Build portable logical root specs carrying stable ids, in scan order."""
    roots = []
    for index, spec in enumerate(catalog.get("roots", [])):
        label = str(spec.get("label") or f"root-{index}")
        roots.append(
            {
                "old_path": str(spec.get("path") or ""),
                "label": label,
                "kind": str(spec.get("kind") or "skill"),
                "logical_path": f"{LOGICAL_ROOT}/{label}",
                "root_id": f"root:{index}",
            }
        )
    return roots


def remap_ids(catalog: Dict[str, Any]) -> Dict[str, str]:
    """Re-map every item id onto a logical, relocation-stable id."""
    mapping: Dict[str, str] = {}
    for index, spec in enumerate(logical_roots(catalog)):
        prefix = f"{spec['old_path']}/"
        members = [item for item in catalog["items"] if str(item.get("source")) == spec["label"]]
        for item in members:
            old_id = str(item.get("id") or "")
            relative = str(item.get("relative_path") or "")
            new_id = f"skill:{index}:{relative}"
            if old_id:
                mapping[old_id] = new_id
    return mapping


def normalize(builder, catalog: Dict[str, Any]) -> Dict[str, Any]:
    """Pin the epoch and re-map identity onto logical roots (grouping unchanged)."""
    roots = logical_roots(catalog)
    path_to_logical = {spec["old_path"]: spec["logical_path"] for spec in roots}
    id_map = remap_ids(catalog)

    def new_id(value: Any) -> Any:
        return id_map.get(str(value), value)

    def logical(value: str) -> str:
        for old, new in sorted(path_to_logical.items(), key=lambda kv: -len(kv[0])):
            if value.startswith(old):
                return new + value[len(old):]
        return value

    # Roots: portable logical paths and ids.
    catalog["roots"] = [
        {
            "path": spec["logical_path"],
            "label": spec["label"],
            "kind": spec["kind"],
            "id": spec["root_id"],
            "allow_delete": False,
        }
        for spec in roots
    ]

    # Stable family ids, mapped before the item loop so member references agree.
    family_map = {
        str(family.get("id") or ""): stable_family_id(family)
        for family in catalog.get("families", [])
    }

    # Items: stable ids + logical locations/paths.
    for item in catalog["items"]:
        item["id"] = new_id(item.get("id"))
        item["family_id"] = family_map.get(str(item.get("family_id") or ""), item.get("family_id"))
        item["root_id"] = next(
            (spec["root_id"] for spec in roots if str(item.get("source")) == spec["label"]),
            item.get("root_id"),
        )
        for field in ("path", "manifest_path"):
            if item.get(field):
                item[field] = logical(str(item[field]))
        for location in item.get("location_evidence", []) or []:
            if isinstance(location, dict) and location.get("path"):
                location["path"] = logical(str(location["path"]))
        dedup = item.get("deduplication")
        if isinstance(dedup, dict):
            dedup["location_evidence"] = [
                {**entry, "path": logical(str(entry.get("path", "")))} if isinstance(entry, dict) else entry
                for entry in dedup.get("location_evidence", []) or []
            ]

    # Families and plugins: rewrite member id references and stable aggregate ids.
    for family in catalog.get("families", []):
        family["id"] = family_map.get(str(family.get("id") or ""), family.get("id"))
        family["skill_ids"] = [new_id(value) for value in family.get("skill_ids", [])]
        family["primary_id"] = new_id(family.get("primary_id"))
        family["image_source_member_id"] = new_id(family.get("image_source_member_id"))
    for plugin in catalog.get("plugins", []):
        plugin["skill_ids"] = [new_id(value) for value in plugin.get("skill_ids", [])]
        plugin["image_source_member_id"] = new_id(plugin.get("image_source_member_id"))

    # Refresh policy: replace machine-specific file/path fingerprints.
    policy = catalog.get("refresh_policy")
    if isinstance(policy, dict):
        policy["startup_root_fingerprints"] = [spec["root_id"] for spec in roots]
        policy["startup_root_path_fingerprints"] = [spec["root_id"] for spec in roots]
        policy["startup_config_fingerprint"] = CONFIG_FINGERPRINT
        policy["startup_curation_fingerprints"] = [CURATION_FINGERPRINT]

    catalog["generated_at"] = DEMO_EPOCH
    catalog.pop("previous_generated_at", None)

    # Render from the exact normalized public catalog (no bookkeeping keys).
    catalog["__html__"] = inject_banner(builder.render_html(catalog))  # type: ignore[assignment]
    return catalog


def stable_family_id(family: Dict[str, Any]) -> str:
    """Rebuild a family id from logical root label + name, dropping stale hashes."""
    label = str(family.get("source") or "skill")
    name = str(family.get("name") or "").strip().replace(" ", "-")
    raw = str(family.get("id") or "")
    kind = "singleton" if ":singleton:" in raw else "family"
    return f"family:{label}:{kind}:{name}"


def inject_banner(rendered: str) -> str:
    """Add noindex + a visible synthetic-demo banner to the generated UI."""
    if BANNER_HTML in rendered:
        return rendered
    if BANNER_MARK in rendered:
        return rendered.replace(BANNER_MARK, BANNER_MARK + "\n  " + BANNER_HTML, 1)
    return BANNER_HTML + rendered


def build_normalized(builder) -> Dict[str, Any]:
    catalog = build_real(builder)
    return normalize(builder, catalog)


def public_json(catalog: Dict[str, Any]) -> str:
    public = {key: value for key, value in catalog.items() if not key.startswith("__")}
    return json.dumps(public, ensure_ascii=False, indent=2) + "\n"


def write_output(builder, catalog: Dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    builder.atomic_write_text(OUTPUT_DIR / "catalog.json", public_json(catalog))
    builder.atomic_write_text(
        OUTPUT_DIR / "description-enrichment.json",
        json.dumps(catalog["description_enrichment"], ensure_ascii=False, indent=2) + "\n",
    )
    builder.atomic_write_text(OUTPUT_DIR / "index.html", catalog["__html__"])
    builder.atomic_write_text(OUTPUT_DIR / "favicon.svg", builder.FAVICON_SVG)
    builder.atomic_write_text(OUTPUT_DIR / "catalog-curation.json", DEMO_CURATION_JSON)


def refresh_output() -> None:
    """Remove only this tool's known generated files before a clean rebuild."""
    for name in GENERATED_FILES:
        target = OUTPUT_DIR / name
        if target.is_file():
            target.unlink()


def check_output(directory: Path = OUTPUT_DIR) -> int:
    """Compare a fresh normalized build against a demo directory (read-only)."""
    builder = load_builder()
    catalog = build_normalized(builder)
    expected = {
        "catalog.json": public_json(catalog),
        "description-enrichment.json": json.dumps(
            catalog["description_enrichment"], ensure_ascii=False, indent=2
        )
        + "\n",
        "index.html": catalog["__html__"],
        "favicon.svg": builder.FAVICON_SVG,
        "catalog-curation.json": DEMO_CURATION_JSON,
    }
    drift = []
    for name, content in expected.items():
        tracked = directory / name
        if not tracked.is_file():
            drift.append(f"{name}: missing")
        elif tracked.read_text(encoding="utf-8") != content:
            drift.append(f"{name}: differs from a fresh offline build")
    if drift:
        print("Demo drift detected; rerun `python tools/build_demo.py` to refresh:", file=sys.stderr)
        for entry in drift:
            print(f"  - {entry}", file=sys.stderr)
        return 1
    summary = catalog["summary"]
    print(
        f"Demo OK: {summary['skill_count']} skills, {summary['plugin_count']} plugins, "
        f"{summary['family_count']} families; epoch={DEMO_EPOCH}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or verify the reproducible demo catalog.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Read-only: verify tracked docs/demo matches a fresh offline build (no writes).",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Remove this tool's known generated files in docs/demo before rebuilding.",
    )
    args = parser.parse_args()
    if args.check:
        return check_output()
    builder = load_builder()
    if args.refresh:
        refresh_output()
    catalog = build_normalized(builder)
    write_output(builder, catalog)
    summary = catalog["summary"]
    print(
        f"Generated demo: {summary['skill_count']} skills, {summary['plugin_count']} plugins, "
        f"{summary['family_count']} families -> {OUTPUT_DIR}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
