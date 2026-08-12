# Workflow

## First build

The default `references/catalog-config.json` has an empty `roots` list by design. Supply roots explicitly or create a user-owned config from the Windows/POSIX examples.

```text
python scripts/build_catalog.py --root <skills-root> --output-dir <output-dir>
python scripts/build_catalog.py --config <config.json> --output-dir <output-dir>
```

Use `--root` repeatedly for multiple roots. A root is a skill root by default; plugin caches must be declared with `{"kind":"plugin"}` in a config file.

## Review

Inspect `catalog.json` before opening the page:

- `summary` and `category_coverage`
- `category_candidates`, `category_winner_margin`, `category_tie_reason`, and `low_confidence`
- `image.missing_evidence` and image status
- `families`, `plugins`, `unresolved_roots`, and `warnings`

The default output hides absolute paths. Use `--include-absolute-paths` only for a local diagnostic build.

## Refresh

`--refresh` is an explicit replacement gate. The local server must be started with the exact startup roots and curation files:

```text
python scripts/serve_catalog.py --output-dir <output-dir> --root <skills-root> --root <plugin-root> --curation <curation.json>
```

The server binds to localhost and rejects a refresh when explicit roots are missing or the curation count does not match the startup catalog. In the detail panel, `选择图片` copies a supported image into `<output-dir>/curated-images/`, writes the matching override to `<output-dir>/catalog-curation.json`, and rebuilds immediately. `恢复自动图` removes that output-owned override. Neither action writes to a scanned root.

## Boundaries

Scanning is read-only for discovered Skills and never executes them. When a local GitHub repository URL is available, the default image pass may read the public repository page and cache one size-limited, signature-checked GitHub image in `<output-dir>/github-image-cache/`. Use `--no-github-images` for an offline build. Remote image URLs found only in a Skill frontmatter remain metadata-only. No category or family is inferred from a guessed repository or description-only ecosystem marker.
