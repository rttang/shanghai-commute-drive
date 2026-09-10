import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {Drive, type Input} from '../src/tour/drive';
import {CollisionWorld, type Obstacle} from '../src/tour/collision';
import {Journey, type JourneyData} from '../src/tour/journey';
import type {City} from '../src/tour/data';
// The evidence runner is deliberately JavaScript and is also the standalone CLI.
// @ts-expect-error No declaration file is needed for the local verification CLI.
import {verifyLoopPhysics} from '../scripts/verify_loop_physics.mjs';

type Check={id:string;passed:boolean;failure?:unknown};
// Keep the broad report lazy so --test-name-pattern='seam regression' runs only
// the requested seam cases, without rerunning unrelated acceptance checks.
test('runtime integration report',async t=>{
  const report=verifyLoopPhysics() as {checks:Check[];passed:boolean};
  for(const check of report.checks)await t.test(check.id,()=>{
    assert.equal(check.passed,true,JSON.stringify(check.failure,null,2));
  });
});

const city=JSON.parse(readFileSync(new URL('../public/tour-city.json',import.meta.url),'utf8')) as City;
const journeyData=JSON.parse(readFileSync(new URL('../public/journey.json',import.meta.url),'utf8')) as JourneyData;
const obstacles=JSON.parse(readFileSync(new URL('../public/streets/collisions.json',import.meta.url),'utf8')).obstacles as Obstacle[];
const collision=new CollisionWorld(obstacles),route=city.routes[0];
const idle:Input={throttle:false,brake:false,steer:0};
const throttle:Input={...idle,throttle:true};
const brake:Input={...idle,brake:true};
type SeamEvent={seconds:number;from:number;to:number;laps:number;travelled:number;speed:number};
function startDrive(distance=0,lateral=1.4){
  const d=new Drive(route);d.distance=distance;d.lateral=lateral;
  d.vehicleWidth=1.963;d.vehicleLength=4.997;d.wheelbase=3;d.collision=collision;
  assert.ok(d.start('manual'));return d;
}
function advance(d:Drive,seconds:number,input:Input,events:SeamEvent[]=[],hz=120){
  for(let frame=0;frame<Math.round(seconds*hz);frame++){
    const before=d.distance,lap=d.laps;d.update(1/hz,input);
    if(Math.abs(d.distance-before)>d.path.total/2||d.laps!==lap)
      events.push({seconds:(frame+1)/hz,from:before,to:d.distance,laps:d.laps,travelled:d.travelled,speed:d.speed});
  }
  return events;
}
function sameDurationStraightTravel(seconds:number){
  const reference=new Drive({...route,closed:false,points:[[0,0],[0,1000]],elevations:[0,0],tunnels:[],length:1000});
  assert.ok(reference.start('manual'));advance(reference,seconds,throttle);
  return reference.travelled;
}

test('seam regression: the original 16-substep launch stays on lap zero with the selected dynamics',()=>{
  const d=startDrive(),initialProjection=d.path.project(d.pose,d.distance),events=advance(d,16/120,throttle);
  assert.ok(d.travelled>0&&d.travelled<.05,'The original sixteen-step launch must actually move through the centimetre-scale seam');
  assert.ok(Math.abs(d.travelled-sameDurationStraightTravel(16/120))<1e-6,'Seam travel must match the same elapsed-time straight control');
  assert.equal(d.laps,0,JSON.stringify({initialProjection,events,distance:d.distance,travelled:d.travelled,pose:d.pose},null,2));
});

test('seam regression: millimetre spawn offsets cannot complete a lap during the first metres',()=>{
  const failures:unknown[]=[];
  for(const distance of [0,.001,.01,.05,.1,.2])for(const lateral of [1.1,1.4,1.7]){
    const d=startDrive(distance,lateral),initialProjection=d.path.project(d.pose,d.distance),events=advance(d,3,throttle);
    if(d.laps!==0)failures.push({distance,lateral,initialProjection,events,finalDistance:d.distance,travelled:d.travelled,laps:d.laps});
    assert.ok(d.travelled>10&&Math.abs(d.travelled-sameDurationStraightTravel(3))<1e-6,'The car must actually drive the same elapsed-time control segment');
    assert.equal(d.collisions,0,'Spawn timing case unexpectedly touched a static obstacle');
  }
  assert.deepEqual(failures,[],'Initial projection across the seam must not count a 14 km lap');
});

test('seam regression: waiting and recovery at the origin cannot arm a false forward lap',()=>{
  const failures:unknown[]=[];
  for(const recover of [false,true]){
    const d=startDrive(),events=advance(d,1,idle);
    if(recover)assert.ok(d.recover());
    // Coast from a genuinely low seeded speed after the parked/recovered pose;
    // this isolates the projection boundary from hard acceleration.
    d.speed=.35;advance(d,1,idle,events);advance(d,2,throttle,events);
    if(d.laps!==0)failures.push({recover,events,finalDistance:d.distance,travelled:d.travelled,laps:d.laps});
    assert.equal(d.collisions,0);
  }
  assert.deepEqual(failures,[],'Parking or recovery near zero must retain the unfinished lap');
});

