import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import { mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { spawnSync } from "node:child_process";

const require = createRequire(import.meta.url);
const playwrightPath = process.env.PLAYWRIGHT_MODULE || resolve(process.env.USERPROFILE || "", "node_modules/playwright");
const { chromium } = require(playwrightPath);
const repo = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
function option(name, fallback = "") {
  const index = args.indexOf(name);
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
}
const optionValues = new Set(["--lang", "--output", "--storyboard", "--catalog", "--screenshots-dir"]
  .map(name => args.indexOf(name))
  .filter(index => index >= 0 && args[index + 1])
  .map(index => args[index + 1]));
const legacyCatalog = args.find(value => !value.startsWith("--") && !optionValues.has(value)) || "";
const language = option("--lang", "zh") === "en" ? "en" : "zh";
const output = resolve(repo, option(
  "--output",
  language === "en"
    ? "docs/media/agent-skill-catalog-demo.en.gif"
    : "docs/media/agent-skill-catalog-demo.gif",
));
const screenshotsDir = option("--screenshots-dir", "");
const screenshotMode = Boolean(screenshotsDir);
const captureDir = mkdtempSync(resolve(tmpdir(), "agent-skill-catalog-demo-"));
const storyboard = resolve(repo, option("--storyboard", "docs/media/demo-storyboard.html"));
const catalogUrl = option("--catalog", legacyCatalog || "http://127.0.0.1:8765/index.html");
const catalogOrigin = new URL(catalogUrl).origin;

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: screenshotMode ? { width: 1440, height: 1000 } : { width: 960, height: 540 },
  ...(screenshotMode ? {} : { recordVideo: { dir: captureDir, size: { width: 960, height: 540 } } }),
});
const page = await context.newPage();
if (screenshotMode) {
  await page.goto(pathToFileURL(resolve(repo, ".demo-preview/index.html")).href);
} else {
  await page.goto(`${pathToFileURL(storyboard).href}?lang=${language}&catalog=${encodeURIComponent(catalogUrl)}`);
  await page.waitForFunction(() => window.__demoScene === 4, null, { timeout: 50000 });
}
const frame = screenshotMode ? page.mainFrame() : page.frames().find((candidate) => candidate.url().startsWith(catalogOrigin));
if (!frame) throw new Error("The live catalog iframe did not load.");

async function waitForSceneOffset(scene, offsetMs) {
  await page.waitForFunction(
    ({ scene: expectedScene, offsetMs: expectedOffset }) => (
      window.__demoScene === expectedScene
      && performance.now() - window.__demoSceneStartedAt >= expectedOffset
    ),
    { scene, offsetMs },
    { timeout: 50000 },
  );
}

await frame.addStyleTag({
  content: `
    body{min-width:0!important}
    .shell{width:calc(100% - 28px)!important;padding:14px 0 26px!important}
    .intro{grid-template-columns:1fr auto!important;gap:20px!important;padding:22px 0 16px!important}
    .intro h1{font-size:31px!important}.intro p{font-size:12px!important}
    .toolbar{margin:10px 0!important}.filters{margin-bottom:10px!important}
    .overview{grid-template-columns:repeat(5,1fr)!important;gap:6px!important;margin-bottom:10px!important}
    .category{min-height:60px!important;padding:9px!important}.category strong{margin-top:10px!important;font-size:11px!important}
    .grid{grid-template-columns:repeat(3,1fr)!important;gap:8px!important}.body{padding:8px!important}
    .card h3{font-size:12px!important}.body p{font-size:10px!important;line-height:1.3!important;margin:5px 0!important}
    .evidence{font-size:9px!important}.meta{font-size:9px!important}.stat{padding-left:10px!important}
    .meta-actions{gap:3px!important}.meta-actions button{min-height:22px!important;padding:3px 5px!important;font-size:8px!important}
    .stat strong{font-size:24px!important}
  `,
});

