import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
const root=path.resolve(import.meta.dirname,'..'),base=process.argv[2];
assert.ok(base?.startsWith('https://'));
const index=JSON.parse(await fs.readFile(path.join(root,'release/sites/source/asset-index.json'),'utf8'));
const entries=Object.entries(index);
const result={url:base,startedAt:new Date().toISOString(),checks:[],files:[],errors:[]};
let cursor=0;
async function runner(){
 for(;;){
  const position=cursor++;if(position>=entries.length)return;
  const [pathname,entry]=entries[position];
  try{
   const response=await fetch(new URL(pathname,base),{headers:{'Accept-Encoding':'gzip'},signal:AbortSignal.timeout(180000)});
   assert.equal(response.status,200,pathname);
   assert.equal(response.headers.get('Content-Encoding'),entry.gzip?'gzip':null,pathname);
   const digest=createHash('sha256');let bytes=0;
   for await(const chunk of response.body){digest.update(chunk);bytes+=chunk.length;}
   assert.equal(digest.digest('hex'),entry.hash,pathname);assert.equal(bytes,entry.bytes);
   const immutable=/^\/runtime\/[a-f0-9]{16,}\//.test(pathname)||/^\/assets\/[^/]+-[\w-]{8,}\./.test(pathname);
   assert.equal(response.headers.get('Cache-Control'),immutable?'public, max-age=31536000, immutable, no-transform':'no-cache, no-transform');
   result.files.push({pathname,bytes,encoding:response.headers.get('Content-Encoding'),contentLength:response.headers.get('Content-Length'),etag:response.headers.get('ETag'),cacheControl:response.headers.get('Cache-Control')});
   if(result.files.length%25===0)console.log('RESOURCES',result.files.length,'/',entries.length);
  }catch(error){result.errors.push({pathname,error:String(error)});}
 }
}
await Promise.all(Array.from({length:4},runner));
try{
 const skyline='/runtime/c9f6717e4baa557a223b/skyline.glb';
 const head=await fetch(new URL(skyline,base),{method:'HEAD',headers:{'Accept-Encoding':'gzip'}});assert.equal(head.status,200);
 const cached=await fetch(new URL(skyline,base),{headers:{'Accept-Encoding':'gzip','If-None-Match':head.headers.get('ETag')}});assert.equal(cached.status,304);
 const plain=await fetch(new URL('/runtime/manifest.json',base),{headers:{'Accept-Encoding':'identity'}});assert.equal(plain.headers.get('Content-Encoding'),null);
 assert.equal(createHash('sha256').update(Buffer.from(await plain.arrayBuffer())).digest('hex'),index['/runtime/manifest.json'].hash);
 const missing=await fetch(new URL('/asset-that-does-not-exist.glb',base));assert.equal(missing.status,404);
 result.checks.push('gzip decoded SHA-256 matches every release asset','ETag 304','identity response','404 missing resource');
}catch(error){result.errors.push({error:String(error)});}
result.finishedAt=new Date().toISOString();result.passed=result.errors.length===0&&result.files.length===entries.length;
await fs.writeFile(path.join(root,'docs/evidence/deployment-optimization/sites-resources.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({passed:result.passed,files:result.files.length,errors:result.errors}));if(!result.passed)process.exitCode=1;
