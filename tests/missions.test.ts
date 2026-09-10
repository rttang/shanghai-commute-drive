import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { Missions, createMissionCatalog, MISSION_STORAGE_KEY, type MissionDefinition, type MissionDrive } from '../src/tour/missions';
import type { TourStop } from '../src/tour/journey';
import { MissionsWorld } from '../src/tour/missions-world';
import { Mesh, Scene } from 'three';

const stop = (id: string, distance: number): TourStop => ({ id, name:id, about:'', distance, x:0, z:distance, y:0, heading:0, landmark:[0,distance] });
const pickup = stop('pickup',100), destination = stop('destination',800), eventStop = stop('event',400);
const trip: MissionDefinition = { id:'trip', title:'江岸接送', kind:'tourist', person:'旅人', description:'', pickup, destination, reward:200, pickupLine:'出发吧', finishLine:'谢谢' };
const timed: MissionDefinition = { ...trip, id:'timed', timeLimit:20 };
const detour: MissionDefinition = { ...timed, id:'detour', event:{ stop:eventStop, title:'顺路看看', request:'停一下', thanks:'看好了', bonus:60, extraSeconds:5 } };
const catalog = [trip,timed,detour];
function storage() {
  const data = new Map<string,string>();
  return { data, getItem:(key:string)=>data.get(key)??null, setItem:(key:string,value:string)=>{data.set(key,value);} };
}
function driving(): MissionDrive { return { phase:'running', mode:'manual', rate:1, speed:0, distance:0, pose:{x:0,z:0,y:0,heading:0} }; }
function setup(id = 'trip') {
  const saved=storage(), missions=new Missions([],1000,saved,catalog), drive=driving();
  assert.equal(missions.accept(id,drive,0),true);
  return {missions,drive,saved};
}
function arrive(missions:Missions,drive:MissionDrive,target:TourStop,penalties=0) {
  drive.distance=target.distance;drive.pose={x:target.x,z:target.z,y:target.y,heading:target.heading};drive.speed=0;
  missions.update(1,drive,penalties);missions.update(1,drive,penalties);
}

test('the real Shanghai catalog has six reachable trips and separate forward-route delivery deadlines',()=>{
  const stops=JSON.parse(readFileSync(new URL('../public/journey.json',import.meta.url),'utf8')).stops as TourStop[];
  const city=JSON.parse(readFileSync(new URL('../public/tour-city.json',import.meta.url),'utf8'));
  const missions=createMissionCatalog(stops,city.routes[0].length);
  assert.equal(missions.length,6);
  assert.equal(new Set(missions.map(m=>m.id)).size,6);
  for(const mission of missions){
    assert.ok(stops.includes(mission.pickup));assert.ok(stops.includes(mission.destination));
    if(mission.timeLimit)assert.ok(mission.timeLimit>100 && Number.isFinite(mission.timeLimit));
    if(mission.event)assert.ok(stops.includes(mission.event.stop));
  }
  assert.ok(missions.find(m=>m.id==='night-postcard')!.timeLimit!<200,'The bridge trip must wrap at the loop end instead of taking a full circuit');
  assert.deepEqual(createMissionCatalog([],1000),[]);
});

test('accepting sets one pickup target; manual parking starts delivery, while automatic sightseeing cannot collect a passenger',()=>{
  const {missions,drive}=setup('timed');
  assert.equal(missions.accept('trip',drive,0),false);
  assert.equal(missions.navigation(drive)?.target,pickup);
  drive.mode='auto';arrive(missions,drive,pickup);
  assert.equal(missions.active?.stage,'pickup');
  assert.equal(missions.active?.remaining,20,'No deadline is consumed before pickup');
  drive.mode='manual';missions.update(1,drive,0);
  assert.equal(missions.active?.stage,'pickup');
  missions.update(1,drive,0);
  assert.equal(missions.active?.stage,'dropoff');
  assert.equal(missions.navigation(drive)?.target,destination);
  missions.update(1,drive,0);assert.equal(missions.active?.remaining,19);
});

test('pickup requires correct level, heading, speed and a continuous two-second stop',()=>{
  const {missions,drive}=setup();drive.distance=100;drive.pose={x:0,z:100,y:-3,heading:0};
  missions.update(3,drive,0);assert.equal(missions.parkedSeconds,0);
  drive.pose.y=0;drive.pose.heading=1;missions.update(3,drive,0);assert.equal(missions.parkedSeconds,0);
  drive.pose.heading=0;drive.speed=.4;missions.update(3,drive,0);assert.equal(missions.parkedSeconds,0);
  drive.speed=0;missions.update(1,drive,0);assert.equal(missions.parkedSeconds,1);
  drive.pose.z=106;missions.update(.1,drive,0);assert.equal(missions.parkedSeconds,0);
  drive.pose.z=100;missions.update(1,drive,0);assert.equal(missions.active?.stage,'pickup');
  missions.update(1,drive,0);assert.equal(missions.active?.stage,'dropoff');
});

