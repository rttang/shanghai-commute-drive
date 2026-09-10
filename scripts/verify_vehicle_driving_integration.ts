/** CPU-only Drive/VehicleDynamics/height integration against current static assets.
 * node --import tsx scripts/verify_vehicle_driving_integration.ts [--wide-only] [--no-write]
 */
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { Drive, Path, angleDifference, type Input } from '../src/tour/drive.ts';
import { CollisionWorld, type Obstacle, type VehiclePose } from '../src/tour/collision.ts';
import { VehicleDynamics, VEHICLE_DYNAMICS_PROFILES } from '../src/tour/vehicle-dynamics.ts';
import { FRAME_PATTERNS } from './verify_vehicle_dynamics.ts';
import type { City, Route } from '../src/tour/data.ts';

const root=fileURLToPath(new URL('../',import.meta.url));
const read=(file:string)=>fs.readFileSync(path.join(root,file));
const sha=(file:string)=>createHash('sha256').update(read(file)).digest('hex');
const idle:Input={throttle:false,brake:false,steer:0},full:Input={...idle,throttle:true};
export const WIDE_ENVELOPE={width:2.3,length:5.2,wheelbase:3.2};
const need=(condition:unknown,message:string)=>{if(!condition)throw new Error(message);};
const gap=(a:VehiclePose,b:VehiclePose)=>Math.hypot(a.x-b.x,a.z-b.z);
const configure=(d:Drive,id='porsche-911',collision?:CollisionWorld)=>{
  d.dynamics.setVehicle(id);d.vehicleWidth=WIDE_ENVELOPE.width;d.vehicleLength=WIDE_ENVELOPE.length;d.wheelbase=WIDE_ENVELOPE.wheelbase;d.collision=collision;return d;
};
const straight=(route:Route):Route=>({...route,points:[[0,0],[0,2000]],closed:false,elevations:[0,0],tunnels:[],length:2000});
const run=(d:Drive,seconds:number,input:Input,hz=120)=>{for(let i=0;i<Math.round(seconds*hz);i++)d.update(1/hz,input);};

export function fleetControlIntegration(route:Route){
  const rows=[];
  let autoReference:VehiclePose|undefined,autoSpeed=0;
  for(const profile of VEHICLE_DYNAMICS_PROFILES){
    const d=configure(new Drive(straight(route)),profile.id),reference=new VehicleDynamics(profile.id);d.start('manual');
    let expected=0;for(let i=0;i<360;i++){d.update(1/120,full);expected=reference.step(expected,1,full,1/120);}
    need(Math.abs(d.speed-expected)<1e-10,`${profile.id}: Drive did not use selected manual dynamics`);
    need(d.travelled>10&&d.speed<=80/3.6,`${profile.id}: invalid manual movement`);
    const speedAtThree=d.speed;
    need(d.setMode('auto')&&d.dynamics.pedal===0,`${profile.id}: successful manual-to-auto handoff retained throttle state`);
    run(d,.25,idle);need(d.setMode('manual')&&d.dynamics.pedal===0,`${profile.id}: auto-to-manual handoff retained throttle state`);
    run(d,4,{...full,brake:true});need(Object.is(d.speed,0),`${profile.id}: forward braking did not return +0`);
    need(d.shiftGear()&&d.dynamics.pedal===0,`${profile.id}: shift did not reset pedal`);
    run(d,4,full);need(d.speed<0&&d.speed>=-15/3.6,`${profile.id}: reverse speed limit`);
    const reversePedal=d.dynamics.pedal;need(!d.setMode('auto')&&d.dynamics.pedal===reversePedal,`${profile.id}: rejected reverse handoff changed throttle state`);
    run(d,2,{...full,brake:true});need(Object.is(d.speed,0),`${profile.id}: reverse braking did not return +0`);
    need(d.setMode('auto'),`${profile.id}: could not rejoin straight road at rest`);run(d,2,idle);
    need(d.gear===1,`${profile.id}: auto retained reverse gear`);
    d.start('manual');need(d.dynamics.pedal===0,`${profile.id}: start did not reset pedal`);
    run(d,.5,full);need(d.dynamics.pedal>0,`${profile.id}: throttle did not build`);
    need(d.recover()&&d.dynamics.pedal===0,`${profile.id}: recovery did not reset pedal`);
    d.reset();need(d.dynamics.pedal===0&&d.speed===0,`${profile.id}: reset state`);
    const auto=configure(new Drive(straight(route)),profile.id);auto.start('auto');run(auto,10,full);
    if(autoReference)need(gap(auto.pose,autoReference)<1e-9&&Math.abs(auto.speed-autoSpeed)<1e-9,`${profile.id}: vehicle profile changed auto cruise`);
    else{autoReference=auto.pose;autoSpeed=auto.speed;}
    rows.push({id:profile.id,manualSpeedAt3SecondsKmh:speedAtThree*3.6,autoSpeedAt10SecondsKmh:auto.speed*3.6,reverseBrakeReturnsPositiveZero:true});
  }
  return rows;
}

