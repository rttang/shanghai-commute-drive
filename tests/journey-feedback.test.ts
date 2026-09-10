import test from 'node:test';
import assert from 'node:assert/strict';
import { Drive } from '../src/tour/drive';
import { Journey, type TourStop } from '../src/tour/journey';
import { UI } from '../src/tour/ui';
import type { Route } from '../src/tour/data';

const route: Route = {
  id:'feedback-test',name:'测试路线',subtitle:'',description:'',focus:'',speed:35,
  points:[[0,0],[0,300]],length:300,sourceWays:[],directed:true,
};
const stop = (id:string, distance:number): TourStop => ({
  id,name:id==='first'?'江岸':'桥头',about:'',x:-1.4,z:distance,y:0,
  heading:0,distance,landmark:[0,distance],
});
function parked() {
  const drive=new Drive(route);drive.start('manual');
  const journey=new Journey({stops:[stop('first',0),stop('second',100)],signals:[]});
  journey.update(2.1,drive);
  assert.equal(journey.canCapture,true);
  return {drive,journey};
}

test('parking guidance explains manual takeover and retains a nearby stop after passing its route distance',()=>{
  const drive=new Drive(route);drive.distance=5;drive.start('auto');
  const journey=new Journey({stops:[stop('first',0),stop('second',100)],signals:[]});
  journey.update(.1,drive);
  assert.equal(journey.next(drive)?.id,'second');
  assert.equal(journey.photoGuidance(drive).title,'江岸');
  assert.equal(journey.photoGuidance(drive).stage,'takeover');
  assert.equal(journey.photoGuidance(drive).canCapture,false);
  drive.setMode('manual');
  assert.equal(journey.photoGuidance(drive).stage,'position');
  assert.match(journey.photoGuidance(drive).instruction,/5 米/);
});

test('guidance distinguishes alignment, braking, settling and a genuinely ready shutter',()=>{
  const drive=new Drive(route);drive.start('manual');
  const target=stop('first',0);target.heading=1;
  const journey=new Journey({stops:[target],signals:[]});
  journey.update(3,drive);
  assert.equal(journey.photoGuidance(drive).stage,'align');
  target.heading=0;drive.speed=.4;journey.update(3,drive);
  assert.equal(journey.photoGuidance(drive).stage,'brake');
  drive.speed=0;journey.update(1.1,drive);
  assert.equal(journey.photoGuidance(drive).stage,'settling');
  assert.match(journey.photoGuidance(drive).instruction,/0.9 秒/);
  assert.equal(journey.prepareCapture(),undefined);
  journey.update(.95,drive);
  assert.equal(journey.photoGuidance(drive).stage,'ready');
  assert.equal(journey.photoGuidance(drive).canCapture,true);
});

test('a stale parking frame cannot authorize a photo after pause, motion or relocation',()=>{
  const {drive,journey}=parked();
  drive.togglePause();
  assert.equal(journey.canCapture,false);
  assert.equal(journey.prepareCapture(),undefined);
  assert.equal(journey.photoGuidance(drive).stage,'paused');
  journey.update(.1,drive);drive.togglePause();
  assert.equal(journey.canCapture,false,'Paused time must not satisfy the parking timer');
  journey.update(2.1,drive);drive.speed=.4;
  assert.equal(journey.canCapture,false,'Live speed matters before the next Journey update');
  drive.speed=0;drive.restoreProgress(30);
  assert.equal(journey.canCapture,false,'A reset/recovery pose cannot reuse the old stop');
  assert.equal(journey.prepareCapture(),undefined);
});

test('a different parking spot and an explicit reset both require their own stationary interval',()=>{
  const {drive,journey}=parked();
  drive.restoreProgress(100);journey.update(.3,drive);
  assert.equal(journey.active?.id,'second');
  assert.equal(journey.parkedSeconds,.3);
  assert.equal(journey.canCapture,false);
  journey.update(2,drive);assert.equal(journey.canCapture,true);
  journey.resetParking();assert.equal(journey.canCapture,false);
  journey.update(1,drive);assert.equal(journey.canCapture,false);
  journey.update(1.1,drive);assert.equal(journey.canCapture,true);
});