test('pause, background and resume cannot reuse a half-completed stop or consume the deadline',()=>{
  const {missions,drive}=setup('timed');arrive(missions,drive,pickup);
  drive.pose={x:0,z:800,y:0,heading:0};missions.update(1,drive,0);
  assert.equal(missions.parkedSeconds,1);const remaining=missions.active!.remaining;
  drive.phase='paused';missions.suspend();missions.update(5,drive,0);
  assert.equal(missions.parkedSeconds,0);assert.equal(missions.active?.remaining,remaining);
  drive.phase='running';missions.update(1,drive,0);assert.ok(missions.active);
  missions.update(1,drive,0);assert.equal(missions.active,null);
  assert.equal(missions.save.lastResult?.success,true);
});

test('completion pays only once, survives reload, and does not alter the existing Shanghai album save',()=>{
  const {missions,drive,saved}=setup();
  saved.data.set('shanghai-loop-journey-v1','unchanged album');
  arrive(missions,drive,pickup);arrive(missions,drive,destination);
  assert.equal(missions.save.credits,200);assert.equal(missions.save.completed,1);
  assert.equal(missions.save.lastResult?.stars,5);
  for(let i=0;i<5;i++)missions.update(5,drive,0);
  assert.equal(missions.save.credits,200);
  const restored=new Missions([],1000,saved,catalog);restored.update(3,drive,0);
  assert.equal(restored.active,null);assert.equal(restored.save.credits,200);
  assert.deepEqual(restored.save.records.trip,{completed:1,bestStars:5});
  assert.equal(saved.data.get('shanghai-loop-journey-v1'),'unchanged album');
  assert.equal(restored.retry(drive,0),true);arrive(restored,drive,pickup);arrive(restored,drive,destination);
  assert.equal(restored.save.credits,400);assert.equal(restored.save.completed,2);
});

test('refresh restores remaining delivery time but requires a new stationary interval',()=>{
  const {missions,drive,saved}=setup('timed');arrive(missions,drive,pickup);
  drive.pose={x:0,z:800,y:0,heading:0};missions.update(1,drive,0);missions.suspend();
  const restored=new Missions([],1000,saved,catalog);
  assert.equal(restored.active?.remaining,19);assert.equal(restored.parkedSeconds,0);
  restored.update(1,drive,0);assert.ok(restored.active);
  restored.update(1,drive,0);assert.equal(restored.save.lastResult?.success,true);
});

test('an accepted roadside request changes target, grants time once, survives refresh and pays only after the stop',()=>{
  const {missions,drive,saved}=setup('detour');arrive(missions,drive,pickup);
  drive.pose={x:0,z:300,y:0,heading:0};missions.update(1,drive,0);
  assert.equal(missions.active?.event,'offered');
  assert.equal(missions.chooseEvent(true),true);assert.equal(missions.active?.remaining,24);
  assert.equal(missions.chooseEvent(true),false);assert.equal(missions.active?.remaining,24);
  assert.equal(missions.navigation(drive)?.target,eventStop);
  const restored=new Missions([],1000,saved,catalog);
  assert.equal(restored.active?.stage,'event');assert.equal(restored.active?.remaining,24);
  arrive(restored,drive,eventStop);assert.equal(restored.active?.stage,'dropoff');
  assert.equal(restored.active?.event,'completed');
  arrive(restored,drive,destination);
  assert.equal(restored.save.lastResult?.eventBonus,60);assert.equal(restored.save.credits,260);
});

test('declining a request leaves the destination and rating intact; passing a requested stop cannot complete it',()=>{
  const {missions,drive}=setup('detour');arrive(missions,drive,pickup);
  drive.pose.z=300;missions.update(.1,drive,0);
  assert.equal(missions.chooseEvent(false),true);assert.equal(missions.navigation(drive)?.target,destination);
  arrive(missions,drive,destination);
  assert.equal(missions.save.lastResult?.stars,5);assert.equal(missions.save.lastResult?.eventBonus,0);
  const second=setup('detour');arrive(second.missions,second.drive,pickup);second.drive.pose.z=300;second.missions.update(.1,second.drive,0);second.missions.chooseEvent(true);
  arrive(second.missions,second.drive,destination);assert.equal(second.missions.active?.stage,'event');assert.equal(second.missions.save.credits,0);
});

test('traffic penalties and rescue affect this trip only, with no duplicate penalty on reload',()=>{
  const {missions,drive,saved}=setup();arrive(missions,drive,pickup);
  missions.update(.1,drive,1);missions.noteRecovery();missions.suspend();
  const restored=new Missions([],1000,saved,catalog);
  restored.update(.1,drive,1);assert.equal(restored.active?.incidents,2);
  arrive(restored,drive,destination,1);
  assert.equal(restored.save.lastResult?.stars,3);assert.equal(restored.save.credits,160);
  restored.retry(drive,1);arrive(restored,drive,pickup,1);arrive(restored,drive,destination,1);
  assert.equal(restored.save.lastResult?.stars,5);assert.equal(restored.save.records.trip.bestStars,5);
});

