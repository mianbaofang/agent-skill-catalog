import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { spawnSync } from "node:child_process";

const require = createRequire(import.meta.url);
const playwrightPath = process.env.PLAYWRIGHT_MODULE || resolve(process.env.USERPROFILE || "", "node_modules/playwright");
const { chromium } = require(playwrightPath);
const repo = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const output = resolve(repo, "docs/media/agent-skill-catalog-demo.gif");
const captureDir = mkdtempSync(resolve(tmpdir(), "agent-skill-catalog-demo-"));
const storyboard = resolve(repo, "docs/media/demo-storyboard.html");
const catalogUrl = process.argv[2] || "http://127.0.0.1:8765/index.html";
const catalogOrigin = new URL(catalogUrl).origin;

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 960, height: 540 },
  recordVideo: { dir: captureDir, size: { width: 960, height: 540 } },
});
const page = await context.newPage();
await page.goto(`${pathToFileURL(storyboard).href}?catalog=${encodeURIComponent(catalogUrl)}`);

await page.waitForFunction(() => window.__demoScene === 4, null, { timeout: 50000 });
const frame = page.frames().find((candidate) => candidate.url().startsWith(catalogOrigin));
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

// Keep the real UI sequence on the same six-second rhythm as every other scene.
await waitForSceneOffset(4, 600);
await frame.locator("#search").fill("");
await waitForSceneOffset(4, 1100);
await frame.locator("#search").pressSequentially("agent-skill-catalog", { delay: 40 });
await waitForSceneOffset(4, 2700);
if (await frame.locator(".edit-image").count()) {
  await frame.locator(".edit-image").first().click();
  await frame.locator("#detail").waitFor({ state: "visible" });
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
