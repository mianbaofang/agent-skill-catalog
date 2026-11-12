# Treatment — agent-skill-catalog v0.4.0 demo (20–25 s, 16:9, silent GIF)

## Direction (already fixed by the user)

One direction, not three: the product's own captured interface, in its own teal/off-white palette,
with a code camera that crops and pushes into the real UI. The material is the genuine built-in
In-app Browser recording (`materials/zh-clean.webm` → 10 fps frame sequence). The camera explains:
each move isolates the thing that just changed. No slide decks, no invented UI, no fake backend.
Silent (README GIF direction already fixed), no audio question.

## Rhythm sheet

- Route: **continuous** — one take through the real recording, the camera carrying every transition
  (no hard cuts), so the moving preview never leaves the screen for long.
- Energy curve: hook inside 3 s (camera dives into the card whose preview is already animating),
  a burst at the detail + zoom (the enlarged moving preview), a settle at search, a second small
  peak at plugins, a landing on the full catalog.
- Events per bar (21 s, one GSAP timeline, scene labels):

| t (s) | scene label | camera (on the real frame) | caption (single band) |
|---|---|---|---|
| 0.0 | scene:catalog | wide on the grid; the reference card's preview is already moving | 真实目录 · 首个卡片就是会动的项目预览 |
| 0.4 | — | push into the moving preview card (top-left), ~1.9×, readable before 3 s | (same) |
| 4.2 | scene:detail | crop to the opened detail dialog and its gallery | 打开真实条目 · 预览动画在详情中继续播放 |
| 8.0 | scene:zoom | into the enlarged preview, still animating | 放大查看 · 动画仍在播放 |
| 10.2 | — | return to detail while `复制调用` reports | 复制调用方式 · 一键拿到怎么用 |
| 12.2 | scene:search | pull to the search box + the narrowed 3-member family | 搜索 note-keeper · 收窄到该家族 3 个技能 |
| 14.2 | scene:plugins | crop to the plugin view (`toolkit`, 2 Skills) | 插件单独归档 · toolkit 携带 2 个技能 |
| 16.4 | scene:cta | pull back to the full catalog, settle | 搜索、筛选、查看调用方式 · 用真实目录开始 |
| 19.6 | scene:hold | resting wide poster | (last caption holds) |

## Continuity chain

The animated preview card is the through-line: it is moving in the wide grid, larger in the detail
gallery, largest in the zoom, and the search/plugin beats return to the same catalog. The camera
never cuts away from the real UI; it only reframes it.

## Departures from the references

- The "screen" is real captured footage (a frame sequence), not a code-rebuilt UI — the user
  explicitly wants the real UI retained from the 15 fps recording and forbids fake backends.
- No music/effects: the deliverable is a silent README GIF and the source recording has no track.
- The huashu-motion signature appears above the narration band during the final 1.2 seconds.

## Verification (honest)

`om check` is run for its static structure / motion-rule / file checks. `om render`, `om still` and
`om qa --sheet` normally drive the user's installed Chrome, which the user forbids, so they are
**not** run. Instead the composition is loaded in the built-in In-app Browser, the real timeline is
seeked, and the playing film is recorded there with the built-in recorder; that artifact is encoded
to the versioned GIF with FFmpeg and inspected frame-by-frame. Any `om` visual check not runnable is
reported as unavailable, never faked.
