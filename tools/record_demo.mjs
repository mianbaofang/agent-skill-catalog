import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import { mkdirSync, mkdtempSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { spawnSync } from "node:child_process";

// Documentation-only media recorder. Requires Playwright and FFmpeg in the
// maintainer environment; neither is a runtime dependency of the installed Skill.
//
// The catalog UI captured here is the real generated page, shown unmodified in
// its native Chinese interface. This recorder never translates, restyles, or
// replaces product content inside the catalog. The only injected pixels are
// clearly separate annotation overlays (an intro card, a narration band, and a
// closing card) that sit above the page and explain the flow. English runs use
// the same native Chinese UI and say so explicitly.

const require = createRequire(import.meta.url);
const playwrightPath = process.env.PLAYWRIGHT_MODULE || resolve(process.env.USERPROFILE || "", "node_modules/playwright");
const { chromium } = require(playwrightPath);
const repo = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);

function option(name, fallback = "") {
  const index = args.indexOf(name);
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
}

const language = option("--lang", "zh") === "en" ? "en" : "zh";
const output = resolve(repo, option(
  "--output",
  language === "en"
    ? "docs/media/agent-skill-catalog-demo.en.gif"
    : "docs/media/agent-skill-catalog-demo.gif",
));
const screenshotsDir = option("--screenshots-dir", "");
const screenshotMode = Boolean(screenshotsDir);
const catalogArg = option("--catalog", "");
if (!catalogArg) {
  console.error("error: --catalog <url> is required. Serve a non-personal generated catalog and pass its index.html URL.");
  process.exit(2);
}
const isHttpUrl = /^https?:\/\//i.test(catalogArg);
const isFileUrl = /^file:\/\//i.test(catalogArg);
const catalogUrl = isHttpUrl || isFileUrl
  ? catalogArg
  : pathToFileURL(resolve(repo, catalogArg)).href;

// Serve the catalog with the project's own localhost refresh server and pass
// its index.html URL via --catalog. The recorder opens that URL directly, so the
// localhost-only refresh and image controls behave exactly as they do for a user.

const captureDir = mkdtempSync(resolve(tmpdir(), "agent-skill-catalog-demo-"));

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: screenshotMode ? { width: 1440, height: 1000 } : { width: 960, height: 540 },
  deviceScaleFactor: 1,
  ...(screenshotMode ? {} : { recordVideo: { dir: captureDir, size: { width: 960, height: 540 } } }),
});
const page = await context.newPage();
page.setDefaultTimeout(20000);

await page.goto(catalogUrl, { waitUntil: "load" });

// Wait for the generated catalog data to render real cards.
await page.waitForFunction(() => document.querySelector(".grid")?.children.length > 0);

// Read live counts and names from the rendered catalog. The page exposes its
// data as a lexical `const data` (not a window property), so read it through a
// Function bridge and fall back to the rendered DOM when it is unavailable.
// Nothing about the product is hard-coded here.
async function readCatalog() {
  const fromData = await page.evaluate(() => {
    const data = new Function('return (typeof data !== "undefined" && data) ? data : null')();
    if (!data) return null;
    const asText = value => {
      if (typeof value === "string") return value;
      if (value && typeof value === "object") return String(value.path || value.root || value.name || value.source || "");
      return value == null ? "" : String(value);
    };
    const families = Array.isArray(data.families) ? data.families : [];
    const plugins = Array.isArray(data.plugins) ? data.plugins : [];
    const roots = Array.isArray(data.roots) ? data.roots.map(asText).filter(Boolean) : [];
    if (!roots.length && data.root_source) roots.push(String(data.root_source));
    const familyRecords = families
      .filter(entry => entry && entry.name)
      .map(entry => ({
        name: String(entry.name),
        members: ((entry.skill_ids || []).length) || ((entry.subskills || []).length),
      }));
    return {
      roots,
      familyRecords,
      familyNames: familyRecords.map(entry => entry.name),
      pluginNames: plugins.map(entry => entry && entry.name).filter(Boolean),
      pluginSkillCount: plugins.reduce((total, entry) => total + ((entry && entry.skill_ids) || []).length, 0),
    };
  });
  if (fromData) return fromData;
  return page.evaluate(() => ({
    roots: [],
    familyRecords: [...document.querySelectorAll(".grid .card h3")].map(node => ({ name: node.textContent.trim(), members: 0 })),
    familyNames: [...document.querySelectorAll(".grid .card h3")].map(node => node.textContent.trim()),
    pluginNames: [],
    pluginSkillCount: 0,
  }));
}
const catalog = await readCatalog();