export function integratedFrameComparison(route:Route){
  const traces=(id:string,pattern:readonly number[],reverse:boolean)=>{
    const d=configure(new Drive(straight(route)),id);d.distance=200;d.start('manual');if(reverse)d.shiftGear();
    const points:{pose:VehiclePose;speed:number;steering:number}[]=[];let frames=0;
    for(const [seconds,input] of [[2,full],[1,{...full,steer:.18}],[1,{...full,steer:-.18}],[1,idle],[3,{...full,brake:true}]] as [number,Input][]){
      for(let second=0;second<seconds;second++){let left=1;while(left>1e-9){const dt=Math.min(left,pattern[frames++%pattern.length]);d.update(dt,input);left-=dt;}points.push({pose:d.pose,speed:d.speed,steering:d.steering});}
    }
    return points;
  };
  const rows=[];
  for(const profile of VEHICLE_DYNAMICS_PROFILES)for(const reverse of [false,true]){
    const baseline=traces(profile.id,FRAME_PATTERNS.hz120,reverse);
    for(const [pattern,steps]of Object.entries(FRAME_PATTERNS).filter(([name])=>name!=='hz120')){
      const actual=traces(profile.id,steps,reverse);
      const position=Math.max(...actual.map((p,i)=>gap(p.pose,baseline[i].pose)));
      const speed=Math.max(...actual.map((p,i)=>Math.abs(p.speed-baseline[i].speed)));
      const heading=Math.max(...actual.map((p,i)=>Math.abs(angleDifference(p.pose.heading,baseline[i].pose.heading))));
      need(position<.001&&speed<.0001&&heading<.00001,`${profile.id}/${pattern}/${reverse}: equal-time pose drift ${position}/${speed}/${heading}`);
      rows.push({id:profile.id,reverse,pattern,maximumPositionMetres:position,maximumSpeedMps:speed,maximumHeadingRadians:heading});
    }
  }
  return rows;
}

export function tunnelSupportIntegration(route:Route,collision:CollisionWorld){
  const rows=[];
  for(const tunnel of route.tunnels??[]){
    for(const distance of [tunnel.start+10,tunnel.start+80,tunnel.start+220,(tunnel.start+tunnel.end)/2,tunnel.end-220,tunnel.end-80,tunnel.end-10])for(const reverse of [false,true])for(const dt of [1/60,.05,.1,.25]){
      const d=configure(new Drive(route),'porsche-911',collision);d.distance=distance;d.start('manual');if(reverse)d.shiftGear();d.speed=(reverse?-15:80)/3.6;
      const before=d.pose;d.update(dt,full);const expected=d.path.at(d.distance).y,error=Math.abs((d.pose.y??0)-expected);
      need(d.collisions===0&&!collision.occupied(d.pose,d.vehicleWidth,d.vehicleLength),`${tunnel.name}/${distance}/${dt}: wide car hit ramp lane`);
      need(error<1e-7,`${tunnel.name}/${distance}/${dt}: lost authored support ${d.pose.y}/${expected}`);
      need(Math.abs((d.pose.y??0)-(before.y??0))<=gap(d.pose,before)*.1+.025,`${tunnel.name}: vertical jump`);
      rows.push({tunnel:tunnel.name,distance,reverse,dt,yBefore:before.y,yAfter:d.pose.y,expectedY:expected,heightErrorMetres:error});
    }
    // Seed a surface vehicle over the same X/Z as the deep bore. Only this
    // test fixture touches private pose; production has no new pose setter.
    const surface=configure(new Drive(route));surface.distance=(tunnel.start+tunnel.end)/2;surface.start('manual');
    (surface as unknown as {manualPose:VehiclePose}).manualPose={...surface.pose,y:0};
    run(surface,3,full,10);need(surface.pose.y===0,`${tunnel.name}: surface vehicle inherited underground elevation`);
    rows.push({tunnel:tunnel.name,surfaceCrossing:true,seconds:3,yAfter:surface.pose.y});
  }
  return rows;
}