test('seam regression: repeated reverse and forward crossing near the origin cannot farm laps',()=>{
  const d=startDrive(1),cycles=[];
  for(let cycle=0;cycle<3;cycle++){
    assert.equal(d.speed,0);assert.ok(d.shiftGear());
    const reverseEvents=advance(d,1.5,throttle);advance(d,3,brake,reverseEvents);
    const reversed={distance:d.distance,laps:d.laps,travelled:d.travelled};
    assert.ok(d.shiftGear());
    const forwardEvents=advance(d,1.5,throttle);advance(d,3,brake,forwardEvents);
    cycles.push({cycle,reverseEvents,reversed,forwardEvents,finalDistance:d.distance,laps:d.laps,travelled:d.travelled});
  }
  assert.ok(cycles.some(c=>c.reverseEvents.length)&&cycles.some(c=>c.forwardEvents.length),'Control manoeuvre must cross the seam in both directions');
  assert.equal(d.collisions,0);
  assert.equal(d.laps,0,JSON.stringify(cycles,null,2));
});

test('seam regression: a restored mid-lap save completes exactly one remaining lap at the finish',()=>{
  const d=new Drive(route),savedDistance=d.path.total/2+123,savedLaps=2;
  d.vehicleWidth=1.963;d.vehicleLength=4.997;d.collision=collision;
  const serialized=JSON.stringify({version:1,collected:[],discovered:[],score:1000,lap:savedLaps,distance:savedDistance,penalties:0});
  const journey=new Journey(journeyData,{getItem:()=>serialized,setItem:()=>{}});journey.restore(d);
  assert.ok(Math.abs(d.distance-savedDistance)<1e-8);assert.equal(d.laps,savedLaps);assert.ok(d.start('auto'));d.rate=3;
  let frames=0;const events:SeamEvent[]=[];
  for(;frames<20000&&d.laps===savedLaps;frames++){
    const before=d.distance,lap:number=d.laps;d.update(.05,idle);journey.update(.05,d);
    if(d.laps!==lap)events.push({seconds:(frames+1)*.05,from:before,to:d.distance,laps:d.laps,travelled:d.travelled,speed:d.speed});
  }
  assert.equal(d.laps,savedLaps+1,JSON.stringify({frames,events,pose:d.pose,distance:d.distance}));
  assert.equal(events.length,1);assert.ok(d.distance<3);
  assert.ok(d.travelled>d.path.total-savedDistance-2,'A restored lap may only finish after driving its remaining route');
  assert.equal(journey.save.lap,savedLaps+1);assert.equal(d.collisions,0);
});

test('seam regression: restoring near the finish and crossing manually still counts once',()=>{
  const d=new Drive(route),savedLaps=2,savedDistance=d.path.total-20;
  d.vehicleWidth=1.963;d.vehicleLength=4.997;d.collision=collision;
  const serialized=JSON.stringify({version:1,collected:[],discovered:[],score:1000,lap:savedLaps,distance:savedDistance,penalties:0});
  new Journey(journeyData,{getItem:()=>serialized,setItem:()=>{}}).restore(d);assert.ok(d.start('manual'));
  const events=advance(d,5,throttle);
  assert.equal(d.laps,savedLaps+1,JSON.stringify(events,null,2));
  const expectedTravel=sameDurationStraightTravel(5);
  assert.ok(d.travelled>20&&Math.abs(d.travelled-expectedTravel)<1e-6);
  assert.ok(d.distance>0&&Math.abs(d.distance-(expectedTravel-20))<1);
  assert.equal(d.collisions,0);
});

test('seam regression: negative progress survives storage reload and crossing zero without a false lap',()=>{
  const values=new Map<string,string>();
  const storage={getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value);}};
  const original=startDrive(),journey=new Journey(journeyData,storage);
  advance(original,1,idle);journey.update(1,original);assert.ok(journey.persist());
  assert.ok(original.progress<0&&original.progress>-.2,'The default parked origin must reproduce its small negative projection correction');
  const saved=JSON.parse(values.get('shanghai-loop-journey-v1')!);
  assert.equal(saved.progress,original.progress);assert.equal(saved.lap,0);
  assert.ok(saved.distance>original.path.total-.2,'The public route distance must wrap near the finish while signed progress remains negative');

  const restoredJourney=new Journey(journeyData,storage),restored=new Drive(route);
  restored.vehicleWidth=1.963;restored.vehicleLength=4.997;restored.collision=collision;
  restoredJourney.restore(restored);assert.equal(restored.progress,saved.progress);assert.equal(restored.laps,0);
  assert.ok(restored.start('manual'));restored.speed=.35;
  const events=advance(restored,1,idle);restoredJourney.update(1,restored);
  assert.ok(restored.progress>0&&restored.distance<1,'Low-speed coasting must actually cross from negative to positive progress');
  assert.equal(restored.laps,0,JSON.stringify({saved,events,progress:restored.progress,distance:restored.distance,travelled:restored.travelled},null,2));
  assert.equal(restoredJourney.save.lap,0);assert.ok(restoredJourney.save.progress!>0);assert.equal(restored.collisions,0);
});

test('seam regression: legacy version-one saves without progress preserve route and collected data',()=>{
  const d=new Drive(route),saved={version:1,collected:[journeyData.stops[0].id],discovered:[journeyData.stops[1].id],score:1170,lap:2,distance:4321.25,penalties:3};
  const serialized=JSON.stringify(saved),values=new Map([['shanghai-loop-journey-v1',serialized]]);
  const storage={getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value);}};
  const journey=new Journey(journeyData,storage);journey.restore(d);
  assert.equal(d.progress,saved.lap*d.path.total+saved.distance);assert.equal(d.laps,saved.lap);
  assert.ok(Math.abs(d.distance-saved.distance)<1e-8);
  assert.deepEqual(journey.save.collected,saved.collected);assert.deepEqual(journey.save.discovered,saved.discovered);
  assert.equal(journey.save.score,saved.score);assert.equal(journey.save.penalties,saved.penalties);
  assert.equal(values.get('shanghai-loop-journey-v1'),serialized,'Reading legacy progress must not erase or rewrite user data');
});
