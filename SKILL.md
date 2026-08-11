---
name: agent-skill-catalog
description: "Build or refresh a local searchable Agent Skill Catalog from explicit SKILL.md roots and optional plugin roots. Use for deterministic catalog JSON, desktop HTML, category evidence, image evidence, family grouping, plugin aggregation, and bounded local refresh. Do not install, edit, or execute scanned skills."
---

# Agent Skill Catalog

Build a read-only inventory of local `SKILL.md` directories and optional plugin caches. The builder never installs or edits scanned roots, never fetches remote content, and keeps remote image URLs as metadata only.

## Workflow

1. Choose one or more explicit roots with `--root PATH` and classify each root as `skill` or `plugin` in a config file.
2. Run `python scripts/build_catalog.py --root PATH --output-dir OUTPUT` for a first build. Add `--refresh` only when intentionally replacing that output.
3. Inspect `catalog.json` for category candidates, winning margin, tie reason, low confidence, image evidence, unresolved roots, and warnings.
4. Open the generated `index.html`, or serve the same output with `python scripts/serve_catalog.py --output-dir OUTPUT --root PATH`.

中文说明：本 Skill 只读扫描明确指定的本地根目录，生成可检索的技能/插件 Agent Skill Catalog；不安装、不执行、不修改被扫描内容。没有真实图片证据时必须显示 `missing evidence`，远程图片只保留元数据。

## Output contract

The output directory contains `catalog.json` and a self-contained `index.html`. Defaults redact absolute roots and plugin paths. Use `--include-absolute-paths` only for a deliberate local diagnostic build.

## Boundaries

- No network fetches or remote code execution.
- No inferred category override for an invalid category.
- No automatic family merge from description text alone.
- Refresh must receive the same startup roots and curation files explicitly.
