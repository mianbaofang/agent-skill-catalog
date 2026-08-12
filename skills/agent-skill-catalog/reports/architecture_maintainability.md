# Architecture Maintainability

Generated at: `2026-08-12`

## Summary

- decision: `watch-maintainability-hotspots`
- python files: `4`
- scripts: `0`
- tests: `0`
- internal modules: `1`
- CLI scripts: `3`
- Yao CLI command handlers: `0`
- entrypoint command handlers: `0`
- command modules: `0`
- largest file lines: `1450`
- early watch threshold lines: `600`
- early watchlist: `0`
- watch threshold lines: `720`
- watchlist: `0`
- hotspots: `1`
- blockers: `0`

This report keeps maintainability risk visible before the Meta Skill grows more gates, renderers, and CLI commands.

## Hotspots

| File | Lines | Kind | Severity | Recommended action |
| --- | ---: | --- | --- | --- |
| `scripts\build_catalog.py` | `1450` | `cli-script` | `warn` | Watch this file before adding new responsibilities; extract a helper module when one concern dominates. |

## Watchlist

No near-threshold files found.

## Early Watchlist

No early watch files found.

## Largest Files

| File | Lines | Kind | Severity |
| --- | ---: | --- | --- |
| `scripts\build_catalog.py` | `1450` | `cli-script` | `warn` |
| `scripts\serve_catalog.py` | `427` | `cli-script` | `pass` |
| `scripts\github_preview.py` | `226` | `internal-module` | `pass` |
| `scripts\import_legacy_catalog.py` | `96` | `cli-script` | `pass` |

## Release Rule

- `block` hotspots should be split before governed release.
- `warn` hotspots can ship only when Review Studio keeps them visible and a reviewer accepts the modularization plan.
- Do not split a file only for line count; split when a stable responsibility boundary is clear.
