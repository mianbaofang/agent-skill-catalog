# Agent Skill Catalog

Local-first tooling for turning explicit `SKILL.md` roots into a searchable desktop catalog. It scans read-only directories, classifies each entry with reviewable evidence, groups real parent/child families, aggregates plugins by `provider:name`, and writes deterministic `catalog.json` plus a self-contained `index.html`.

本项目是本地优先的 Agent Skill Catalog 生成器：只读扫描明确指定的 `SKILL.md` 根目录，输出可审查的分类证据、家族/插件聚合、图片证据和桌面检索页面。不安装、不执行、不修改被扫描内容。

## Requirements

- Python 3.10+
- Standard library only

## Quick start

Use explicit roots. The default config intentionally contains no machine-specific roots.

```powershell
python scripts/build_catalog.py --root $env:SKILL_ROOT --output-dir $env:TEMP\agent-skill-catalog-output
```

```bash
python scripts/build_catalog.py --root "$SKILL_ROOT" --output-dir "${TMPDIR:-/tmp}/agent-skill-catalog-output"
```

To scan a plugin root, configure its kind explicitly in a user-owned JSON file. Start with `references/catalog-config.windows.example.json` or `references/catalog-config.posix.example.json`, then pass `--config PATH`.

```text
python scripts/build_catalog.py --config path/to/catalog-config.json --output-dir path/to/output
```

`--refresh` is required before replacing an existing output directory. Add `--include-absolute-paths` only for a deliberate local diagnostic; the default catalog redacts absolute roots and plugin paths.

## Desktop UI and refresh

Open the generated `index.html` directly for a static view. The page keeps separate Skills and Plugins views, family grouping, category filters, search, GitHub thumbnail links, image-evidence labels, and a detail dialog with invocation, child skills, confidence, and classification evidence.

For the refresh button, serve the exact output with explicit startup roots and the same curation files:

```text
python scripts/serve_catalog.py --output-dir path/to/output --root path/to/skills --root path/to/plugins --curation path/to/curation.json
```

The server binds to localhost only. It rejects refresh when startup roots or curation counts are omitted, so a refresh cannot silently switch to another config's roots.

## Evidence model

Each item records `category_candidates`, `category_winner_margin`, `category_tie_reason`, `low_confidence`, `category_evidence`, and `image.missing_evidence`. Generated covers and remote metadata are visual fallbacks, not verified skill images.

## Validation

```text
python scripts/validate_package.py .
python tests/test_build_catalog.py
```

The GitHub Actions workflow runs the same standard-library checks and creates a source package without local catalogs or reports.

## License

MIT. See [LICENSE](LICENSE).
