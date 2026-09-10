import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoadClearance } from '../src/tour/road-clearance.ts';
const root=path.resolve(import.meta.dirname,'..');
const read=async p=>JSON.parse(await fs.readFile(path.join(root,p),'utf8'));
const city=await read('public/tour-city.json'),specs=await read('src/tour/photo-architecture.json');
const corrections=await read('docs/evidence/tourism/street-master-orientation.json');
const roads=new RoadClearance(city.roads),results=[];
const clip=(vertices,height,above)=>{
 const out=[];
 for(let i=0;i<vertices.length;i++){
  const a=vertices[i],b=vertices[(i+1)%vertices.length],ia=above?a.y>=height:a.y<=height,ib=above?b.y>=height:b.y<=height;
  if(ia)out.push(a);
  if(ia!==ib)out.push(a.clone().lerp(b,(height-a.y)/(b.y-a.y)));
 }
 return out;
};
for(const district of ['bund','pudong']){
 const manifest=await read(`public/streets/districts/${district}/manifest.json`);
 for(const model of manifest.models){
  const spec=specs.find(s=>s.id===model.id);if(!spec)continue;
  const points=city.buildings.find(b=>b.id===model.ways[0]).points;
  const centroid=[0,1].map(i=>points.reduce((s,p)=>s+p[i],0)/points.length);
  const inward=Math.sin(model.heading)*(centroid[0]-model.center[0])+Math.cos(model.heading)*(centroid[1]-model.center[1]);
  assert.ok(inward>0,`${model.id}: facade extrudes away from mapped building interior`);
  const result={id:model.id,inwardProjectionM:inward};
  const correction=corrections.corrections.find(c=>c.id===model.id);
  if(correction){
   const file=await fs.readFile(path.join(root,'public',model.file));
   const length=file.readUInt32LE(12),doc=JSON.parse(file.subarray(20,20+length));
   // Geometry-only parse: source image bytes and actual geometry remain unchanged.
   doc.materials=doc.materials.map(()=>({}));doc.images=[];doc.textures=[];doc.samplers=[];
   const json=Buffer.from(JSON.stringify(doc)),pad=Buffer.alloc((4-json.length%4)%4,32),binary=file.subarray(20+length),header=Buffer.alloc(20);
   header.writeUInt32LE(0x46546c67,0);header.writeUInt32LE(2,4);header.writeUInt32LE(20+json.length+pad.length+binary.length,8);header.writeUInt32LE(json.length+pad.length,12);header.writeUInt32LE(0x4e4f534a,16);
   const glb=Buffer.concat([header,json,pad,binary]);const scene=(await new GLTFLoader().parseAsync(glb.buffer.slice(glb.byteOffset,glb.byteOffset+glb.byteLength),'')).scene;
   const inspect=heading=>{
    const wrapper=new THREE.Group();wrapper.position.set(...[model.center[0],.12,model.center[1]]);wrapper.rotation.y=heading;wrapper.add(scene);wrapper.updateMatrixWorld(true);
    let clippedFaces=0,intersectingFaces=0;const hits=new Map();
    scene.traverse(o=>{
     if(!o.isMesh)return;const p=o.geometry.attributes.position,index=o.geometry.index,n=index?index.count:p.count;
     for(let i=0;i<n;i+=3){
      let poly=[0,1,2].map(k=>new THREE.Vector3().fromBufferAttribute(p,index?index.getX(i+k):i+k).applyMatrix4(o.matrixWorld));
      poly=clip(clip(poly,.25,true),4.5,false);if(poly.length<2)continue;clippedFaces++;
      let hit=false;
      for(let k=0;k<poly.length;k++){
       const a=poly[k],b=poly[(k+1)%poly.length];
       for(const c of roads.conflicts([a.x,a.z],[b.x,b.z],0,0)){
        hit=true;hits.set(`${c.roadId}:${c.segment}`,c);
       }
      }
      if(hit)intersectingFaces++;
     }
    });
    return {heightBandM:[.25,4.5],clippedFaces,intersectingFaces,roadSegments:[...hits.values()]};
   };
   result.before=inspect(correction.oldHeading);result.after=inspect(model.heading);
   assert.ok(result.before.intersectingFaces>0,`${model.id}: regression must demonstrate the previous road conflict`);
   assert.equal(result.after.intersectingFaces,0,`${model.id}: low facade geometry still intersects a motor road`);
  }
  results.push(result);
 }
}
await fs.writeFile(path.join(root,'docs/evidence/tourism/street-master-photo-placement.json'),JSON.stringify({pass:true,method:'All legacy photo facades point into their mapped footprint; both corrected models are decoded and their actual triangles clipped to 0.25–4.5m and compared against complete motor-road widths before and after rotation.',results},null,2)+'\n');
console.log(JSON.stringify(results.filter(r=>r.after),null,2));
