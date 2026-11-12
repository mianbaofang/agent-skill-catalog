---
name: agent-skill-catalog
description: "Build or refresh a local searchable skill catalog for Codex and other AI agents from explicit SKILL.md roots and optional plugin roots. Use for deterministic catalog JSON, desktop HTML, category evidence, GitHub preview images, family grouping, plugin aggregation, and bounded local refresh. Do not install, edit, or execute scanned skills."
license: MIT
---

# Agent Skill Catalog

Build a read-only catalog from explicit local `SKILL.md` roots and optional
plugin roots. Never install, edit, or execute scanned content. Write only
to the selected output directory.

Two build outcomes exist; name the one you are delivering:

- **Preview**: `build_catalog.py` with explicit roots and, for a fully offline
  run, `--no-github-discovery --no-github-images`. Success is exit code 0 with a
  readable `index.html`; missing Chinese descriptions stay pending and are not a
  failure.
- **Enriched completion** (only when the user asks for full Chinese
  descriptions): add `--require-complete-descriptions`, complete the Agent-owned
  description queue, then rebuild. Success is exit code 0 **and**
  `summary.pending_description_count == 0`; exit code 3 means that mode is not
  finished yet, not that the tool crashed.

Network is optional and off only when the flags above are used. Unless disabled,
a family-primary Skill without repository metadata triggers a bounded GitHub
search by Skill name (`api.github.com`), candidate repository checks, public
repository page reads for preview images, and one README excerpt per queue item.
Discovery and preview reads may reuse an existing `gh`/token login and never save
credentials. Use the offline flags when the library must stay off the network.

## Workflow

Quick preview of the roots the user named (default first response):

1. Choose `--root PATH`, or a config labeling each root `skill` or `plugin`.
2. Run `python scripts/build_catalog.py --root PATH --output-dir OUTPUT --no-github-discovery --no-github-images`.
3. Report exit code 0 and open `OUTPUT/index.html`; state that Chinese descriptions are still pending and that no network was used.

Enriched completion, only when the user asked for full Chinese descriptions. It
still uses the offline flags unless the user separately accepts GitHub network
reads; asking for descriptions is not consent to discovery, images, or README
fetches:

4. Run `python scripts/build_catalog.py --root PATH --output-dir OUTPUT --refresh --require-complete-descriptions --no-github-discovery --no-github-images` (reuse `--config` for config builds; `--refresh` is required when `OUTPUT` already holds a catalog).
5. On exit code 3, run `python scripts/description_queue.py next --root PATH --output-dir OUTPUT --batch-size 12 --no-github-readmes` (reuse `--config` when applicable; drop the offline flags only when the user explicitly accepts those GitHub reads).
6. Write evidence-backed Chinese results to `OUTPUT/description-batch.responses.json` using `response_contract`, then run `python scripts/description_queue.py apply --output-dir OUTPUT --input OUTPUT/description-batch.responses.json`. Repeat until `batch_count` is zero; progress stays in `catalog-curation.json`.
7. Rebuild with `--refresh --require-complete-descriptions` plus the same offline flags; success means exit 0 and `summary.pending_description_count == 0`.
8. Check `summary.image_evidence` and every `image.status`; use only observed GitHub sources.
9. Open `index.html`, or serve it with `python scripts/serve_catalog.py --output-dir OUTPUT --root PATH --require-complete-descriptions` (add the same offline flags to keep refreshes offline).

## Images and optional public introductions

Select actual Skill images before GitHub: manual/configured override, local frontmatter, sidecars, then local README images. Fetch GitHub images only for remaining gaps. All cover frames are 16:9; preserve originals and animation. See `references/image-priority.md`.

When the user requests public introductions and the invoking Agent has web access, prepare `python scripts/description_queue.py next --root PATH --output-dir OUTPUT --web-research --no-github-readmes` (or use the matching config). The Agent uses its available search/browser tools, opens exact-identity matches, and returns the batch contract with `web_research: true`, factual Chinese descriptions, and `sources` containing URL, title, retrieval date and identity evidence. Apply with the normal `apply` command and rebuild with the same roots/config. The details show clickable introduction sources. This mode includes Skills whose local description was already complete.

The Python scripts do not contain a search engine, invoke hidden models, or require a provider key. Search is supplied by the Agent runtime. If it cannot browse, or no exact match is verified, leave that research item unresolved and retain its local description. A normal offline preview never triggers public research.

## Output Contract

The output directory contains `catalog.json`, `description-enrichment.json`, a
self-contained `index.html`, and output-owned image/curation files. Absolute
roots stay redacted unless `--include-absolute-paths` is explicit.

## Boundaries

- The Agent, builder, and scanner never modify scanned roots: no installs, edits, deletions, or writes outside the selected output directory. The only source-writing feature in the product is an explicit, opt-in localhost-server deletion described below, which requires operator configuration and full-name confirmation and is never triggered by scanning, building, image selection, or refresh.
- Network is opt-out, not opt-in. Without the flags below, a build may search GitHub by Skill name, verify candidate repositories, read public repository pages and images for observed repositories, and read one README excerpt per queue item; these reads may reuse an existing local `gh`/token login and never store credentials. Use `--no-github-discovery --no-github-images` for an offline build; the description queue additionally needs `--no-github-readmes`.
- The optional localhost server offers an explicit, opt-in deletion action for one top-level standalone Skill: it runs only when the serving config marks that root `allow_delete: true`, the item is an independent top-level Skill, and the request confirms the full Skill name. It is disabled by default in every shipped config, including the Windows example. Never enable it unless the user asks, and a deleted Skill directory is removed from its root. The shipped static page and CLI defaults never delete anything.
- Manual images live in output-owned `curated-images/` and `catalog-curation.json`; unavailable proof stays `missing evidence`.
- Skills with the same observed or verified GitHub repository automatically share a family, including independently named Skills without a parent router. Details retain every member and its invocation. Nested entry-point and explicit product-affiliation evidence also remain supported. Different repositories, plugin identities, and unverified same-name matches stay separate; manual family overrides win.
- Refresh reuses recorded roots, config, and curation; HTTP callers cannot supply roots, config, or command arguments. The queue validates Agent-written Chinese copy; these Python scripts never call a hidden model or require a provider key. The Agent runtime that writes that copy is a separate boundary: it may send local Skill evidence to its own model provider, so only the fully offline script preview (`--no-github-discovery --no-github-images`, with `--no-github-readmes` for the queue) is a claim that this tool makes no network request.

## Resources

Read `references/workflow.md` first; load other references only for the matching
configuration, category, image, or prompt task. Maintainer-only evals and release
evidence stay outside the installed Skill boundary.
