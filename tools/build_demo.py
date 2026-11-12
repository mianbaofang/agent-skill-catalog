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
BODY_END_MARK = "</body>"

# Synthetic-boundary meta line (always visible, one compact row).
DEMO_NOTE_ZH = "合成示例目录，仅展示功能，不扫描访客设备，不提供真实服务。"
DEMO_NOTE_EN = "Synthetic example catalog; limited functionality, nothing is executed or fetched."

# Collapsed one-line action summary so the guide never pushes content down.
DEMO_ACTIONS_SUMMARY = "可试用：搜索 · 家族详情 · 插件视图 · 重置"

# Static-demo guidance: what genuinely works offline vs. what needs the local service.
GUIDE_AVAILABLE = (
    "静态演示可用：搜索、分类筛选、家族/插件详情、查看自动封面图。"
    " 刷新、换图保存、删除需真实本地服务（serve_catalog），静态页不做模拟。"
)
GUIDE_AVAILABLE_EN = (
    "Works offline: search, category filter, family/plugin detail, cover gallery. "
    "Refresh, image save and delete need a real local catalog service and are not simulated here."
)
COVER_NOTE = (
    "点击封面或“查看详情”打开详情；自动封面是按分类生成的占位图，不是图片生成器，也不代表真实项目截图。"
)
COVER_NOTE_EN = (
    "A cover or “查看详情” opens the detail dialog. The auto cover is a per-category placeholder, "
    "not an image generator and not a real project screenshot."
)

# Styling: teal/white, compact, collapsed by default, >=44px touch targets.
DEMO_STYLE = (
    "<style>"
    ".demo-banner{margin:0;padding:8px 16px 10px;background:#123b3a;color:#e6f2f0;"
    "font:14px/1.5 system-ui,-apple-system,'Segoe UI','Microsoft YaHei',sans-serif;text-align:left}"
    ".demo-banner__row{max-width:1180px;margin:0 auto;display:flex;flex-wrap:wrap;"
    "align-items:center;gap:6px 14px;justify-content:space-between}"
    ".demo-banner__note{margin:0;font-size:13px;line-height:1.45}"
    ".demo-banner__note strong{font-weight:700;color:#fff}"
    ".demo-banner__note .demo-banner__en{color:#bcd8d4}"
    ".demo-guide__toggle{flex:0 0 auto;min-height:44px;min-width:44px;padding:8px 16px;"
    "border:1px solid rgba(230,242,240,.55);border-radius:6px;background:transparent;"
    "color:#e6f2f0;font:inherit;font-weight:700;cursor:pointer}"
    ".demo-guide__toggle:hover{background:rgba(255,255,255,.08)}"
    ".demo-guide__panel{max-width:1180px;margin:8px auto 0;padding:12px 14px;border-radius:8px;"
    "background:#fff;color:#1b2a2c;border:1px solid #cfd8d5}"
    ".demo-guide__actions{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 10px;padding:0;list-style:none}"
    ".demo-action{min-height:44px;min-width:44px;padding:8px 14px;border:0;border-radius:6px;"
    "background:#0f766e;color:#fff;font:inherit;font-weight:700;cursor:pointer}"
    ".demo-action:hover{background:#0b5d56}"
    ".demo-guide__note{margin:6px 0 0;font-size:13px;line-height:1.5;color:#33474a}"
    ".demo-guide__note b{color:#123b3a}"
    "</style>"
)


def demo_values(catalog: Dict[str, Any]) -> Dict[str, str]:
    """Derive truthful guide targets from the real (normalized) fixture catalog.

    No counts or names are invented: the sample family is the largest real family and
    the sample plugin is the first real plugin, taken from the built catalog itself.
    """
    families = [family for family in catalog.get("families", []) if family.get("skill_ids")]
    family = max(families, key=lambda entry: len(entry.get("skill_ids") or []), default=None)
    plugins = [plugin for plugin in catalog.get("plugins", []) if plugin.get("name")]
    plugin = plugins[0] if plugins else None
    members = len(family.get("skill_ids") or []) if family else 0
    return {
        "family_id": str(family.get("id") or "") if family else "",
        "family_name": str(family.get("name") or "") if family else "",
        "family_members": str(members),
        "plugin_name": str(plugin.get("name") or "") if plugin else "",
    }


def demo_guide_html(catalog: Dict[str, Any]) -> str:
    """Render the compact, collapsible hands-on guide from real fixture values."""
    values = demo_values(catalog)
    family = values["family_name"]
    members = values["family_members"]
    plugin = values["plugin_name"]
    search_label = f"试试搜索 {family}" if family else "试试搜索"
    detail_label = f"看家族详情（{family}，{members} 个技能）" if family else "看家族详情"
    plugin_label = f"看插件（{plugin}）" if plugin else "看插件"
    reset_label = "重置演示"
    return (
        '<div class="demo-banner" role="note" aria-label="演示数据说明">'
        + DEMO_STYLE
        + '<div class="demo-banner__row">'
        '<p class="demo-banner__note"><strong>演示数据 · Demo data</strong> — '
        + DEMO_NOTE_ZH
        + ' <span class="demo-banner__en">'
        + DEMO_NOTE_EN
        + "</span><br>"
        + DEMO_ACTIONS_SUMMARY
        + "</p>"
        '<button class="demo-guide__toggle" type="button" id="demo-guide-toggle" '
        'aria-expanded="false" aria-controls="demo-guide-panel">操作指南 ▾</button>'
        "</div>"
        '<div class="demo-guide__panel" id="demo-guide-panel" hidden>'
        '<ul class="demo-guide__actions">'
        f'<li><button class="demo-action" type="button" data-demo="search">{search_label}</button></li>'
        f'<li><button class="demo-action" type="button" data-demo="details">{detail_label}</button></li>'
        f'<li><button class="demo-action" type="button" data-demo="plugins">{plugin_label}</button></li>'
        f'<li><button class="demo-action" type="button" data-demo="reset">{reset_label}</button></li>'
        "</ul>"
        f'<p class="demo-guide__note"><b>说明</b> {COVER_NOTE} {GUIDE_AVAILABLE}</p>'
        f'<p class="demo-guide__note"><b>Note</b> {COVER_NOTE_EN} {GUIDE_AVAILABLE_EN}</p>'
        "</div>"
        "</div>"
    )


