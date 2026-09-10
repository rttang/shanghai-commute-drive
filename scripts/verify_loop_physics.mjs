/** Pure CPU acceptance against the assets loaded by world.ts.
 * Run: node --import tsx scripts/verify_loop_physics.mjs
 * --no-write emits the same JSON without changing evidence files.
 * No browser, renderer, service, synthetic replacement city or collider removal.
 */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {performance} from 'node:perf_hooks';
import {Drive, Path, angleDifference} from '../src/tour/drive.ts';
import {CollisionWorld, rectangle} from '../src/tour/collision.ts';
import {Journey} from '../src/tour/journey.ts';

const ROOT=fileURLToPath(new URL('../',import.meta.url));
const OUTPUT='docs/evidence/tourism/loop-physics-verification.json';
const FILES=['public/tour-city.json','public/streets/collisions.json','public/journey.json','src/tour/cars.json','src/tour/drive.ts','src/tour/collision.ts','src/tour/journey.ts','src/main.ts','scripts/verify_loop_physics.mjs'];
const read=p=>fs.readFileSync(path.join(ROOT,p));
const sha=b=>createHash('sha256').update(b).digest('hex');
const input={throttle:false,brake:false,steer:0};
const gap=(a,b)=>Math.hypot(a.x-b.x,a.z-b.z);
const finite=p=>[p.x,p.z,p.y??0,p.heading].every(Number.isFinite);
const need=(condition,message,detail={})=>{if(!condition){const error=new Error(message);error.detail=detail;throw error;}};
const round=n=>Math.round(n*1e6)/1e6;
const poseRecord=p=>Object.fromEntries(Object.entries(p).map(([k,v])=>[k,typeof v==='number'?round(v):v]));
const memoryStorage=()=>{const values=new Map();return {values,getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,v)};};

