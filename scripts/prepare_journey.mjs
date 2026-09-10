import fs from 'node:fs/promises';
import { LANDMARKS, project } from '../src/tour/data.ts';
import { Path } from '../src/tour/drive.ts';
import { CollisionWorld,rectangle } from '../src/tour/collision.ts';
import { pointInPolygon,polylineDistance } from '../src/tour/road-clearance.ts';
const city=JSON.parse(await fs.readFile('public/tour-city.json'));
const collision=new CollisionWorld(JSON.parse(await fs.readFile('public/streets/collisions.json')).obstacles);
const route=city.routes[0],path=new Path(route.points,true,route.elevations);
const landmarks=[...LANDMARKS,
  {id:'waibaidu',name:'外白渡桥',lon:121.485735,lat:31.24531,about:'沿苏州河口看百年钢桥，让浦江与外滩同时进入画面。'},
  {id:'shiliupu',name:'十六铺',lon:121.4911,lat:31.2300,about:'沿黄浦江岸，回望外滩与陆家嘴的天际线。'},
  {id:'north-bund',name:'北外滩',lon:121.4960,lat:31.2492,about:'在北外滩回望一江两岸，完成这一圈上海的风景收藏。'},
];
const stops=[];
for(const l of landmarks){
  const landmark=project(l.lon,l.lat),near=path.project({x:landmark[0],z:landmark[1]},0,true);
  let choice;
  for(let d=150;d<path.total-30;d+=10){
    const p=path.at(d);
    if(Math.hypot(p.x-landmark[0],p.z-landmark[1])>800)continue;
    const offset=Math.abs(d-near.distance);
    if(p.y<-.1 || d<140)continue;
    const road=city.roads.find(r=>r.id===route.segmentWays[Math.max(0,path.distances.findIndex(x=>x>d)-1)]);
    const lateral=Math.max(3.8,(road?.width??6.4)/2+1.6),q=path.pose(d,lateral);
    if(stops.some(s=>Math.hypot(s.x-q.x,s.z-q.z)<12))continue;
    if(collision.occupied(q,3,6.4))continue;
    const corners=rectangle(q.x,q.z,q.heading,3,6.4);
    if(city.buildings.some(b=>corners.some(v=>pointInPolygon(v,b.points))) || city.water.some(w=>corners.some(v=>pointInPolygon(v,w.points))))continue;
    const cost=Math.hypot(q.x-landmark[0],q.z-landmark[1]);
    if(!choice||cost<choice.cost)choice={...q,distance:d,cost};
  }
  if(!choice)throw Error(`No clear parking site: ${l.name}`);
  const {cost,...pose}=choice;stops.push({id:l.id,name:l.name,about:l.about,...pose,landmark});
}
// Traffic controls are game placements at actual surface road junctions.
// Signal timings are authored for play, not live Shanghai timings.
const signals=[];
for(let d=500;d<path.total-150;d+=650){
  if(path.at(d).y<-.1 || stops.some(s=>Math.abs(s.distance-d)<50))continue;
  const p=path.pose(d,0);
  const roads=city.roads.filter(r=>!r.foot&&!r.tunnel&&polylineDistance([p.x,p.z],r.points)<20);
  if(roads.length<3)continue;
  signals.push({id:`signal-${signals.length}`,distance:d,x:p.x,z:p.z,heading:p.heading,offset:(signals.length*17)%70});
}
const roadRules=[];
for(let i=0;i<route.segmentWays.length;i++){
  const road=city.roads.find(r=>r.id===route.segmentWays[i]);
  const oneway=['yes','1','-1'].includes(String(road?.oneway));
  const last=roadRules.at(-1);
  if(last && last.way===route.segmentWays[i])last.end=path.distances[i+1];
  else roadRules.push({way:route.segmentWays[i],start:path.distances[i],end:path.distances[i+1],oneway,width:road?.width??6.4});
}
await fs.writeFile('public/journey.json',JSON.stringify({version:1,stops,signals,roadRules,parkingSource:'game sightseeing bays on the mapped street corridor; not real parking guidance',signalSource:'authored game timings at mapped junctions'},null,2));
console.log(JSON.stringify({stops:stops.map(s=>({name:s.name,distance:Math.round(s.distance)})),signals:signals.length}));
