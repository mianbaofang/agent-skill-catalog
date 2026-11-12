# Materials — agent-skill-catalog v0.4.0 demo film

All material is the product's own, captured unmodified. No invented UI, no placeholder boxes, no fake backend.

## Real captured UI (primary material)

- `materials/zh-clean.webm` — 26.3 s, 15 fps, 395 frames, 1280×720. Genuine screen recording of the
  generated offline catalog (`docs/demo/index.html`), captured with the ZCode **built-in In-app
  Browser** recorder while driving the page's real controls (search input, category/mode buttons,
  `查看详情` detail open, `复制调用` copy, `放大查看` zoom). No DOM translation, no restyling, no
  synthetic backend. This is the source for the code camera.
- `materials/frames/f0001.png … f0210.png` — the same recording decoded to a 10 fps PNG sequence
  (1280×720, first 21 s) with FFmpeg. The composition seeks this sequence, so every frame is a
  pure function of time (no `Date.now`, no unseeded random).
- `materials/overview.png`, `materials/filter.png`, `materials/detail.png` — the three committed
  native-UI stills (1280×720), used as reference for framing and as fallback stills.

## Provenance of the animated preview inside the product

The moving preview shown on the `agent-skill-catalog` card is the product's own: a
**document-derived clip** of this project's published promo animation, committed as
`examples/demo-library/roots/community-skills/agent-skill-catalog/preview.gif`
(status `verified-local`, source `frontmatter:preview_image`). It is **not** a runtime GitHub
auto-fetch and **not** automatically generated animation. The other eight catalog entries are
synthetic with generated per-category covers — the page labels provenance visibly
(`Skill 自带图片` vs `自动生成封面`).

## Palette and type

Taken from the catalog UI itself (no new colours): off-white canvas `#f5f7f5`, deep teal
`#0f494d` / `#0f766e`, ink `#142127`, slate `#587076`, coral accent `#f05a35`. Captions use the
bundled `Noto Sans SC` (500/900), which also carries the Latin run (`note-keeper`, `toolkit`).

## What I could not get

- No external Chrome: the user requires the built-in In-app Browser only, so `om render` /
  `om still` / `om qa` (which drive the user's installed Chrome) are **not** run. Visual
  verification is done by loading the composition in the built-in browser, seeking the real
  timeline, and recording it there; `om check` is run for its static structure/motion/file rules.
- The captured recording has no audio track, so the film is silent by construction (the README
  direction is already fixed as a silent GIF).
