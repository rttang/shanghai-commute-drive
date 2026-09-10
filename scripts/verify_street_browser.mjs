import { chromium } from "/Users/maiziheng/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs";
import fs from "node:fs/promises";
import path from "node:path";
import assert from "node:assert/strict";
const root = path.resolve(import.meta.dirname, "..");
const out = path.join(root, "docs/evidence/tourism");
const context = await chromium.launchPersistentContext(
  path.join(root, ".tooling/street-ui-browser"),
  {
    executablePath: path.join(root, "scripts/chrome-native.sh"),
    headless: false,
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
const results = {
  method:
    "Isolated ARM Chrome, actual product controls and animation loop, no simulation writes",
  errors: [],
  checks: [],
  tours: [],
};
if (process.env.RESUME_BROWSER_TEST) {
  const prior = JSON.parse(
    await fs.readFile(path.join(out, "photo-browser-regression.json"), "utf8"),
  );
  results.tours = prior.tours.filter(
    (t) => t.samples.at(-1)?.phase === "complete",
  );
  results.resumedFrom = prior.failure;
}
const page = context.pages()[0] || (await context.newPage());
for (const event of ["SIGINT", "SIGTERM"])
  process.on(event, async () => {
    await context.close();
    process.exit(1);
  });
const diag = () => page.evaluate(() => window.tourDiagnostics);
const click = (action) =>
  page.locator(`[data-action="${action}"]:visible`).first().click();
const shot = (name) =>
  page.screenshot({ path: path.join(out, `photo-ui-${name}.png`) });
async function check(name, fn) {
  await fn();
  results.checks.push({ name, passed: true });
  console.log("PASS", name);
}
try {
  page.on("pageerror", (e) => results.errors.push(String(e)));
  page.on("requestfailed", (r) =>
    results.errors.push(r.url() + ": " + r.failure()?.errorText),
  );
  await page.goto("http://127.0.0.1:8080/");
  await page.bringToFront();
  await page.waitForFunction(
    () => window.tourDiagnostics,
    {},
    { timeout: 90000 },
  );
  await shot("home");
  await check("three detailed cars load through garage", async () => {
    for (const id of ["model-3", "dolphin", "su7"]) {
      await click("garage");
      await page.locator(`[data-action="car"][data-value="${id}"]`).click();
      await page.waitForFunction(
        (id) => window.tourDiagnostics?.car === id,
        id,
        { timeout: 30000 },
      );
      await page.waitForTimeout(700);
      assert.equal((await diag()).car, id);
    }
  });
  await page.locator('[data-action="route"][data-value="1"]').click();
  await click("auto");
  await page.waitForTimeout(1200);
  await click("pause");
  await check("pause freezes position", async () => {
    const d = (await diag()).distance;
    await page.waitForTimeout(700);
    assert.equal((await diag()).distance, d);
  });
  await check("all four cameras render", async () => {
    for (const camera of ["follow", "vehicle", "hood", "panorama"]) {
      assert.equal((await diag()).camera, camera);
      await page.waitForTimeout(700);
      await shot(camera);
      await click("camera");
    }
  });
  await check(
    "high quality AO initializes and returns to balanced",
    async () => {
      await click("sources");
      await page.locator("#quality").selectOption("high");
      await click("close");
      await page.waitForTimeout(1800);
      assert.equal(
        await page.locator("body").getAttribute("data-quality"),
        "high",
      );
      await click("sources");
      await page.locator("#quality").selectOption("balanced");
      await click("close");
    },
  );
  await check("hide and restore interface", async () => {
    await click("photo");
    assert.equal(await page.locator(".restore-ui").isVisible(), true);
    await click("photo");
    assert.equal(await page.locator(".drive-dock").isVisible(), true);
  });
  await check("manual input advances within the route", async () => {
    await click("mode");
    await click("pause");
    const start = (await diag()).distance;
    await page.keyboard.down("w");
    await page.waitForTimeout(2000);
    await page.keyboard.up("w");
    await page.keyboard.down(" ");
    await page.waitForTimeout(700);
    await page.keyboard.up(" ");
    assert.ok((await diag()).distance > start);
    await click("pause");
  });
  for (const [index, id] of [
    [1, "pudong"],
    [0, "bund"],
  ]) {
    if (results.tours.some((t) => t.id === id)) continue;
    await click("home");
    await page.locator(`[data-action="route"][data-value="${index}"]`).click();
    await click("auto");
    await click("rate");
    await click("rate");
    const samples = [];
    const start = Date.now();
    let previous = -1;
    while (true) {
      const d = await diag();
      samples.push({ ...d, elapsedMs: Date.now() - start });
      assert.ok(d.distance >= previous);
      previous = d.distance;
      console.log(
        "TOUR",
        id,
        d.phase,
        Math.round(d.distance),
        Math.round(d.total),
      );
      if (d.phase === "complete") break;
      assert.equal(d.phase, "running", "Unexpected pause during tour");
      assert.ok(
        Date.now() - start < 600000,
        "Tour did not finish within 10 minutes",
      );
      await page.waitForTimeout(15000);
    }
    await shot(`${id}-complete`);
    results.tours.push({ id, samples });
    await click("close");
  }
  await click("home");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(600);
  await shot("mobile-home");
  await check("mobile viewport has no horizontal overflow", async () =>
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      true,
    ),
  );
  await click("manual");
  await page.waitForTimeout(900);
  await shot("mobile-drive");
  await check("mobile touch controls are visible", async () =>
    assert.equal(await page.locator('[data-control="gas"]').isVisible(), true),
  );
  await click("pause");
  results.browser = await context.browser().version();
  results.final = await diag();
  results.complete = true;
  assert.deepEqual(results.errors, []);
} catch (error) {
  results.failure = String(error);
  await shot("failure").catch(() => {});
  throw error;
} finally {
  await fs.writeFile(
    path.join(out, "photo-browser-regression.json"),
    JSON.stringify(results, null, 2),
  );
  await context.close();
}