if (language === "en") {
  await frame.evaluate(() => {
    const exact = new Map(Object.entries({
      "刷新索引": "Refresh index",
      "按分类查找 Skill，打开就能看调用方式。": "Find Skills by category and open one to see how to invoke it.",
      "找到正确的能力，直接开始工作。": "Find the right capability and get to work.",
      "将本机 Skill 与插件按用途、来源、调用方式和预览整理为可检索目录。独立技能按家族聚合；插件只在插件视图中展示。": "Turn local Skills and plugins into a searchable catalog organized by purpose, source, invocation, and preview. Skill families are grouped; plugins stay in their own view.",
      "技能": "Skills",
      "插件": "Plugins",
      "搜索技能与插件": "Search Skills and plugins",
      "搜索名称、用途、GitHub 或本地相对路径": "Search name, purpose, GitHub, or relative path",
      "分类筛选": "Category filters",
      "分类概览": "Category overview",
      "全部": "All",
      "视觉与图片": "Visual and image",
      "视频与动效": "Video and motion",
      "音频与配音": "Audio and voice",
      "内容与增长": "Content and growth",
      "互联网搜索": "Web search",
      "学习教育": "Learning",
      "证券股市": "Markets",
      "数据与研究": "Data and research",
      "开发与自动化": "Development",
      "办公与交付": "Productivity",
      "专业领域": "Specialist",
      "其他工具": "Other tools",
      "查看详情": "View details",
      "更换预览图": "Replace preview",
      "关闭详情": "Close details",
      "GitHub 仓库": "GitHub repository",
      "更换预览图": "Replace preview image",
      "选择一张本地图片作为这个 Skill 的预览图。图片只保存在目录输出中，不会修改原 Skill。": "Choose a local image for this Skill. It is stored only in the catalog output and does not change the source Skill.",
      "选择图片": "Choose image",
      "保存预览图": "Save preview",
      "恢复自动图": "Restore automatic image",
      "调用方式": "Invocation",
      "来源位置": "Source location",
      "技能详情": "Skill detail",
      "分类与来源证据": "Classification and source evidence",
      "分类证据": "Classification evidence",
      "置信度": "Confidence",
      "图片状态": "Image status",
      "图片来源": "Image source",
      "未说明": "Not specified",
      "独立技能": "Standalone Skill",
      "人工预览图": "Manual preview",
      "Skill 自带图片": "Skill-provided image",
      "GitHub 仓库图片": "GitHub repository image",
      "GitHub 仓库预览": "GitHub repository preview",
      "远程元数据（缺证据）": "Remote metadata (missing evidence)",
      "分类封面（缺证据）": "Category cover (missing evidence)",
      "生成封面（缺证据）": "Generated cover (missing evidence)",
      "扫描指定的 Skill 与插件目录，按分类、家族、调用方式和图片来源生成可检索页面。": "Scan selected Skill and plugin roots and build a searchable catalog with categories, families, invocation, and image provenance.",
      "扫描指定的 Skill 与插件目录，按分类、家族、调用方式、中文说明和图片来源生成可检索页面。": "Scan selected Skill and plugin roots and build a searchable catalog with categories, families, invocation, Chinese descriptions, and image provenance.",
      "准备产品发布定位、文案版本和各渠道交付内容。": "Prepare product positioning, copy variants, and channel deliverables.",
      "准备产品发布定位、文案版本和各渠道交付内容，适合统一发布页面与宣传材料。": "Prepare product positioning, copy variants, and channel deliverables for consistent launch pages and campaign materials.",
      "按主题生成概念、练习、阶段目标和复习安排。": "Build concepts, exercises, milestones, and review plans for a topic.",
      "按主题生成概念、练习、阶段目标和复习安排，适合课程学习与阶段复盘。": "Build concepts, exercises, milestones, and review plans for a course or study review.",
      "整理公开市场数据、催化因素、风险和带日期的观察清单。": "Organize public market data, catalysts, risks, and dated watchlists.",
      "整理公开市场数据、催化因素、风险和带日期的观察清单，不提供投资建议。": "Organize public market data, catalysts, risks, and dated watchlists without providing investment advice.",
      "规划短视频的镜头、时长、字幕和交付要求。": "Plan shots, timing, captions, and delivery requirements for short videos.",
      "规划短视频的镜头、时长、字幕和交付要求，适合动效短片与产品演示。": "Plan shots, timing, captions, and delivery requirements for motion shorts and product demos.",
      "用一个主入口组织动效项目的动画设计与交付检查。": "Use one parent entry to organize motion design and delivery checks.",
      "用一个主入口组织动效项目的动画设计、时间线和交付检查。": "Use one parent entry to organize motion design, timelines, and delivery checks.",
      "把创意需求整理成图片方向、参考信息和可执行的生成提示。": "Turn a creative brief into visual direction, references, and usable generation prompts.",
      "搜索公开网页，比较证据并输出带来源的研究笔记。": "Search public web pages, compare evidence, and produce sourced research notes.",
      "搜索公开网页、比较证据并输出带来源的研究笔记，适合事实核对与资料整理。": "Search public web pages, compare evidence, and produce sourced research notes for fact checking and source review."
    }));
    const replace = value => {
      const trimmed = value.trim();
      if (exact.has(trimmed)) return value.replace(trimmed, exact.get(trimmed));
      return value
        .replace(/^全部 (\d+)$/, "All $1")
        .replace(/^(视觉与图片|视频与动效|音频与配音|内容与增长|互联网搜索|学习教育|证券股市|数据与研究|开发与自动化|办公与交付|专业领域|其他工具) (\d+)$/, (_, label, count) => `${exact.get(label) || label} ${count}`)
        .replace(/^全部技能$/, "All Skills")
        .replace(/^全部插件$/, "All plugins")
        .replace(/^(\d+) 项结果 · 索引更新于 /, "$1 results · indexed at ")
        .replace(/^(\d+) 个主技能$/, "$1 parent Skills")
        .replace(/^(\d+) 个插件$/, "$1 plugins")
        .replace(/^已整理主技能$/, "organized Skills")
        .replace(/^已整理插件$/, "organized plugins")
        .replace(/^包含 (\d+) 个子技能$/, "Includes $1 child Skills")
        .replace(/^携带 (\d+) 个技能$/, "Contains $1 Skills")
        .replace(/^包含的子技能（(\d+)）$/, "Child Skills ($1)")
        .replace(/^插件携带技能（(\d+)）$/, "Plugin Skills ($1)")
        .replace(/^证据：/, "Evidence: ")
        .replace(/^置信度：/, "Confidence: ")
        .replace(/^图片：/, "Image: ")
        .replace(/^来源：/, "Source: ")
        .replace(/^边际：/, "Margin: ")
        .replace(/^调用：在你的 Agent 中明确说明任务，并要求它按 (.+?) 的 SKILL\.md 执行。$/, "Invoke: tell your agent what to do and ask it to follow $1.")
        .replace(/^调用：/, "Invoke: ")
        .replace(/^在你的 Agent 中明确说明任务，并要求它按 (.+?) 的 SKILL\.md 执行。$/, "Tell your agent what to do and ask it to follow $1.")
        .replace(/ 的预览图$/, " preview image")
        .replace(/ 插件$/, " plugin");
    };
    const translate = root => {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      const nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      nodes.forEach(node => { node.nodeValue = replace(node.nodeValue); });
      root.querySelectorAll?.("[title],[aria-label],[placeholder],[alt]").forEach(node => {
        for (const attr of ["title", "aria-label", "placeholder", "alt"]) {
          if (node.hasAttribute(attr)) node.setAttribute(attr, replace(node.getAttribute(attr)));
        }
      });
    };
    translate(document.documentElement);
    new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
      if (node.nodeType === Node.ELEMENT_NODE) translate(node);
      if (node.nodeType === Node.TEXT_NODE) node.nodeValue = replace(node.nodeValue);
    }))).observe(document.body, { childList: true, subtree: true });
    document.documentElement.lang = "en";
  });
  await frame.waitForTimeout(150);
  const chineseText = await frame.locator("body").innerText();
  if (/[㐀-鿿]/.test(chineseText)) {
    const leftovers = [...new Set(chineseText.split(/\r?\n/).filter(line => /[㐀-鿿]/.test(line)))].slice(0, 12);
    throw new Error(`English demo catalog still contains Chinese UI text: ${leftovers.join(" | ")}`);
  }
}

