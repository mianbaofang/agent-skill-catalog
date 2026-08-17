---
name: agent-skill-catalog
description: "Build or refresh a local searchable skill catalog for Codex and other AI agents from explicit SKILL.md roots and optional plugin roots. Use for deterministic catalog JSON, desktop HTML, category evidence, GitHub preview images, family grouping, plugin aggregation, and bounded local refresh. Do not install, edit, or execute scanned skills."
license: MIT
---

# Agent Skill Catalog

Build a read-only catalog from explicit local `SKILL.md` roots and optional
plugin roots. Never install, edit, or execute scanned content. Observed GitHub
repositories may provide bounded preview images and README evidence; write only
to the selected output directory.

## Workflow

The invoking Agent owns the description queue and must complete its `next`/`apply`
loop; never hand it to the user.

1. Choose `--root PATH`, or a config labeling each root `skill` or `plugin`.
2. Run `python scripts/build_catalog.py --root PATH --output-dir OUTPUT --require-complete-descriptions`.
3. On exit code 3, run `python scripts/description_queue.py next --root PATH --output-dir OUTPUT --batch-size 12` (reuse `--config` when applicable).
4. Write evidence-backed Chinese results to `OUTPUT/description-batch.responses.json` using `response_contract`, then run `python scripts/description_queue.py apply --output-dir OUTPUT --input OUTPUT/description-batch.responses.json`. Repeat until `batch_count` is zero; progress stays in `catalog-curation.json`.
5. Rebuild with `--refresh --require-complete-descriptions`; success means exit 0 and `summary.pending_description_count == 0`.
6. Check `summary.image_evidence` and every `image.status`; use only observed GitHub sources.
7. Open `index.html`, or serve it with `python scripts/serve_catalog.py --output-dir OUTPUT --root PATH --require-complete-descriptions`.

## Output Contract

The output directory contains `catalog.json`, `description-enrichment.json`, a
self-contained `index.html`, and output-owned image/curation files. Absolute
roots stay redacted unless `--include-absolute-paths` is explicit.

## Boundaries

- No remote code execution and no writes to scanned roots.
- GitHub reads are HTTPS-only, host-allowlisted, size-limited, and limited to observed repositories. Use `--no-github-images` or `--no-github-readmes` offline.
- Manual images live in output-owned `curated-images/` and `catalog-curation.json`; unavailable proof stays `missing evidence`.
- Do not infer category or family from description alone. A sibling family needs a same-named root Skill, at least two same-prefix siblings, and no conflicting observed repository; otherwise use explicit curation.
- Refresh reuses recorded roots, config, and curation. The queue validates Agent-written Chinese copy; it does not call a hidden model or require a provider key.

## Resources

Read `references/workflow.md` first; load other references only for the matching
configuration, category, image, or prompt task. Maintainer-only evals and release
evidence stay outside the installed Skill boundary.
