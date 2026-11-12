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

### One real public reference among the synthetic examples

`agent-skill-catalog` (under `examples/demo-library/roots/community-skills/`) is a **real
public reference**, not a synthetic example. Its name and repository link point at the actual
`mianbaofang/agent-skill-catalog` project, and it carries a **real animated preview** so the
key selling point — a card playing a moving project preview — is visible offline. Everything
about it is disclosed honestly:

- The preview `preview.gif` is **documentation-derived**: a short clip sampled and scaled down
  from this project's own promo animation `docs/media/agent-skill-catalog-demo.gif`. Its full
  provenance (source SHA256, derived SHA256, frame count, derivation, MIT license) is recorded
  in `examples/demo-library/media/agent-skill-catalog-preview.manifest.json`.
- It is **not** presented as a runtime GitHub README auto-capture. The scanner embeds it through
  its supported `verified-local` frontmatter path (labelled “Skill 自带图片”), never as
  `github-repository`, and the fixture text states it is a documentation-derived snapshot.
- The remaining eight fixtures stay **synthetic** with `generated-fallback` category
  placeholders. The generated page keeps the real reference visually and textually separate, so
  a fictional Skill is never shown wearing a real project's preview.

## The demo page is a standalone static file

`docs/demo/index.html` is a self-contained page that runs offline from a direct `file://` open.
It performs no fetches, starts no server, mutates no data, and writes nothing. Its only
interactions are the in-page search, category filter, detail dialog, and plugin view. Because it
uses `--no-github-discovery --no-github-images`, it contains no live manual image editor, no
GitHub fetch, and no installation step; apart from the one real public reference described above
(which carries its own committed animated preview), every other image is a generated category
fallback (labelled as such, never presented as a Skill-specific preview) or no image at all.

### What the in-page interactions actually do

- **Open a detail entry** from a card's cover, its title, or its `查看详情` action button; each
  opens the same native detail dialog for that record.
- **Detail dialog** shows the invocation line with a `复制调用` copy button, the image gallery,
  the bundled sub-skills, the source locations, and the classification evidence.
- **Image gallery** shows the larger project images for the record and its bundled skills. Each
  gallery figure is captioned with its provenance (`自动生成封面` for the offline synthetic
  fixtures, `Skill 自带图片` for the real `agent-skill-catalog` reference), so a generated
  category placeholder is never presented as a Skill-specific screenshot and the real animated
  reference is never passed off as a synthetic example.
- **Copy invocation** first tries the Clipboard API, then a selected-text fallback inside the
  detail dialog. If both copy methods fail, it leaves the invocation selected for manual Ctrl+C
  and reports that copying was not completed. A `file://` open may lack the Clipboard API; the
  fallback can still succeed.
- **Search, category filter, and the plugin view** all operate on the generated catalog data
  only.

Only the public demo page ships a compact, **collapsible guide banner** (`操作指南`) above the
product UI. It is collapsed by default and occupies about 55 pixels on the recorded desktop
viewport. Its action buttons (`试试搜索`, `看家族详情`, `看插件`, `重置演示`) drive the page's own
native controls — the search input, the mode/category buttons, and the real per-record detail
button. A visible note explains the mixture of synthetic fixtures and one real public reference;
the demo is marked `noindex`. The guide also states that refresh, image save, and delete need a
real local catalog service and are not simulated in the static page.

## Storyboard

The v0.4.0 film is driven by real interactions against the generated catalog, captured from the
page's native Chinese UI. The moving preview is on screen from the first frames — there is no
title-only intro:

1. **Catalog overview**: the full grid, with the real `agent-skill-catalog` entry's animated
   preview already playing among the static synthetic covers.
2. **Entry detail**: opening the reference entry shows its purpose, invocation, source location,
   and classification evidence; the animated preview keeps playing in the detail gallery.
3. **Zoom**: `放大查看` opens the enlarged preview, still animating.
4. **Copy invocation**: back in detail, the `复制调用` button reports its result honestly.
5. **Real search**: typing `note-keeper` narrows the grid to that 3-member family.
6. **Plugin view**: `toolkit` keeps its 2 bundled Skills in a separate view.
7. **Call to action**: back to the full catalog — search, filter, inspect invocation.

The composition reframes the captured catalog with a code-driven camera, adds one narration
band, and shows a huashu-motion signature in the last 1.2 seconds. The underlying product
controls and content are captured from the actual generated page.

## Animation acceptance

