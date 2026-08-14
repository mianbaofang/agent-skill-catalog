# Changelog

## Unreleased

No unreleased changes.

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