if (screenshotMode) {
  const targetDir = resolve(repo, screenshotsDir);
  mkdirSync(targetDir, { recursive: true });
  const applyEnglishPreviews = () => frame.evaluate(() => {
    const escape = value => String(value ?? "").replace(/[&<>]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[char]));
    const preview = (name, label, index) => {
      const colors = [["#0f494d", "#5eead4"], ["#3d5160", "#93c5fd"], ["#5b492f", "#fde68a"]];
      const [background, accent] = colors[index % colors.length];
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675"><rect width="1200" height="675" fill="${background}"/><rect x="72" y="112" width="190" height="10" fill="${accent}"/><text x="72" y="178" fill="${accent}" font-family="Segoe UI, sans-serif" font-size="24" font-weight="700">${escape(label)}</text><text x="72" y="232" fill="#d7f0f2" font-family="Segoe UI, sans-serif" font-size="17">AGENT SKILL CATALOG</text><text x="72" y="328" fill="#ffffff" font-family="Segoe UI, sans-serif" font-size="46" font-weight="700">${escape(name)}</text><rect x="854" y="152" width="210" height="210" rx="16" fill="none" stroke="${accent}" stroke-width="14"/><path d="M885 316l61-75 49 47 35-43 48 71" fill="none" stroke="${accent}" stroke-width="14" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
      return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
    };
    const images = [...document.querySelectorAll(".card .thumb img")];
    images.forEach((image, index) => {
      const card = image.closest(".card");
      image.src = preview(card?.querySelector("h3")?.textContent || "Skill", card?.querySelector(".tag")?.textContent || "Skill", index);
    });
    return images[0]?.src || "";
  });
  const englishPreview = await applyEnglishPreviews();
  const bodyText = await frame.locator("body").innerText();
  if (/[㐀-鿿]/.test(bodyText)) {
    const leftovers = [...new Set(bodyText.split(/\r?\n/).filter(line => /[㐀-鿿]/.test(line)))].slice(0, 12);
    throw new Error(`English screenshot catalog still contains Chinese UI text: ${leftovers.join(" | ")}`);
  }
  await page.screenshot({ path: resolve(targetDir, "agent-skill-catalog-overview.en.png") });
  await frame.locator("#search").fill("agent-skill-catalog");
  await frame.waitForTimeout(250);
  await applyEnglishPreviews();
  await page.screenshot({ path: resolve(targetDir, "agent-skill-catalog-filter.en.png") });
  const editButton = frame.locator(".edit-image").first();
  await editButton.click();
  await frame.locator("#detail").waitFor({ state: "visible" });
  await frame.locator("#detail-image").evaluate((image, src) => { image.src = src; }, englishPreview);
  await frame.locator("#image-remove").evaluate(button => { button.hidden = false; });
  await frame.waitForTimeout(250);
  const detailText = await frame.locator("#detail").innerText();
  if (/[㐀-鿿]/.test(detailText)) {
    const leftovers = [...new Set(detailText.split(/\r?\n/).filter(line => /[㐀-鿿]/.test(line)))].slice(0, 12);
    throw new Error(`English screenshot detail still contains Chinese UI text: ${leftovers.join(" | ")}`);
  }
  await page.screenshot({ path: resolve(targetDir, "agent-skill-catalog-detail.en.png") });
  await context.close();
  await browser.close();
  rmSync(captureDir, { recursive: true, force: true });
  console.log(`Wrote English screenshots to ${targetDir}`);
  process.exit(0);
}

