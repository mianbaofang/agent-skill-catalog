---
name: agent-skill-catalog
description: "Build or refresh a local searchable Agent Skill Catalog from explicit SKILL.md roots and optional plugin roots. Use for deterministic catalog JSON, desktop HTML, category evidence, image evidence, family grouping, plugin aggregation, and bounded local refresh. Do not install, edit, or execute scanned skills."
license: MIT
---

# Agent Skill Catalog

Build a read-only inventory of local `SKILL.md` directories and optional plugin caches. The builder never installs or edits scanned roots. When a Skill has an observed GitHub repository URL, it may download one public repository preview into the selected output cache; use `--no-github-images` to keep a build offline.

## Workflow

1. Choose one or more explicit roots with `--root PATH` and classify each root as `skill` or `plugin` in a config file.
2. Run `python scripts/build_catalog.py --root PATH --output-dir OUTPUT` for a first build. Add `--refresh` only when intentionally replacing that output.
3. Inspect `catalog.json` for category candidates, winning margin, tie reason, low confidence, image evidence, unresolved roots, and warnings.
4. Open the generated `index.html`, or serve the same output with `python scripts/serve_catalog.py --output-dir OUTPUT --root PATH`.

中文说明：本 Skill 只读扫描明确指定的本地根目录，生成可检索的技能/插件 Agent Skill Catalog；不安装、不执行、不修改被扫描内容。默认会从已识别的 GitHub 仓库获取并缓存公开预览图；手工选择的本地图片优先，写入输出目录而不是 Skill 源目录。没有真实图片证据时必须显示 `missing evidence`。

## Output contract

The output directory contains `catalog.json` and a self-contained `index.html`. Defaults redact absolute roots and plugin paths. Use `--include-absolute-paths` only for a deliberate local diagnostic build.

## Boundaries

- No remote code execution. GitHub 图片获取只允许 GitHub 相关图片域名、受大小限制、签名校验，并只写入选定输出目录的缓存。
- No inferred category override for an invalid category.
- No family merge from description text alone. A rooted sibling family needs a same-named root Skill, at least two same-prefix sibling Skills, and no conflicting observed GitHub source; otherwise use explicit curation.
- Refresh must receive the same startup roots and curation files explicitly.

## Resources

- Read `references/workflow.md` for the end-to-end operating flow, and load the other files in `references/` only for the matching configuration, category, image, or prompt task.
- Use `evals/trigger_cases.json` for routing regression checks and `evals/output/cases.jsonl` for output-contract evaluation before a governed release.
