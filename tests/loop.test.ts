import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {Drive,Path} from '../src/tour/drive';
import {CollisionWorld,wall,rectangle,sweepPolygon} from '../src/tour/collision';
import {Journey,signalState} from '../src/tour/journey';
import type {City,Route} from '../src/tour/data';
const city=JSON.parse(readFileSync(new URL('../public/tour-city.json',import.meta.url),'utf8')) as City;
const input={throttle:false,brake:false,steer:0};
const route:Route={...city.routes[0],closed:false,elevations:undefined,points:[[0,0],[0,2000]],length:2000};
test('Shanghai loop closes on the mapped graph and has two continuous cross-river tunnel profiles',()=>{
  const r=city.routes[0],p=new Path(r.points,true,r.elevations);
  assert.equal(city.routes.length,1);assert.equal(r.closed,true);assert.deepEqual(r.points[0],r.points.at(-1));
  assert.ok(Math.abs(p.total-r.length)<1);assert.equal(r.tunnels?.length,2);assert.ok(r.sourceWays.length>80);
  assert.deepEqual(p.pose(0),p.pose(p.total));
  for(let i=1;i<r.points.length;i++)assert.ok(Math.abs(r.elevations![i]-r.elevations![i-1])/Math.hypot(r.points[i][0]-r.points[i-1][0],r.points[i][1]-r.points[i-1][1])<.062);
});
test('continuous collision stops 20/50/80 km/h frontal and oblique impacts against thin walls, including a 10 FPS frame',()=>{
  for(const speed of [20,50,80])for(const hz of [10,20,60])for(const angle of [0,.45]){
    const collision=new CollisionWorld([wall('thin',[-30,10],[30,10],0,4,.02)]);
    const from={x:0,z:0,heading:angle,y:0},to={...from,x:Math.sin(angle)*speed/3.6/hz,z:11+speed/3.6/hz};
    const hit=collision.move(from,to,1.9,4.8);
    assert.ok(hit.contacts.length,`${speed}/${hz}/${angle}`);
    assert.ok(Math.max(...rectangle(hit.pose.x,hit.pose.z,hit.pose.heading,1.9,4.8).map(p=>p[1]))<9.995);
  }
});
test('manual driving has contact feedback and cannot accelerate through a railing; reverse exits a contact',()=>{
  const d=new Drive(route);d.collision=new CollisionWorld([wall('rail',[-20,20],[20,20],0,2,.1)]);d.start('manual');
  for(let i=0;i<900;i++)d.update(1/60,{...input,throttle:true});
  assert.ok(d.pose.z<17.6);assert.ok(d.collisions>0);assert.ok(d.speed<.2);assert.equal(d.lastImpact?.kind,'barrier');
  assert.ok(d.shiftGear());const start=d.pose.z;
  for(let i=0;i<180;i++)d.update(1/60,{...input,throttle:true});
  assert.ok(d.pose.z<start-5);assert.ok(d.speed<0);
});
test('vertical separation permits a tunnel under a surface building and still blocks a tunnel side wall',()=>{
  const c=new CollisionWorld([wall('surface',[-20,10],[20,10],0,100,.2),wall('underground',[5,-20],[5,40],-18,-12,.2)]);
  const start={x:0,z:0,y:-18,heading:0};
  assert.equal(c.move(start,{...start,z:20}).contacts.length,0);
  assert.ok(c.move(start,{...start,x:10,z:20}).contacts.some(h=>h.id==='underground'));
});
test('driving collides with a traffic vehicle and can brake to a complete standstill in reverse',()=>{
  const c=new CollisionWorld();c.setTraffic([{id:'car',pose:{x:0,z:12,heading:.3,y:0},width:2,length:5}]);
  assert.ok(c.move({x:0,z:0,heading:0},{x:0,z:30,heading:0}).contacts.some(h=>h.kind==='vehicle'));
  const d=new Drive(route);d.start('manual');assert.ok(d.shiftGear());
  for(let i=0;i<120;i++)d.update(1/60,{...input,throttle:true});
  for(let i=0;i<180;i++)d.update(1/60,{...input,brake:true});
  assert.equal(d.speed,0);
});
test('automatic sightseeing waits for reverse motion to stop and then selects forward gear',()=>{
  const d=new Drive(route);d.distance=100;d.start('manual');d.shiftGear();
  for(let i=0;i<60;i++)d.update(1/60,{...input,throttle:true});
  assert.ok(d.speed<-.2);assert.equal(d.setMode('auto'),false);assert.equal(d.gear,-1);
  for(let i=0;i<180;i++)d.update(1/60,{...input,brake:true});
  assert.equal(d.speed,0);assert.equal(d.setMode('auto'),true);assert.equal(d.gear,1);
});
test('three closed laps continue without a finish phase or a teleport at the seam',()=>{
  const points: [number,number][]=[];for(let i=0;i<=80;i++)points.push([Math.sin(i/80*Math.PI*2)*100,Math.cos(i/80*Math.PI*2)*100]);points[80]=points[0];
  const d=new Drive({...route,points,closed:true});d.start('auto');d.rate=3;let previous=d.pose;
  for(let i=0;i<30000&&d.laps<3;i++){d.update(.05,input);assert.ok(Math.hypot(d.pose.x-previous.x,d.pose.z-previous.z)<2);previous=d.pose;}
  assert.equal(d.laps,3);assert.equal(d.phase,'running');assert.ok(d.speed>0);
});
test('photo collection requires manual parking, cannot double award, and restores validated progress',()=>{
  const values=new Map<string,string>();const storage={getItem:(k:string)=>values.get(k)??null,setItem:(k:string,v:string)=>{values.set(k,v);}};
  const data={stops:[{id:'bund',name:'外滩',about:'test',x:-1.4,z:0,y:0,heading:0,distance:0,landmark:[0,0] as [number,number]}],signals:[]};
  const j=new Journey(data,storage),d=new Drive(route);d.start('auto');j.update(3,d);assert.equal(j.canCapture,false);
  d.setMode('manual');j.update(2.1,d);assert.ok(j.canCapture);assert.ok(j.capture());assert.equal(j.capture(),false);assert.equal(j.save.score,1100);
  const restored=new Journey(data,storage);assert.deepEqual(restored.save.collected,['bund']);assert.equal(restored.save.score,1100);
  assert.equal(signalState(40,{id:'test',distance:0,x:0,z:0,heading:0,offset:0}),'red');
});
