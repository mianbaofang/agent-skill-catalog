# Product Demo

The README preview is a 16:9 product story, not a sequence of unrelated screenshots. It uses the same restrained off-white canvas, deep teal controls, muted slate and ochre accents, and compact evidence labels as the catalog UI.

## Storyboard

1. **The problem**: a growing Skill library hides the difference between a standalone Skill, a parent family, and a plugin bundle.
2. **The scan contract**: explicit local roots enter a read-only pipeline; the roots themselves are never edited or executed.
3. **The evidence map**: frontmatter, manifests, source paths, sibling structure, curation, and GitHub metadata are combined into reviewable classification evidence.
4. **The family and plugin map**: a parent Skill stays one catalog item while child Skills appear in its detail; plugin aggregates move to a separate view.
5. **The image path**: output-owned manual override → verified public GitHub repository preview → Skill-provided local preview → generated fallback marked `missing evidence`. Skill-provided remote image URLs remain metadata-only.
6. **The result**: the real generated catalog shows category filtering, search, family detail, invocation, evidence labels, plugin separation, GitHub links, and the manual image controls.

## Animation acceptance

`docs/media/agent-skill-catalog-demo.gif` must remain:

- exactly `960x540` pixels (`16:9`)
- exactly `5 fps`
- `20-60` seconds long
- no larger than `8 MiB` (target `6 MiB` or less)
- a continuous narrative with animated information graphics and a real product interaction segment
- readable at README width, with no stretched source ratio

The animation is allowed to use explanatory text, process diagrams, evidence cards, and annotated transitions. The functional UI segment must be captured from the generated catalog, while explanatory graphics must stay faithful to the implemented scan contract.

## Visual and copy system

- Use one type system: Segoe UI / Microsoft YaHei with the catalog's dark ink, deep teal, slate, ochre, and coral accent colors.
- Keep explanatory copy short and factual. Each claim must map to the current Skill workflow or a visible UI state.
- Use real catalog cards and detail states for the final-effect section. Do not use category fallback covers as if they were Skill-specific screenshots.
- Explain image provenance visibly: manual output override first, then verified GitHub repository preview, then Skill-provided local evidence, and finally `missing evidence` when proof is absent.
- Keep the README hero, screenshots, animation title, labels, and terminology aligned. If the UI changes, regenerate the animation and screenshot gallery together.

## Media source boundary

The committed animation and screenshots contain no private machine paths or personal Skill inventory. The animation's information graphics are original documentation artwork; the final product frames were captured from a generated local catalog. Demo Skill records are not included in the repository or the installable package.

## Re-recording

The source storyboard is [`docs/media/demo-storyboard.html`](media/demo-storyboard.html). Serve a non-personal local catalog, then record it:

```powershell
node tools/record_demo.mjs http://127.0.0.1:8768/index.html
```

The supplied catalog must not expose personal paths or a private Skill inventory. This documentation-only recording tool requires Playwright and FFmpeg in the maintainer environment. Neither is a runtime dependency of the installed Skill.