export function verifyVehicleDrivingIntegration({wideOnly=false}={}){
  const files=['src/tour/drive.ts','src/tour/world.ts','src/tour/driving-height.ts','src/tour/vehicle-dynamics.ts','src/tour/vehicle-dynamics.json','src/tour/collision.ts','src/tour/cars.json','public/tour-city.json','public/streets/collisions.json','scripts/verify_vehicle_driving_integration.ts'];
  const hashes=Object.fromEntries(files.map(file=>[file,sha(file)]));
  const city=JSON.parse(read('public/tour-city.json').toString()) as City,route=city.routes[0],track=new Path(route.points,route.closed,route.elevations);
  const obstacles=JSON.parse(read('public/streets/collisions.json').toString()).obstacles as Obstacle[],collision=new CollisionWorld(obstacles);
  const checks:{id:string;passed:boolean;result?:unknown;failure?:string;wallSeconds:number}[]=[];
  const wideChecks=new Set(['wide-envelope-covers-published-collision-dimensions','actual-tunnel-ramp-and-surface-height','wide-envelope-whole-route-forward-and-reverse','wide-envelope-three-actual-auto-laps','luxury-high-speed-oblique-and-reverse-actual-wall','input-sha-stability']);
  const check=(id:string,fn:()=>unknown)=>{if(wideOnly&&!wideChecks.has(id))return;const start=performance.now();try{checks.push({id,passed:true,result:fn(),wallSeconds:(performance.now()-start)/1000});}catch(error){checks.push({id,passed:false,failure:String((error as Error).message),wallSeconds:(performance.now()-start)/1000});}console.error(`${checks.at(-1)!.passed?'PASS':'FAIL'} ${id}`);};
  check('ten-profiles-manual-auto-and-state-reset',()=>fleetControlIntegration(route));
  check('drive-pose-10-20-60-and-dropped-frames',()=>integratedFrameComparison(route));
  check('wide-envelope-covers-published-collision-dimensions',()=>{
    const cars=JSON.parse(read('src/tour/cars.json').toString()) as {id:string;dimensions:number[];collisionDimensions?:number[]}[];
    return cars.map(car=>{const dimensions=car.collisionDimensions??car.dimensions;need(dimensions[0]/1000<=WIDE_ENVELOPE.length&&dimensions[1]/1000<=WIDE_ENVELOPE.width,`${car.id}: published dimensions exceed tested envelope`);return {id:car.id,collisionDimensionsMillimetres:dimensions,usesMeasuredBounds:!!car.collisionDimensions};});
  });
  check('actual-tunnel-ramp-and-surface-height',()=>tunnelSupportIntegration(route,collision));
  check('wide-envelope-whole-route-forward-and-reverse',()=>{
    let samples=0;
    for(const reverse of [false,true])for(let distance=0;distance<track.total;distance+=1){
      const a=track.pose(distance),b=track.pose(reverse?distance-1:distance+1),moved=collision.move(a,b,WIDE_ENVELOPE.width,WIDE_ENVELOPE.length);
      need(!moved.contacts.length&&!collision.occupied(a,WIDE_ENVELOPE.width,WIDE_ENVELOPE.length)&&gap(moved.pose,b)<.001,`wide envelope blocked at ${distance}, reverse=${reverse}, contacts=${moved.contacts.map(c=>c.id).join(',')}`);samples++;
    }
    return {samples,metres:track.total,contacts:0,envelope:WIDE_ENVELOPE};
  });
  check('wide-envelope-three-actual-auto-laps',()=>{
    const d=configure(new Drive(route),'porsche-911',collision);d.start('auto');d.rate=3;
    let frames=0,maxMovement=0;for(;frames<50000&&d.laps<3;frames++){const before=d.pose;d.update(.05,idle);maxMovement=Math.max(maxMovement,gap(before,d.pose));need(d.phase==='running'&&maxMovement<3,'wide auto loop discontinuity');}
    need(d.laps===3&&d.collisions===0,'wide auto loop failed or contacted geometry');
    return {frames,laps:d.laps,collisions:d.collisions,maximumFrameMovementMetres:maxMovement,envelope:WIDE_ENVELOPE};
  });
  check('luxury-high-speed-oblique-and-reverse-actual-wall',()=>{
    const edgeLength=(o:Obstacle)=>Math.max(...o.points.map((p,i)=>Math.hypot(p[0]-o.points[(i+1)%o.points.length][0],p[1]-o.points[(i+1)%o.points.length][1])));
    const obstacle=obstacles.filter(o=>o.kind==='building').sort((a,b)=>edgeLength(b)-edgeLength(a))[0];
    const center={x:obstacle.points.reduce((s,p)=>s+p[0],0)/obstacle.points.length,z:obstacle.points.reduce((s,p)=>s+p[1],0)/obstacle.points.length};
    let edge=0;for(let i=1;i<obstacle.points.length;i++)if(Math.hypot(obstacle.points[i][0]-obstacle.points[(i+1)%obstacle.points.length][0],obstacle.points[i][1]-obstacle.points[(i+1)%obstacle.points.length][1])>Math.hypot(obstacle.points[edge][0]-obstacle.points[(edge+1)%obstacle.points.length][0],obstacle.points[edge][1]-obstacle.points[(edge+1)%obstacle.points.length][1]))edge=i;
    const a=obstacle.points[edge],b=obstacle.points[(edge+1)%obstacle.points.length],normal=[-(b[1]-a[1]),b[0]-a[0]],heading=Math.atan2(-normal[0],-normal[1]);
    const rows=[];
    for(const id of ['porsche-911','ferrari-488','urus','g63','alphard'])for(const angle of [0,.45])for(const dt of [1/60,.05,.1,.25])for(const reverse of [false,true]){
      const yaw=heading+angle,v={x:Math.sin(yaw),z:Math.cos(yaw)},direction=reverse?-1:1;
      const r:Route={...route,closed:false,tunnels:[],elevations:[0,0],length:200,points:[[center.x-v.x*100*direction,center.z-v.z*100*direction],[center.x+v.x*100*direction,center.z+v.z*100*direction]]};
      const isolated=new CollisionWorld([obstacle]),d=configure(new Drive(r),id,isolated);d.lateral=0;d.distance=reverse?130:70;d.start('manual');if(reverse)d.shiftGear();d.speed=(reverse?-15:80)/3.6;
      let frames=0;for(;frames<Math.ceil(12/dt)&&!d.collisions;frames++)d.update(dt,full);
      need(d.collisions>0&&d.lastImpact?.id===obstacle.id,`${id}/${angle}/${dt}/${reverse}: no collision`);
      for(let i=0;i<Math.ceil(2/dt);i++)d.update(dt,full);
      need(!isolated.occupied(d.pose,d.vehicleWidth,d.vehicleLength),`${id}/${angle}/${dt}/${reverse}: penetrated wall`);
      run(d,4,{...full,brake:true},20);need(Object.is(d.speed,0)&&d.shiftGear(),`${id}: could not stop and reverse away`);
      const hit=d.pose;run(d,3,full,20);need(gap(d.pose,hit)>1&&!isolated.occupied(d.pose,d.vehicleWidth,d.vehicleLength),`${id}: stuck in wall after gear reversal`);
      rows.push({id,angle,dt,reverse,initialSpeedKmh:reverse?-15:80,framesToImpact:frames,escapedMetres:gap(d.pose,hit)});
    }
    return {obstacleId:obstacle.id,cases:rows.length,rows,envelope:WIDE_ENVELOPE};
  });
  check('input-sha-stability',()=>{for(const file of files)need(sha(file)===hashes[file],`${file} changed during run`);return hashes;});
  return {generatedAt:new Date().toISOString(),passed:checks.every(c=>c.passed),scope:wideOnly?'wide-envelope affected checks only':'all integration checks',inputs:hashes,collisionCount:obstacles.length,runtimeCarIds:JSON.parse(read('src/tour/cars.json').toString()).map((c:{id:string})=>c.id),envelope:WIDE_ENVELOPE,
    boundaries:['Drive and CollisionWorld CPU execution; no browser or final luxury GLB acceptance.','5.2 by 2.3 metre envelope covers the published Urus mirror width of 2.258949 m with margin; remaining luxury GLBs require their final measured bounds to fit this envelope.','Current complete static collision asset is used for route/ramp/lap checks; impact wall is an unchanged isolated runtime polygon.','Dynamic traffic is covered by existing loop unit tests; no live renderer or traffic simulation is invoked here.'],checks};
}

if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href){
  const report=verifyVehicleDrivingIntegration({wideOnly:process.argv.includes('--wide-only')});
  const output=JSON.stringify(report,(_key,value)=>typeof value==='number'?Math.round(value*1e8)/1e8:value,2)+'\n';
  if(!process.argv.includes('--no-write'))fs.writeFileSync(path.join(root,'docs/evidence/tourism/vehicle-driving-integration.json'),output);
  console.log(output);if(!report.passed)process.exitCode=1;
}