export function verifyLoopPhysics({progress=()=>{}}={}) {
  const started=performance.now(),startedAt=new Date().toISOString();
  const snapshots=Object.fromEntries(FILES.map(p=>[p,read(p)]));
  const city=JSON.parse(snapshots[FILES[0]]),collisionData=JSON.parse(snapshots[FILES[1]]),journeyData=JSON.parse(snapshots[FILES[2]]),cars=JSON.parse(snapshots[FILES[3]]);
  const route=city.routes[0],track=new Path(route.points,route.closed,route.elevations),obstacles=collisionData.obstacles,world=new CollisionWorld(obstacles);
  const vehicle={width:Math.max(...cars.map(c=>c.dimensions[1]))/1000,length:Math.max(...cars.map(c=>c.dimensions[0]))/1000,wheelbase:Math.max(...cars.map(c=>c.wheelbase))/1000};
  vehicle.matchingCarIds=cars.filter(c=>c.dimensions[1]/1000===vehicle.width&&c.dimensions[0]/1000===vehicle.length).map(c=>c.id);
  const checks=[];
  const check=(id,parameters,run)=>{
    const begin=performance.now();let row;
    try{row={id,passed:true,parameters,result:run()};}
    catch(error){row={id,passed:false,parameters,failure:{message:String(error.message??error),detail:error.detail??{}}};}
    row.wallSeconds=round((performance.now()-begin)/1000);checks.push(row);progress({id,passed:row.passed,wallSeconds:row.wallSeconds});return row;
  };
  const configure=d=>{d.vehicleWidth=vehicle.width;d.vehicleLength=vehicle.length;d.wheelbase=vehicle.wheelbase;d.collision=world;return d;};
  const atStop=(stop,mode='manual')=>{const d=configure(new Drive(route));d.distance=stop.distance;d.lateral=track.project(stop,stop.distance).lateral;d.start(mode);return d;};
  const blockingAt=(p,to=p)=>world.move(p,to,vehicle.width,vehicle.length).contacts;

  check('real-assets-and-closed-route',{expectedRoutes:1,expectedStops:12,expectedMetres:14057.001},()=>{
    need(city.routes.length===1&&route.closed,'The runtime must expose one closed route');
    need(journeyData.stops.length===12&&new Set(journeyData.stops.map(s=>s.id)).size===12,'Expected 12 unique runtime stops');
    need(Math.abs(track.total-14057.001)<.01,'Unexpected route length',{metres:track.total});
    need(gap(track.pose(0),track.pose(track.total))<1e-8,'Route seam is not closed');
    need(obstacles.length>0,'Runtime collision asset is empty');
    return {routeId:route.id,metres:track.total,points:route.points.length,obstacles:world.count,obstaclesByKind:obstacles.reduce((a,o)=>(a[o.kind]=(a[o.kind]??0)+1,a),{}),stops:journeyData.stops.map(s=>s.id)};
  });

  check('full-route-largest-car-sweep',{sampleMetres:1,lateralMetres:1.4,vehicle,world:'complete runtime static collision asset'},()=>{
    const failures=[];let samples=0,minY=Infinity,maxY=-Infinity;
    for(let d=0;d<track.total;d+=1){
      const from=track.pose(d),desired=track.pose(Math.min(track.total,d+1));
      const moved=world.move(from,desired,vehicle.width,vehicle.length);samples++;minY=Math.min(minY,from.y);maxY=Math.max(maxY,from.y);
      if(moved.contacts.length||gap(moved.pose,desired)>.001||world.occupied(from,vehicle.width,vehicle.length))failures.push({distance:round(d),from:poseRecord(from),desired:poseRecord(desired),resolved:poseRecord(moved.pose),contacts:moved.contacts});
    }
    need(!failures.length,'Runtime route contains blocked or occupied poses',{samples,failures});
    return {samples,minimumY:minY,maximumY:maxY,contacts:0,occupiedSamples:0};
  });

  check('three-real-continuous-laps',{laps:3,frameSeconds:.05,renderHzEquivalent:20,rate:3,maximumFrames:50000,stallFrames:200,vehicle,dynamicTraffic:false},()=>{
    const d=configure(new Drive(route));d.start('auto');d.rate=3;
    let previous=d.pose,lastAdvance=0,frames=0,maxStep=0,maxSpeed=0,lastProgress=0;const seams=[];
    for(;frames<50000&&d.laps<3;frames++){
      const oldLap=d.laps,oldDistance=d.distance;d.update(.05,input);
      const movement=gap(previous,d.pose);maxStep=Math.max(maxStep,movement);maxSpeed=Math.max(maxSpeed,d.speed);
      need(finite(d.pose)&&Number.isFinite(d.speed),'Non-finite driving state',{frames,pose:d.pose});
      need(d.phase==='running','Closed route entered a finishing state',{frames,phase:d.phase});
      need(movement<3,'Discontinuous frame movement',{frames,oldDistance,distance:d.distance,previous,pose:d.pose,movement});
      if(d.laps>oldLap)seams.push({frame:frames+1,lap:d.laps,fromDistance:round(oldDistance),toDistance:round(d.distance),movement:round(movement),from:poseRecord(previous),to:poseRecord(d.pose)});
      const advance=d.laps*track.total+d.distance;if(advance-lastProgress>.01){lastAdvance=frames;lastProgress=advance;}
      need(frames-lastAdvance<200,'Vehicle stalled on the real loop',{frames,lap:d.laps,distance:d.distance,pose:d.pose,speed:d.speed,collisions:d.collisions,lastImpact:d.lastImpact,contacts:blockingAt(d.pose,track.pose(d.distance+2))});
      previous=d.pose;
    }
    need(d.laps===3,'Three laps did not finish within the bounded frame budget',{frames,laps:d.laps,distance:d.distance,pose:d.pose});
    need(d.collisions===0,'Automatic route contacted runtime geometry',{collisions:d.collisions,lastImpact:d.lastImpact});
    return {frames,renderElapsedSeconds:round(frames*.05),simulationSeconds:round(frames*.05*3),distanceMetres:round(d.laps*track.total+d.distance),travelledMetres:round(d.travelled),laps:d.laps,phase:d.phase,maximumFrameMovement:round(maxStep),maximumSpeedKmh:round(maxSpeed*3.6),collisions:d.collisions,seams};
  });

  check('equal-duration-drive-10-20-60-fps',{framesHz:[10,20,60],maximumAcceptedFrameSeconds:.25,maximumOuterSubstepSeconds:.05,vehicle,world:'complete runtime static collision asset',positionToleranceMetres:.001,speedToleranceMetresPerSecond:.0001,headingToleranceRadians:.00001,checkpointIntervalSeconds:1},()=>{
    const scenarios=[
      {id:'forward-acceleration',mode:'manual',startDistance:20,segments:[{seconds:8,input:{...input,throttle:true}}]},
      {id:'forward-steering',mode:'manual',startDistance:20,segments:[{seconds:2,input:{...input,throttle:true}},{seconds:1,input:{...input,throttle:true,steer:.08}},{seconds:1,input:{...input,throttle:true,steer:-.08}},{seconds:4,input:{...input,throttle:true}}]},
      {id:'forward-acceleration-and-braking',mode:'manual',startDistance:20,segments:[{seconds:6,input:{...input,throttle:true}},{seconds:4,input:{...input,brake:true}}]},
      {id:'reverse-acceleration-and-braking',mode:'manual',startDistance:80,reverse:true,segments:[{seconds:6,input:{...input,throttle:true}},{seconds:2,input:{...input,brake:true}}]},
      {id:'automatic-route',mode:'auto',startDistance:0,segments:[{seconds:30,input}]},
    ];
    const results=[];
    for(const scenario of scenarios){
      const runs=[];
      for(const hz of [10,20,60]){
        const d=configure(new Drive(route));d.distance=scenario.startDistance;d.start(scenario.mode);if(scenario.reverse)need(d.shiftGear(),'Could not initialize reverse FPS scenario');
        const initial=d.pose,checkpoints=[];let totalFrames=0;
        for(const segment of scenario.segments)for(let frame=0;frame<Math.round(segment.seconds*hz);frame++){
          d.update(1/hz,segment.input);totalFrames++;
          need(finite(d.pose)&&Number.isFinite(d.speed),'Non-finite same-duration driving state',{scenario:scenario.id,hz,totalFrames,pose:d.pose});
          if(totalFrames%hz===0)checkpoints.push({seconds:totalFrames/hz,pose:d.pose,speed:d.speed,distance:d.distance,travelled:d.travelled,steering:d.steering,collisions:d.collisions});
        }
        need(d.collisions===0,'Static geometry affected an FPS timing-control scenario',{scenario:scenario.id,hz,pose:d.pose,collisions:d.collisions,lastImpact:d.lastImpact});
        need(Math.abs(d.travelled)>5,'Timing-control scenario did not drive a meaningful distance',{scenario:scenario.id,hz,travelled:d.travelled});
        runs.push({hz,frames:totalFrames,submittedSeconds:totalFrames/hz,displacementMetres:gap(initial,d.pose),finalSpeedKmh:d.speed*3.6,travelledMetres:d.travelled,finalPose:d.pose,checkpoints});
      }
      const reference=runs.find(r=>r.hz===60),comparisons=[];
      for(const actual of runs.filter(r=>r.hz!==60)){
        const differences=actual.checkpoints.map((point,i)=>{
          const expected=reference.checkpoints[i];
          return {seconds:point.seconds,positionMetres:gap(point.pose,expected.pose),speedMetresPerSecond:Math.abs(point.speed-expected.speed),headingRadians:Math.abs(angleDifference(point.pose.heading,expected.pose.heading)),travelledMetres:Math.abs(point.travelled-expected.travelled),routeDistanceMetres:Math.abs(point.distance-expected.distance),steeringRadians:Math.abs(point.steering-expected.steering)};
        });
        const maximum=Object.fromEntries(['positionMetres','speedMetresPerSecond','headingRadians','travelledMetres','routeDistanceMetres','steeringRadians'].map(key=>[key,Math.max(...differences.map(p=>p[key]))]));
        need(maximum.positionMetres<=.001&&maximum.speedMetresPerSecond<=.0001&&maximum.headingRadians<=.00001&&maximum.travelledMetres<=.001&&maximum.routeDistanceMetres<=.001&&maximum.steeringRadians<=.00001,'Equal elapsed driving diverged between frame rates',{scenario:scenario.id,hz:actual.hz,referenceHz:60,maximum,differences,runs});
        comparisons.push({hz:actual.hz,referenceHz:60,maximum});
      }
      results.push({scenario,runs,comparisons});
    }
    return {scenarios:results,caseCount:scenarios.length*3,comparisonCount:scenarios.length*2,boundary:'Drive.update is executed directly with each requested frame duration. main.ts is hash-bound but its animation callback and dynamic traffic are not executed by this Node timing check.'};
  });

  // Isolate unchanged asset polygons to test all object kinds reproducibly.
  // These are geometry fixtures, not a claim that 80 km/h is reachable beside every object.
  const longestEdge=o=>Math.max(...o.points.map((p,i)=>Math.hypot(p[0]-o.points[(i+1)%o.points.length][0],p[1]-o.points[(i+1)%o.points.length][1])));
  const fixtures=[...new Set(obstacles.map(o=>o.kind))].map(kind=>obstacles.filter(o=>o.kind===kind).sort((a,b)=>longestEdge(b)-longestEdge(a))[0]);
  const impactFrame=o=>{
    const center={x:o.points.reduce((s,p)=>s+p[0],0)/o.points.length,z:o.points.reduce((s,p)=>s+p[1],0)/o.points.length};
    let edge=0;for(let i=1;i<o.points.length;i++)if(gap({x:o.points[i][0],z:o.points[i][1]},{x:o.points[(i+1)%o.points.length][0],z:o.points[(i+1)%o.points.length][1]})>gap({x:o.points[edge][0],z:o.points[edge][1]},{x:o.points[(edge+1)%o.points.length][0],z:o.points[(edge+1)%o.points.length][1]}))edge=i;
    const a=o.points[edge],b=o.points[(edge+1)%o.points.length],length=Math.hypot(b[0]-a[0],b[1]-a[1]),normal=[-(b[1]-a[1])/length,(b[0]-a[0])/length];
    return {center,normal,y:o.minY};
  };
  check('asset-collision-speed-angle-frame-matrix',{speedsKmh:[20,50,80],framesHz:[10,20,60],anglesRadians:[0,.45],directions:['forward','reverse'],vehicle,method:'constant-speed CollisionWorld.move; supplied dt is not clamped',isolatedUnmodifiedAssetPolygons:true},()=>{
    const cases=[],failures=[];
    for(const obstacle of fixtures)for(const speed of [20,50,80])for(const hz of [10,20,60])for(const angle of [0,.45])for(const direction of ['forward','reverse']){
      const {center,normal,y}=impactFrame(obstacle),base=Math.atan2(normal[0],normal[1])+Math.PI,travelHeading=base+angle,heading=travelHeading+(direction==='reverse'?Math.PI:0),v={x:Math.sin(travelHeading),z:Math.cos(travelHeading)},c=new CollisionWorld([obstacle]);
      let p={x:center.x-v.x*10,z:center.z-v.z*10,heading,y},first,postImpactOccupied=false;let frames=0;
      for(;frames<Math.ceil(4*hz);frames++){
        const desired={...p,x:p.x+v.x*speed/3.6/hz,z:p.z+v.z*speed/3.6/hz},m=c.move(p,desired,vehicle.width,vehicle.length);p=m.pose;
        if(m.contacts.length){first={frame:frames+1,pose:poseRecord(p),contacts:m.contacts};postImpactOccupied=c.occupied(p,vehicle.width,vehicle.length);break;}
      }
      const row={kind:obstacle.kind,obstacleId:obstacle.id,speedKmh:speed,hz,angle,direction,hit:!!first,postImpactOccupied,firstImpact:first};cases.push(row);
      if(!first||postImpactOccupied)failures.push(row);
    }
    need(!failures.length,'Asset geometry failed a continuous collision case',{cases:cases.length,failures});
    return {cases:cases.length,passedCases:cases.length,fixtures:fixtures.map(o=>({id:o.id,kind:o.kind,minY:o.minY,maxY:o.maxY,points:o.points})),results:cases};
  });

  check('drive-impact-feedback-reverse-and-low-fps',{initialSpeedsKmh:[20,50,80],requestedFramesHz:[10,20,60],maximumAcceptedFrameSeconds:.25,maximumOuterSubstepSeconds:.05,reverseLimitKmh:15,vehicle,fixture:'longest runtime building wall; isolated unchanged asset'},()=>{
    const obstacle=fixtures.find(o=>o.kind==='building'),{center,normal,y}=impactFrame(obstacle),v={x:-normal[0],z:-normal[1]},cases=[];
    for(const speed of [20,50,80])for(const hz of [10,20,60]){
      const points=[[center.x-v.x*20,center.z-v.z*20],[center.x+v.x*100,center.z+v.z*100]],r={...route,points,closed:false,elevations:[y,y],length:120};
      const d=new Drive(r);d.vehicleWidth=vehicle.width;d.vehicleLength=vehicle.length;d.wheelbase=vehicle.wheelbase;d.collision=new CollisionWorld([obstacle]);d.start('manual');d.speed=speed/3.6;
      let frames=0;for(;frames<hz*15&&!d.collisions;frames++)d.update(1/hz,{...input,throttle:true});
      need(d.collisions>0&&d.lastImpact?.id===obstacle.id,'Drive did not report the expected wall impact',{speed,hz,frames,pose:d.pose,lastImpact:d.lastImpact});
      need(!d.collision.occupied(d.pose,vehicle.width,vehicle.length),'Drive ended impact inside the wall',{speed,hz,pose:d.pose});
      for(let i=0;i<hz*2;i++)d.update(1/hz,{...input,throttle:true});
      need(Math.abs(d.speed)<.2,'Throttle continued through a frontal contact',{speed,hz,pose:d.pose,speedAfter:d.speed});
      const contactPose=d.pose;need(d.shiftGear(),'Reverse could not be selected at standstill');
      for(let i=0;i<hz*3;i++)d.update(1/hz,{...input,throttle:true});
      need(gap(d.pose,contactPose)>1&&d.speed<0,'Reverse did not escape a frontal contact',{speed,hz,contactPose,reversePose:d.pose,reverseSpeed:d.speed});
      const reverseSpeed=d.speed;for(let i=0;i<hz*3;i++)d.update(1/hz,{...input,brake:true});
      need(d.speed===0,'Reverse braking failed to stop',{speed,hz,remainingSpeed:d.speed});
      cases.push({speedKmh:speed,hz,framesToImpact:frames,contactPose:poseRecord(contactPose),reverseSpeedKmh:round(reverseSpeed*3.6),finalSpeed:d.speed,collisions:d.collisions});
    }
    return {cases,note:'Drive.update accepts the full 0.1-second request at 10 FPS and subdivides it. Equal-duration displacement and speed are separately checked at 10, 20 and 60 FPS.'};
  });

  check('real-tunnel-and-surface-height-isolation',{vehicle,world:'full runtime asset for tunnel lateral impacts; unchanged individual geometry for matched-height controls'},()=>{
    const results=[];
    for(const tunnel of route.tunnels??[]){
      const distance=(tunnel.start+tunnel.end)/2,from=track.pose(distance),to=track.pose(distance,8),hit=world.move(from,to,vehicle.width,vehicle.length);
      need(hit.contacts.some(h=>h.kind==='tunnel'),'Full-world underground lateral travel did not hit a tunnel wall',{tunnel,from,to,contacts:hit.contacts});
      const tunnelObstacle=obstacles.find(o=>o.id===hit.contacts.find(h=>h.kind==='tunnel').id);
      const surface=fixtures.find(o=>o.kind==='building');
      for(const [o,blockY,clearY] of [[tunnelObstacle,from.y,0],[surface,0,from.y]]){
        const {center,normal}=impactFrame(o),heading=Math.atan2(-normal[0],-normal[1]),a={x:center.x+normal[0]*6,z:center.z+normal[1]*6,heading,y:blockY},b={...a,x:center.x-normal[0]*6,z:center.z-normal[1]*6};
        const c=new CollisionWorld([o]),blocked=c.move(a,b,vehicle.width,vehicle.length),clear=c.move({...a,y:clearY},{...b,y:clearY},vehicle.width,vehicle.length);
        need(blocked.contacts.some(h=>h.id===o.id)&&clear.contacts.length===0&&gap(clear.pose,b)<1e-6,'Height filter confused surface and underground geometry',{tunnel:tunnel.name,obstacleId:o.id,blockY,clearY,blocked:blocked.contacts,clear:clear.contacts});
        results.push({tunnel:tunnel.name,distance,obstacleId:o.id,kind:o.kind,blockY,clearY,blockedContacts:blocked.contacts,clearContacts:clear.contacts.length});
      }
    }
    need(results.length===4,'Expected two crossed tunnels and two height controls each');return {results};
  });

  check('parking-reachability-and-car-clearance',{stops:12,vehicle,path:'cubic Bezier with start/end tangent aligned to car; continuous collision sweeps; negative lead means reverse parking from downstream',approachMetres:[24,36,48,60,12,16,20,-12,-16,-20,-24,-36],sampleApproxMetres:.25,clearancePerSideMetres:.5,maximumSteeringRadians:.58},()=>{
    const results=[],failures=[];
    for(const stop of journeyData.stops){
      const occupied=world.occupied(stop,vehicle.width,vehicle.length),withClearance=world.occupied(stop,vehicle.width+1,vehicle.length);
      let clearPerSide=0;for(let margin=.05;margin<=5; margin+=.05){if(world.occupied(stop,vehicle.width+2*margin,vehicle.length))break;clearPerSide=margin;}
      const attempts=[];let accepted;
      for(const lead of [24,36,48,60,12,16,20,-12,-16,-20,-24,-36]){
        const start=track.pose(stop.distance-lead),end=stop,arm=lead/3,control=[start,{x:start.x+Math.sin(start.heading)*arm,z:start.z+Math.cos(start.heading)*arm},{x:end.x-Math.sin(end.heading)*arm,z:end.z-Math.cos(end.heading)*arm},end],count=Math.ceil((Math.abs(lead)+gap(track.pose(stop.distance),stop))/.25);
        let previous=start,maxCurvature=0,contacts=[],firstOccupied;const position=t=>({x:(1-t)**3*control[0].x+3*(1-t)**2*t*control[1].x+3*(1-t)*t*t*control[2].x+t**3*control[3].x,z:(1-t)**3*control[0].z+3*(1-t)**2*t*control[1].z+3*(1-t)*t*t*control[2].z+t**3*control[3].z,y:0});
        for(let i=1;i<=count;i++){
          const t=i/count,p=position(t),dx=3*(1-t)**2*(control[1].x-control[0].x)+6*(1-t)*t*(control[2].x-control[1].x)+3*t*t*(control[3].x-control[2].x),dz=3*(1-t)**2*(control[1].z-control[0].z)+6*(1-t)*t*(control[2].z-control[1].z)+3*t*t*(control[3].z-control[2].z);p.heading=Math.atan2(dx,dz)+(lead<0?Math.PI:0);
          maxCurvature=Math.max(maxCurvature,Math.abs(angleDifference(p.heading,previous.heading))/Math.max(.0001,gap(p,previous)));
          const m=world.move(previous,p,vehicle.width,vehicle.length);if(m.contacts.length){contacts=m.contacts;firstOccupied={sample:i,pose:p};break;}
          if(world.occupied(p,vehicle.width,vehicle.length)){firstOccupied={sample:i,pose:p};break;}previous=p;
        }
        const steering=Math.atan(maxCurvature*vehicle.wheelbase),attempt={leadMetres:lead,direction:lead<0?'reverse':'forward',samples:count,maximumCurvature:maxCurvature,maximumSteering:steering,contacts,firstOccupied};attempts.push(attempt);
        if(!contacts.length&&!firstOccupied&&steering<=.58){accepted={...attempt,controlPoints:control.map(p=>({x:p.x,z:p.z})),endPositionError:gap(previous,stop),endHeadingError:Math.abs(angleDifference(previous.heading,stop.heading))};break;}
      }
      const row={id:stop.id,name:stop.name,pose:poseRecord(stop),occupied,clearanceHalfMetresAvailable:!withClearance,minimumMeasuredSideClearance:round(clearPerSide),sideClearanceSearchCap:5,approach:accepted,attempts};results.push(row);
      if(occupied||withClearance||!accepted)failures.push(row);
    }
    need(!failures.length,'Some real parking sites lack a collision-free drivable approach or half-metre side clearance',{results,failures});return {results,boundary:'A curvature-bounded continuously swept geometric path proves local reachability. It is not a browser or human parking test; moving traffic is excluded.'};
  });

  check('all-twelve-photo-parking-gates-and-save-restore',{stopSecondsRequired:2,rollingSpeedMetresPerSecond:.4,allowedStoppedSpeedLessThan:.2,vehicle,storage:'in-memory Storage adapter; actual Journey serialization'},()=>{
    const storage=memoryStorage(),j=new Journey(journeyData,storage),results=[];
    for(const stop of journeyData.stops){
      const d=atStop(stop,'auto');j.update(3,d);need(!j.canCapture&&!j.capture(),'Automatic mode captured a stop',{id:stop.id});
      d.setMode('manual');d.speed=.4;j.update(3,d);need(!j.canCapture&&!j.capture(),'Rolling vehicle captured a stop',{id:stop.id});
      d.speed=0;j.update(1.9,d);need(!j.canCapture&&!j.capture(),'Capture unlocked before two seconds',{id:stop.id});
      j.update(.11,d);need(j.canCapture,'Aligned parked car did not unlock capture',{id:stop.id,pose:d.pose,active:j.active?.id,seconds:j.parkedSeconds});
      const before=j.save.score;need(j.capture()&&!j.capture(),'Capture was unavailable or repeatable',{id:stop.id});need(j.save.score===before+100,'Duplicate capture changed score',{id:stop.id});results.push({id:stop.id,awardedPoints:j.save.score-before,parkedSeconds:j.parkedSeconds});
    }
    const last=atStop(journeyData.stops.at(-1));last.laps=3;j.update(.01,last);j.persist();const expected=JSON.parse(JSON.stringify(j.save)),restored=new Journey(journeyData,storage),restoredDrive=configure(new Drive(route));restored.restore(restoredDrive);
    need(j.complete&&j.save.collected.length===12,'All 12 stops were not completed');need(JSON.stringify(restored.save)===JSON.stringify(expected),'Serialized journey progress did not restore exactly',{expected,actual:restored.save});
    need(Math.abs(restoredDrive.distance-expected.distance)<1e-8&&restoredDrive.laps===3,'Drive position/lap did not restore',{expected,actual:{distance:restoredDrive.distance,laps:restoredDrive.laps}});
    need(!world.occupied(restoredDrive.pose,vehicle.width,vehicle.length),'Restored route position occupies runtime geometry',{pose:restoredDrive.pose});
    return {results,complete:j.complete,saved:expected,restored:restored.save,restoredPose:poseRecord(restoredDrive.pose),boundary:'Validates progress data and route/lap restoration. IndexedDB image blobs and browser reload persistence require browser evidence.'};
  });

  check('photo-shutter-ticket-freezes-stop-and-awards-once',{stops:journeyData.stops.slice(0,2).map(s=>s.id),asynchronousStorage:'simulated completion order; no browser IndexedDB'},()=>{
    const j=new Journey(journeyData,memoryStorage()),a=atStop(journeyData.stops[0]);j.update(2.1,a);
    const first=j.prepareCapture(),duplicate=j.prepareCapture(),abandoned=j.prepareCapture();need(first&&duplicate&&abandoned,'Parked stop did not issue capture authorization');
    need(j.save.collected.length===0&&j.save.score===1000,'Preparing a photo awarded before image storage succeeded');
    a.speed=5;j.update(.1,a);need(!j.prepareCapture(),'Moving vehicle obtained new shutter authorization');
    const b=atStop(journeyData.stops[1]);j.update(2.1,b);need(j.active?.id===journeyData.stops[1].id,'Second stop did not become active');
    need(first.commit(),'First stored image did not award its shutter stop');need(j.save.collected[0]===journeyData.stops[0].id,'Delayed photo awarded the later active stop');
    need(!first.commit()&&!duplicate.commit()&&!abandoned.commit(),'Duplicate or competing shutter tickets awarded twice');
    need(j.save.score===1100&&j.save.collected.length===1,'Delayed capture awarded incorrect count or score');
    return {authorizedStop:first.stop.id,activeAtCommit:j.active?.id,collected:j.save.collected,score:j.save.score,duplicateCommitAccepted:false,uncommittedTicketAwarded:false};
  });

  check('recovery-avoids-occupied-nearby-and-refuses-all-blocked',{vehicle,origin:'real route pose at 100m',extraObstacles:'test-only traffic rectangles added over full unchanged static world'},()=>{
    const d=configure(new Drive(route));d.distance=100;d.start('manual');const original=d.pose,blocked=new CollisionWorld(obstacles);blocked.setTraffic([{id:'recovery-test-car',pose:original,width:vehicle.width+.4,length:vehicle.length+1}]);d.collision=blocked;
    need(d.recover(),'Recovery did not find a nearby clear route pose');need(gap(original,d.pose)>2&&!blocked.occupied(d.pose,vehicle.width+.3,vehicle.length+.5),'Recovery placed the car inside an occupied pose',{original,resolved:d.pose});const recovered=d.pose;
    const jam=new CollisionWorld(obstacles),cars=[];for(let distance=d.distance-100;distance<=d.distance+100;distance+=2)cars.push({id:`recovery-jam-${distance}`,pose:track.pose(distance),width:vehicle.width+2,length:vehicle.length+2});jam.setTraffic(cars);d.collision=jam;d.speed=1;const before={pose:d.pose,distance:d.distance,speed:d.speed,laps:d.laps,gear:d.gear};
    need(d.recover()===false,'Recovery succeeded when every candidate was occupied');need(JSON.stringify(before)===JSON.stringify({pose:d.pose,distance:d.distance,speed:d.speed,laps:d.laps,gear:d.gear}),'Failed recovery mutated drive state',{before,after:{pose:d.pose,distance:d.distance,speed:d.speed,laps:d.laps,gear:d.gear}});
    return {original:poseRecord(original),recovered:poseRecord(recovered),refusedWhenAllBlocked:true,unchangedAfterRefusal:true,testTrafficCount:cars.length};
  });

  check('save-validation-and-storage-error',{malformedVersions:[0,2],invalidIds:true,duplicates:true,nonfiniteAndNegativeNumbers:true},()=>{
    const key='shanghai-loop-journey-v1',id=journeyData.stops[0].id,storage=memoryStorage();storage.setItem(key,JSON.stringify({version:1,collected:[id,id,'unknown',null,123],discovered:[id,id,'bad'],score:-8,lap:-1,distance:1e10,penalties:'Infinity'}));
    const restored=new Journey(journeyData,storage),d=new Drive(route);restored.restore(d);need(restored.save.collected.length===1&&restored.save.discovered.length===1,'Invalid/duplicate stop IDs survived restore');need(restored.save.score===1000&&restored.save.lap===0&&restored.save.penalties===0,'Invalid saved numbers replaced defaults');need(d.distance===d.path.total-.001&&finite(d.pose),'Out-of-range saved distance was not clamped');
    for(const serialized of ['invalid json','null',JSON.stringify({version:0,collected:[id]}),JSON.stringify({version:2,collected:[id]})]){storage.setItem(key,serialized);const j=new Journey(journeyData,storage);need(j.save.collected.length===0&&j.save.score===1000,'Malformed/unsupported save was accepted',{serialized});}
    const j=new Journey(journeyData,{getItem:()=>null,setItem:()=>{throw new Error('quota exceeded');}});need(j.persist()===false&&j.notice.includes('保存'),'Storage failure was silently reported as success');
    return {validStopIds:restored.save.collected,clampedDistance:d.distance,malformedSaveCases:4,storageFailureReported:true};
  });
  check('input-and-source-snapshot-stability',{files:FILES},()=>{
    const changed=FILES.filter(p=>sha(read(p))!==sha(snapshots[p]));need(!changed.length,'A source or runtime asset changed during this verification; rerun before acceptance',{changed});return {changed};
  });
  return {schemaVersion:1,startedAt,finishedAt:new Date().toISOString(),command:'node --import tsx scripts/verify_loop_physics.mjs',runtime:{node:process.version,platform:process.platform,arch:process.arch},passed:checks.every(c=>c.passed),summary:{checks:checks.length,passed:checks.filter(c=>c.passed).length,failed:checks.filter(c=>!c.passed).length,wallSeconds:round((performance.now()-started)/1000)},inputs:FILES.map(p=>({path:p,bytes:snapshots[p].length,sha256:sha(snapshots[p])})),vehicle,checks,boundaries:['Pure Node/CPU execution of the actual Drive, CollisionWorld and Journey classes. No browser, screenshots, renderer, network, service or Blender was used.','Three-lap route test includes all 26k+ authored static colliders but excludes dynamic traffic. Dynamic objects are separately exercised by recovery and isolated collision controls.','The speed/frame matrix uses unchanged real asset polygons in isolated worlds to make impact invariants reproducible. It does not claim those speeds are achievable at each physical object.','Parking validation proves static geometric reachability with bounded curvature and clear swept car bodies, not manual user skill or browser parking acceptance.','Image blob persistence and actual browser storage reload are outside this pure-physics and serialization report.','No runtime geometry, source implementation, images, models or prior evidence was modified to make a test pass.']};
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  const report=verifyLoopPhysics({progress:row=>process.stderr.write(`${row.passed?'PASS':'FAIL'} ${row.id} (${row.wallSeconds}s)\n`)});
  if(!process.argv.includes('--no-write')){
    const dest=path.join(ROOT,OUTPUT);fs.mkdirSync(path.dirname(dest),{recursive:true});
    if(fs.existsSync(dest)){const previous=fs.readFileSync(dest),id=sha(previous).slice(0,12),archive=path.join(path.dirname(dest),`loop-physics-verification.previous-${id}.json`);if(!fs.existsSync(archive))fs.writeFileSync(archive,previous);}
    fs.writeFileSync(dest,JSON.stringify(report,null,2)+'\n');
  }
  process.stdout.write(JSON.stringify(report,null,2)+'\n');process.exitCode=report.passed?0:1;
}
