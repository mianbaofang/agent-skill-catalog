# Changelog

## 0.5.1 - 2026-11-14

- Add the explicit `--follow-linked-dirs` opt-in to also scan skills reached through Windows junctions or directory symlinks, report every skipped link in the build output instead of silently dropping it, and give followed links unique identities so same-named skills do not collapse into one entry; guard POSIX symlink loops with a visited-directory set. A real 474-skill directory that previously collapsed to 466 entries now scans fully and deterministically.
- Lead both READMEs with the verified `npx skills add mianbaofang/agent-skill-catalog` install line and add the real-catalog intro film preview.
- Keep Skill-provided frontmatter and sidecar preview images inside the Skill's own folder, so a scanned `SKILL.md` cannot read an arbitrary local image from outside the selected root.
- Skip `SKILL.md` files that resolve outside the explicit scan root, including files reached through a Windows directory junction or a directory symlink.
- Check a local image's size before reading it into memory, so an oversized preview is rejected without allocating the whole file.
- Place the reproducible demo's banner and guide markup inside `<body>` instead of after the charset meta in `<head>`; keep the `noindex` meta in the document head and regenerate `docs/demo`.
- Reject foreign `Host` and cross-site `Origin` values on the local catalog server, so a DNS-rebinding or CSRF page cannot drive refresh, image, or delete endpoints.
- Escape an HTML comment opener in the embedded catalog payload so untrusted Skill text cannot put the inline script into an escaped parser state.
- Read UTF-8 BOM JSON and `SKILL.md` files on Windows, including the server's config and output curation, instead of dropping frontmatter or overwriting existing curation.
- Fail fast when an explicitly requested `--curation` file is missing instead of silently building without it.
- Prefer the Git `origin` remote over submodule or upstream URLs when inferring a Skill repository, and let a later curation category override win an exact selector tie.
- Add regression coverage for the image path boundary, linked-directory scan boundary, oversized-image rejection, demo banner placement, BOM inputs, missing curation, Git remote preference, category tie-breaking, payload escaping, and server request-origin checks.

## 0.5.0 - 2026-11-13

- Prefer the images a Skill already ships: frontmatter, sidecar files, and its local README (Markdown and HTML) are read before any GitHub request, and original GIF/WebP bytes are preserved.
- Request GitHub images only for entries that still have no local image, and keep the generated category cover explicitly labelled when nothing is available.
- Render every card cover and detail image in a uniform 16:9 frame with the whole original visible, instead of mixing portrait and landscape heights.
- Group standalone Skills installed from the same GitHub repository into one family even when their names share no prefix; plugins stay in a separate view and manual family overrides still win.
- Add optional Agent-owned public introduction research (`description_queue.py next --web-research`) with persisted source URL, title, retrieval date, and identity evidence shown as links in the detail dialog.
- Fix repository inference that could mistake an installer repository mentioned in a README for the Skill's own source; prefer an explicit source or a unique git clone URL.
- Fix the invocation text so a Skill whose path already ends in `SKILL.md` no longer renders "SKILL.md 的 SKILL.md".
- Rebuild the reproducible public demo and refresh the README screenshots; extend regression coverage for local README previews, repository families, sourced introductions, and installation-source inference.


## 0.4.0 - 2026-11-12

- Separate fast offline preview from optional completed Chinese descriptions.
- Serve the catalog correctly while offline and keep Skill deletion off unless it is explicitly enabled.
- Improve desktop search, category filters, and detail dialogs.
- Open a record's detail dialog from its card cover, its title, or its action button, so each entry point reaches the same native detail view.
- Show a copy-invocation button in the detail dialog that reports clipboard failures honestly instead of claiming success when the browser blocks clipboard access.
- Caption every detail-gallery image with its provenance so a generated category placeholder is never presented as a Skill-specific screenshot.
- Add a compact, collapsible operation-guide banner to the public demo page, whose buttons drive the demo's own search, mode, category, and detail controls; the banner is specific to the public demo and is not added to every generated catalog page.
- Add a real public `agent-skill-catalog` reference record to the synthetic demo with a documentation-derived animated preview, so the moving-preview capability is visible offline while it is labelled honestly as a derived snapshot of the project's own promo animation and the fictional fixtures stay on generated fallbacks.
- Generate a reproducible synthetic demo catalog that preserves same-name Skill collisions and shows a curated family and plugin grouping.
- Add three bilingual task guides covering the primary install path, offline builds, and cross-folder skill and plugin inventories.
- Compile every Skill script and repository tool in CI from the directories that hold them, so newly added scripts are checked without editing the workflow.
- Syntax-check the documentation demo recorder and verify demo and documentation reproducibility on every push and pull request, failing the build when the committed demo no longer matches its generator.
- Publish the GitHub Pages site only after the test suite passes and the committed demo and documentation are confirmed reproducible, preventing a deploy from a mismatched generator.
- Limit Pages publishing and identity-token permissions to the deploy job, so validation tests run without the ability to publish the site.

## 0.3.6 - 2026-08-18

- Batch missing-repository discovery in groups of five, reuse authenticated GitHub CLI credentials in memory, and require a unique high-confidence match before associating a repository.
- Cache failed GitHub image lookups and compiled family patterns so repeated catalog refreshes avoid redundant network requests and regex work.
- Strengthen package-family aggregation for Tavily, CloudBase, HyperFrames, and similar multi-Skill bundles while preserving the correct parent repository and preview image.
- Refresh the desktop catalog UI with illustrated category navigation, independently scrollable detail panes, manual preview controls, and deletion behind a second confirmation.

