---
name: agent-skill-catalog
description: "Build or refresh a local searchable Agent Skill Catalog from explicit SKILL.md roots and optional plugin roots. Use for deterministic catalog JSON, desktop HTML, category evidence, image evidence, family grouping, plugin aggregation, and bounded local refresh. Do not install, edit, or execute scanned skills."
license: MIT
---

# Agent Skill Catalog

Build a read-only catalog from explicitly supplied local `SKILL.md` roots and
optional plugin roots. Scanned roots are never installed, edited, or executed.
Observed GitHub repositories may provide bounded preview images and README
evidence; output caches are the only write target.

## Workflow

The invoking Agent owns the description queue end to end: it must complete the
`next`/`apply` loop itself and must not hand the queue to the user for manual
writing or completion.

1. Choose roots with `--root PATH`, or a config that labels each root `skill` or `plugin`.
2. Run `python scripts/build_catalog.py --root PATH --output-dir OUTPUT --require-complete-descriptions`.
3. If exit code 3 reports pending copy, the invoking Agent must run `python scripts/description_queue.py next --root PATH --output-dir OUTPUT --batch-size 12` (use the same `--config` for config builds).
4. The invoking Agent must write evidence-backed Chinese results to `OUTPUT/description-batch.responses.json` using its `response_contract`, then run `python scripts/description_queue.py apply --output-dir OUTPUT --input OUTPUT/description-batch.responses.json`. Repeat until `batch_count` is zero; progress resumes from `catalog-curation.json`. Do not ask the user to write, apply, or complete a batch.
5. Rebuild with `--refresh --require-complete-descriptions`; success requires exit code 0 and `summary.pending_description_count == 0`.
6. Check `summary.image_evidence` and every `image.status`. Use only observed GitHub sources; verified family/plugin members keep the strongest image.
7. Open `index.html`, or serve it with `python scripts/serve_catalog.py --output-dir OUTPUT --root PATH --require-complete-descriptions`.

## Output Contract

The output directory contains `catalog.json`, `description-enrichment.json`, a
self-contained `index.html`, and output-owned image/curation files. Absolute
roots are redacted unless `--include-absolute-paths` is explicitly requested.

## Boundaries

- No remote code execution and no writes to scanned roots.
- GitHub reads are HTTPS-only, host-allowlisted, size-limited, and restricted to observed repositories. Use `--no-github-images` or `--no-github-readmes` for offline evidence collection.
- Manual images live in output-owned `curated-images/` and are recorded in `catalog-curation.json`; unavailable proof stays `missing evidence`.
- Do not infer a category or family from a description alone. A rooted sibling family needs a same-named root Skill, at least two same-prefix siblings, and no conflicting observed repository; otherwise use explicit curation.
- Refresh reuses the recorded startup roots, config, and curation. The queue validates Agent-written Chinese copy and does not call a hidden model or require a provider key.

## Resources

Read `references/workflow.md` first. Load the other `references/` files only for
the matching configuration, category, image, or prompt task. Maintainer-only
evals and release evidence live outside the installed Skill boundary.
