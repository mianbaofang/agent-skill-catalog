# Agent Skill Catalog

[中文说明](README.zh-CN.md) | A local-first Agent Skill and plugin catalog for Codex and other AI coding agents.

Agent Skill Catalog scans only the `SKILL.md` roots you explicitly provide and generates a searchable desktop catalog. It classifies Skills with reviewable evidence, groups real parent/child Skill families, separates plugin aggregates from standalone Skills, and presents invocation, GitHub metadata, image evidence, and source locations in one place.

It does not install, execute, edit, or upload the Skills it scans.

## Product demo

The animation below is captured from the generated product UI with public demo Skills. It shows category overview, filtering, and a Skill detail view.

![Agent Skill Catalog: browse categories, filter video Skills, and open a Skill detail view](docs/media/agent-skill-catalog-demo.gif)

| Catalog overview | Skill detail |
| --- | --- |
| ![Agent Skill Catalog overview with category filters and Skill cards](docs/media/agent-skill-catalog-overview.png) | ![Agent Skill Catalog Skill detail view with invocation and classification evidence](docs/media/agent-skill-catalog-detail.png) |

## Install

Install the published Skill through the GitHub CLI:

```powershell
gh skill install mianbaofang/agent-skill-catalog agent-skill-catalog --agent codex --scope user
```

To install a specific release after the repository publishes one:

```powershell
gh skill install mianbaofang/agent-skill-catalog agent-skill-catalog --pin v0.2.1 --agent codex --scope user
```

The installable Skill lives in [`skills/agent-skill-catalog`](skills/agent-skill-catalog). This is the GitHub Agent Skills discovery path; the repository root is reserved for human-facing documentation, tests, release evidence, and demo media.

## Use with an agent

Ask your agent to use the Skill with explicit local roots. For example:

```text
Use $agent-skill-catalog to scan my local Skill root and Codex plugin cache, build a searchable catalog, keep standalone Skills and plugins separate, and report low-confidence classifications and missing image evidence. Do not install, edit, or execute scanned Skills.
```

## Build a catalog from source

Requirements: Python 3.10+ and the standard library only.

```powershell
python skills/agent-skill-catalog/scripts/build_catalog.py `
  --root "C:\path\to\skills" `
  --output-dir "$env:TEMP\agent-skill-catalog-output"
```

To include plugin caches, copy a platform example, set each root's `kind` to `plugin`, and pass it with `--config`:

```powershell
python skills/agent-skill-catalog/scripts/build_catalog.py `
  --config .\my-catalog-config.json `
  --output-dir "$env:TEMP\agent-skill-catalog-output"
```

Open the generated `index.html` directly for a static catalog. To make the page refresh button available, run the bounded localhost server with the same roots and curation files:

```powershell
python skills/agent-skill-catalog/scripts/serve_catalog.py `
  --output-dir "$env:TEMP\agent-skill-catalog-output" `
  --root "C:\path\to\skills"
```

## What the catalog contains

| Area | Included information |
| --- | --- |
| Classification | Category candidates, supporting evidence, confidence, winner margin, and low-confidence markers |
| Skill families | Parent/child aggregation from nested folders, or a same-named root plus at least two source-consistent sibling Skills; explicit curation handles exceptions |
| Plugins | A dedicated view aggregated by `provider:name`, separate from standalone Skills |
| Invocation | Agent-facing invocation guidance and source-relative location |
| Images | Verified local image, curated local preview, remote metadata, or an explicitly labeled fallback |
| GitHub | Repository address only when local Skill metadata, Git config, or curation provides it |

## Privacy and operating boundaries

- Scan only roots supplied by the operator.
- Keep scanned roots read-only.
- Do not fetch remote content or execute discovered Skills.
- Redact absolute paths in catalog output by default.
- Accept no browser-provided command or path on the refresh endpoint.

## Compatibility and discovery

- GitHub Agent Skills: the installable package is discoverable at `skills/agent-skill-catalog/SKILL.md`.
- Codex: includes `agents/openai.yaml` for UI metadata and `agents/interface.yaml` for the Yao Meta interface contract.
- Generic/local use: run the Python scripts directly with explicit roots.

## Verification

```powershell
python tools/validate_package.py .
python tests/test_build_catalog.py
gh skill publish --dry-run
```

The public demo data used for the screenshots is under [`docs/demo`](docs/demo). Its `DEMO.md` files are intentionally non-discoverable examples; they contain no local machine paths or personal catalog data.

## License

MIT. See [LICENSE](LICENSE).
