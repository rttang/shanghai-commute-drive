import { chromium } from "/Users/maiziheng/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs";
import fs from "node:fs/promises";
import { createReadStream } from "node:fs";
import http from "node:http";
import path from "node:path";
import assert from "node:assert/strict";
import { execFileSync, spawn } from "node:child_process";
import { createHash } from "node:crypto";

// Build the production dist first; this script never controls the simulation.
// All screenshots, profiles, HTTP evidence and scratch files remain on this disk.
const root = path.resolve(import.meta.dirname, "..");
const dist = path.join(root, "dist");
const out = path.join(root, "docs/evidence/tourism");
const runId = new Date().toISOString().replace(/[:.]/g, "-");
const prefix = `street-master-${runId}`;
const baseURL = "http://127.0.0.1:8081";
const results = {
  startedAt: new Date().toISOString(),
  method: "Production dist on isolated 8081; genuine window/tab focus and visibility; real product controls and animation loop; diagnostics are read-only",
  nodeArch: process.arch, checks: [], tours: [], screenshots: [], phases: [],
  network: [], errors: [], console: [], navigation: [], lifecycle: [], cleanupErrors: [],
};
let context, page, server, phase = "setup", browserCDP, nativeChrome, nativeBrowser;
const diag = () => page.evaluate(() => window.tourDiagnostics);
const stream = (d) => d.streetStreaming ?? d.streaming ?? d.streetStream ?? d;
const compact = (d) => d && ({
  route:d.route, mode:d.mode, phase:d.phase, pauseReason:d.pauseReason,
  distance:d.distance,total:d.total,car:d.car,camera:d.camera,
  pose:d.pose,speed:d.speed,steering:d.steering,travelled:d.travelled,
  routeDeviation:d.routeDeviation,streaming:stream(d),
});
const click = (action) => page.locator(`[data-action="${action}"]:visible`).first().click();
const browserState = () => page.evaluate(() => ({visibilityState:document.visibilityState,hidden:document.hidden,focused:document.hasFocus(),diagnostics:window.tourDiagnostics}));
async function persist() { await fs.writeFile(path.join(out, `${prefix}.json`),JSON.stringify(results,null,2)+"\n"); }
async function shot(name) {
  const file=`${prefix}-${name}.png`;
  await page.screenshot({path:path.join(out,file)});
  results.screenshots.push({name,file,phase,state:await browserState()});
}
async function check(name,fn) {
  const startedAt=new Date().toISOString();
  try {const detail=await fn();results.checks.push({name,phase,startedAt,passed:true,detail});console.log("PASS",name);}
  catch(error){results.checks.push({name,phase,startedAt,passed:false,failure:String(error),state:await browserState().catch(()=>null)});await shot(`failure-${results.checks.length}`).catch(()=>{});throw error;}
  finally {await persist();}
}
async function chooseCamera(mode) {
  for(let i=0;i<4&&(await diag()).camera!==mode;i++) await click("camera");
  assert.equal((await diag()).camera,mode);
}
async function waitChunks() {
  await page.waitForFunction(()=>{
    const d=window.tourDiagnostics,s=d&&(d.streetStreaming??d.streaming??d.streetStream??d);
    return s && Array.isArray(s.loadedChunkIds) && s.activeLoads===0 && s.pendingChunkIds.length===0;
  },{}, {timeout:180000});
  const s=stream(await diag());assert.deepEqual(s.failedChunks,[]);return s;
}
async function movingFPS(frameCount=360) {
  return page.evaluate((frameCount)=>new Promise(resolve=>{
    const samples=[];let last=performance.now();
    const tick=t=>{samples.push(t-last);last=t;
      if(samples.length<frameCount+30)requestAnimationFrame(tick);
      else{const frames=samples.slice(30),sorted=[...frames].sort((a,b)=>a-b);resolve({sampleFrames:frames.length,fps:1000*frames.length/frames.reduce((a,b)=>a+b,0),p95FrameMs:sorted[Math.floor(sorted.length*.95)],maxFrameMs:sorted.at(-1),viewport:[innerWidth,innerHeight],dpr:devicePixelRatio,quality:document.body.dataset.quality,diagnostics:window.tourDiagnostics});}
    };requestAnimationFrame(tick);
  }),frameCount);
}
async function startServer() {
  // Ownership preflight: never stop or replace an existing listener.
  let listeners = "";
  try { listeners = execFileSync("/usr/sbin/lsof", ["-nP", "-iTCP:8081", "-sTCP:LISTEN"], { encoding: "utf8" }); }
  catch (error) { if (error.status !== 1) throw error; }
  assert.equal(listeners.trim(), "", `Port 8081 already has a listener: ${listeners}`);
  const index = await fs.stat(path.join(dist, "index.html"));
  const indexText=await fs.readFile(path.join(dist,"index.html"),"utf8");
  const scripts=[...indexText.matchAll(/<script[^>]+src="([^"]+)"/g)].map(m=>m[1]);
  const scriptAssets=[];for(const url of scripts)scriptAssets.push({url,sha256:await hashFile(assetPath(url))});
  results.build = { root: dist, indexModifiedAt: index.mtime.toISOString(), indexSHA256:await hashFile(path.join(dist,"index.html")), scriptAssets };
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
    const firstTiming = record.resourceTiming?.find((t) => t.name === error.url && t.phase === error.phase);
    const recheck = record.recheckedResources?.find((r) => r.url === error.url && r.phase === error.phase);
    const laterFinished = record.network?.find((n) => n.url === error.url && n.phase === error.phase && n.id > error.requestId && n.outcome === "finished" && n.status === 200 && Number(n.headers?.["content-length"]) === recheck?.bytes);
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
      requestId: error.requestId, url: error.url, phase: error.phase,
      classification: "cancellation notification with fully received and independently verified payload",
      initialStatus: request.status, initialContentLength: contentLength,
      initialEncodedBodySize: firstTiming.encodedBodySize,
      recheckBytes: recheck.bytes, recheckSHA256: recheck.sha256,
      successfulRequestId: laterFinished.id,
      underlyingCause: "unknown",
    });
  }
  for (const request of record.network ?? []) if (request.status >= 400) unexplainedErrors.push({ type: "http", requestId: request.id, url: request.url, status: request.status });
  for (const entry of record.console ?? [])
    if (entry.type === "error" || /GL_INVALID_OPERATION|sampler.*mismatch|WebGL.*CONTEXT_LOST/i.test(entry.text))
      unexplainedErrors.push({ type: "console", ...entry });
  return { strictNetworkClean: record.errors.length === 0 && unexplainedErrors.length === 0, rawErrorCount: record.errors.length, explainedCancellations, unexplainedErrors, underlyingCause: "unknown" };
}
async function auditNetwork() {
    // Capture the original responses before any explicit verification fetches.
    const timings = await page.evaluate(() => performance.getEntriesByType("resource").map((r) => ({ name: r.name, initiatorType: r.initiatorType, duration: r.duration, transferSize: r.transferSize, encodedBodySize: r.encodedBodySize, decodedBodySize: r.decodedBodySize, responseStatus: r.responseStatus })));
    results.resourceTiming = [...(results.resourceTiming ?? []), ...timings.map(t=>({...t,phase}))];
    results.recheckedResources ??= [];
    const failedURLs = [...new Set(results.errors.filter((r) => r.phase === phase && r.type === "requestfailed" && r.error === "net::ERR_ABORTED" && r.method === "GET" && r.resourceType === "fetch" && r.status === 200 && r.url.startsWith(baseURL + "/")).map((r) => r.url))];
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
      results.recheckedResources.push({ ...observed, phase, expectedBytes: bytes.length, expectedSHA256: sha256, matched: true });
    }
    await page.waitForTimeout(100); // Deliver requestfinished events after digest evaluation.
    results.networkAudit = classifyNetworkEvidence(results);
    assert.deepEqual(results.networkAudit.unexplainedErrors, [], "Unexplained browser/network errors remain after per-resource integrity audit");
    return results.networkAudit;
}
async function openBrowser(name, headless) {
  phase=name;
  const profile=path.join(root,`.tooling/${prefix}-${name}`);
  if(!headless){
    await fs.mkdir(profile,{recursive:true});
    nativeChrome=spawn(path.join(root,"scripts/chrome-native.sh"),[`--user-data-dir=${profile}`,"--remote-debugging-port=0","--remote-debugging-address=127.0.0.1","--no-first-run","--no-default-browser-check","--disable-background-networking","--use-angle=metal","--enable-gpu",`--disk-cache-dir=${path.join(root,`.tooling/${prefix}-${name}-cache`)}`,"about:blank"],{cwd:root,stdio:["ignore","ignore","pipe"]});
    nativeChrome.once("exit",(code,signal)=>results.lifecycle.push({phase,event:"native-chrome-exit",code,signal,at:new Date().toISOString()}));
    const startup=[];nativeChrome.stderr.on("data",data=>{if(startup.length<30)startup.push(data.toString());});
    let port;
    for(let i=0;i<150;i++){
      if(nativeChrome.exitCode!==null)throw new Error(`Isolated Chrome exited: ${startup.join("")}`);
      try{port=Number((await fs.readFile(path.join(profile,"DevToolsActivePort"),"utf8")).split("\n")[0]);if(port>0)break;}catch{}
      await new Promise(resolve=>setTimeout(resolve,100));
    }
    assert.ok(port>0,"Isolated Chrome did not publish a local CDP port");
    nativeBrowser=await chromium.connectOverCDP(`http://127.0.0.1:${port}`,{noDefaults:true,isLocal:true});
    nativeBrowser.on("disconnected",()=>results.lifecycle.push({phase,event:"browser-disconnected",at:new Date().toISOString()}));
    context=nativeBrowser.contexts()[0];
    results.nativeBrowser={pid:nativeChrome.pid,profile,port,noDefaults:true,focusMethod:"Native Chrome window/tab activation; Playwright default focus emulation not enabled"};
  }else context=await chromium.launchPersistentContext(profile,{
    executablePath:path.join(root,"scripts/chrome-native.sh"),headless,
    viewport:{width:1280,height:720},deviceScaleFactor:1,
    args:["--no-first-run","--disable-background-networking","--use-angle=metal","--enable-gpu",`--disk-cache-dir=${path.join(root,`.tooling/${prefix}-${name}-cache`)}`],
  });
  browserCDP=await context.browser().newBrowserCDPSession();
  page=context.pages()[0]||await context.newPage();
  page.on("close",()=>results.lifecycle.push({phase,event:"main-page-close",at:new Date().toISOString()}));
  page.on("crash",()=>results.errors.push({phase,type:"page-crash",at:new Date().toISOString()}));
  if(!headless)await page.setViewportSize({width:1280,height:720});
  // Keep Resource Timing observations for a long streaming tour; this only
  // expands the browser's measurement buffer and never writes game state.
  await page.addInitScript(()=>{
    performance.setResourceTimingBufferSize(5000);
    // Passive focus evidence: never change visibility, input or product state.
    window.__focusEvidence=[];
    const record=(event)=>{
      const active=document.activeElement;
      window.__focusEvidence.push({event,at:Date.now(),hidden:document.hidden,
        focused:document.hasFocus(),dialogOpen:document.querySelector("dialog")?.open,
        active:active?`${active.tagName}:${active.getAttribute("data-action")??""}:${active.getAttribute("data-value")??""}`:null,
        car:window.tourDiagnostics?.car,phase:window.tourDiagnostics?.phase,
        pauseReason:window.tourDiagnostics?.pauseReason});
    };
    for(const name of ["visibilitychange","focus","blur","focusin","focusout","close"])
      document.addEventListener(name,()=>record(name),true);
    for(const name of ["focus","blur"])window.addEventListener(name,()=>record(`window-${name}`));
    document.addEventListener("DOMContentLoaded",()=>{
      new MutationObserver(mutations=>{
        if(mutations.some(m=>m.target instanceof HTMLDialogElement&&m.attributeName==="open"))record("dialog-open-change");
      }).observe(document.body,{subtree:true,attributes:true,attributeFilter:["open"]});
    });
  });
  const requestRecords=new WeakMap();
  page.on("request",request=>{const entry={id:results.network.length+1,phase,url:request.url(),method:request.method(),resourceType:request.resourceType(),startedAt:new Date().toISOString()};results.network.push(entry);requestRecords.set(request,entry);});
  page.on("response",response=>{const entry=requestRecords.get(response.request());if(entry)Object.assign(entry,{status:response.status(),headers:response.headers(),responseAt:new Date().toISOString()});});
  page.on("requestfinished",request=>{const entry=requestRecords.get(request);if(entry)Object.assign(entry,{outcome:"finished",finishedAt:new Date().toISOString()});});
  page.on("requestfailed",request=>{const entry=requestRecords.get(request),error=request.failure()?.errorText;if(entry)Object.assign(entry,{outcome:"failed",error,failedAt:new Date().toISOString()});results.errors.push({type:"requestfailed",phase,requestId:entry?.id,url:request.url(),method:request.method(),resourceType:request.resourceType(),status:entry?.status,error,at:new Date().toISOString()});});
  page.on("pageerror",error=>results.errors.push({type:"pageerror",phase,error:String(error),at:new Date().toISOString()}));
  page.on("console",message=>{if(["error","warning"].includes(message.type()))results.console.push({phase,type:message.type(),text:message.text(),at:new Date().toISOString()});});
  page.on("framenavigated",frame=>{if(frame===page.mainFrame())results.navigation.push({phase,url:frame.url(),at:new Date().toISOString()});});
  await page.goto(baseURL+"/",{waitUntil:"domcontentloaded"});
  await page.bringToFront();
  await page.waitForFunction(()=>window.tourDiagnostics?.wheels?.length===4,{}, {timeout:240000});
  await waitChunks();
  results.phases.push({name,headless,browser:context.browser().version(),readyAt:new Date().toISOString(),readyDiagnostics:compact(await diag())});
}
async function closeBrowser() {
  if(nativeBrowser){await nativeBrowser.close().catch(()=>{});nativeBrowser=undefined;}
  else if(context)await context.close().catch(()=>{});
  if(nativeChrome){if(nativeChrome.exitCode===null){nativeChrome.kill("SIGTERM");await Promise.race([new Promise(resolve=>nativeChrome.once("exit",resolve)),new Promise(resolve=>setTimeout(resolve,5000))]);}if(results.nativeBrowser)results.nativeBrowser.stopped=nativeChrome.exitCode!==null;nativeChrome=undefined;}
  context=undefined;page=undefined;browserCDP=undefined;
}
async function cleanup() {
  await closeBrowser();
  if(server?.listening){server.closeAllConnections();await new Promise(resolve=>server.close(resolve));results.service.state="stopped";results.service.stoppedAt=new Date().toISOString();}
}
async function targetFor(p) {const session=await context.newCDPSession(p);const result=await session.send("Target.getTargetInfo");await session.detach();return result.targetInfo.targetId;}
async function newActualTarget(newWindow, background=false) {
  const arrived=context.waitForEvent("page");
  const {targetId}=await browserCDP.send("Target.createTarget",{url:"about:blank",newWindow,background});
  const targetPage=await arrived;
  await targetPage.waitForLoadState("domcontentloaded");
  assert.equal(await targetFor(targetPage),targetId,"New page event must belong to the requested native browser target");
  return {page:targetPage,targetId,window:(await browserCDP.send("Browser.getWindowForTarget",{targetId})).windowId};
}
async function assertPaused(reason) {
  await page.waitForFunction(reason=>window.tourDiagnostics?.phase==="paused"&&window.tourDiagnostics?.pauseReason===reason,reason,{timeout:10000,polling:100});
  const first=await diag();await page.waitForTimeout(500);const second=await diag();
  assert.equal(second.travelled,first.travelled);return compact(second);
}
async function resumeViaButton() {
  const button=page.getByRole("button",{name:"继续行程",exact:true});
  assert.equal(await button.isVisible(),true);assert.match(await button.innerText(),/继续/);
  await button.click();
  await page.waitForFunction(()=>window.tourDiagnostics?.phase==="running",{}, {timeout:10000});
}
async function verifyPauseBehaviour() {
  await openBrowser("pause",false);
  const mainTarget=await targetFor(page),mainWindow=(await browserCDP.send("Browser.getWindowForTarget",{targetId:mainTarget})).windowId;
  const screen=await page.evaluate(()=>({width:window.screen.availWidth,height:window.screen.availHeight}));
  await browserCDP.send("Browser.setWindowBounds",{windowId:mainWindow,bounds:{left:0,top:30,width:Math.max(680,Math.floor(screen.width*.65)),height:Math.min(820,screen.height-50),windowState:"normal"}});
  const otherWindow=await newActualTarget(true);
  await browserCDP.send("Browser.setWindowBounds",{windowId:otherWindow.window,bounds:{left:Math.floor(screen.width*.68),top:40,width:Math.max(320,Math.floor(screen.width*.3)),height:300,windowState:"normal"}});
  results.focusTestWindows={screen,mainTarget,mainWindow,otherTarget:otherWindow.targetId,otherWindow:otherWindow.window,mainBounds:(await browserCDP.send("Browser.getWindowBounds",{windowId:mainWindow})).bounds,otherBounds:(await browserCDP.send("Browser.getWindowBounds",{windowId:otherWindow.window})).bounds};
  await page.bringToFront();
  await click("auto");
  await check("visible automatic sightseeing survives window blur",async()=>{
    const before=await diag();await otherWindow.page.bringToFront();
    await page.waitForFunction(()=>!document.hidden&&!document.hasFocus(),{}, {timeout:10000});
    await page.waitForTimeout(1200);const state=await browserState();
    assert.equal(state.diagnostics.phase,"running");assert.ok(state.diagnostics.distance>before.distance);
    await page.bringToFront();return state;
  });
  await check("manual blur pauses and clears a held accelerator",async()=>{
    await click("home");await click("manual");await page.keyboard.down("w");await page.waitForTimeout(1400);
    await otherWindow.page.bringToFront();await page.waitForFunction(()=>!document.hidden&&!document.hasFocus(),{}, {timeout:10000});
    const paused=await assertPaused("blur");await page.bringToFront();await shot("desktop-blur-continue");
    await resumeViaButton();const resumed=await diag();await page.waitForTimeout(800);const released=await diag();
    await page.keyboard.up("w");assert.ok(released.speed<resumed.speed,"Held W must not remain active after blur");
    return {paused,resumed:compact(resumed),after:compact(released)};
  });
  await otherWindow.page.close();await page.bringToFront();
  const otherTab=await newActualTarget(false,true);
  assert.equal(otherTab.window,mainWindow,"Visibility test requires a real second tab in the same window");
  results.focusTestWindows.backgroundTab={targetId:otherTab.targetId,windowId:otherTab.window};
  await check("inactive browser tab pauses in background and does not resume on return",async()=>{
    await click("home");await click("auto");await click("photo");assert.equal(await page.locator(".restore-ui").isVisible(),true);await otherTab.page.bringToFront();
    await page.waitForFunction(()=>document.hidden,{}, {timeout:10000});
    const hidden=await assertPaused("background");await page.bringToFront();
    const returned=await assertPaused("background");assert.equal(await page.locator(".drive-dock").isVisible(),true,"Safety pause must restore its continue control from photo mode");await resumeViaButton();return {hidden,returned};
  });
  await check("explicit user pause survives opening and closing a dialog",async()=>{
    await click("pause");const paused=await assertPaused("user");await click("sources");await click("close");
    const after=await assertPaused("user");await resumeViaButton();return {paused,after};
  });
  await check("390px viewport exposes a working continue button",async()=>{
    await page.setViewportSize({width:390,height:844});await click("pause");await assertPaused("user");await shot("mobile-continue");
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await resumeViaButton();await page.waitForTimeout(400);assert.equal((await diag()).phase,"running");await shot("mobile-resumed");
  });
  await page.setViewportSize({width:1280,height:720});
  await check("an async garage dialog closing in background cannot resume the tour",async()=>{
    const session=await context.newCDPSession(page);await session.send("Network.enable");
    await session.send("Network.emulateNetworkConditions",{offline:false,latency:1800,downloadThroughput:250000,uploadThroughput:250000});
    try{
      await click("garage");await assertPaused("dialog");
      await page.locator('[data-action="car"][data-value="model-3"]').click();
      await otherTab.page.bringToFront();await page.waitForFunction(()=>document.hidden,{}, {timeout:10000});
      await page.waitForFunction(()=>window.tourDiagnostics?.car==="model-3",{}, {timeout:120000,polling:100});
      await page.waitForTimeout(700);
      const state=await browserState();assert.equal(state.hidden,true);assert.equal(state.diagnostics.phase,"paused");assert.equal(state.diagnostics.pauseReason,"background");
      await page.bringToFront();
      await page.waitForFunction(()=>!document.querySelector("dialog")?.open,{}, {timeout:10000});
      await assertPaused("background");await shot("background-dialog-closed");await resumeViaButton();return state;
    }finally{
      results.focusEvidence=await page.evaluate(()=>window.__focusEvidence);
      results.backgroundTabState=await otherTab.page.evaluate(()=>({hidden:document.hidden,focused:document.hasFocus()}));
      await session.send("Network.emulateNetworkConditions",{offline:false,latency:0,downloadThroughput:-1,uploadThroughput:-1}).catch(error=>results.cleanupErrors.push(String(error)));await session.detach().catch(error=>results.cleanupErrors.push(String(error)));
    }
  });
  await click("pause");await waitChunks();await auditNetwork();
  assert.equal(results.navigation.filter(n=>n.phase===phase).length,1);
  await closeBrowser();
}
function assetPath(url) {
  const file=path.resolve(dist,"."+new URL(url,baseURL).pathname);
  assert.ok(file.startsWith(dist+path.sep),"Asset must remain inside dist");return file;
}
async function hashFile(file) {
  const hash=createHash("sha256");for await(const chunk of createReadStream(file))hash.update(chunk);return hash.digest("hex");
}
async function inspectMasterManifest() {
  const manifestFile=path.join(dist,"streets/master/manifest.json");
  const manifest=JSON.parse(await fs.readFile(manifestFile,"utf8"));
  assert.ok(Array.isArray(manifest.chunks)&&manifest.chunks.length>0);
  const masterFile=assetPath(manifest.master.file),masterSize=(await fs.stat(masterFile)).size;
  const budget=JSON.parse(await fs.readFile(path.join(dist,'streets/model-budget.json'),'utf8')).streetMaster;
  assert.equal(masterSize,manifest.master.bytes);assert.ok(masterSize>budget.minBytesExclusive&&masterSize<budget.maxBytesExclusive,"Street master must fit its GLB byte-length field");
  assert.ok(manifest.chunks.reduce((sum,c)=>sum+c.bytes,0)<=budget.runtimePackageMaxBytesInclusive,"Street runtime resources exceed the approved 5 GB budget");
  assert.equal(await hashFile(masterFile),manifest.master.sha256);
  for(const chunk of manifest.chunks){
    assert.equal((await fs.stat(assetPath(chunk.file))).size,chunk.bytes,`${chunk.id}: declared bytes match actual file`);
    assert.ok(chunk.bounds.length===4&&chunk.bounds.every(Number.isFinite));assert.ok(Array.isArray(chunk.coveredWays));
  }
  const coverageFile=path.join(root,"references/tourism/street-frontage-coverage.json");
  const coverage=JSON.parse(await fs.readFile(coverageFile,"utf8"));
  const firstRow=coverage.buildings.filter(b=>b.frontage.classification==="first-row-sampled");
  const masterWays=new Set(manifest.coveredWays),chunkWays=new Set(manifest.chunks.flatMap(c=>c.coveredWays));
  for(const route of ["bund","pudong"]){
    const expected=firstRow.filter(b=>b.route===route);assert.equal(expected.length,route==="bund"?57:85);
    for(const b of expected){assert.ok(masterWays.has(b.wayId),`${b.wayId} missing from master`);assert.ok(chunkWays.has(b.wayId),`${b.wayId} missing from runtime chunks`);}
  }
  results.master={manifestFile:path.relative(root,manifestFile),manifestSHA256:await hashFile(manifestFile),file:manifest.master.file,bytes:masterSize,sha256:await hashFile(masterFile),chunks:manifest.chunks.length,runtimeDeclaredBytes:manifest.chunks.reduce((a,c)=>a+c.bytes,0),coveredWays:manifest.coveredWays,firstRowCounts:{bund:57,pudong:85},coverageSHA256:await hashFile(coverageFile)};
  return {manifest,coverage,firstRow};
}
// Distances are real route metres. Landmark names use the checked frontage inventory.
const CHECKPOINTS={
  bund:[{distance:0,name:"bridge-north-approach"},{distance:105,name:"bridge-south-exit"},{distance:175,name:"suzhou-road-bend"},{distance:330,name:"north-bund-street-corner"},{distance:500,name:"bank-of-china"},{distance:550,name:"peace-hotel"},{distance:610,name:"bund-18"},{distance:810,name:"customs-house"},{distance:880,name:"hsbc-bund"},{distance:1100,name:"bund-south-frontage"},{distance:1250,name:"bund-south-street-corner"},{distance:1480,name:"bund-return-corner"},{distance:1715,name:"bund-route-end"}],
  pudong:[{distance:0,name:"pearl-start"},{distance:140,name:"riverside-bend"},{distance:320,name:"lujiazui-ring-corner"},{distance:560,name:"ocean-aquarium"},{distance:730,name:"north-pudong-corner"},{distance:1050,name:"financial-district-frontage"},{distance:1220,name:"hang-seng"},{distance:1450,name:"east-pudong-frontage"},{distance:1810,name:"east-pudong-bend"},{distance:2250,name:"shanghai-tower"},{distance:2590,name:"south-pudong-corner"},{distance:2990,name:"bea-tower"},{distance:3310,name:"pudong-return-frontage"},{distance:3740,name:"pudong-route-end"}],
};
async function sceneryViews(route,point,index,firstRow) {
  const before=await diag();if(before.phase==="running")await click("pause");await assertPaused("user");
  const chunks=await waitChunks();
  const expectedNearbyFirstRowWays=firstRow.filter(b=>b.route===route&&b.frontage.routeStartM<=before.distance+90&&b.frontage.routeEndM>=before.distance-90).map(b=>({wayId:b.wayId,name:b.name,confidence:b.confidence,photoRef:b.photoRef}));
  await chooseCamera("hood");await page.waitForTimeout(500);await shot(`${route}-${String(index).padStart(2,"0")}-${point.name}-hood`);
  const y=310,x=640;
  await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x-250,y,{steps:20});await page.mouse.up();await page.waitForTimeout(300);
  await shot(`${route}-${String(index).padStart(2,"0")}-${point.name}-left`);
  await page.mouse.move(x-250,y);await page.mouse.down();await page.mouse.move(x+250,y,{steps:30});await page.mouse.up();await page.waitForTimeout(300);
  await shot(`${route}-${String(index).padStart(2,"0")}-${point.name}-right`);
  if(index===0||index%3===0){await chooseCamera("panorama");await page.waitForTimeout(500);await shot(`${route}-${String(index).padStart(2,"0")}-${point.name}-overview`);}
  // Cycle through a different camera to reset the orbit using real UI controls.
  await chooseCamera("follow");await chooseCamera("hood");
  const record={...point,actualDistance:before.distance,expectedNearbyFirstRowWays,loadedChunkIds:chunks.loadedChunkIds,loadedBytes:chunks.loadedBytes,interpretation:"Screenshots and loaded coverage are evidence for visual review, not an automatic claim of photo fidelity"};
  await resumeViaButton();return record;
}
async function verifyWholeRoutes(data) {
  await openBrowser("routes",true);await click("garage");await page.locator('[data-action="car"][data-value="su7"]').click();
  await page.waitForFunction(()=>window.tourDiagnostics?.car==="su7",{}, {timeout:60000});
  for(const [routeIndex,id] of [[0,"bund"],[1,"pudong"]]){
    await check(`${id}: complete route with first-row coverage and near-street views`,async()=>{
      if(routeIndex>0)await click("home");
      await page.locator(`[data-action="route"][data-value="${routeIndex}"]`).click();await click("auto");await click("rate");await click("rate");
      await chooseCamera("hood");
      assert.ok((await diag()).distance<10,"Whole route must begin at its real starting point");
      const tour={id,startedAt:new Date().toISOString(),samples:[],views:[],movingWindows:[],loadedChunkIds:[]};results.tours.push(tour);
      const checkpoints=CHECKPOINTS[id];let next=0,previous=-1;const loaded=new Set(),start=Date.now();
      while(true){
        const d=await diag(),s=stream(d);assert.equal(d.route,id);assert.ok(d.distance>=previous,"Unexpected route reset");previous=d.distance;
        assert.deepEqual(s.failedChunks,[]);assert.ok(s.activeLoads<=2,"Streaming concurrency exceeds two");s.loadedChunkIds.forEach(c=>loaded.add(c));
        tour.samples.push({...compact(d),elapsedMs:Date.now()-start});
        if(d.phase==="complete")break;
        assert.equal(d.phase,"running");assert.ok(Date.now()-start<1800000,"Tour exceeded 30 minutes");
        if(next<checkpoints.length&&d.distance>=checkpoints[next].distance){
          const view=await sceneryViews(id,checkpoints[next],next,data.firstRow);tour.views.push(view);view.loadedChunkIds.forEach(c=>loaded.add(c));next++;
          if(tour.movingWindows.length<2&&(next===3||d.distance>d.total*.55)){
            // Measure ordinary 1x moving frames, then return to 3x sightseeing.
            await click("rate");const fps=await movingFPS();fps.rate="1x";tour.movingWindows.push(fps);await click("rate");await click("rate");
          }
          console.log("VIEW",id,next,"/",checkpoints.length,Math.round(d.distance));await persist();
        }else await page.waitForTimeout(400);
      }
      tour.loadedChunkIds=[...loaded];
      const covered=new Set(data.manifest.chunks.filter(c=>loaded.has(c.id)).flatMap(c=>c.coveredWays));
      const expected=data.firstRow.filter(b=>b.route===id).map(b=>b.wayId);tour.missingFirstRowWays=expected.filter(id=>!covered.has(id));
      assert.deepEqual(tour.missingFirstRowWays,[],"Expected first-row building chunks were never observed loaded");assert.equal(next,checkpoints.length);
      assert.ok(tour.movingWindows.length>0);await shot(`${id}-complete`);await click("close");tour.completedAt=new Date().toISOString();
      return {distance:(await diag()).distance,firstRowBuildings:expected.length,checkpoints:tour.views.length,movingWindows:tour.movingWindows};
    });
  }
  await click("home");await waitChunks();
  const chunkPaths=new Set(data.manifest.chunks.map(c=>new URL(c.file,baseURL).pathname));
  const runtimeRequests=results.network.filter(n=>n.phase==="routes"&&chunkPaths.has(new URL(n.url).pathname));
  const masterRequests=results.network.filter(n=>new URL(n.url).pathname===new URL(data.manifest.master.file,baseURL).pathname);
  assert.equal(masterRequests.length,0,"Runtime must not download the monolithic master GLB");
  results.resources={declaredRuntimeBytes:results.master.runtimeDeclaredBytes,uniqueRuntimeFilesRequested:new Set(runtimeRequests.map(n=>n.url)).size,runtimeRequestCount:runtimeRequests.length,loadedBytesAtEnd:stream(await diag()).loadedBytes,masterRequestCount:masterRequests.length};
  await check("per-resource network integrity and no unexpected document navigation",async()=>{
    const audit=await auditNetwork();assert.equal(results.navigation.filter(n=>n.phase===phase).length,1);return audit;
  });
  results.resources.measuredTransferBytes=(results.resourceTiming??[]).filter(t=>t.phase==="routes").reduce((sum,t)=>sum+t.transferSize,0);
  await closeBrowser();
}
for(const signal of ["SIGINT","SIGTERM"])process.once(signal,async()=>{results.failure=`Interrupted by ${signal}`;await cleanup();await persist();process.exit(1);});
try{
  await fs.mkdir(out,{recursive:true});results.verifierSHA256=await hashFile(path.join(root,"scripts/verify_street_master_browser.mjs"));await startServer();
  const data=await inspectMasterManifest();
  if(process.env.STREET_MASTER_PHASE!=="routes")await verifyPauseBehaviour();
  if(process.env.STREET_MASTER_PHASE!=="pause")await verifyWholeRoutes(data);
  results.complete=true;
}catch(error){results.failure=String(error);if(page){results.finalState=await browserState().catch(()=>null);await shot("failure-final").catch(()=>{});}process.exitCode=1;}
finally{await cleanup();results.finishedAt=new Date().toISOString();await persist();console.log("RESULT",path.join(out,`${prefix}.json`),results.complete?"PASS":"FAIL",results.failure||"");}
