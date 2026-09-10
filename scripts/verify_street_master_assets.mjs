import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { PLACEMENT_CLEARANCE } from '../src/tour/road-clearance.ts';
const root=path.resolve(import.meta.dirname,'..');
const pub=path.join(root,'public');
const json=async file=>JSON.parse(await fs.readFile(path.join(root,file),'utf8'));
const sha=data=>createHash('sha256').update(data).digest('hex');
function readGLB(buffer) {
  assert.equal(buffer.readUInt32LE(0),0x46546c67);assert.equal(buffer.readUInt32LE(4),2);assert.equal(buffer.readUInt32LE(8),buffer.length);
  const length=buffer.readUInt32LE(12);assert.equal(buffer.readUInt32LE(16),0x4e4f534a);
  const doc=JSON.parse(buffer.subarray(20,20+length));
  const start=28+length;assert.equal(buffer.readUInt32LE(24+length),0x004e4942);
  return {doc,binary:buffer.subarray(start)};
}
function integrity(doc,binary) {
  assert.equal(doc.asset.version,'2.0');assert.equal(doc.buffers.length,1);assert.ok(!doc.buffers[0].uri);
  assert.ok(doc.buffers[0].byteLength<=binary.length);
  for(const v of doc.bufferViews)assert.ok(v.buffer===0&&(v.byteOffset||0)>=0&&(v.byteOffset||0)+v.byteLength<=binary.length);
  for(const a of doc.accessors){if(a.bufferView!==undefined)assert.ok(doc.bufferViews[a.bufferView]);for(const k of ['min','max'])if(a[k])assert.ok(a[k].every(Number.isFinite));}
  for(const m of doc.meshes)for(const p of m.primitives){
    assert.ok(doc.materials[p.material]);for(const a of Object.values(p.attributes))assert.ok(doc.accessors[a]);
    if(p.indices!==undefined){
      const index=doc.accessors[p.indices];assert.ok(index);
      if(index.bufferView!==undefined){
        const view=doc.bufferViews[index.bufferView],format={5121:[1,'readUInt8'],5123:[2,'readUInt16LE'],5125:[4,'readUInt32LE']}[index.componentType];
        assert.ok(format&&index.type==='SCALAR','Triangle indices must be unsigned integer scalars');
        const [width,method]=format,start=(view.byteOffset||0)+(index.byteOffset||0),stride=view.byteStride||width;
        assert.ok(start+Math.max(0,index.count-1)*stride+width<=(view.byteOffset||0)+view.byteLength,'Index accessor exceeds its declared buffer view');
        const positions=doc.accessors[p.attributes.POSITION].count;
        for(let i=0;i<index.count;i++)assert.ok(binary[method](start+i*stride)<positions,`Out-of-range triangle index in ${m.name||'unnamed mesh'}`);
      }
    }
  }
  for(const n of doc.nodes){if(n.mesh!==undefined)assert.ok(doc.meshes[n.mesh]);for(const c of n.children||[])assert.ok(doc.nodes[c]);for(const k of ['translation','rotation','scale','matrix'])if(n[k])assert.ok(n[k].every(Number.isFinite));}
  for(const i of doc.images||[])assert.ok(i.bufferView!==undefined&&!i.uri);
  assert.ok(!doc.animations?.length&&!doc.skins?.length);
}
const manifest=await json('public/streets/master/manifest.json');
const master=await fs.readFile(path.join(pub,manifest.master.file));
assert.equal(master.length,manifest.master.bytes);assert.equal(sha(master),manifest.master.sha256);
const budget=(await json('public/streets/model-budget.json')).streetMaster;
assert.ok(master.length>budget.minBytesExclusive&&master.length<budget.maxBytesExclusive,'Single master must fit the GLB byte-length field');
assert.ok(manifest.chunks.reduce((sum,c)=>sum+c.bytes,0)<=budget.runtimePackageMaxBytesInclusive,'Runtime street resources exceed the approved 5 GB budget');
const {doc,binary}=readGLB(master);integrity(doc,binary);
const uniqueTriangles=doc.meshes.reduce((n,m)=>n+m.primitives.reduce((s,p)=>s+((p.mode??4)===4 ? doc.accessors[p.indices??p.attributes.POSITION].count/3 : 0),0),0);
assert.equal(uniqueTriangles,manifest.master.uniqueTriangles);
const covered=new Set(manifest.coveredWays);
const inventory=await json('references/tourism/street-frontage-coverage.json');
const first=inventory.buildings.filter(b=>b.frontage.classification==='first-row-sampled');
for(const b of first)assert.ok(covered.has(b.wayId),`Unmodeled first frontage ${b.wayId}`);
const chunks=[];
for(const chunk of manifest.chunks){const buffer=await fs.readFile(path.join(pub,chunk.file));assert.equal(buffer.length,chunk.bytes);assert.equal(sha(buffer),chunk.sha256);const g=readGLB(buffer);integrity(g.doc,g.binary);chunks.push({id:chunk.id,bytes:buffer.length,sha256:sha(buffer)});}
const furniture=await json('public/streets/districts/furniture/manifest.json');
const lowFootprints=[];
for(const [id,policy] of Object.entries(PLACEMENT_CLEARANCE.objects)){
  const model=furniture.models.find(m=>m.id===id),buffer=await fs.readFile(path.join(pub,model.file));
  const scene=(await new GLTFLoader().parseAsync(buffer.buffer.slice(buffer.byteOffset,buffer.byteOffset+buffer.byteLength),'')).scene;
  scene.updateMatrixWorld(true);let radius=0,checked=0;
  scene.traverse(o=>{if(!o.isMesh)return;const a=o.geometry.attributes.position;for(let i=0;i<a.count;i++){const v=new THREE.Vector3().fromBufferAttribute(a,i).applyMatrix4(o.matrixWorld);if(v.y<PLACEMENT_CLEARANCE.minimumStreetOverhangHeight){radius=Math.max(radius,Math.hypot(v.x,v.z));checked++;}}});
  assert.ok(radius<=policy.radius+.005,`${id}: real low mesh radius ${radius} exceeds placement envelope ${policy.radius}`);
  lowFootprints.push({id,verticesChecked:checked,actualRadius:radius,allowedRadius:policy.radius});
}
const bridge=furniture.models.find(m=>m.id==='waibaidu-bridge');
assert.ok(bridge.geometryClearanceValidation.passClearance&&bridge.geometryClearanceValidation.minimumActualHeight>=5.2);
// Protected originals and their restored copies are part of the delivery boundary.
const restoration=await json('docs/evidence/tourism/image-restoration.json');
const records=Array.isArray(restoration)?restoration:restoration.files||restoration.restored||restoration.images;
assert.ok(Array.isArray(records),'Image preservation record schema changed');
let preservedImages=0;
for(const record of records){for(const name of ['path','retained']){const data=await fs.readFile(path.isAbsolute(record[name])?record[name]:path.join(root,record[name]));assert.equal(sha(data),record.sha256);preservedImages++;}}
const generated=await json('docs/evidence/tourism/street-master-generated-images.json');
for(const record of generated){for(const name of ['path','retained']){const data=await fs.readFile(path.isAbsolute(record[name])?record[name]:path.join(root,record[name]));assert.equal(sha(data),record.sha256);preservedImages++;}}
const loop=await json('references/tourism/loop-frontage-catalog.json');
const loopFirst=loop.buildings.filter(b=>b.firstRow),loopMissing=loopFirst.filter(b=>!covered.has(b.wayId)).map(b=>b.wayId);
const result={pass:true,boundary:'GLB integrity, collision-envelope and protected-image checks; not a photo-fidelity acceptance',generated:new Date().toISOString(),master:{bytes:master.length,sha256:sha(master),uniqueTriangles,placedTriangles:manifest.master.triangles,meshResources:doc.meshes.length,nodes:doc.nodes.length,embeddedImages:doc.images?.length||0},legacyFirstRowCoverage:{total:first.length,covered:first.length},loopFirstRowCoverage:{total:loopFirst.length,covered:loopFirst.length-loopMissing.length,missing:loopMissing,complete:!loopMissing.length},chunks,lowFootprints,bridgeClearance:bridge.geometryClearanceValidation,preservedImages};
if(process.argv.includes('--require-loop-coverage')&&loopMissing.length)result.pass=false;
await fs.writeFile(path.join(root,'docs/evidence/tourism/street-master-assets.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify(result,null,2));
if(!result.pass)throw new Error(`Full loop geometry is incomplete: ${loopMissing.length} first-row ways still lack a district model`);
