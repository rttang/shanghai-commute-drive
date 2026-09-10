import { chromium } from "/Users/maiziheng/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs";
import fs from "node:fs/promises";
import path from "node:path";
import { existsSync } from "node:fs";
import { execFileSync, spawnSync } from "node:child_process";
// Intel Node makes a universal Chrome inherit Rosetta on Apple Silicon. Prefer
// the installed native runtime when available, without downloading another one.
const nativeNode =
  "/Applications/ChatGPT.app/Contents/Resources/cua_node/bin/node";
if (
  process.platform === "darwin" &&
  process.arch === "x64" &&
  existsSync(nativeNode) &&
  execFileSync(nativeNode, ["-p", "process.arch"], {
    encoding: "utf8",
  }).trim() === "arm64"
) {
  const child = spawnSync(nativeNode, process.argv.slice(1), {
    stdio: "inherit",
    env: process.env,
  });
  process.exit(child.status ?? 1);
}
const root = path.resolve(import.meta.dirname, "..");
const dir = path.join(root, "docs/evidence/tourism");
const name = process.argv[2] || "photo-round1-bund-hood";
const query = process.argv[3] || "route=bund&distance=600&view=hood";
const context = await chromium.launchPersistentContext(
  path.join(root, ".tooling/street-review-browser"),
  {
    executablePath: path.join(root, "scripts/chrome-native.sh"),
    headless: !process.env.HEADFUL,
    viewport: { width: 1280, height: 720 },
    deviceScaleFactor: 1,
    args: [
      "--no-first-run",
      "--disable-background-networking",
      "--use-angle=metal",
      "--enable-gpu",
    ],
  },
);
for (const event of ["SIGINT", "SIGTERM"])
  process.on(event, async () => {
    await context.close();
    process.exit(0);
  });
try {
  const pages = context.pages();
  console.log(
    "Isolated context tabs",
    pages.map((p) => p.url()),
  );
  const page = pages[0] || (await context.newPage());
  for (const other of pages.slice(1)) await other.close();
  const errors = [];
  const warnings = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("requestfailed", (r) =>
    errors.push(r.url() + ": " + r.failure()?.errorText),
  );
  page.on("response", (r) => {
    if (r.status() >= 400) errors.push(r.status() + " " + r.url());
  });
  page.on("worker", (w) => {
    console.log("Worker", w.url());
    w.on("console", (m) => console.log("worker", m.type(), m.text()));
  });
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
    if (m.type() === "warning") warnings.push(m.text());
  });
  await page.goto(
    "http://127.0.0.1:8080/" +
      (process.env.MODEL_REVIEW
        ? "architecture-review.html"
        : "streets-review.html") +
      "?" +
      query,
  );
  await page.bringToFront();
  await page.waitForSelector("canvas", { state: "attached", timeout: 180000 });
  const gpu = await page.evaluate(() => {
    const gl = document.querySelector("canvas")?.getContext("webgl2");
    if (!gl) return null;
    const d = gl.getExtension("WEBGL_debug_renderer_info");
    return d
      ? gl.getParameter(d.UNMASKED_RENDERER_WEBGL)
      : gl.getParameter(gl.RENDERER);
  });
  console.log("GPU", gpu);
  let waitError;
  try {
    await page.waitForFunction(
      () => document.body.dataset.review,
      {},
      { timeout: 180000 },
    );
    await page.waitForFunction(
      () =>
        document.body.dataset.sample &&
        JSON.parse(document.body.dataset.sample).frames >=
          (location.pathname.includes("architecture-review") ? 180 : 600),
      {},
      { timeout: 180000 },
    );
  } catch (e) {
    waitError = String(e);
  }
  await page.screenshot({ path: path.join(dir, name + ".png") });
  const data = await page.evaluate(() => ({
    review: JSON.parse(document.body.dataset.review || "null"),
    sample: JSON.parse(document.body.dataset.sample || "null"),
    tour: document.body.dataset.tour,
    status: document.querySelector("#status")?.textContent,
  }));
  data.waitError = waitError;
  data.errors = errors;
  data.warnings = warnings;
  data.gpu = gpu;
  data.nodeArch = process.arch;
  data.browser = await context.browser().version();
  data.method = `Isolated local Chrome ${process.env.HEADFUL ? "headed" : "headless"}; 1280x720 DPR1. Not the in-app browser.`;
  await fs.writeFile(
    path.join(dir, name + ".json"),
    JSON.stringify(data, null, 2),
  );
  console.log(JSON.stringify(data));
} finally {
  await context.close();
}
