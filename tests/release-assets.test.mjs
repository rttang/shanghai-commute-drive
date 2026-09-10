import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { brotliDecompressSync, gunzipSync } from 'node:zlib';
import { compressGlb, parseGlb, packGlb } from '../scripts/lib/release-glb.mjs';
import { splitContext } from '../scripts/lib/split-context.mjs';
import { createStaticServer } from '../scripts/serve-release.mjs';
const root=path.resolve(import.meta.dirname,'..');
const hash=b=>createHash('sha256').update(b).digest('hex');

test('published files and both HTTP encodings match the recorded content hashes',async()=>{
  const dir=path.join(root,'dist-release');
  const manifest=JSON.parse(await fs.readFile(path.join(dir,'release-manifest.json')));
  const license=(await fs.readFile(path.join(root,'node_modules/meshoptimizer/LICENSE.md'),'utf8')).trim();
  assert.ok((await fs.readFile(path.join(dir,'THIRD_PARTY_NOTICES.md'),'utf8')).includes(license));
  for(const entry of manifest.files){
    const bytes=await fs.readFile(path.join(dir,entry.file));assert.equal(hash(bytes),entry.sha256,entry.file);
    for(const [ext,field,decode]of [['br','brotli',brotliDecompressSync],['gz','gzip',gunzipSync]]){
      if(!entry[field+'Bytes'])continue;
      const encoded=await fs.readFile(path.join(dir,entry.file+'.'+ext));
      assert.equal(encoded.length,entry[field+'Bytes']);assert.equal(hash(encoded),entry[field+'Sha256']);assert.equal(hash(decode(encoded)),entry.sha256,`${entry.file}.${ext}`);
    }
  }
});

test('partition preserves every triangle and never moves position bytes across distant cells',()=>{
  const positions=new Float32Array([0,0,0,10,0,0,0,0,10,2000,0,0,2010,0,0,2000,0,10]);
  const indices=new Uint32Array([0,1,2,3,4,5]);
  const bin=Buffer.concat([Buffer.from(positions.buffer),Buffer.from(indices.buffer)]);
  const j={asset:{version:'2.0'},buffers:[{byteLength:bin.length}],bufferViews:[{buffer:0,byteLength:72},{buffer:0,byteOffset:72,byteLength:24}],accessors:[{bufferView:0,componentType:5126,type:'VEC3',count:6},{bufferView:1,componentType:5125,type:'SCALAR',count:6}],nodes:[{name:'context-road',mesh:0}],meshes:[{primitives:[{attributes:{POSITION:0},indices:1}]}],scene:0,scenes:[{nodes:[0]}]};
  const chunks=splitContext(packGlb(j,bin));assert.equal(chunks.length,2);assert.equal(chunks.reduce((s,c)=>s+c.triangles,0),2);
  const restored=chunks.map(c=>{const {json,bin}=parseGlb(c.bytes),a=json.accessors[0],v=json.bufferViews[a.bufferView];return bin.subarray(v.byteOffset,v.byteOffset+v.byteLength);});
  assert.ok(Buffer.concat(restored).equals(Buffer.from(positions.buffer)));
  assert.ok(chunks.every(c=>!c.always));
});

test('generated release preserves all original source hashes and shares only existing content-addressed textures',async()=>{
  const report=JSON.parse(await fs.readFile(path.join(root,'docs/evidence/deployment-optimization/asset-generation.json')));
  assert.ok(report.outputs.length>report.sources.length);
  for(const source of report.sources)assert.equal(hash(await fs.readFile(path.join(root,'public',source.file))),source.sha256,source.file);
  const dir=path.join(root,'.tooling/deployment-optimization/runtime-assets');
  for(const asset of report.outputs){
    const bytes=await fs.readFile(path.join(dir,asset.file));assert.equal(hash(bytes),asset.sha256);
    const {json}=parseGlb(bytes);
    for(const image of json.images||[]){if(!image.uri)continue;assert.match(image.uri,/^\/runtime\/[a-f0-9]{20}\/texture\.(png|jpg|webp)$/);assert.equal(hash(await fs.readFile(path.join(dir,image.uri))).slice(0,20),image.uri.split('/')[2]);}
  }
  const skyline=report.outputs.find(a=>a.id==='skyline');assert.ok(skyline.verifiedViews>0);
  const data=await fs.readFile(path.join(root,'public/streets/performance/skyline.glb'));
  const compressed=await compressGlb(data);assert.ok(compressed.bytes.length<data.length);assert.ok(compressed.verifiedViews>0);
});

test('static hosting revalidates manifests, honors cache validators and rejects unavailable paths',async()=>{
  const server=createStaticServer({directory:path.join(root,'dist-release')});
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
  const base=`http://127.0.0.1:${server.address().port}`;
  const service={pid:process.pid,port:server.address().port,ownership:'task-started',startedAt:new Date().toISOString(),status:'RUNNING'};
  try{
    const response=await fetch(base+'/runtime/manifest.json',{headers:{'Accept-Encoding':'identity'}});assert.equal(response.status,200);assert.equal(response.headers.get('cache-control'),'no-cache');
    const etag=response.headers.get('etag'),manifest=await response.json();
    const published=JSON.parse(await fs.readFile(path.join(root,'dist-release/release-manifest.json')));
    assert.equal(etag,`"${published.files.find(f=>f.file==='runtime/manifest.json').sha256}-identity"`);
    assert.equal(manifest.master,undefined,'The release manifest must not reference an unpublished master');
    const unchanged=await fetch(base+'/runtime/manifest.json',{headers:{'If-None-Match':etag,'Accept-Encoding':'identity'}});assert.equal(unchanged.status,304);
    const model=await fetch(base+manifest.chunks[0].file,{method:'HEAD'});assert.equal(model.status,200);assert.match(model.headers.get('cache-control'),/immutable/);assert.equal(model.headers.get('content-type'),'model/gltf-binary');
    assert.equal((await fetch(base+'/scripts/build-release.mjs')).status,404);
    assert.equal((await fetch(base+'/index.html',{method:'POST'})).status,405);
  }finally{
    await new Promise(resolve=>server.close(resolve));service.status='STOPPED';service.finishedAt=new Date().toISOString();
    await fs.writeFile(path.join(root,'docs/evidence/deployment-optimization/http-test-service.json'),JSON.stringify(service,null,2)+'\n');
  }
});
