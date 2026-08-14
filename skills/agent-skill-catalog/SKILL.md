---
name: agent-skill-catalog
description: "Build or refresh a local searchable Agent Skill Catalog from explicit SKILL.md roots and optional plugin roots. Use for deterministic catalog JSON, desktop HTML, category evidence, image evidence, family grouping, plugin aggregation, and bounded local refresh. Do not install, edit, or execute scanned skills."
license: MIT
---

# Agent Skill Catalog

Build a read-only inventory of local `SKILL.md` directories and optional plugin caches. The builder never installs or edits scanned roots. When a Skill has an observed GitHub repository URL, it downloads one bounded public repository preview into the selected output cache; use `--no-github-images` to keep a build offline.

## Workflow

1. Choose one or more explicit roots with `--root PATH` and classify each root as `skill` or `plugin` in a config file.
2. Run `python scripts/build_catalog.py --root PATH --output-dir OUTPUT --require-complete-descriptions` for a first build. Exit code 3 is expected until the invoking Agent completes the Chinese description queue; add `--refresh` only when intentionally replacing that output.
3. Inspect `catalog.json` and `description-enrichment.json`. The invoking Agent owns this work; do not hand the queue back to the user. While `summary.pending_description_count` is non-zero, read each listed source `SKILL.md` and its observed GitHub README when available, write a concise natural Chinese description to `OUTPUT/catalog-curation.json`, then rerun with `--refresh --require-complete-descriptions`. Exit code 3 means the Agent must continue.
4. Confirm `summary.image_evidence` and each `image.status`. Treat installer lock metadata, injected `metadata.github-repo`, observed package/plugin metadata, manifests, explicit Skill links, and local Git remotes as repository evidence. A reachable source must yield `github-social-preview` or `github-repository`; family and plugin cards must keep the best verified member image instead of hiding it behind a generated cover.
5. Open the generated `index.html`, or serve the same output with `python scripts/serve_catalog.py --output-dir OUTPUT --root PATH --require-complete-descriptions`.

中文说明：本 Skill 只读扫描明确指定的本地根目录，生成可检索的技能/插件 Agent Skill Catalog；不安装、不执行、不修改被扫描内容。默认会从已识别的 GitHub 仓库获取并缓存公开预览图；手工选择的本地图片优先，写入输出目录而不是 Skill 源目录。没有真实图片证据时必须显示 `missing evidence`。

## Output contract

The output directory contains `catalog.json`, `description-enrichment.json`, a self-contained `index.html`, and output-owned image/curation files. Defaults redact absolute roots and plugin paths. Use `--include-absolute-paths` only for a deliberate local diagnostic build.

## Boundaries

- No remote code execution. GitHub 图片获取只允许 GitHub 相关图片域名、受大小限制、签名校验，并只写入选定输出目录的缓存。
- No inferred category override for an invalid category.
- No family merge from description text alone. A rooted sibling family needs a same-named root Skill, at least two same-prefix sibling Skills, and no conflicting observed GitHub source; otherwise use explicit curation.
- Refresh must receive the same startup roots and curation files explicitly.
- The builder only creates the description work queue. The invoking Agent must generate and review the Chinese copy, and `--require-complete-descriptions` prevents it from reporting success with unfinished items.

## Resources

- Read `references/workflow.md` for the end-to-end operating flow, and load the other files in `references/` only for the matching configuration, category, image, or prompt task.
- Maintainer-only evaluation cases and governed-release evidence live under `governance/agent-skill-catalog/` in the source repository. They are intentionally outside the installed Skill boundary.