test('automatic speed-up consumes proportional time and failure can retry without losing earlier earnings',()=>{
  const {missions,drive}=setup();arrive(missions,drive,pickup);arrive(missions,drive,destination);
  missions.accept('timed',drive,0);arrive(missions,drive,pickup);
  drive.mode='auto';drive.rate=3;missions.update(5,drive,0);
  assert.equal(missions.active?.remaining,5);missions.update(2,drive,0);
  assert.equal(missions.active,null);assert.equal(missions.save.lastResult?.success,false);
  assert.equal(missions.save.lastResult?.reward,0);assert.equal(missions.save.credits,200);
  assert.equal(missions.retry(drive,0),true);
  assert.deepEqual(missions.active,{id:'timed',stage:'pickup',event:'skipped',elapsed:0,remaining:20,incidents:0});
});

test('abandoning a trip records a retryable result without a payment',()=>{
  const {missions,drive}=setup();arrive(missions,drive,pickup);
  assert.equal(missions.abandon(),true);assert.equal(missions.abandon(),false);
  assert.equal(missions.save.lastResult?.message,'已结束本次委托');assert.equal(missions.save.credits,0);
  assert.equal(missions.retry(drive,0),true);missions.abandon();missions.dismissResult();
  assert.equal(missions.retry(drive,0),false);
});

test('navigation retains a nearby stop just passed, but cannot treat an underground vehicle as arrived',()=>{
  const {missions,drive}=setup();drive.distance=103;drive.pose.z=103;
  assert.equal(missions.navigation(drive)?.distance,3);assert.equal(missions.navigation(drive)?.nearby,true);
  drive.pose.y=-5;assert.equal(missions.navigation(drive)?.nearby,false);
  missions.update(3,drive,0);assert.equal(missions.active?.stage,'pickup');
});

test('an expired saved delivery fails on resume, and malformed or removed missions do not crash driving',()=>{
  const saved=storage();saved.data.set(MISSION_STORAGE_KEY,'{');
  assert.equal(new Missions([],1000,saved,catalog).active,null);
  saved.data.set(MISSION_STORAGE_KEY,JSON.stringify({version:1,credits:-20,completed:'oops',active:{id:'removed',stage:'event'},records:{trip:{completed:-1,bestStars:90}}}));
  let missions=new Missions([],1000,saved,catalog);
  assert.equal(missions.active,null);assert.equal(missions.save.credits,0);assert.equal(missions.save.completed,0);assert.equal(missions.save.records.trip.bestStars,5);
  saved.data.set(MISSION_STORAGE_KEY,JSON.stringify({version:1,active:{id:'timed',stage:'dropoff',event:'accepted',remaining:0,elapsed:22,incidents:0}}));
  missions=new Missions([],1000,saved,catalog);missions.update(.1,driving(),0);
  assert.equal(missions.active,null);assert.equal(missions.save.lastResult?.success,false);
});

test('unavailable browser storage does not interrupt the mission state machine',()=>{
  const saved={getItem(){throw new Error('blocked');},setItem(){throw new Error('quota');}};
  const missions=new Missions([],1000,saved,catalog),drive=driving();
  assert.equal(missions.accept('trip',drive,0),true);assert.equal(missions.storageAvailable,false);
  arrive(missions,drive,pickup);arrive(missions,drive,destination);
  assert.equal(missions.save.credits,200);assert.equal(missions.save.lastResult?.success,true);
});

test('street mission cues reuse two meshes, hide across height layers and home, and release their own resources',()=>{
  const {missions,drive}=setup();
  const visual=new MissionsWorld(),scene=new Scene();scene.add(visual.group);
  const meshes=visual.group.children as Mesh[];
  assert.equal(meshes.length,2);
  assert.ok(meshes.reduce((sum,mesh)=>sum+mesh.geometry.getAttribute('position').count/3,0)<400);
  assert.ok(meshes.every(mesh=>!mesh.castShadow && !mesh.receiveShadow));
  visual.update(missions.navigation(drive),drive);
  assert.equal(visual.group.visible,true);assert.equal(meshes[1].visible,true);
  const resources=meshes.map(mesh=>mesh.geometry);
  drive.pose.y=-6;visual.update(missions.navigation(drive),drive);assert.equal(visual.group.visible,false);
  drive.pose.y=0;visual.update(missions.navigation(drive),drive,false);assert.equal(visual.group.visible,false);
  arrive(missions,drive,pickup);drive.pose.z=790;visual.update(missions.navigation(drive),drive);
  assert.equal(visual.group.visible,true);assert.equal(meshes[1].visible,false);
  assert.deepEqual(meshes.map(mesh=>mesh.geometry),resources,'Changing stage must not allocate new geometry');
  let disposed=0;resources.forEach(geometry=>geometry.addEventListener('dispose',()=>disposed++));
  visual.dispose();assert.equal(disposed,2);assert.equal(scene.children.length,0);
});
