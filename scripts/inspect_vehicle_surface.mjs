import fs from 'node:fs';
import path from 'node:path';
import {Matrix4,Quaternion,Vector3,Ray} from 'three';
import {parseGlb,primitiveGeometry} from './model_collision_geometry.mjs';
const root=path.resolve(import.meta.dirname,'..');
const file=process.argv[2]??'public/vehicles/rigged/yuan-up.glb';
const {doc,binary}=parseGlb(fs.readFileSync(path.join(root,file)));
const triangles=[];
async function visit(id,parent){
  const n=doc.nodes[id],local=n.matrix?new Matrix4().fromArray(n.matrix):new Matrix4().compose(new Vector3(...(n.translation??[0,0,0])),new Quaternion(...(n.rotation??[0,0,0,1])),new Vector3(...(n.scale??[1,1,1]))),matrix=parent.clone().multiply(local);
  if(n.mesh!==undefined)for(const p of doc.meshes[n.mesh].primitives){
    const {positions,indices}=await primitiveGeometry(doc,binary,p,root);
    const vertices=Array.from({length:positions.length/3},(_,i)=>new Vector3(...positions.slice(i*3,i*3+3)).applyMatrix4(matrix));
    for(let i=0;i<indices.length;i+=3){
      const points=[vertices[indices[i]],vertices[indices[i+1]],vertices[indices[i+2]]];
      if(Math.max(...points.map(p=>p.y))<1.1||Math.min(...points.map(p=>p.y))>1.6)continue;
      triangles.push({points,node:n.name,material:doc.materials[p.material]?.name});
    }
  }
  for(const c of n.children??[])await visit(c,matrix);
}
for(const id of doc.scenes[doc.scene??0].nodes)await visit(id,new Matrix4());
const result=[];
for(const y of [1.18,1.30,1.43,1.54])for(const z of [-1.2,-1.05,-.9,-.75,-.6,-.45]){
  const ray=new Ray(new Vector3(2,y,z),new Vector3(-1,0,0));let best;
  for(const t of triangles){const hit=ray.intersectTriangle(...t.points,false,new Vector3());if(hit&&(!best||hit.x>best.x))best={x:hit.x,node:t.node,material:t.material};}
  if(best)result.push({y,z,...best});
}
console.log(JSON.stringify({file,trianglesChecked:triangles.length,visibleSideMaterials:result},null,2));
