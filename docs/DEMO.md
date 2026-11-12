# Product Demo

The README preview is a 16:9 product story, not a sequence of unrelated screenshots. It uses the same restrained off-white canvas, deep teal controls, muted slate and ochre accents, and compact evidence labels as the catalog UI.

## Where the demo comes from

- **Synthetic fixtures are committed.** The demo library lives in
  [`examples/demo-library`](../examples/demo-library/README.md) as original, synthetic
  example data. Every fixture is committed as `SKILL.md.example` (never `SKILL.md`) so the
  copies are visibly non-installable templates and are never discovered as repository Skills.
- **The committed demo is a build artifact.** `tools/build_demo.py` copies the fixtures into an
  isolated temp tree, restores real `SKILL.md` names there, and runs the real scanner offline.
  It then pins the timestamp to a documented build epoch and re-maps every path and id onto
  portable logical roots (`<demo-root>/<label>`), so the committed output is byte-stable and
  free of machine-specific paths. It writes only its own known files into `docs/demo`.
- **`docs/demo` is not part of the installed Skill.** The generated catalog is documentation
  shipped in the repository only; the packaged Skill installs `SKILL.md`, its scripts,
  references, and security policies, not `docs/demo` or `examples/`.
- **The fixtures are labelled.** Each fixture body carries a visible boundary note (合成演示
  data, no runnable implementation), and the generated page adds a `noindex` meta plus a
  visible "Demo data / 演示数据" banner.

## The demo page is a standalone static file

`docs/demo/index.html` is a self-contained page that runs offline from a direct `file://` open.
It performs no fetches, starts no server, mutates no data, and writes nothing. Its only
interactions are the in-page search, category filter, detail dialog, and plugin view. Because it
uses `--no-github-discovery --no-github-images`, it contains no live manual image editor, no
GitHub fetch, and no installation step; every image is either a generated category fallback
(labelled as such, never presented as a Skill-specific preview) or no image at all.

## Storyboard

The recorder's timeline, driven by real interactions against the generated catalog:

1. **Intro card**: the synthetic roots this demo was generated from, and a note that the
   interface below is the product's native Chinese UI, captured unmodified.
2. **Catalog overview**: all Skills and families in one grid, each with purpose, source, and
   image evidence.
3. **Real search**: typing a genuinely multi-member family name narrows the grid to that
   family's bundled Skills.
4. **Entry detail**: the detail dialog shows purpose, how to invoke it, source location, and
   classification evidence.
5. **Plugin view**: plugin aggregates move to a separate view, keeping their bundled Skills
   apart from families.
6. **Closing card**: a short call to open an entry and see where it belongs.

The catalog interaction is genuine; the only added pixels are clearly separate annotation
overlays (intro card, narration band, closing card) that sit above the page and never restyle
or replace product UI.

## Animation acceptance

Both README animations must remain:

- English: `docs/media/agent-skill-catalog-demo.en.gif`
- Chinese: `docs/media/agent-skill-catalog-demo.gif`

- exactly `960x540` pixels (`16:9`)
- exactly `5 fps`
- `20-60` seconds long
- no larger than `8 MiB` (target `6 MiB` or less)
- a continuous narrative with animated information graphics and a real product interaction segment
- readable at README width, with no stretched source ratio

The animation is allowed to use explanatory text, process diagrams, evidence cards, and
annotated transitions. The functional UI segment must be captured from the generated catalog,
while explanatory graphics must stay faithful to the implemented scan contract.

## Visual and copy system

- Use one type system: Segoe UI / Microsoft YaHei with the catalog's dark ink, deep teal,
  slate, ochre, and coral accent colors.
- Keep explanatory copy short and factual. Each claim must map to the current Skill workflow or
  a visible UI state.
- Use real catalog cards and detail states for the final-effect section. Do not use generated
  category fallback covers as if they were Skill-specific screenshots.
- Explain image provenance visibly: manual output override first, then verified GitHub
  repository preview, then Skill-provided local evidence, and finally `missing evidence` when
  proof is absent. The offline demo exercises the `missing evidence` / generated-fallback path.
- Keep the README hero, screenshots, animation title, labels, and terminology aligned. If the
  UI changes, regenerate the animation and screenshot gallery together.

## Media source boundary

The committed animation and screenshots contain no private machine paths or personal Skill
inventory. The animation's information graphics are original documentation artwork; the final
product frames were captured from the generated local demo catalog. The synthetic fixtures are
committed as `SKILL.md.example` templates and the generated demo catalog is committed as
repository documentation, but no demo Skill record is included in the installable Skill package.

## Re-recording

Regenerate the offline demo catalog, then record both languages straight from the committed
static file (no server, no network):

```bash
python tools/build_demo.py                       # rebuild docs/demo from the fixtures
node tools/record_demo.mjs --lang en --catalog docs/demo/index.html
node tools/record_demo.mjs --lang zh --catalog docs/demo/index.html
```

`--catalog` accepts a path (resolved relative to the repo, opened as a `file://` URL) or an
explicit `http(s)://`/`file://` URL if you prefer to serve the catalog. Add
`--screenshots-dir docs/media` to (re)capture the native-UI stills (`overview`, `filter`,
`detail`) instead of the animation; stills are shot without the annotation overlay, so the same
files serve both the English and Chinese docs.

This documentation-only recorder requires Playwright and FFmpeg in the maintainer environment;
neither is a runtime dependency of the installed Skill. Set `PLAYWRIGHT_MODULE` to point at a
Playwright install if it is not on the default resolution path. The storyboard
[`docs/media/demo-storyboard.html`](media/demo-storyboard.html) is a reference copy guide only;
`tools/record_demo.mjs` is the source of truth for both the animation and the screenshots.