# Wiring template: every action drives the page's own native controls (search input
# event, category/mode buttons, the real per-record "查看详情" button). No product
# state is duplicated and no fetch is made. __FAMILY_ID__/__FAMILY__ are filled from
# the real fixture catalog at build time.
DEMO_SCRIPT_TEMPLATE = """<script>
  (function(){
    var panel=document.getElementById('demo-guide-panel');
    var toggle=document.getElementById('demo-guide-toggle');
    function setMode(mode){
      var tab=document.querySelector('[data-mode="'+mode+'"]');
      if(tab&&!(tab.classList.contains('active')))tab.click();
    }
    function clearSearch(){
      var input=document.getElementById('search');
      if(input&&input.value){input.value='';input.dispatchEvent(new Event('input',{bubbles:true}))}
    }
    function closeDetail(){
      var dialog=document.getElementById('detail');
      if(dialog&&dialog.open&&typeof dialog.close==='function')dialog.close();
    }
    function reset(){
      closeDetail();clearSearch();setMode('skills');
      var all=document.querySelector('[data-category="all"]');
      if(all&&!(all.classList.contains('active')))all.click();
    }
    function clickRecord(id){
      if(!id)return false;
      var button=document.querySelector('[data-record="'+id+'"]');
      if(button){button.click();return true}
      return false;
    }
    var actions={
      search:function(){reset();setMode('skills');
        var input=document.getElementById('search');
        if(input){input.value=__FAMILY__;input.dispatchEvent(new Event('input',{bubbles:true}))}},
      details:function(){reset();setMode('skills');
        if(!clickRecord(__FAMILY_ID__)){var input=document.getElementById('search');
          if(input){input.value=__FAMILY__;input.dispatchEvent(new Event('input',{bubbles:true}))}}},
      plugins:function(){reset();setMode('plugins')},
      reset:function(){reset()}
    };
    if(panel&&!panel.dataset.demoWired){
      panel.dataset.demoWired='1';
      panel.addEventListener('click',function(event){
        var button=event.target.closest('[data-demo]');
        if(!button)return;
        var action=actions[button.getAttribute('data-demo')];
        if(action)action();
      });
    }
    if(toggle&&!toggle.dataset.demoWired){
      toggle.dataset.demoWired='1';
      toggle.addEventListener('click',function(){
        var open=toggle.getAttribute('aria-expanded')==='true';
        toggle.setAttribute('aria-expanded',open?'false':'true');
        if(panel)panel.hidden=open;
        toggle.textContent=open?'操作指南 ▾':'收起指南 ▴';
      });
    }
  })();
  </script>"""


def demo_script(catalog: Dict[str, Any]) -> str:
    """Wire the guide actions to the real catalog's sample family id/name.

    Values are JSON-encoded so they land as proper JS string literals (a bare
    ``note-keeper`` would otherwise parse as ``note - keeper``).
    """
    values = demo_values(catalog)
    return (
        DEMO_SCRIPT_TEMPLATE.replace("__FAMILY_ID__", json.dumps(values["family_id"]))
        .replace("__FAMILY__", json.dumps(values["family_name"]))
    )


def inject_banner(rendered: str, catalog: Dict[str, Any] | None = None) -> str:
    """Add noindex + a compact, collapsible synthetic-demo guide to the generated UI.

    The banner markup is anchored right after the charset meta so it precedes the
    product UI; the wiring script is anchored before ``</body>`` so the native
    controls it drives already exist. With no catalog supplied, a static boundary
    banner (no action buttons) is emitted.
    """
    values = demo_values(catalog) if catalog is not None else {
        "family_id": "", "family_name": "", "family_members": "0", "plugin_name": ""
    }
    banner = demo_guide_html(catalog or {"families": [], "plugins": []})
    script = demo_script({"families": [], "plugins": []}) if catalog is None else demo_script(catalog)
    head = '<meta name="robots" content="noindex">' + banner
    if BODY_END_MARK in rendered:
        rendered = rendered.replace(BODY_END_MARK, script + BODY_END_MARK, 1)
    else:
        rendered = rendered + script
    if head in rendered:
        return rendered
    if BANNER_MARK in rendered:
        return rendered.replace(BANNER_MARK, BANNER_MARK + "\n  " + head, 1)
    return head + rendered


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
    catalog["__html__"] = inject_banner(builder.render_html(catalog), catalog)  # type: ignore[assignment]
    return catalog


def stable_family_id(family: Dict[str, Any]) -> str:
    """Rebuild a family id from logical root label + name, dropping stale hashes."""
    label = str(family.get("source") or "skill")
    name = str(family.get("name") or "").strip().replace(" ", "-")
    raw = str(family.get("id") or "")
    kind = "singleton" if ":singleton:" in raw else "family"
    return f"family:{label}:{kind}:{name}"


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