test('collection advances the task, completion stays clear, and the v1 save remains readable',()=>{
  const values=new Map<string,string>();
  const storage={getItem:(k:string)=>values.get(k)??null,setItem:(k:string,v:string)=>{values.set(k,v);}};
  const drive=new Drive(route);drive.start('manual');
  const data={stops:[stop('first',0),stop('second',100)],signals:[]};
  const journey=new Journey(data,storage);journey.update(2.1,drive);
  assert.equal(journey.capture(),true);
  assert.equal(journey.capture(),false);
  assert.equal(journey.photoGuidance(drive).stage,'collected');
  assert.match(journey.photoGuidance(drive).instruction,/下一处：桥头/);
  assert.doesNotMatch(journey.photoGuidance(drive).instruction,/0.0 秒/);
  drive.restoreProgress(100);journey.update(2.1,drive);assert.equal(journey.capture(),true);
  assert.equal(journey.photoGuidance(drive).stage,'complete');
  assert.equal(journey.photoGuidance(drive).canCapture,false);
  assert.match(journey.consumeNotice(),/全部 2 处风景已收藏/);
  const restored=new Journey(data,storage);
  assert.deepEqual(restored.save.collected,['first','second']);
  assert.equal(restored.save.score,1200);
  assert.equal(restored.save.version,1);
});

test('empty stop data does not claim a completed Shanghai album',()=>{
  const journey=new Journey({stops:[],signals:[]});
  assert.equal(journey.complete,false);
  assert.equal(journey.photoGuidance(new Drive(route)).stage,'explore');
});

function withDocument(value: unknown, run:()=>void) {
  const old=Object.getOwnPropertyDescriptor(globalThis,'document');
  Object.defineProperty(globalThis,'document',{configurable:true,value});
  try { run(); }
  finally { if(old)Object.defineProperty(globalThis,'document',old);else Reflect.deleteProperty(globalThis,'document'); }
}

test('the objective disables capture and names the pending photo until storage finishes',()=>{
  const {drive,journey}=parked();
  const elements=new Map<string,Record<string,unknown>>();
  for(const id of ['collection-progress','driving-score','next-stop','stop-instruction','capture-button']){
    const attrs: Record<string,string>={};
    elements.set(id,{textContent:'',innerHTML:'',dataset:{},disabled:false,attrs,setAttribute:(name:string,value:string)=>{attrs[name]=value;}});
  }
  withDocument({getElementById:(id:string)=>elements.get(id)},()=>{
    const ui=Object.create(UI.prototype) as UI;
    ui.journey(journey,drive,'江岸');
    assert.equal(elements.get('capture-button')!.disabled,true);
    assert.match(String(elements.get('capture-button')!.innerHTML),/正在保存/);
    assert.equal((elements.get('capture-button')!.attrs as Record<string,string>)['aria-busy'],'true');
    assert.equal(elements.get('next-stop')!.textContent,'江岸');
    ui.journey(journey,drive);
    assert.equal(elements.get('capture-button')!.disabled,false,'A failed save can be retried while still parked');
    journey.capture();ui.journey(journey,drive);
    assert.equal(elements.get('capture-button')!.disabled,true);
    assert.match(String(elements.get('capture-button')!.innerHTML),/已收藏/);
    assert.doesNotMatch(String(elements.get('stop-instruction')!.textContent),/停稳 0.0/);
  });
});

test('a newer toast stays visible for its full lifetime instead of inheriting an older timer',t=>{
  t.mock.timers.enable({apis:['setTimeout']});
  const element={textContent:'',hidden:true};
  withDocument({querySelector:()=>element},()=>{
    const ui=Object.create(UI.prototype) as UI;
    ui.toast('发现江岸');t.mock.timers.tick(3000);
    ui.toast('江岸已收入相册');t.mock.timers.tick(501);
    assert.equal(element.hidden,false);
    assert.equal(element.textContent,'江岸已收入相册');
    t.mock.timers.tick(2999);assert.equal(element.hidden,true);
  });
});