let englishCatalogPreview = null;
if (language === "en") {
  englishCatalogPreview = `data:image/png;base64,${(await frame.locator("body").screenshot({ type: "png" })).toString("base64")}`;
  const targetCard = frame.locator(".card").filter({ has: frame.locator("h3", { hasText: "agent-skill-catalog" }) }).first();
  if (await targetCard.count()) await targetCard.locator(".thumb img").evaluate((image, src) => { image.src = src; }, englishCatalogPreview);
}

// Keep the real UI sequence on the same six-second rhythm as every other scene.
await waitForSceneOffset(4, 600);
await frame.locator("#search").fill("");
await waitForSceneOffset(4, 1100);
await frame.locator("#search").pressSequentially("agent-skill-catalog", { delay: 40 });
await waitForSceneOffset(4, 2700);
if (await frame.locator(".edit-image").count()) {
  await frame.locator(".edit-image").first().click();
  await frame.locator("#detail").waitFor({ state: "visible" });
  if (englishCatalogPreview) {
    await frame.locator("#detail-image").evaluate((image, src) => { image.src = src; }, englishCatalogPreview);
  }
  if (language === "en") {
    await frame.waitForTimeout(150);
    const detailText = await frame.locator("#detail").innerText();
    if (/[㐀-鿿]/.test(detailText)) {
      const leftovers = [...new Set(detailText.split(/\r?\n/).filter(line => /[㐀-鿿]/.test(line)))].slice(0, 12);
      throw new Error(`English demo detail still contains Chinese UI text: ${leftovers.join(" | ")}`);
    }
  }
}

await waitForSceneOffset(5, 5700);
await context.close();
await browser.close();

const { readdir } = await import("node:fs/promises");
const videos = (await readdir(captureDir)).filter((name) => name.endsWith(".webm"));
if (videos.length !== 1) throw new Error(`Expected one recorded video, found ${videos.length}.`);
const video = resolve(captureDir, videos[0]);
const ffmpeg = spawnSync("ffmpeg", [
  "-y", "-i", video,
  "-vf", "trim=start=0.2,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=0.2,fps=5,scale=960:540:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=96:stats_mode=diff[p];[s1][p]paletteuse=dither=bayer",
  "-loop", "0", output,
], { stdio: "inherit" });
if (ffmpeg.status !== 0) throw new Error("ffmpeg failed while encoding the README GIF.");
console.log(`Wrote ${output}`);
rmSync(captureDir, { recursive: true, force: true });
