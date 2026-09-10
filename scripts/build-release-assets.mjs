import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { compressGlb,parseGlb,packGlb } from './lib/release-glb.mjs';
import { splitContext } from './lib/split-context.mjs';
import { usePerformanceStreets } from '../src/tour/performance-streets.ts';
const root=path.resolve(import.meta.dirname,'..');
const publicRoot=path.join(root,'public');
const out=path.join(root,'.tooling/deployment-optimization/runtime-assets');
const sha=b=>createHash('sha256').update(b).digest('hex');
const read=async n=>JSON.parse(await fs.readFile(path.join(publicRoot,n),'utf8'));
const report={version:1,generatedAt:new Date().toISOString(),method:'Lossless meshopt; exact whole-triangle context partition; unchanged embedded image bytes stored once',sources:[],outputs:[]};
const master=await read('streets/master/manifest.json');
const selected=usePerformanceStreets(master,(await read('streets/performance/manifest.json')).variants);
await fs.mkdir(out,{recursive:true});
async function store(bytes,name){
  const hash=sha(bytes),url=`/runtime/${hash.slice(0,20)}/${name}`,file=path.join(out,url);
  await fs.mkdir(path.dirname(file),{recursive:true});
  try{const old=await fs.readFile(file);if(!old.equals(bytes))throw new Error('Hash collision');}catch(e){if(e.code!=='ENOENT')throw e;await fs.writeFile(file,bytes);}
  if(sha(await fs.readFile(file))!==hash)throw new Error('Output hash mismatch');
  return {file:url,bytes:bytes.length,sha256:hash};
}
async function externalize(bytes){
  const {json:j,bin}=parseGlb(bytes);
  // Keep pre-compressed formats untouched. Plain models can share their original images.
  if(j.extensionsUsed?.some(e=>e.includes('compression')))return bytes;
  for(const image of j.images||[]){
    if(image.bufferView===undefined)continue;
    const v=j.bufferViews[image.bufferView],raw=bin.subarray(v.byteOffset||0,(v.byteOffset||0)+v.byteLength);
    const type=image.mimeType==='image/png'?'png':image.mimeType==='image/webp'?'webp':'jpg';
    image.uri=(await store(raw,`texture.${type}`)).file;delete image.bufferView;
  }
  const used=new Set(j.accessors.filter(a=>a.bufferView!==undefined).map(a=>a.bufferView));
  const remap=new Map(),parts=[];let offset=0;const views=[];
  for(const id of used){const v=j.bufferViews[id],data=bin.subarray(v.byteOffset||0,(v.byteOffset||0)+v.byteLength);remap.set(id,views.length);views.push({...v,byteOffset:offset});parts.push(data);offset+=data.length;const pad=(4-offset%4)%4;if(pad){parts.push(Buffer.alloc(pad));offset+=pad;}}
  for(const a of j.accessors)if(a.bufferView!==undefined)a.bufferView=remap.get(a.bufferView);
  j.bufferViews=views;j.buffers=[{byteLength:offset}];return packGlb(j,Buffer.concat(parts));
}
const chunks=[];
for(const chunk of selected.chunks){
  const source=await fs.readFile(path.join(publicRoot,chunk.file));
  if(sha(source)!==chunk.sha256 || source.length!==chunk.bytes)throw new Error(`Source manifest mismatch: ${chunk.file}`);
  report.sources.push({file:chunk.file,bytes:source.length,sha256:sha(source)});
  const pieces=chunk.id==='context'?splitContext(source):[{...chunk,bytes:source}];
  for(const piece of pieces){
    const external=await externalize(piece.bytes),compressed=await compressGlb(external);
    const asset=await store(compressed.bytes,`${piece.id}.glb`);
    chunks.push({...chunk,id:piece.id,bounds:piece.bounds,always:piece.always,triangles:piece.triangles,...asset});
    report.outputs.push({id:piece.id,...asset,verifiedViews:compressed.verifiedViews});
  }
  if(sha(await fs.readFile(path.join(publicRoot,chunk.file)))!==chunk.sha256)throw new Error('Source changed during generation');
  console.log(JSON.stringify({source:chunk.id,sourceBytes:source.length,pieces:pieces.length,outputBytes:report.outputs.filter(x=>x.id===chunk.id||chunk.id==='context'&&x.id.startsWith('context-')).reduce((s,x)=>s+x.bytes,0)}));
}
const manifest={version:1,delivery:true,chunks,coveredWays:master.coveredWays};
await fs.mkdir(path.join(out,'runtime'),{recursive:true});
await fs.writeFile(path.join(out,'runtime/manifest.json'),JSON.stringify(manifest)+'\n');
report.sourceBytes=report.sources.reduce((s,x)=>s+x.bytes,0);report.chunkBytes=chunks.reduce((s,x)=>s+x.bytes,0);report.alwaysBytes=chunks.filter(c=>c.always).reduce((s,x)=>s+x.bytes,0);
await fs.writeFile(path.join(root,'docs/evidence/deployment-optimization/asset-generation.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({done:true,chunks:chunks.length,sourceBytes:report.sourceBytes,chunkBytes:report.chunkBytes,alwaysBytes:report.alwaysBytes}));
