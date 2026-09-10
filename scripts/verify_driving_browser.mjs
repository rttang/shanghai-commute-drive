import { chromium } from "/Users/maiziheng/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs";
import fs from "node:fs/promises";
import { createReadStream } from "node:fs";
import http from "node:http";
import path from "node:path";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";

// Run only after the production build is ready. An isolated static server means
// another developer's Vite HMR cannot reset a tour halfway through this check.
// All interaction uses real controls. Diagnostics and animation frames are read
// only; this script never writes the driving simulation or advances its clock.
const root = path.resolve(import.meta.dirname, "..");
const dist = path.join(root, "dist");
const out = path.join(root, "docs/evidence/tourism");
const runId = new Date().toISOString().replace(/[:.]/g, "-");
const prefix = `driving-${runId}`;
const baseURL = "http://127.0.0.1:8081";
const networkOnly = process.env.DRIVING_NETWORK_ONLY === "1";
const results = {
  startedAt: new Date().toISOString(),
  method: "Production dist on isolated 8081 static server, headless ARM Chrome, real product clicks/keys/pointers, read-only diagnostics",
  nodeArch: process.arch,
  checks: [], cars: [], tours: [], errors: [], navigation: [], screenshots: [], network: [], console: [],
};
let context, page, server;
const compact = (d) => d && ({
  route: d.route, mode: d.mode, phase: d.phase, distance: d.distance,
  total: d.total, travelled: d.travelled, speed: d.speed,
  steering: d.steering, routeDeviation: d.routeDeviation,
  pose: d.pose, car: d.car, camera: d.camera, wheels: d.wheels,
});
const diag = () => page.evaluate(() => window.tourDiagnostics);
const click = (action) => page.locator(`[data-action="${action}"]:visible`).first().click();
const metres = (a, b) => Math.hypot(a.pose.x - b.pose.x, a.pose.z - b.pose.z);
const wheelRoll = (w) => w.roll ?? w.rotation ?? w.spin;
const wheelSteer = (w) => w.steer ?? w.steering ?? 0;
const frontWheel = (w) => w.front ?? /front|^f[lr]$/i.test(w.name ?? w.id ?? "");
const wheelMap = (d) => new Map(d.wheels.map((w, i) => [w.name ?? w.id ?? String(i), w]));
const angularDistance = (a, b) => Math.abs(Math.atan2(Math.sin(a - b), Math.cos(a - b)));
async function shot(name) {
  const file = `${prefix}-${name}.png`;
  await page.screenshot({ path: path.join(out, file) });
  results.screenshots.push({ name, file, diagnostics: compact(await diag()) });
}
async function persist() {
  await fs.writeFile(path.join(out, `${prefix}.json`), JSON.stringify(results, null, 2) + "\n");
}
async function check(name, fn) {
  const startedAt = new Date().toISOString();
  try {
    const detail = await fn();
    results.checks.push({ name, passed: true, startedAt, detail });
    console.log("PASS", name);
  } catch (error) {
    results.checks.push({ name, passed: false, startedAt, failure: String(error), diagnostics: compact(await diag().catch(() => null)) });
    await shot(`failure-${results.checks.length}`).catch(() => {});
    console.log("FAIL", name, String(error));
    throw error;
  } finally { await persist(); }
}
async function hold(keys, duration) {
  for (const key of keys) await page.keyboard.down(key);
  try { await page.waitForTimeout(duration); }
  finally { for (const key of keys.reverse()) await page.keyboard.up(key); }
}
async function brakeToStop() {
  await page.keyboard.down("s");
  try { await page.waitForFunction(() => window.tourDiagnostics?.speed < 0.01, {}, { timeout: 12000 }); }
  finally { await page.keyboard.up("s"); }
  await page.waitForTimeout(150);
}
async function chooseCar(id) {
  await click("garage");
  await page.locator(`[data-action="car"][data-value="${id}"]`).click();
  await page.waitForFunction((id) => window.tourDiagnostics?.car === id, id, { timeout: 45000 });
  await page.waitForTimeout(250);
}
async function chooseCamera(mode) {
  for (let i = 0; i < 4 && (await diag()).camera !== mode; i++) await click("camera");
  assert.equal((await diag()).camera, mode);
}
async function movingFPS(frameCount = 360) {
  return page.evaluate((frameCount) => new Promise((resolve) => {
    const samples = []; let last = performance.now();
    const tick = (t) => {
      samples.push(t - last); last = t;
      if (samples.length < frameCount + 30) requestAnimationFrame(tick);
      else {
        const frames = samples.slice(30), sorted = [...frames].sort((a, b) => a - b);
        resolve({ sampleFrames: frames.length, fps: 1000 * frames.length / frames.reduce((a, b) => a + b, 0), p95FrameMs: sorted[Math.floor(sorted.length * 0.95)], maxFrameMs: sorted.at(-1), viewport: [innerWidth, innerHeight], dpr: devicePixelRatio, quality: document.body.dataset.quality, diagnostics: window.tourDiagnostics });
      }
    }; requestAnimationFrame(tick);
  }), frameCount);
}
async function startServer() {
  // Ownership preflight: never stop or replace an existing listener.
  let listeners = "";
  try { listeners = execFileSync("/usr/sbin/lsof", ["-nP", "-iTCP:8081", "-sTCP:LISTEN"], { encoding: "utf8" }); }
  catch (error) { if (error.status !== 1) throw error; }
  assert.equal(listeners.trim(), "", `Port 8081 already has a listener: ${listeners}`);
  const index = await fs.stat(path.join(dist, "index.html"));
  results.build = { root: dist, indexModifiedAt: index.mtime.toISOString() };
  const mime = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".json": "application/json", ".glb": "model/gltf-binary", ".gltf": "model/gltf+json", ".wasm": "application/wasm", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".svg": "image/svg+xml", ".hdr": "application/octet-stream" };
  server = http.createServer(async (request, response) => {
    try {
      const pathname = decodeURIComponent(new URL(request.url, baseURL).pathname);
      const file = path.resolve(dist, "." + (pathname === "/" ? "/index.html" : pathname));
      if (!file.startsWith(dist + path.sep)) { response.writeHead(403).end(); return; }
      const stat = await fs.stat(file);
      if (!stat.isFile()) { response.writeHead(404).end(); return; }
      response.writeHead(200, { "Content-Type": mime[path.extname(file)] || "application/octet-stream", "Content-Length": stat.size, "Cache-Control": "no-store" });
      if (request.method === "HEAD") response.end(); else createReadStream(file).pipe(response);
    } catch { response.writeHead(404).end(); }
  });
  await new Promise((resolve, reject) => { server.once("error", reject); server.listen({ port: 8081, host: "127.0.0.1", exclusive: true }, resolve); });
  results.service = { url: baseURL, port: 8081, pid: process.pid, cwd: process.cwd(), owner: "this verification process", initial: "port free", state: "running" };
  console.log("SERVER", JSON.stringify(results.service));
}
function classifyNetworkEvidence(record) {
  const explainedCancellations = [], unexplainedErrors = [];
  for (const error of record.errors) {
    const request = record.network?.find((n) => n.id === error.requestId);
    const firstTiming = record.resourceTiming?.find((t) => t.name === error.url);
    const recheck = record.recheckedResources?.find((r) => r.url === error.url);
    const laterFinished = record.network?.find((n) => n.url === error.url && n.id > error.requestId && n.outcome === "finished" && n.status === 200 && Number(n.headers?.["content-length"]) === recheck?.bytes);
    const reasons = [];
    if (error.type !== "requestfailed" || error.error !== "net::ERR_ABORTED") reasons.push("Not a cancellation notification; always fail");
    if (error.method !== "GET" || error.resourceType !== "fetch") reasons.push("Not a GET fetch request");
    if (request?.status !== 200 || error.status !== 200) reasons.push("Initial response was not HTTP 200");
    const contentLength = Number(request?.headers?.["content-length"]);
    if (!(contentLength > 0 && firstTiming?.responseStatus === 200 && firstTiming.encodedBodySize === contentLength)) reasons.push("Initial full response body is not evidenced by Resource Timing and Content-Length");
    if (!(recheck?.status === 200 && recheck.matched && recheck.bytes === recheck.expectedBytes && recheck.bytes === contentLength && recheck.sha256 === recheck.expectedSHA256 && /^[a-f0-9]{64}$/.test(recheck.sha256))) reasons.push("Subsequent complete fetch does not match dist size and SHA-256");
    if (!laterFinished) reasons.push("No subsequent successful requestfinished event for the same complete payload");
    if (reasons.length) unexplainedErrors.push({ ...error, reasons });
    else explainedCancellations.push({
      requestId: error.requestId, url: error.url,
      classification: "cancellation notification with fully received and independently verified payload",
      initialStatus: request.status, initialContentLength: contentLength,
      initialEncodedBodySize: firstTiming.encodedBodySize,
      recheckBytes: recheck.bytes, recheckSHA256: recheck.sha256,
      successfulRequestId: laterFinished.id,
      underlyingCause: "unknown",
    });
  }
  for (const request of record.network ?? []) if (request.status >= 400) unexplainedErrors.push({ type: "http", requestId: request.id, url: request.url, status: request.status });
  for (const entry of record.console ?? []) if (entry.type === "error") unexplainedErrors.push({ type: "console", ...entry });
  return { strictNetworkClean: record.errors.length === 0 && unexplainedErrors.length === 0, rawErrorCount: record.errors.length, explainedCancellations, unexplainedErrors, underlyingCause: "unknown" };
}
async function auditNetwork() {
    // Capture the original responses before any explicit verification fetches.
    results.resourceTiming = await page.evaluate(() => performance.getEntriesByType("resource").map((r) => ({ name: r.name, initiatorType: r.initiatorType, duration: r.duration, transferSize: r.transferSize, encodedBodySize: r.encodedBodySize, decodedBodySize: r.decodedBodySize, responseStatus: r.responseStatus })));
    results.recheckedResources = [];
    const failedURLs = [...new Set(results.errors.filter((r) => r.type === "requestfailed" && r.error === "net::ERR_ABORTED" && r.method === "GET" && r.resourceType === "fetch" && r.status === 200 && r.url.startsWith(baseURL + "/")).map((r) => r.url))];
    for (const url of failedURLs) {
      const observed = await page.evaluate(async (url) => {
        const response = await fetch(url), bytes = await response.arrayBuffer();
        const digest = await crypto.subtle.digest("SHA-256", bytes);
        return { url, status: response.status, bytes: bytes.byteLength, contentLength: response.headers.get("content-length"), sha256: [...new Uint8Array(digest)].map((n) => n.toString(16).padStart(2, "0")).join("") };
      }, url);
      const file = path.resolve(dist, "." + decodeURIComponent(new URL(url).pathname));
      assert.ok(file.startsWith(dist + path.sep));
      const bytes = await fs.readFile(file), sha256 = createHash("sha256").update(bytes).digest("hex");
      assert.equal(observed.bytes, bytes.length); assert.equal(observed.sha256, sha256); assert.equal(observed.status, 200);
      results.recheckedResources.push({ ...observed, expectedBytes: bytes.length, expectedSHA256: sha256, matched: true });
    }
    await page.waitForTimeout(100); // Deliver requestfinished events after digest evaluation.
    results.networkAudit = classifyNetworkEvidence(results);
    assert.deepEqual(results.networkAudit.unexplainedErrors, [], "Unexplained browser/network errors remain after per-resource integrity audit");
    return results.networkAudit;
}
async function verifyNetwork() {
  await check("fresh-profile loading and detailed vehicle switching", async () => {
    for (const id of ["model-3", "dolphin", "su7"]) await chooseCar(id);
    await page.waitForTimeout(1500);
    const audit = await auditNetwork();
    assert.equal(results.navigation.length, 1);
    assert.equal(results.errors.filter((r) => r.type === "pageerror").length, 0);
    return { requests: results.network.length, rawErrors: results.errors.length, explainedCancellations: audit.explainedCancellations.length, unexplainedErrors: audit.unexplainedErrors.length, strictNetworkClean: audit.strictNetworkClean };
  });
  await shot("network-ready");
  // Raw cancellation events remain in results.errors. The audit only explains
  // individual fully evidenced payloads; it does not claim a clean network or
  // attribute the browser's notification to a Three.js cancellation call.
}
async function summarizeRecordedRuns() {
  const names = ["driving-2026-09-09T01-57-01-874Z.json", "driving-2026-09-09T02-02-29-965Z.json"];
  const sources = [];
  for (const file of names) {
    const bytes = await fs.readFile(path.join(out, file));
    sources.push({ file, sha256: createHash("sha256").update(bytes).digest("hex"), data: JSON.parse(bytes.toString("utf8")) });
  }
  const [functional, network] = sources.map((s) => s.data), audit = classifyNetworkEvidence(network);
  assert.equal(functional.checks.slice(0, 9).filter((c) => c.passed).length, 9);
  assert.equal(functional.tours.length, 2);
  assert.ok(functional.tours.every((t) => t.samples.at(-1).phase === "complete"));
  assert.equal(functional.build.indexModifiedAt, network.build.indexModifiedAt, "Both runs must use the same frozen dist build");
  assert.equal(audit.explainedCancellations.length, 30);
  assert.deepEqual(audit.unexplainedErrors, []);
  const rejectionCases = [
    ["initial HTTP failure", (r) => { r.network.find((n) => n.id === r.errors[0].requestId).status = 500; }],
    ["truncated initial body", (r) => { r.resourceTiming.find((t) => t.name === r.errors[0].url).encodedBodySize -= 1; }],
    ["different re-fetch hash", (r) => { r.recheckedResources.find((v) => v.url === r.errors[0].url).sha256 = "0".repeat(64); }],
    ["missing requestfinished", (r) => { const url = r.errors[0].url; r.network = r.network.filter((n) => !(n.url === url && n.outcome === "finished")); }],
    ["non-cancellation error", (r) => { r.errors.push({ type: "pageerror", error: "verification sentinel" }); }],
  ];
  for (const [name, damage] of rejectionCases) {
    const copy = structuredClone(network); damage(copy);
    assert.ok(classifyNetworkEvidence(copy).unexplainedErrors.length > 0, `Must reject ${name}`);
  }
  const summary = {
    createdAt: new Date().toISOString(),
    method: "Offline classification of immutable full functional run and fresh-profile focused network run; no rerun or alteration of historical failures",
    sources: sources.map(({ file, sha256 }) => ({ file, sha256 })),
    originalRuns: sources.map(({ file, data }) => ({ file, originalComplete: data.complete === true, originalStrictFinalGatePassed: false, preservedFailure: data.failure?.split("\n")[0], unchanged: true })),
    build: functional.build,
    functionalChecks: { passedGroups: 9, groups: functional.checks.slice(0, 9), allTenCarsPassed: functional.cars.length === 10, originalStrictNetworkGatePassed: false },
    tours: functional.tours.map((t) => ({ id: t.id, complete: t.samples.at(-1).phase === "complete", elapsedMs: t.samples.at(-1).elapsedMs, distance: t.samples.at(-1).distance, total: t.samples.at(-1).total, movingFPS: t.movingFPS })),
    rawNotifications: { fullFunctionalRun: functional.errors.length, focusedNetworkRun: network.errors.length },
    networkAudit: audit,
    classifierVerification: { positiveRecordExplained: 30, rejectedIncompleteEvidenceCases: rejectionCases.map(([name]) => name), method: "Existing captured log plus in-memory damaged copies; original files never modified" },
    strictNetworkClean: false,
    unexplainedErrors: audit.unexplainedErrors,
    underlyingCause: "unknown; no evidence that Three.js explicitly cancels these completed requests",
    acceptance: "functional checks passed; each focused-run cancellation has complete original response, matching re-fetch SHA-256, and subsequent requestfinished evidence",
    boundaries: ["Not zero network cancellation notifications", "FPS describes 360 moving frames per route at 1280x720 DPR 1 balanced quality in headless ARM Chrome; not all hardware or whole-route 60 FPS", "Seven vehicle exteriors remain prototypes", "No collision, suspension, or tire-slip simulation acceptance"],
    services: sources.map(({ file, data }) => ({ source: file, ...data.service })),
  };
  await fs.writeFile(path.join(out, "driving-acceptance-summary.json"), JSON.stringify(summary, null, 2) + "\n");
  console.log("AUDIT", "30 individually verified cancellation payloads, 0 unexplained errors, strictNetworkClean=false");
}
if (process.env.DRIVING_AUDIT_RECORDED === "1") {
  await summarizeRecordedRuns();
  process.exit(0);
}
async function cleanup() {
  if (context) { await context.close().catch(() => {}); context = undefined; }
  if (server?.listening) {
    server.closeAllConnections();
    await new Promise((resolve) => server.close(resolve));
    results.service.state = "stopped";
    results.service.stoppedAt = new Date().toISOString();
  }
}
for (const signal of ["SIGINT", "SIGTERM"]) process.once(signal, async () => {
  results.failure = `Interrupted by ${signal}`;
  await cleanup(); await persist(); process.exit(1);
});