// Annotation overlays are used for the animated GIF only. They live entirely
// outside the catalog DOM, never restyle or replace product UI, and are not
// applied in screenshot mode so stills stay pure native UI.
if (!screenshotMode) {
  await page.addStyleTag({ content: `
  .ac-overlay{position:fixed;inset:0;z-index:9999;pointer-events:none;font-family:"Segoe UI","Microsoft YaHei",system-ui,sans-serif}
  .ac-intro{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;gap:18px;padding:0 84px;background:#f5f7f5;color:#142127;opacity:0;transition:opacity .6s ease}
  .ac-intro[data-show="1"]{opacity:1}
  .ac-kicker{color:#f05a35;font-size:20px;font-weight:760;letter-spacing:.7px;text-transform:uppercase}
  .ac-title{margin:0;max-width:760px;font-size:36px;line-height:1.1;letter-spacing:-.3px}
  .ac-lede{margin:0;max-width:700px;color:#587076;font-size:21px;line-height:1.5}
  .ac-roots{display:flex;flex-wrap:wrap;gap:10px}
  .ac-root{padding:6px 14px;border:1px solid #c9d5d0;border-radius:999px;background:rgba(255,255,255,.7);color:#3d5160;font-size:20px}
  .ac-note{color:#5b492f;font-size:20px}
  .ac-band{position:absolute;left:0;right:0;bottom:0;min-height:54px;display:flex;align-items:center;gap:16px;padding:10px 28px;background:rgba(15,73,77,.94);color:#eaf4f2;font-size:22px;line-height:1.3;opacity:0;transition:opacity .4s ease}
  .ac-band[data-show="1"]{opacity:1}
  .ac-chip{flex:none;padding:4px 12px;border:1px solid rgba(234,244,242,.5);border-radius:999px;font-size:20px;letter-spacing:.6px;text-transform:uppercase}
  .ac-band span.ac-text{min-width:0}
` });

  await page.evaluate(() => {
    const layer = document.createElement("div");
    layer.className = "ac-overlay";
    layer.innerHTML = `
    <div class="ac-intro" data-show="1">
      <div class="ac-kicker" id="ac-kicker"></div>
        <h1 class="ac-title" id="ac-title"></h1>
        <p class="ac-lede" id="ac-lede"></p>
        <div class="ac-roots" id="ac-roots"></div>
        <div class="ac-note" id="ac-note"></div>
      </div>
      <div class="ac-band" data-show="0"><span class="ac-chip" id="ac-chip"></span><span class="ac-text" id="ac-text"></span></div>
    `;
    document.body.appendChild(layer);
  });
}

const setIntro = values => page.evaluate(entries => {
  for (const [id, value] of Object.entries(entries)) {
    const node = document.getElementById(id);
    if (node && value != null) node.textContent = value;
  }
}, values);

// A native <dialog> renders in the browser top layer above any fixed overlay,
// so while the detail modal is open the narration band must live inside it to
// stay visible. Move it back out when the modal closes.
const syncBandLayer = async () => {
  await page.evaluate(() => {
    const band = document.querySelector(".ac-band");
    if (!band) return;
    const detail = document.getElementById("detail");
    const open = Boolean(detail && detail.open);
    const inModal = band.parentElement === detail;
    if (open && !inModal) detail.appendChild(band);
    if (!open && inModal) document.querySelector(".ac-overlay").appendChild(band);
  });
};

const setBand = async (chip, text) => {
  await page.evaluate(({ chip, text }) => {
    const band = document.querySelector(".ac-band");
    document.getElementById("ac-chip").textContent = chip;
    document.getElementById("ac-text").textContent = text;
    band.dataset.show = "1";
  }, { chip, text });
  await syncBandLayer();
};

const hideBand = async () => {
  await page.evaluate(() => { document.querySelector(".ac-band").dataset.show = "0"; });
  await syncBandLayer();
};