## 0.3.5 - 2026-08-17

- Add the exact `local skill catalog` discovery phrase to the English README's first screen.
- Clarify the Skill trigger as a searchable catalog for Codex and other AI agents, including GitHub preview images.
- Reduce the Skill entry instructions below the Yao Meta initial-load budget without removing the description queue or read-only safety gates.

## 0.3.4 - 2026-08-15

- Ignore legacy `missing-evidence` GitHub README cache entries so a previous transient failure can be retried automatically on the next description batch.
- Clamp configured GitHub README request timeouts to at least one second before passing them to the description queue.
- Add regression coverage for legacy failure-cache invalidation and non-positive timeout values.

## 0.3.3 - 2026-08-15

- Increase bounded GitHub repository preview and README evidence request timeouts to 15 seconds while preserving explicit configuration overrides, host allowlists, response-size limits, and offline operation.
- Pass the configured README timeout through the description queue and leave transient GitHub README failures retryable instead of caching them for seven days.
- Make the invoking Agent explicitly responsible for completing the resumable Chinese description queue instead of handing batch writing or application back to the user.
- Add regression coverage for the default preview and README timeouts and for explicit preview-timeout overrides. This improves tolerance of slower GitHub responses but does not guarantee retrieval when GitHub or the network is unavailable.

## 0.3.2 - 2026-08-15

- Deduplicate repository-backed copies of the same Skill across scan roots while preserving every observed location, and keep same-named members from different plugins separate.
- Aggregate repository-backed `gsap`, `hyperframes`, `research`, `story`, and similar parent/child families even when their folders are split across roots.
- Fetch each observed GitHub repository preview once per build and reuse that evidence for matching Skill, family, and plugin records.
- Add a resumable `description_queue.py next/apply` workflow that supplies bounded local `SKILL.md` and GitHub README evidence, validates Agent-written Chinese descriptions, and stores completed batches under a unique curation key.
- Require CI and package validation to include the description queue, its completion gate, and the complete test suite.

## 0.3.1 - 2026-08-14

- Restored GitHub repository discovery from installation locks, plugin and package metadata, explicit Skill links, and local Git remotes so installed Skills can use observed repository evidence instead of a category placeholder.
- Cache a verified public GitHub repository preview for observed sources, recover from partial GitHub README responses, and keep the strongest verified member image on family and plugin aggregate cards.
- Require the invoking Agent to complete the Chinese description queue before reporting a catalog complete; the documented first build and local refresh endpoint now use `--require-complete-descriptions`.
- Moved maintainer-only evaluation fixtures and release evidence outside the GitHub-installed Skill boundary, so source installs and release ZIPs contain runtime files only.
- Added a bilingual GitHub Pages discovery surface with canonical metadata, Open Graph/Twitter previews, JSON-LD, robots.txt, sitemap.xml, and llms.txt.
- Added a Pages metadata regression check and a deploy workflow; the public site uses only the repository's sanitized demo media.

## 0.3.0 - 2026-08-14

- Added separate factual capability labels beneath the four operational status badges in both READMEs.
- Added a fully English README animation while keeping the Chinese animation for `README.zh-CN.md`.
- Made the demo recorder support explicit language, storyboard, catalog, and output arguments, with Chinese-text guards for English recordings.
- Fixed GitHub repository detection for the nested `metadata.github-repo` fields injected by `gh skill install`.
- Added explicit GitHub URL discovery from local `SKILL.md` body text without guessing a repository.
- Added `description-enrichment.json`, per-item review reasons, and a required Agent curation loop for missing, short, or non-Chinese descriptions.
- Accepted UTF-8 BOM in Windows-edited JSON configuration and curation files.
- Added clean-install regression coverage proving that observed GitHub sources drive repository previews and that the description queue closes after output-owned curation.

## 0.2.2 - 2026-08-12

- Kept the authoritative GitHub-discoverable Skill under `skills/agent-skill-catalog/`, matching `gh skill publish` validation.
- Added public GitHub repository preview retrieval with allowlisted hosts, size limits, image-signature checks, output caching, and an offline switch.
- Added detail-view controls to choose a manual preview image, save it in the catalog output, and restore the automatic image.
- Reused each unique GitHub repository preview during a build and extended Windows output replacement retries.
- Added end-to-end tests for Skill discovery, image upload, refresh, and rollback.

## 0.2.1 - 2026-08-11

- Restored conservative family aggregation for packages installed as sibling root folders, such as `gsap`, `hyperframes`, `research`, and `story`.
- Require a same-named root Skill, at least two sibling children, and no conflicting observed GitHub repository before inferring a family.

## 0.2.0 - 2026-08-11

- Moved the installable source to `skills/agent-skill-catalog/` so it is discoverable by `gh skill publish` and `gh skill install`.
- Added the required published-Skill license declaration and the recommended Codex UI metadata in `agents/openai.yaml`.
- Separated repository documentation and development tooling from the installable Skill package.

## 0.1.0 - 2026-08-11

- Initial public source release of the local-first Agent Skill Catalog.
- Added deterministic scanning, scoped category evidence, family and plugin aggregation, image-evidence labels, and a self-contained desktop UI.
- Added standard-library tests, package validation, release packaging, and generic metadata.