try {
  await fs.mkdir(out, { recursive: true });
  await startServer();
  context = await chromium.launchPersistentContext(path.join(root, networkOnly ? `.tooling/driving-network-${runId}` : ".tooling/driving-acceptance-browser"), {
    executablePath: path.join(root, "scripts/chrome-native.sh"), headless: true,
    viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1,
    args: ["--no-first-run", "--disable-background-networking", "--use-angle=metal", "--enable-gpu", `--disk-cache-dir=${path.join(root, ".tooling/driving-acceptance-cache")}`],
  });
  page = context.pages()[0] || await context.newPage();
  const requestRecords = new WeakMap();
  page.on("request", (request) => {
    const entry = { id: results.network.length + 1, url: request.url(), method: request.method(), resourceType: request.resourceType(), startedAt: new Date().toISOString() };
    results.network.push(entry); requestRecords.set(request, entry);
  });
  page.on("response", (response) => {
    const entry = requestRecords.get(response.request());
    if (entry) Object.assign(entry, { status: response.status(), headers: response.headers(), responseAt: new Date().toISOString() });
  });
  page.on("requestfinished", (request) => {
    const entry = requestRecords.get(request);
    if (entry) Object.assign(entry, { outcome: "finished", finishedAt: new Date().toISOString() });
  });
  page.on("console", (message) => { if (["error", "warning"].includes(message.type())) results.console.push({ type: message.type(), text: message.text(), at: new Date().toISOString() }); });
  page.on("pageerror", (error) => results.errors.push({ type: "pageerror", error: String(error), at: new Date().toISOString() }));
  page.on("requestfailed", (request) => {
    const entry = requestRecords.get(request), error = request.failure()?.errorText;
    if (entry) Object.assign(entry, { outcome: "failed", error, failedAt: new Date().toISOString() });
    results.errors.push({ type: "requestfailed", requestId: entry?.id, url: request.url(), method: request.method(), resourceType: request.resourceType(), status: entry?.status, error, at: new Date().toISOString() });
  });
  page.on("framenavigated", (frame) => { if (frame === page.mainFrame()) results.navigation.push({ url: frame.url(), at: new Date().toISOString() }); });
  results.browser = context.browser().version();
  await page.goto(baseURL + "/", { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => window.tourDiagnostics?.wheels?.length === 4, {}, { timeout: 180000 });
  if (networkOnly) {
    await verifyNetwork();
  } else {
  if (await page.locator("body").getAttribute("data-quality") !== "balanced") {
    await click("sources"); await page.locator("#quality").selectOption("balanced"); await click("close");
  }
  await shot("home");
  const ids = JSON.parse(await fs.readFile(path.join(root, "src/tour/cars.json"), "utf8")).map((c) => c.id);
  await check("all ten vehicles: four wheel rigs, rolling, steering, coasting, braking", async () => {
    for (const id of ids) {
      await chooseCar(id);
      await page.locator('[data-action="route"][data-value="0"]').click();
      await click("manual");
      await chooseCamera("vehicle");
      const start = await diag();
      assert.equal(start.wheels.length, 4, `${id}: must have four wheels`);
      const before = wheelMap(start);
      for (const w of start.wheels) {
        assert.ok(Number.isFinite(wheelRoll(w)), `${id}: finite roll angle`);
        assert.ok(w.radius > 0.2 && w.radius < 0.6, `${id}: plausible wheel radius`);
      }
      await hold(["w"], 1600);
      const rolling = await diag();
      assert.ok(rolling.speed > 1, `${id}: accelerator increases speed`);
      assert.ok(rolling.travelled - start.travelled > 1, `${id}: real vehicle travels`);
      for (const [name, wheel] of wheelMap(rolling)) {
        const expected = (rolling.travelled - start.travelled) / wheel.radius;
        const change = wheelRoll(wheel) - wheelRoll(before.get(name));
        assert.ok(angularDistance(Math.abs(change), expected) < 0.15, `${id}/${name}: wheel angle corresponds to distance/radius`);
      }
      await page.waitForTimeout(650);
      const coast = await diag();
      assert.ok(coast.speed > 0 && coast.speed < rolling.speed, `${id}: releasing gas coasts and slows`);
      assert.ok(coast.travelled > rolling.travelled, `${id}: coasting continues to move`);
      await page.keyboard.down("w"); await page.keyboard.down("d");
      await page.waitForTimeout(900);
      const steering = await diag();
      if (["su7", "model-3", "dolphin"].includes(id)) await shot(`steering-${id}`);
      await page.keyboard.up("d"); await page.keyboard.up("w");
      const front = steering.wheels.filter(frontWheel), rear = steering.wheels.filter((w) => !frontWheel(w));
      assert.equal(front.length, 2, `${id}: two front wheels`);
      assert.equal(rear.length, 2, `${id}: two rear wheels`);
      assert.ok(front.every((w) => Math.abs(wheelSteer(w)) > 0.03), `${id}: both front wheels steer`);
      assert.ok(rear.every((w) => Math.abs(wheelSteer(w)) < 0.001), `${id}: rear wheels do not steer`);
      await brakeToStop();
      const stopped = await diag();
      await page.waitForTimeout(500);
      const still = await diag();
      assert.ok(metres(stopped, still) < 0.001, `${id}: stopped body remains still`);
      for (const [name, wheel] of wheelMap(still)) assert.ok(angularDistance(wheelRoll(wheel), wheelRoll(wheelMap(stopped).get(name))) < 0.001, `${id}/${name}: stopped wheel remains still`);
      results.cars.push({ id, start: compact(start), rolling: compact(rolling), coast: compact(coast), steering: compact(steering), stopped: compact(still) });
      await shot(`wheels-${id}`);
      await click("home");
      console.log("CAR", id, "PASS");
      await persist();
    }
  });
  await check("manual without steering leaves a bend; off-route auto request never teleports; restart recovers", async () => {
    await chooseCar("su7");
    await page.locator('[data-action="route"][data-value="1"]').click();
    await click("manual");
    const initial = await diag();
    await page.keyboard.down("w");
    try { await page.waitForFunction(() => Math.abs(window.tourDiagnostics?.routeDeviation) > 8, {}, { timeout: 45000 }); }
    finally { await page.keyboard.up("w"); }
    await brakeToStop();
    const offroad = await diag();
    assert.ok(Math.abs(offroad.routeDeviation) > 6);
    assert.ok(angularDistance(offroad.pose.heading, initial.pose.heading) < 0.001, "no steering means body heading stays fixed rather than following road curvature");
    await shot("manual-offroad");
    await click("mode");
    const afterMode = await diag();
    assert.ok(metres(offroad, afterMode) < 1, "auto request must preserve current physical position");
    await page.waitForTimeout(200);
    const afterWait = await diag();
    assert.ok(metres(afterMode, afterWait) < 2, "no delayed route teleport");
    await click("restart");
    const restarted = await diag();
    assert.ok(restarted.distance < 2, "restart returns to route start");
    assert.ok(Math.abs(restarted.routeDeviation) < 3, "restart returns to roadway");
    await click("home");
    return { offroad: compact(offroad), afterMode: compact(afterMode), afterWait: compact(afterWait), restarted: compact(restarted) };
  });
  await page.locator('[data-action="route"][data-value="1"]').click();
  await click("auto");
  await page.waitForTimeout(1300);
  await click("pause");
  await check("pause freezes body and wheels", async () => {
    const before = await diag(); await page.waitForTimeout(600); const after = await diag();
    assert.equal(after.distance, before.distance); assert.equal(after.travelled, before.travelled);
    assert.deepEqual(after.wheels, before.wheels);
  });
  await check("four camera modes render", async () => {
    const modes = new Set();
    for (let i = 0; i < 4; i++) { const d = await diag(); modes.add(d.camera); await page.waitForTimeout(450); await shot(`camera-${d.camera}`); await click("camera"); }
    assert.deepEqual([...modes].sort(), ["follow", "hood", "panorama", "vehicle"]);
  });
  await check("high quality and balanced quality remain available", async () => {
    for (const quality of ["high", "balanced"]) {
      await click("sources"); await page.locator("#quality").selectOption(quality); await click("close"); await page.waitForTimeout(900);
      assert.equal(await page.locator("body").getAttribute("data-quality"), quality);
    }
  });
  await check("interface hides and restores", async () => {
    await click("photo"); assert.equal(await page.locator(".restore-ui").isVisible(), true);
    await shot("hidden-ui"); await click("photo"); assert.equal(await page.locator(".drive-dock").isVisible(), true);
  });
  for (const [index, id] of [[1, "pudong"], [0, "bund"]]) {
    await check(`${id}: complete entire automatic tour at 3x using real animation frames`, async () => {
      await click("home"); await page.locator(`[data-action="route"][data-value="${index}"]`).click(); await click("auto"); await click("rate"); await click("rate");
      await chooseCamera("follow");
      const tour = { id, samples: [], startedAt: new Date().toISOString() };
      results.tours.push(tour);
      let previous = -1; const start = Date.now();
      tour.samples.push({ ...compact(await diag()), elapsedMs: 0 });
      assert.ok(tour.samples[0].distance < 10, "full tour begins at start");
      tour.movingFPS = await movingFPS();
      while (true) {
        const d = await diag(); tour.samples.push({ ...compact(d), elapsedMs: Date.now() - start });
        assert.equal(d.route, id, "route must not reset or switch"); assert.ok(d.distance >= previous, "route progress must be monotonic"); previous = d.distance;
        console.log("TOUR", id, d.phase, Math.round(d.distance), "/", Math.round(d.total));
        if (d.phase === "complete") break;
        assert.equal(d.phase, "running", "automatic tour must keep running");
        assert.ok(Date.now() - start < 900000, "tour timeout after 15 minutes");
        await persist(); await page.waitForTimeout(12000);
      }
      tour.completedAt = new Date().toISOString();
      await shot(`${id}-complete`); await click("close");
      return { samples: tour.samples.length, movingFPS: tour.movingFPS, elapsedMs: Date.now() - start };
    });
  }
  await click("home");
  await page.setViewportSize({ width: 390, height: 844 }); await page.waitForTimeout(600);
  await shot("mobile-home");
  await check("mobile home and manual drive have no horizontal overflow; touch gas works", async () => {
    const noOverflow = () => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
    assert.equal(await noOverflow(), true); await click("manual"); await page.waitForTimeout(450);
    assert.equal(await noOverflow(), true);
    const gas = page.locator('[data-control="gas"]'); assert.equal(await gas.isVisible(), true);
    const initial = await diag(); const box = await gas.boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2); await page.mouse.down(); await page.waitForTimeout(1200); await page.mouse.up();
    const accelerated = await diag();
    assert.ok(accelerated.speed > initial.speed + 1 && accelerated.travelled > initial.travelled, "pointer input on touch accelerator moves vehicle");
    await shot("mobile-drive"); await click("pause");
    return { initial: compact(initial), accelerated: compact(accelerated) };
  });
  await check("no unexpected document navigations or unexplained errors after per-resource integrity audit", async () => {
    assert.equal(results.navigation.length, 1, JSON.stringify(results.navigation));
    return await auditNetwork();
  });
  }
  results.final = compact(await diag()); results.complete = true;
} catch (error) {
  results.failure = String(error); results.final = compact(await diag().catch(() => null));
  if (page) await shot("failure-final").catch(() => {});
  process.exitCode = 1;
} finally {
  await cleanup(); results.finishedAt = new Date().toISOString(); await persist();
  console.log("RESULT", path.join(out, `${prefix}.json`), results.complete ? "PASS" : "FAIL", results.failure || "");
}