// The closing reuses the proven intro card with closing copy, so the final
// frames are a real card and never a blank layer.
const showClosing = async () => {
  await page.evaluate(({ kicker, title, lede }) => {
    document.querySelector(".ac-intro .ac-kicker").textContent = kicker;
    document.getElementById("ac-title").textContent = title;
    document.getElementById("ac-lede").textContent = lede;
    document.querySelector(".ac-intro").dataset.show = "1";
  }, { kicker: copy.outroKicker, title: copy.outroTitle, lede: copy.outroLede });
};
const settle = ms => page.waitForTimeout(ms);

const copy = language === "en"
  ? {
      demoKicker: "Agent Skill Catalog · Synthetic demo",
      introTitle: "Find the right Skill, and see how to call it.",
      introLede: "This demo catalog is generated from the synthetic roots below. It is a static example: nothing is executed, fetched, or installed.",
      rootPrefix: "Synthetic root",
      note: "Synthetic demo data (演示数据). The interface below is the product's native Chinese UI, captured unmodified.",
      overviewChip: "Catalog",
      overview: fam => `All Skills and families: ${fam} generated entries, each with purpose, source, and image evidence.`,
      searchChip: "Search",
      search: (name, members) => `Searching for "${name}" narrows the grid to that family of ${members} bundled Skills.`,
      detailChip: "Detail",
      detail: "Opening the entry shows its purpose, how to invoke it, source location, and classification evidence.",
      pluginChip: "Plugins",
      plugin: (name, count) => `Plugins keep their bundled Skills in a separate view: ${name} carries ${count}.`,
      outroKicker: "Synthetic demo · Start from evidence",
      outroTitle: "Open an entry and see where it belongs.",
      outroLede: "Search, filter by category, inspect invocation and source, and switch to the plugin view. Demo data only.",
    }
  : {
      demoKicker: "Agent Skill Catalog · 合成演示",
      introTitle: "找到合适的能力，直接看调用方式。",
      introLede: "该演示目录由下面的合成根目录生成，是静态示例：不执行、不联网、不安装。",
      rootPrefix: "合成根目录",
      note: "合成演示数据（demo data）。下方界面为产品原生中文界面，未做任何修改。",
      overviewChip: "目录",
      overview: fam => `全部技能与家族：共 ${fam} 个条目，均带用途、来源与图片来源。`,
      searchChip: "搜索",
      search: (name, members) => `搜索“${name}”后，列表收窄到该家族的 ${members} 个技能。`,
      detailChip: "详情",
      detail: "打开条目可看到用途、调用方式、来源位置与分类依据。",
      pluginChip: "插件",
      plugin: (name, count) => `插件单独归档：${name} 携带 ${count} 个技能。`,
      outroKicker: "合成演示 · 从证据开始",
      outroTitle: "打开条目，看清归属。",
      outroLede: "支持搜索、按分类筛选、查看调用与来源，并切换到插件视图。",
    };

// Demonstrate a real multi-member family from the generated data. The searched
// family must genuinely bundle several Skills; if the catalog has none, fail
// rather than silently showcasing a nonexistent or single-Skill entry.
const multiMemberFamily = catalog.familyRecords.find(entry => entry.members > 1);
if (!multiMemberFamily) {
  throw new Error("No multi-member Skill family found in the supplied catalog; cannot record a truthful family demo.");
}
const familyName = multiMemberFamily.name;
const familyMemberCount = multiMemberFamily.members;
const pluginName = catalog.pluginNames[0] || "";
const rootChips = catalog.roots.slice(0, 3).map(root => `${copy.rootPrefix}: ${root}`);

// Populate the intro card now that both the overlay and the copy exist.
await setIntro({
  "ac-kicker": copy.demoKicker,
  "ac-title": copy.introTitle,
  "ac-lede": copy.introLede,
  "ac-note": copy.note,
});

