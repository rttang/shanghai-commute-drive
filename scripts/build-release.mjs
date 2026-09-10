import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { promisify } from 'node:util';
import { gzip, brotliCompress, constants } from 'node:zlib';
import { parseGlb } from './lib/release-glb.mjs';
const root=path.resolve(import.meta.dirname,'..'),out=path.join(root,'dist-release');
const runtime=path.join(root,'.tooling/deployment-optimization/runtime-assets');
const marker=path.join(out,'.deployment-owned');
const sha=b=>createHash('sha256').update(b).digest('hex');
const read=async p=>JSON.parse(await fs.readFile(p,'utf8'));
if(!process.argv.includes('--reuse-assets'))execFileSync(process.execPath,['--import','tsx','scripts/build-release-assets.mjs'],{cwd:root,stdio:'inherit'});
const manifest=await read(path.join(runtime,'runtime/manifest.json'));
const sources=(await read(path.join(root,'docs/evidence/deployment-optimization/asset-generation.json'))).sources;
for(const source of sources)if(sha(await fs.readFile(path.join(root,'public',source.file)))!==source.sha256)throw new Error(`Stale release source: ${source.file}`);
try { await fs.access(out);await fs.access(marker); } catch(e) { if(e.code!=='ENOENT')throw e;try{await fs.access(out);throw new Error('Refusing to overwrite an unowned dist-release');}catch(missing){if(missing.code!=='ENOENT')throw missing;} }
execFileSync(process.execPath,['node_modules/typescript/bin/tsc','--noEmit'],{cwd:root,stdio:'inherit'});
await fs.mkdir(out,{recursive:true});await fs.writeFile(marker,'Owned by scripts/build-release.mjs\n');
try{execFileSync(process.execPath,['node_modules/vite/bin/vite.js','build','--outDir',out],{cwd:root,stdio:'inherit',env:{...process.env,DEPLOY_RELEASE:'1',VITE_STREET_MANIFEST:'/runtime/manifest.json'}});}finally{await fs.writeFile(marker,'Owned by scripts/build-release.mjs\n');}
const needed=new Map();
const add=(url,base)=>{if(!url.startsWith('/')||url.includes('..'))throw new Error(`Unsafe asset URL: ${url}`);needed.set(url,path.join(base,url));};
add('/runtime/manifest.json',runtime);
for(const c of manifest.chunks){
  const source=path.join(runtime,c.file),bytes=await fs.readFile(source);
  if(bytes.length!==c.bytes||sha(bytes)!==c.sha256)throw new Error(`Derived asset hash mismatch: ${c.file}`);
  add(c.file,runtime);
  const {json}=parseGlb(bytes);
  for(const image of json.images||[])if(image.uri&&!image.uri.startsWith('data:'))add(image.uri,runtime);
}
const publicRoot=path.join(root,'public');
for(const file of ['/tour-city.json','/journey.json','/streets/collisions.json','/environment/sky.hdr','/favicon.svg','/home-preview.jpg'])add(file,publicRoot);
const assets=await read(path.join(root,'src/tour/vehicle-assets.json'));
const cars=await read(path.join(root,'src/tour/cars.json'));
for(const car of cars){const a=assets[car.id];if(a?.file)add(a.file,publicRoot);add(a?.preview||`/cars/${car.id}.png`,publicRoot);}
for(const car of cars.filter(c=>c.id==='model-y'||c.id==='model-3'||assets[c.id]?.trafficFile).slice(0,7))add(assets[car.id]?.trafficFile||`/vehicles/rigged/prototypes/${car.id}.glb`,publicRoot);
for(const name of await fs.readdir(path.join(publicRoot,'decoders/draco')))if(!name.startsWith('.'))add(`/decoders/draco/${name}`,publicRoot);
for(const [url,source]of needed){const target=path.join(out,url);await fs.mkdir(path.dirname(target),{recursive:true});await fs.copyFile(source,target);if(sha(await fs.readFile(target))!==sha(await fs.readFile(source)))throw new Error(`Copy mismatch: ${url}`);}
await fs.copyFile(path.join(root,'THIRD_PARTY_NOTICES.md'),path.join(out,'THIRD_PARTY_NOTICES.md'));
async function files(dir){const result=[];for(const e of await fs.readdir(dir,{withFileTypes:true})){if(e.name.startsWith('.'))continue;const p=path.join(dir,e.name);if(e.isDirectory())result.push(...await files(p));else result.push(p);}return result;}
const entries=[];
for(const file of await files(out)){
  const bytes=await fs.readFile(file),entry={file:path.relative(out,file),bytes:bytes.length,sha256:sha(bytes)};
  if(/\.(html|js|css|json|glb|wasm|hdr|svg)$/.test(file)&&bytes.length>1024){
    const br=await promisify(brotliCompress)(bytes,{params:{[constants.BROTLI_PARAM_QUALITY]:5}});
    const gz=await promisify(gzip)(bytes,{level:6});
    if(br.length<bytes.length*.95){await fs.writeFile(file+'.br',br);entry.brotliBytes=br.length;entry.brotliSha256=sha(br);}
    if(gz.length<bytes.length*.95){await fs.writeFile(file+'.gz',gz);entry.gzipBytes=gz.length;entry.gzipSha256=sha(gz);}
  }
  entries.push(entry);
}
const result={generatedAt:new Date().toISOString(),sourceFiles:needed.size,files:entries,uncompressedBytes:entries.reduce((s,x)=>s+x.bytes,0),brotliTransferBytes:entries.reduce((s,x)=>s+(x.brotliBytes??x.bytes),0),diskBytes:entries.reduce((s,x)=>s+x.bytes+(x.brotliBytes||0)+(x.gzipBytes||0),0)};
await fs.writeFile(path.join(out,'release-manifest.json'),JSON.stringify(result,null,2)+'\n');
await fs.writeFile(path.join(root,'docs/evidence/deployment-optimization/release-build.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({done:true,files:entries.length,uncompressedBytes:result.uncompressedBytes,brotliTransferBytes:result.brotliTransferBytes,diskBytes:result.diskBytes}));
