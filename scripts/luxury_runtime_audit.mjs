/** Decode final GLB vertices and measure ground/radius through the full hierarchy. */
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {Matrix4,Quaternion,Vector3} from 'three';
import {parseGlb,primitiveGeometry} from './model_collision_geometry.mjs';
const root=process.cwd();
const [id,output]=process.argv.slice(2);
if(!['urus','porsche-911','ferrari-488','g63','alphard'].includes(id)||!output)throw new Error('Usage: node scripts/luxury_runtime_audit.mjs <id> <external-output.json>');
const results=[];
for(const relative of [`public/vehicles/rigged/${id}.glb`,`public/vehicles/rigged/luxury-traffic/${id}.glb`]){
 const raw=fs.readFileSync(path.join(root,relative)),{doc,binary}=parseGlb(raw),min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity],wheels={};let triangles=0,vertices=0;
 async function walk(index,parent,wheel){
  const node=doc.nodes[index];const local=node.matrix?new Matrix4().fromArray(node.matrix):new Matrix4().compose(new Vector3(...(node.translation??[0,0,0])),new Quaternion(...(node.rotation??[0,0,0,1])),new Vector3(...(node.scale??[1,1,1])));const world=parent.clone().multiply(local);
  if(/^Wheel_(FL|FR|RL|RR)$/.test(node.name??'')){
   wheel=node.name.slice(6);wheels[wheel]={radius:node.extras.wheelRadius,center:new Vector3().setFromMatrixPosition(world).toArray(),minY:Infinity,maxY:-Infinity,maxRadial:0,vertices:0};
  }
  if(node.mesh!==undefined)for(const primitive of doc.meshes[node.mesh].primitives){
   const geometry=await primitiveGeometry(doc,binary,primitive,root);const declared=doc.accessors[primitive.indices].count/3;if(geometry.indices.length/3!==declared)throw new Error('Decoded/index-accessor triangles differ');triangles+=declared;vertices+=geometry.positions.length/3;
   const v=new Vector3();for(let i=0;i<geometry.positions.length;i+=3){v.fromArray(geometry.positions,i).applyMatrix4(world);const p=v.toArray();for(let axis=0;axis<3;axis++){min[axis]=Math.min(min[axis],p[axis]);max[axis]=Math.max(max[axis],p[axis]);}if(wheel){const w=wheels[wheel];w.minY=Math.min(w.minY,v.y);w.maxY=Math.max(w.maxY,v.y);w.maxRadial=Math.max(w.maxRadial,Math.hypot(v.y-w.center[1],v.z-w.center[2]));w.vertices++;}}
  }
  for(const child of node.children??[])await walk(child,world,wheel);
 }
 for(const node of doc.scenes[doc.scene??0].nodes)await walk(node,new Matrix4(),null);
 if(Object.keys(wheels).length!==4)throw new Error('Expected four wheel pivots');
 const groundPass=Object.values(wheels).every(w=>w.minY>=-.002&&w.minY<=.012);
 results.push({file:relative,sha256:createHash('sha256').update(raw).digest('hex'),bytes:raw.length,triangles,decodedVertices:vertices,minXYZ:min,maxXYZ:max,dimensionsM:[max[2]-min[2],max[0]-min[0],max[1]-min[1]],wheels,groundPass,groundToleranceM:[-.002,.012]});
}
const result={id,method:'All decoded Draco POSITION vertices transformed through complete glTF node hierarchy; triangles checked against decoded indices',createdAt:new Date().toISOString(),results};
const destination=path.resolve(root,output);if(!destination.startsWith(root+path.sep))throw new Error('Audit must remain on external workspace');fs.writeFileSync(destination,JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
if(results.some(r=>!r.groundPass))process.exitCode=1;