if (screenshotMode) {
  // Screenshots are the pure native UI with no annotation overlay, so the same
  // files serve both the English and Chinese docs.
  const targetDir = resolve(repo, screenshotsDir);
  mkdirSync(targetDir, { recursive: true });
  const base = language === "en"
    ? "agent-skill-catalog-overview.en.png"
    : "agent-skill-catalog-overview.png";
  const filterName = language === "en"
    ? "agent-skill-catalog-filter.en.png"
    : "agent-skill-catalog-filter.png";
  const detailName = language === "en"
    ? "agent-skill-catalog-detail.en.png"
    : "agent-skill-catalog-detail.png";

  await settle(300);
  await page.screenshot({ path: resolve(targetDir, base) });

  await page.fill("#search", familyName);
  await page.waitForFunction(() => document.querySelectorAll(".grid .card").length <= 2);
  await settle(300);
  await page.screenshot({ path: resolve(targetDir, filterName) });

  const detailButton = page.locator(".grid .card [data-record]").first();
  await detailButton.click();
  await page.waitForSelector("#detail", { state: "visible" });
  await page.waitForTimeout(400);
  await page.screenshot({ path: resolve(targetDir, detailName) });

  await context.close();
  await browser.close();
  rmSync(captureDir, { recursive: true, force: true });
  console.log(`Wrote native-UI screenshots to ${targetDir}`);
  process.exit(0);
}

// GIF timeline: intro card -> real catalog overview -> search -> detail ->
// plugin view -> closing card. The catalog interaction is genuine; the only
// added pixels are the annotation overlays.

// Root labels are part of the intro card, so populate them while it is visible.
for (const root of rootChips.slice(0, 3)) {
  await page.evaluate(value => {
    const chip = document.createElement("span");
    chip.className = "ac-root";
    chip.textContent = value;
    document.getElementById("ac-roots").appendChild(chip);
  }, root);
}

await settle(4200);
await page.evaluate(() => { document.querySelector(".ac-intro").dataset.show = "0"; });
await settle(600);

// Genuine page scroll only: bring the generated card grid into the 540px
// frame. This never restyles the product or hides the synthetic banner.
const scrollGridIntoView = () => page.evaluate(() => {
  document.querySelector(".grid")?.scrollIntoView({ block: "start", behavior: "instant" });
});

await setBand(copy.overviewChip, copy.overview(catalog.familyNames.length));
await scrollGridIntoView();
await settle(5200);

// Search for the multi-member family and keep the filter applied, so the entry
// opened in the detail step is the family the narration describes.
await page.fill("#search", familyName);
await page.waitForFunction(() => document.querySelectorAll(".grid .card").length <= 2);
await scrollGridIntoView();
await setBand(copy.searchChip, copy.search(familyName, familyMemberCount));
await settle(4200);

const familyCard = page.locator(".grid .card").filter({ has: page.locator("h3", { hasText: familyName }) }).first();
await familyCard.locator("[data-record]").click();
await page.waitForSelector("#detail", { state: "visible" });
await setBand(copy.detailChip, copy.detail);
await settle(7200);

await page.locator("#detail .close").click();
await page.waitForSelector("#detail", { state: "hidden" });
await settle(400);

const pluginsTab = page.locator('[data-mode="plugins"]');
if (await pluginsTab.count()) {
  await pluginsTab.click();
  await page.waitForFunction(() => document.querySelectorAll(".grid .card").length > 0);
  await scrollGridIntoView();
  await setBand(copy.pluginChip, copy.plugin(pluginName, catalog.pluginSkillCount));
  await settle(5200);
}

await hideBand();
await settle(500);
await showClosing();
await settle(3600);

await page.close();
await context.close();
await browser.close();

const { readdir } = await import("node:fs/promises");
const videos = (await readdir(captureDir)).filter(name => name.endsWith(".webm"));
if (videos.length !== 1) throw new Error(`Expected one recorded video, found ${videos.length}.`);
const video = resolve(captureDir, videos[0]);
const ffmpeg = spawnSync("ffmpeg", [
  "-y", "-i", video,
  "-vf", "trim=start=0.2,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=0.2,fps=5,scale=960:540:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=96:stats_mode=diff[p];[s1][p]paletteuse=dither=bayer",
  "-loop", "0", output,
], { stdio: "inherit" });
if (ffmpeg.status !== 0) throw new Error("ffmpeg failed while encoding the README GIF.");
rmSync(captureDir, { recursive: true, force: true });
const bytes = statSync(output).size;
console.log(`Wrote ${output} (${(bytes / 1024 / 1024).toFixed(2)} MiB)`);
