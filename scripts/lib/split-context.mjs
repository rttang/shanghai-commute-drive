import assert from 'node:assert/strict';
import { parseGlb, packGlb } from './release-glb.mjs';

/** Partition whole triangles; no clipping or vertex movement. Driving geometry stays exact. */
export function splitContext(bytes, cellSize = 600) {
  const {json,bin}=parseGlb(bytes), groups=new Map();
  assert.ok(!json.animations?.length && !json.skins?.length);
  const size={5126:4,5125:4,5123:2,5121:1}, dims={SCALAR:1,VEC2:2,VEC3:3,VEC4:4};
  const read=id=>{const a=json.accessors[id],v=json.bufferViews[a.bufferView],stride=dims[a.type]*size[a.componentType];assert.ok(stride&&!a.sparse&&!a.normalized&&!v.byteStride);return {a,stride,data:bin.subarray((v.byteOffset||0)+(a.byteOffset||0),(v.byteOffset||0)+(a.byteOffset||0)+a.count*stride)};};
  let sourceTriangles=0;
  for(const node of json.nodes){
    assert.ok(!node.matrix && (node.translation||[0,0,0]).every(v=>v===0) && (node.rotation||[0,0,0,1]).every((v,i)=>v===(i===3?1:0)) && (node.scale||[1,1,1]).every(v=>v===1),'Context coordinates must already be world-space');
    if(node.mesh===undefined)continue;
    for(const primitive of json.meshes[node.mesh].primitives){
      assert.equal(primitive.mode??4,4);assert.ok(!primitive.extensions&&!primitive.targets);
      const attrs=Object.fromEntries(Object.entries(primitive.attributes).map(([k,id])=>[k,read(id)]));
      const position=attrs.POSITION;assert.equal(position.a.componentType,5126);
      const ix=read(primitive.indices);assert.ok([5123,5125].includes(ix.a.componentType));
      const indices=Array.from({length:ix.a.count},(_,i)=>ix.stride===2?ix.data.readUInt16LE(i*2):ix.data.readUInt32LE(i*4));
      const buckets=new Map();
      for(let i=0;i<indices.length;i+=3){
        const tri=indices.slice(i,i+3);sourceTriangles++;
        const cx=tri.reduce((s,v)=>s+position.data.readFloatLE(v*12),0)/3;
        const cz=tri.reduce((s,v)=>s+position.data.readFloatLE(v*12+8),0)/3;
        // Retain the distant silhouette; only near street and tunnel geometry streams.
        const key=/^context-(ground|water|roof|lowrise|modern|heritage)$/.test(node.name)?'global':`${Math.floor(cx/cellSize)}_${Math.floor(cz/cellSize)}`;
        if(!buckets.has(key))buckets.set(key,[]);buckets.get(key).push(...tri);
      }
      for(const [key,originalIndices] of buckets){
        if(!groups.has(key))groups.set(key,{parts:[],bounds:[Infinity,Infinity,-Infinity,-Infinity],triangles:0});
        const group=groups.get(key), remap=new Map(),originalVertices=[];
        const nextIndices=originalIndices.map(v=>{if(!remap.has(v)){remap.set(v,remap.size);originalVertices.push(v);}return remap.get(v);});
        const nextAttrs={};
        for(const [name,a] of Object.entries(attrs)){
          const data=Buffer.alloc(originalVertices.length*a.stride);
          originalVertices.forEach((v,i)=>a.data.copy(data,i*a.stride,v*a.stride,(v+1)*a.stride));
          nextAttrs[name]={...a,data};
        }
        const pos=nextAttrs.POSITION.data;
        for(let i=0;i<originalVertices.length;i++){
          const x=pos.readFloatLE(i*12),z=pos.readFloatLE(i*12+8);
          group.bounds[0]=Math.min(group.bounds[0],x);group.bounds[1]=Math.min(group.bounds[1],z);group.bounds[2]=Math.max(group.bounds[2],x);group.bounds[3]=Math.max(group.bounds[3],z);
        }
        // Each output triangle references the exact original vertex attribute bytes, in order.
        assert.ok(nextIndices.every((v,i)=>originalVertices[v]===originalIndices[i]));
        group.triangles+=nextIndices.length/3;
        group.parts.push({node,primitive,attrs:nextAttrs,indices:nextIndices});
      }
    }
  }
  assert.equal([...groups.values()].reduce((s,g)=>s+g.triangles,0),sourceTriangles);
  return [...groups].map(([key,g])=>{
    const j={asset:json.asset,scene:0,scenes:[{nodes:[]}],nodes:[],meshes:[],materials:json.materials,textures:json.textures,samplers:json.samplers,images:structuredClone(json.images),extensionsUsed:json.extensionsUsed,accessors:[],bufferViews:[]};
    const bins=[];let offset=0;
    const addView=data=>{const id=j.bufferViews.length;j.bufferViews.push({buffer:0,byteOffset:offset,byteLength:data.length});bins.push(data);offset+=data.length;const pad=(4-offset%4)%4;if(pad){bins.push(Buffer.alloc(pad));offset+=pad;}return id;};
    for(const part of g.parts){
      const attributes={};
      for(const [name,a]of Object.entries(part.attrs)){
        const accessor={...a.a,bufferView:addView(a.data),byteOffset:0,count:a.data.length/a.stride};delete accessor.min;delete accessor.max;
        if(name==='POSITION'){
          const min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];
          for(let i=0;i<accessor.count;i++)for(let d=0;d<3;d++){const v=a.data.readFloatLE(i*12+d*4);min[d]=Math.min(min[d],v);max[d]=Math.max(max[d],v);}Object.assign(accessor,{min,max});
        }
        attributes[name]=j.accessors.length;j.accessors.push(accessor);
      }
      const indices=Buffer.alloc(part.indices.length*4);part.indices.forEach((v,i)=>indices.writeUInt32LE(v,i*4));
      const ai=j.accessors.length;j.accessors.push({bufferView:addView(indices),componentType:5125,type:'SCALAR',count:part.indices.length});
      const mesh=j.meshes.length;j.meshes.push({primitives:[{...part.primitive,attributes,indices:ai}]});
      j.scenes[0].nodes.push(j.nodes.length);j.nodes.push({...part.node,mesh});
    }
    for(const image of j.images||[]){if(image.bufferView!==undefined){const v=json.bufferViews[image.bufferView];image.bufferView=addView(bin.subarray(v.byteOffset||0,(v.byteOffset||0)+v.byteLength));}}
    j.buffers=[{byteLength:offset}];
    return {id:`context-${key}`,always:key==='global',bounds:g.bounds,triangles:g.triangles,bytes:packGlb(j,Buffer.concat(bins))};
  });
}
