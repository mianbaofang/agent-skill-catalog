# Changelog

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
