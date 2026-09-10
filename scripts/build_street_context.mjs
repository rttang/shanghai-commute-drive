// The master and runtime share this exact OSM terrain/backdrop geometry.
// Close buildings belong to photographed district assets, never this backdrop.
import * as THREE from 'three';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import fs from 'node:fs/promises';
import path from 'node:path';
import { Path } from '../src/tour/drive.ts';
import { buildStreetTunnels } from './street_tunnels.mjs';
import { buildStreetPortals } from './street_portals.mjs';
const root = path.resolve(import.meta.dirname, '..');
const city = JSON.parse(await fs.readFile(path.join(root, 'public/tour-city.json')));
const placements = JSON.parse(await fs.readFile(path.join(root, 'public/streets/master/placements.json')));
const covered = new Set();
for (const name of ['bund', 'pudong', 'north-bund', 'loop-frontages']) {
  if(!(await fs.stat(path.join(root, `public/streets/districts/${name}/manifest.json`)).catch(()=>null)))continue;
  const m = JSON.parse(await fs.readFile(path.join(root, `public/streets/districts/${name}/manifest.json`)));
  for (const model of m.models) for (const way of model.ways || []) covered.add(way);
}
globalThis.FileReader = class {
  readAsArrayBuffer(blob) { blob.arrayBuffer().then(result => { this.result = result; this.onloadend?.(); }); }
  readAsDataURL(blob) { blob.arrayBuffer().then(result => { this.result = `data:${blob.type};base64,${Buffer.from(result).toString('base64')}`; this.onloadend?.(); }); }
};
const scene = new THREE.Scene();
const buckets = new Map();
function add(g, name) {
  if (g.index) { const old = g; g = g.toNonIndexed(); old.dispose(); }
  g.clearGroups();
  if (!g.getAttribute('uv')) g.setAttribute('uv', new THREE.Float32BufferAttribute(new Float32Array(g.getAttribute('position').count * 2), 2));
  if (!g.getAttribute('normal')) g.computeVertexNormals();
  const group = buckets.get(name) || [];
  group.push(g); buckets.set(name, group);
}
function surface(points, height) {
  const g = new THREE.ShapeGeometry(new THREE.Shape(points.map(p => new THREE.Vector2(p[0], -p[1]))));
  g.rotateX(-Math.PI / 2); g.translate(0, height, 0); return g;
}
function ribbon(points, width, y) {
  const p = [], uv = [], indices = []; let distance = 0;
  for (let i = 0; i < points.length; i++) {
    const a = points[Math.max(0, i - 1)], b = points[Math.min(points.length - 1, i + 1)];
    const dx = b[0] - a[0], dz = b[1] - a[1], length = Math.hypot(dx, dz) || 1;
    if (i) distance += Math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]);
    for (const side of [-1, 1]) { p.push(points[i][0] + dz / length * width / 2 * side, y, points[i][1] - dx / length * width / 2 * side); uv.push(side * width / 6, distance / 3); }
    if (i) { const k = i * 2; indices.push(k - 2, k, k - 1, k - 1, k, k + 1); }
  }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(p, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2)); g.setIndex(indices); g.computeVertexNormals(); return g;
}
const colors = {'context-ground':'#96988b','context-water':'#52766e','context-grass':'#698957','context-paving':'#bbb9af','context-asphalt':'#888c86','context-curb':'#c2bdb0','context-markings':'#eee8d7','context-roof':'#93958b','context-heritage':'#cac1af','context-lowrise':'#c2c2b7','context-modern':'#8396a0'};
const groundShape=new THREE.Shape([new THREE.Vector2(-10000,-10000),new THREE.Vector2(10000,-10000),new THREE.Vector2(10000,10000),new THREE.Vector2(-10000,10000)]);
const tunnelPaths=[];
for(const route of city.routes) {
  const routePath=new Path(route.points,!!route.closed,route.elevations);
  for(const tunnel of route.tunnels??[]){
    const left=[],right=[],samples=[];
    for(let d=tunnel.start;d<tunnel.end;d+=5)samples.push(d);
    samples.push(tunnel.end);
    for(const d of samples){
      const a=routePath.pose(d,5.2),b=routePath.pose(d,-5.2);
      left.push(new THREE.Vector2(a.x,-a.z));right.push(new THREE.Vector2(b.x,-b.z));
    }
    groundShape.holes.push(new THREE.Path([...left,...right.reverse()]));
    tunnelPaths.push({path:routePath,tunnel,samples});
  }
}
const ground=new THREE.ShapeGeometry(groundShape);ground.rotateX(-Math.PI/2);ground.translate(0,-.18,0);
for(let i=0;i<ground.attributes.uv.count;i++) ground.attributes.uv.setXY(i,ground.attributes.position.getX(i)/3,ground.attributes.position.getZ(i)/3);
add(ground,'context-ground');
const tunnelDetails=buildStreetTunnels(tunnelPaths,add,colors);
const portalDetails=buildStreetPortals(tunnelPaths,city.roads,add,colors);
const seen = new Set();
for (const w of city.water) { if (!seen.has(w.id)) add(surface(w.points, -.06), 'context-water'); seen.add(w.id); }
for (const p of city.parks) add(surface(p.points, .045), 'context-grass');
for (const r of city.roads) {
  if (r.tunnel || (['人民路隧道','新建路隧道'].includes(r.name)&&city.routes.some(t=>t.sourceWays.includes(r.id))) || r.kind === 'steps' || r.points.length < 2) continue;
  add(ribbon(r.points, r.width, r.foot ? .105 : .125), r.foot ? 'context-paving' : 'context-asphalt');
  if (r.foot) continue;
  add(ribbon(r.points, r.width + (city.routes.some(t => t.sourceWays.includes(r.id)) ? 18 : 2), .07), 'context-paving');
  if (r.width < 6) continue;
  // Reproduce road markings from the same measured polyline used by driving.
  const lanes = Math.max(2, Math.round(r.width / 3.2));
  let traversed = 0;
  for (let i = 1; i < r.points.length; i++) {
    const a = r.points[i-1], b = r.points[i], dx = b[0]-a[0], dz = b[1]-a[1], length = Math.hypot(dx,dz);
    if (!length) continue;
    for (let d = (3 - traversed % 10 + 10) % 10; d < length - .2; d += 10) for (let lane=1;lane<lanes;lane++) {
      const offset=-r.width/2+lane*r.width/lanes, end=Math.min(d+4,length);
      add(ribbon([[a[0]+dx*d/length+dz*offset/length,a[1]+dz*d/length-dx*offset/length],[a[0]+dx*end/length+dz*offset/length,a[1]+dz*end/length-dx*offset/length]],.14,.15),'context-markings');
    }
    traversed += length;
  }
}
// Each whole curb segment has already passed exact road/intersection clearance.
// A real 0.28 x 0.16 m block replaces the previous flat strip crossing junctions.
for (const c of placements.curbs) {
  const dx=c.b[0]-c.a[0],dz=c.b[1]-c.a[1],length=Math.hypot(dx,dz);
  const g = new THREE.BoxGeometry(.28,.16,length);
  g.rotateY(Math.atan2(dx,dz)); g.translate((c.a[0]+c.b[0])/2,.15,(c.a[1]+c.b[1])/2); add(g,'context-curb');
}
let backgroundBuildings=0;
for (const b of city.buildings) {
  if (covered.has(b.id) || b.points.length < 4) continue;
  const g=new THREE.ExtrudeGeometry(new THREE.Shape(b.points.map(p=>new THREE.Vector2(p[0],-p[1]))),{depth:b.height,bevelEnabled:false,steps:1});
  g.rotateX(-Math.PI/2);
  const positions=g.getAttribute('position'),normals=g.getAttribute('normal'),uv=g.getAttribute('uv');
  for(let i=0;i<positions.count;i++) if(Math.abs(normals.getY(i))<.5) uv.setXY(i,(Math.abs(normals.getX(i))>.7?positions.getZ(i):positions.getX(i))/13.6,positions.getY(i)/13.6);
  const x=b.points.reduce((n,p)=>n+p[0],0)/b.points.length;
  for (const group of g.groups) {
    const part = new THREE.BufferGeometry();
    for (const key of ['position','normal','uv']) { const a=g.getAttribute(key); part.setAttribute(key,new THREE.BufferAttribute(a.array.slice(group.start*a.itemSize,(group.start+group.count)*a.itemSize),a.itemSize)); }
    add(part,group.materialIndex===0?'context-roof':b.height>70?'context-modern':x< -450?'context-heritage':'context-lowrise');
  }
  g.dispose(); backgroundBuildings++;
}
let triangles=0;
for(const [name, geometries] of buckets) {
  const geometry=mergeGeometries(geometries,false); for(const g of geometries)g.dispose();
  if(!geometry)throw new Error('Unable to merge '+name);
  const material=new THREE.MeshStandardMaterial({name,color:colors[name],roughness:name==='context-water'?.24:.88,metalness:name==='context-modern'?.24:0,side:THREE.DoubleSide});
  if(name==='context-tunnel-light'){material.emissive.set('#ffefcf');material.emissiveIntensity=2;}
  if(name==='context-tunnel-green'){material.emissive.set('#22ec91');material.emissiveIntensity=2;}
  if(name==='context-tunnel-panel'||name==='context-tunnel-cream'){material.emissive.set(colors[name]);material.emissiveIntensity=.12;material.roughness=.48;}
  if(name.startsWith('context-portal-')&&name.endsWith('-sign'))material.side=THREE.FrontSide;
  if(name==='context-portal-glass'){material.transparent=true;material.opacity=.36;material.roughness=.3;material.depthWrite=false;}
  if(name==='context-portal-hailun-sign'||name==='context-portal-limit43-sign'){material.transparent=true;material.alphaTest=.2;}
  const mesh=new THREE.Mesh(geometry,material);mesh.name=name;mesh.userData.category='context';scene.add(mesh);triangles+=geometry.getAttribute('position').count/3;
}
const buffer=await new GLTFExporter().parseAsync(scene,{binary:true,onlyVisible:false});
const out=path.join(root,'public/streets/master/context.glb');await fs.writeFile(out,Buffer.from(buffer));
await fs.writeFile(path.join(root,'public/streets/master/context.json'),JSON.stringify({generator:'scripts/build_street_context.mjs',backgroundBuildings,tunnelDetails,portalDetails,coveredWays:[...covered],triangles,bytes:buffer.byteLength,materialTextures:{'context-portal-renmin-sign':'streets/textures/portal-renmin-r1.png','context-portal-xinjian-sign':'streets/textures/portal-xinjian-r1.png','context-portal-hailun-sign':'streets/textures/portal-hailun-r1.png','context-portal-limit43-sign':'streets/textures/portal-limit43-r1.png','context-ground':'streets/textures/paving-diff.jpg','context-paving':'streets/textures/paving-diff.jpg','context-asphalt':'environment/asphalt-diff.jpg','context-tunnel-floor':'environment/asphalt-diff.jpg','context-curb':'streets/textures/stone-diff.jpg','context-grass':'streets/textures/ground-grass-diff.jpg','context-heritage':'streets/textures/heritage-facade.png','context-lowrise':'streets/textures/heritage-facade.png'}},null,2)+'\n');
console.log(JSON.stringify({out,bytes:buffer.byteLength,triangles,backgroundBuildings,covered:covered.size}));
