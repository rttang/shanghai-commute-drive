import { chromium } from '/Users/maiziheng/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { createStaticServer } from './serve-release.mjs';
const root=path.resolve(import.meta.dirname,'..');
const baseline=process.argv.includes('--baseline');
const tag=baseline?'baseline':'optimized';
const out=path.join(root,'docs/evidence/deployment-optimization');
const server=createStaticServer({directory:path.join(root,baseline?'.tooling/deployment-optimization/baseline-site':'dist-release'),fallbackDirectory:baseline?path.join(root,'public'):undefined});
await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(8081,'127.0.0.1',resolve);});
let context;
const result={tag,startedAt:new Date().toISOString(),errors:[],network:[],screenshots:[],runs:[]};
if(!baseline)result.buildManifestSha256=createHash('sha256').update(await fs.readFile(path.join(root,'dist-release/release-manifest.json'))).digest('hex');
try {
  context=await chromium.launchPersistentContext(path.join(root,`.tooling/deployment-optimization/browser-${tag}-${Date.now()}`),{executablePath:path.join(root,'scripts/chrome-native.sh'),headless:true,viewport:{width:1280,height:720},deviceScaleFactor:1,args:['--no-first-run','--disable-background-networking','--use-angle=metal','--enable-gpu']});
  const page=await context.newPage();
  page.on('pageerror',e=>{result.errors.push(e.message);console.log('PAGE ERROR',e.message);});
  page.on('response',r=>{if(r.status()>=400)result.errors.push(`${r.status()} ${r.url()}`);});
  const snapshot=()=>page.evaluate(()=>({resources:performance.getEntriesByType('resource').map(r=>({url:r.name,transferSize:r.transferSize,encodedBodySize:r.encodedBodySize,decodedBodySize:r.decodedBodySize,duration:r.duration})),diagnostics:window.tourDiagnostics,ms:performance.now()}));
  await page.goto('http://127.0.0.1:8081/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.body.classList.contains('ready'),null,{timeout:180000});
  const interactiveMs=await page.evaluate(()=>performance.now());
  // Include the initial thumbnail/background even if controls become ready before image transfer ends.
  await page.waitForLoadState('networkidle');
  result.runs.push({phase:'home',...await snapshot(),interactiveMs});
  await page.screenshot({path:path.join(out,`${tag}-home.png`)});
  const launchMs=await page.evaluate(()=>performance.now());
  await page.locator('[data-action="auto"]:visible').click();
  await page.waitForFunction(()=>window.tourDiagnostics?.phase==='running'||document.querySelector('[data-action="retry-load"]'),null,{timeout:180000});
  assert.equal(await page.locator('[data-action="retry-load"]').count(),0,'Initial scene load failed');
  const sceneReadyMs=await page.evaluate(()=>performance.now());
  await page.locator('[data-action="pause"]:visible').click();
  result.runs.push({phase:'driving',...await snapshot(),clickToSceneReadyMs:sceneReadyMs-launchMs});
  await page.screenshot({path:path.join(out,`${tag}-driving.png`)});
  for(const route of ['bund','pudong']){
    await page.goto(`http://127.0.0.1:8081/streets-review.html?route=${route}&distance=600&view=hood`,{waitUntil:'domcontentloaded'});
    await page.waitForFunction(()=>Boolean(document.body.dataset.review),null,{timeout:180000});
    await page.waitForFunction(()=>Boolean(document.body.dataset.sample),null,{timeout:120000});
    const file=`${tag}-${route}-hood.png`;
    await page.screenshot({path:path.join(out,file)});
    result.screenshots.push({file,route,sample:await page.evaluate(()=>JSON.parse(document.body.dataset.sample))});
  }
  await page.goto('http://127.0.0.1:8081/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.body.classList.contains('ready'),null,{timeout:180000});
  await page.locator('[data-action="auto"]:visible').click();
  await page.waitForFunction(()=>window.tourDiagnostics?.phase==='running',null,{timeout:180000});
  result.runs.push({phase:'warm-driving',...await snapshot()});
  result.passed=result.errors.length===0;
} catch(e){result.failure=String(e);throw e;}
finally{
  await fs.mkdir(out,{recursive:true});await fs.writeFile(path.join(out,`${tag}-loading.json`),JSON.stringify(result,null,2)+'\n');
  await context?.close();await new Promise(resolve=>server.close(resolve));
  console.log(JSON.stringify({tag,passed:result.passed,failure:result.failure,runs:result.runs.map(r=>({phase:r.phase,ms:r.ms,bytes:r.resources.reduce((s,x)=>s+x.encodedBodySize,0),transfer:r.resources.reduce((s,x)=>s+x.transferSize,0)}))}));
}
