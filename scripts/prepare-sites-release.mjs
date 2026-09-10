import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { gzipSync, gunzipSync } from 'node:zlib';
import assert from 'node:assert/strict';
const root = path.resolve(import.meta.dirname, '..');
const input = path.join(root, 'dist-release');
const output = path.join(root, 'release/sites/source');
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const manifestBytes = await fs.readFile(path.join(input, 'release-manifest.json'));
const manifest = JSON.parse(manifestBytes);
const index = {};
const evidence = {sourceManifestSha256:sha(manifestBytes),partLimitBytes:8*1024*1024,files:[],storedBytes:0,parts:0};
for (const entry of manifest.files) {
  const original = await fs.readFile(path.join(input, entry.file));
  assert.equal(sha(original), entry.sha256, `Release changed: ${entry.file}`);
  let encoded;
  try { encoded = await fs.readFile(path.join(input, entry.file+'.gz')); }
  catch (error) { if(error.code!=='ENOENT') throw error; encoded=gzipSync(original,{level:9}); }
  assert.deepEqual(gunzipSync(encoded), original, `Gzip mismatch: ${entry.file}`);
  const gzip = encoded.length < original.length;
  const stored = gzip ? encoded : original;
  const hash = sha(stored);
  const parts = [];
  for (let start=0;start<stored.length;start+=evidence.partLimitBytes) {
    const part=stored.subarray(start,start+evidence.partLimitBytes);
    const relative=`/_delivery/${hash}/${parts.length}.bin`;
    const file=path.join(output,'assets',relative);
    await fs.mkdir(path.dirname(file),{recursive:true});
    await fs.writeFile(file,part);
    assert.equal(sha(await fs.readFile(file)),sha(part));
    parts.push(relative);evidence.parts++;evidence.storedBytes+=part.length;
  }
  index['/'+entry.file]={hash:entry.sha256,bytes:original.length,encodedBytes:stored.length,gzip,parts};
  evidence.files.push({file:entry.file,sha256:entry.sha256,bytes:original.length,storedSha256:hash,storedBytes:stored.length,gzip,parts:parts.length});
}
await fs.writeFile(path.join(output,'asset-index.json'),JSON.stringify(index)+'\n');
await fs.writeFile(path.join(root,'docs/evidence/deployment-optimization/sites-preparation.json'),JSON.stringify(evidence,null,2)+'\n');
console.log(JSON.stringify({files:evidence.files.length,parts:evidence.parts,bytes:evidence.storedBytes,partLimitBytes:evidence.partLimitBytes,sourceManifestSha256:evidence.sourceManifestSha256}));
