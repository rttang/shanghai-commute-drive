import { chromium } from '/Users/maiziheng/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { createStaticServer } from './serve-release.mjs';
const root=path.resolve(import.meta.dirname,'..'),out=path.join(root,'docs/evidence/deployment-optimization');
const server=createStaticServer({directory:path.join(root,'dist-release')});
await new Promise((r,j)=>{server.once('error',j);server.listen(8082,'127.0.0.1',r);});
const base='http://127.0.0.1:8082';
const result={startedAt:new Date().toISOString(),checks:[],errors:[],cars:[],routeSamples:[],requests:[]};
result.service={pid:process.pid,port:8082,status:'RUNNING'};
result.buildManifestSha256=createHash('sha256').update(await fs.readFile(path.join(root,'dist-release/release-manifest.json'))).digest('hex');
const persist=()=>fs.writeFile(path.join(out,'browser-regression.json'),JSON.stringify(result,null,2)+'\n');
let context,page,expectedFailure=false;
const check=(name,detail)=>{result.checks.push({name,detail,passed:true});console.log('PASS',name);};
try{
  context=await chromium.launchPersistentContext(path.join(root,`.tooling/deployment-optimization/regression-browser-${Date.now()}`),{executablePath:path.join(root,'scripts/chrome-native.sh'),headless:true,viewport:{width:1280,height:720},deviceScaleFactor:1,args:['--no-first-run','--disable-background-networking','--use-angle=metal','--enable-gpu']});
  page=await context.newPage();
  page.on('pageerror',e=>result.errors.push(e.message));
  page.on('console',message=>{if(!expectedFailure&&(message.type()==='error'||/WebGL.*Context Lost/i.test(message.text())))result.errors.push(message.text());});
  page.on('response',r=>{result.requests.push({url:new URL(r.url()).pathname,status:r.status()});if(r.status()>=400&&!expectedFailure)result.errors.push(`${r.status()} ${r.url()}`);});
  const diag=()=>page.evaluate(()=>window.tourDiagnostics);
  const click=action=>page.locator(`[data-action="${action}"]:visible`).first().click();
  const running=()=>page.waitForFunction(()=>window.tourDiagnostics?.phase==='running',null,{timeout:180000});
  await page.goto(base+'/');await page.waitForFunction(()=>window.tourDiagnostics&&document.body.classList.contains('ready'));
  assert.equal((await diag()).sceneReady,false);
  assert.equal(result.requests.filter(r=>r.url.endsWith('.glb')).length,0);
  await click('garage');
  const cars=JSON.parse(await fs.readFile(path.join(root,'src/tour/cars.json')));
  await page.locator(`[data-action="car"][data-value="${cars.at(-1).id}"]`).click();
  assert.equal(result.requests.filter(r=>r.url.endsWith('.glb')).length,0);check('Home and garage selection download no GLB');
  let injected=false;expectedFailure=true;
  await page.route('**/runtime/*/*.glb',async route=>{if(!injected){injected=true;await route.fulfill({status:503,body:'Temporary test failure'});}else await route.continue();});
  await click('auto');await page.locator('[data-action="retry-load"]').waitFor({timeout:180000});
  assert.ok(injected);await page.unroute('**/runtime/*/*.glb');expectedFailure=false;
  await click('retry-load');await running();await click('pause');
  assert.deepEqual((await diag()).streetStreaming.failedChunks,[]);check('A failed street request can be retried without reloading the page');
  for(const car of cars){
    await click('garage');await page.locator(`[data-action="car"][data-value="${car.id}"]`).click();
    await page.waitForFunction(id=>window.tourDiagnostics?.car===id,car.id,{timeout:90000});
    const d=await diag();assert.equal(d.car,car.id);assert.ok(d.detailedCarsLoaded<=2);assert.equal(d.wheels.length,4);result.cars.push({id:car.id,cached:d.detailedCarsLoaded,wheels:d.wheels});
  }
  check('Every current vehicle loads with four independent wheels and a bounded detail cache',{count:cars.length});
  await click('home');await click('manual');await running();await page.bringToFront();
  const before=await diag();await page.keyboard.down('w');await page.waitForTimeout(1700);await page.keyboard.up('w');
  const after=await diag();assert.ok(after.travelled>before.travelled+1);assert.ok(after.wheels.some((w,i)=>JSON.stringify(w)!==JSON.stringify(before.wheels[i])));await click('pause');check('Manual throttle moves the car and rotates its wheels',{travelled:after.travelled-before.travelled});
  await page.setViewportSize({width:390,height:844});await click('home');
  assert.ok(await page.locator('[data-action="manual"]:visible').isVisible());
  await page.screenshot({path:path.join(out,'mobile-home.png')});check('Mobile departure control remains available');
  await page.setViewportSize({width:1280,height:720});
  const city=JSON.parse(await fs.readFile(path.join(root,'public/tour-city.json')));
  // Real-time automatic traversal through the existing diagnostic page, without writing simulation state.
  const route=city.routes[0];
  const finish=route.closed?'stopLaps=1':`stopAt=${route.length-1}`;
  await page.goto(`${base}/streets-review.html?route=${route.id}&distance=0&view=hood&drive=auto&rate=3&${finish}`);
  await page.waitForFunction(()=>Boolean(document.body.dataset.review),null,{timeout:180000});
  const start=Date.now();let lastDistance=0;
  while(Date.now()-start<900000){
    await page.waitForTimeout(15000);
    const sample=await page.evaluate(()=>({traversal:JSON.parse(document.body.dataset.traversal||'{}'),sample:JSON.parse(document.body.dataset.sample||'{}'),error:document.body.dataset.streetError}));
    result.routeSamples.push(sample);await persist();
    console.log('ROUTE',Math.round(sample.traversal.end||0),'/',Math.round(route.length));
    assert.ok(!sample.error,sample.error);assert.deepEqual(sample.sample.streetStreaming?.failedChunks??[],[]);
    if(sample.traversal.stopped){
      if(route.closed)assert.equal(sample.traversal.laps,1);
      check('Complete current loop traversed with streamed assets',{route:route.id,distance:sample.traversal.travelled,laps:sample.traversal.laps,seconds:(Date.now()-start)/1000});break;
    }
    assert.ok(sample.traversal.end>lastDistance+.1,'Automatic traversal stopped making progress');lastDistance=sample.traversal.end;
  }
  assert.ok(result.checks.some(c=>c.name.startsWith('Complete current loop')),'Traversal exceeded timeout');
  assert.ok(result.requests.every(r=>!r.url.includes('/streets/master/shanghai-streets.glb')));
  assert.deepEqual(result.errors,[]);result.passed=true;
}catch(e){result.failure=String(e);if(page)await page.screenshot({path:path.join(out,'regression-failure.png')}).catch(()=>{});throw e;}
finally{
  await context?.close().catch(error=>{result.errors.push(`Browser cleanup: ${error}`);result.passed=false;});
  await new Promise(r=>server.close(r));result.service.status='STOPPED';await persist();
}