The v0.4.0 README animations are versioned so they never collide with cached older assets:

- English: `docs/media/agent-skill-catalog-demo.en.v0.4.0.gif`
- Chinese: `docs/media/agent-skill-catalog-demo.v0.4.0.gif`

Both are exactly `960x540` pixels (`16:9`), `5 fps`, `22.6` seconds, and about `6.6 MiB`
(under the `8 MiB` ceiling). They are produced by a **huashu-motion composition**
(`out/catalog-v040-motion/`, GSAP + the huashu-motion `OM` runtime): a code camera reframes the
genuine built-in-browser recording of the generated catalog, and a single narration band carries
the captions. The film seeks a 10 fps PNG sequence decoded from the real 15 fps capture, so every
frame is a pure function of time (no clock, no unseeded random). The English variant is the same
composition opened with `?lang=en`, which swaps only the seven caption strings — the real frames,
camera and timing are identical to the Chinese pass. The functional UI segment is captured from
the generated catalog; the animated project preview is the real public reference described above,
not a generated placeholder and not an auto-fetch. An editable source excerpt
(`index.html`, `materials.md`, `treatment.md`) is staged at
[`docs/media/motion-v0.4.0/`](media/motion-v0.4.0/). The excerpt excludes vendor runtime, fonts, recordings, and decoded frames; it is not a
standalone reproducible project. Capture provenance, sampling, and per-file
metrics are recorded in
[`docs/media/capture-manifest.v0.4.0.json`](media/capture-manifest.v0.4.0.json).

The static screenshots are likewise versioned (`agent-skill-catalog-overview|filter|detail`
with a `.v0.4.0` / `.en.v0.4.0` suffix); the native Chinese UI is identical for both languages,
so each zh and en still is byte-identical.

## Visual and copy system

- Use one type system: Segoe UI / Microsoft YaHei with the catalog's dark ink, deep teal,
  slate, ochre, and coral accent colors.
- Keep explanatory copy short and factual. Each claim must map to the current Skill workflow or
  a visible UI state.
- Use real catalog cards and detail states for the final-effect section. Do not use generated
  category fallback covers as if they were Skill-specific screenshots.
- Explain image provenance visibly: manual output override first, then verified GitHub
  repository preview, then Skill-provided local evidence, and finally `missing evidence` when
  proof is absent. The offline demo exercises verified-local animation and generated fallback covers.
- Keep the README hero, screenshots, animation title, labels, and terminology aligned. If the
  UI changes, regenerate the animation and screenshot gallery together.

## Media source boundary

The committed animation and screenshots contain no private machine paths or personal Skill
inventory. The animation's information graphics are original documentation artwork; the final
product frames were captured from the generated local demo catalog. The synthetic fixtures are
committed as `SKILL.md.example` templates and the generated demo catalog is committed as
repository documentation, but no demo Skill record is included in the installable Skill package.

## Re-recording

The shipped v0.4.0 films are **not** produced by `tools/record_demo.mjs`. They come from the
huashu-motion composition, recorded with ZCode's built-in In-app Browser and encoded with FFmpeg
(see the capture manifest's `verification` block for exactly which `om` checks ran and which were
skipped because they need the user's Chrome). The composition lives in `out/catalog-v040-motion/`;
an editable source excerpt is committed at `docs/media/motion-v0.4.0/`.

To regenerate the offline demo catalog that the film records:

```bash
python tools/build_demo.py                       # rebuild docs/demo from the fixtures
```

Using the full local project with its vendor files, fonts, and captured frames, serve
`out/catalog-v040-motion/` over localhost. Open `/index.html` for Chinese or
`/index.html?lang=en` for English in the built-in In-app Browser, play the `film` timeline
from frame 0, and capture about 26 seconds at 1280x720/15 fps. Encode with FFmpeg
(`fps=5, scale=960:540, palettegen/paletteuse`) to the versioned filenames above. The six native-UI
stills are captured separately and are shared by both languages.

`tools/record_demo.mjs` (Playwright + FFmpeg) is retained for maintainers as an alternative
documentation-only recorder; it did **not** produce the v0.4.0 animations. It requires Playwright
and FFmpeg in the maintainer environment (neither is a runtime dependency of the installed Skill);
set `PLAYWRIGHT_MODULE` to point at a Playwright install if it is not on the default resolution
path. The storyboard [`docs/media/demo-storyboard.html`](media/demo-storyboard.html) is a
reference copy guide only.
