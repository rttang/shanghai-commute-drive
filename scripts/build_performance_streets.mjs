/** Derive ordinary glTF 2 GLBs; never edits master inputs or embeds new images. */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { MeshoptSimplifier as simplify, MeshoptEncoder as encoder } from 'meshoptimizer';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const OUT = path.join(ROOT, 'public/streets/performance');
const EVIDENCE = path.join(ROOT, 'docs/evidence/tourism/performance-street-assets.json');
const sha = b => crypto.createHash('sha256').update(b).digest('hex');
const components = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4 };
const types = { 5126: Float32Array, 5125: Uint32Array, 5123: Uint16Array, 5121: Uint8Array };
const namesFor = j => j.meshes.map((m, i) => j.nodes.find(n => n.mesh === i)?.name || m.name || `mesh-${i}`);
function assert(ok, message) { if (!ok) throw new Error(message); }
function parse(b) {
  assert(b.readUInt32LE(0) === 0x46546c67 && b.readUInt32LE(4) === 2 && b.readUInt32LE(8) === b.length, 'Invalid GLB header');
  assert(b.readUInt32LE(16) === 0x4e4f534a, 'Missing JSON chunk');
  const n = b.readUInt32LE(12), j = JSON.parse(b.subarray(20, 20 + n));
  assert(b.readUInt32LE(24 + n) === 0x004e4942, 'Missing BIN chunk');
  assert(!j.animations?.length && !j.skins?.length && j.buffers.length === 1, 'Only static single-buffer GLBs supported');
  assert(!j.extensionsRequired?.length, 'Unsupported required extensions in source');
  return { j, bin: b.subarray(28 + n, 28 + n + b.readUInt32LE(20 + n)) };
}
function accessor(src, id) {
  const a = src.j.accessors[id], v = src.j.bufferViews[a.bufferView], C = types[a.componentType], n = components[a.type];
  assert(C && n && !a.sparse && !a.normalized && !v.extensions && (v.buffer ?? 0) === 0, 'Unsupported accessor format');
  const bytes = C.BYTES_PER_ELEMENT, stride = v.byteStride || n * bytes, start = (v.byteOffset || 0) + (a.byteOffset || 0);
  assert(start + Math.max(0, a.count - 1) * stride + n * bytes <= src.bin.length, 'Accessor overflow');
  const packed = Buffer.alloc(a.count * n * bytes);
  for (let i = 0; i < a.count; i++) src.bin.copy(packed, i * n * bytes, start + i * stride, start + i * stride + n * bytes);
  return { array: new C(packed.buffer, packed.byteOffset, a.count * n), n, meta: a };
}
function readPrimitive(src, p) {
  assert((p.mode ?? 4) === 4 && !p.targets && !p.extensions, 'Only plain static triangles supported');
  const attrs = Object.fromEntries(Object.entries(p.attributes).map(([k, id]) => [k, accessor(src, id)]));
  assert(attrs.POSITION.array instanceof Float32Array && attrs.POSITION.n === 3, 'Float32 positions required');
  const count = attrs.POSITION.array.length / 3;
  for (const a of Object.values(attrs)) assert(a.array.length / a.n === count, 'Mismatched vertex counts');
  const indices = p.indices !== undefined ? Uint32Array.from(accessor(src, p.indices).array) : Uint32Array.from({ length: count }, (_, i) => i);
  assert(indices.length % 3 === 0, 'Invalid triangle count');
  for (const i of indices) assert(i < count, 'Index out of range');
  return { attrs, indices };
}
// Exact full-attribute welding preserves hard edges, UV seams and authored normals.
// Numeric hash buckets are checked against every component; hash collisions cannot merge vertices.
function weld(data) {
  const entries = Object.values(data.attrs), count = entries[0].array.length / entries[0].n;
  const bits = entries.map(a => new Uint8Array(a.array.buffer, a.array.byteOffset, a.array.byteLength));
  const sizes = entries.map(a => a.n * a.array.BYTES_PER_ELEMENT);
  const table = new Map(), remap = new Uint32Array(count), originals = [];
  for (let i = 0; i < count; i++) {
    let h = 2166136261;
    for (let k = 0; k < bits.length; k++) for (let q = 0; q < sizes[k]; q++) h = Math.imul(h ^ bits[k][i * sizes[k] + q], 16777619);
    let bucket = table.get(h), found = -1;
    if (bucket) outer: for (const prior of bucket) {
      for (let k = 0; k < entries.length; k++) {
        const a = entries[k];
        for (let q = 0; q < a.n; q++) if (a.array[i * a.n + q] !== a.array[prior * a.n + q]) continue outer;
      }
      found = remap[prior]; break;
    }
    if (found < 0) {
      found = originals.length; originals.push(i);
      if (bucket) bucket.push(i); else table.set(h, [i]);
    }
    remap[i] = found;
  }
  const attrs = {};
  for (const [name, a] of Object.entries(data.attrs)) {
    const array = new a.array.constructor(originals.length * a.n);
    for (let i = 0; i < originals.length; i++) array.set(a.array.subarray(originals[i] * a.n, (originals[i] + 1) * a.n), i * a.n);
    attrs[name] = { ...a, array };
  }
  return { attrs, indices: data.indices.map(i => remap[i]), sourceVertices: count, weldedVertices: originals.length };
}
function policy(chunk, name) {
  if (chunk === 'context') {
    // Whole driving surfaces, tunnel shells, lights and safety markers remain geometrically exact.
    if (!/context-(curb|tunnel-rib|tunnel-joint|roof|lowrise|modern|heritage)$/.test(name)) return { error: 0, ratio: 1, flags: [] };
    return { error: /curb|tunnel/.test(name) ? 0.015 : 0.03, ratio: 0.25, flags: ['ErrorAbsolute', 'LockBorder'] };
  }
  // Materials, apertures and all disconnected components are retained; no Prune or sloppy decimation.
  if (/photo-|entrance|nameplate|limestone|roof-waterproof|waterproof-roof|plaza|hedge|flower/.test(name)) return { error: 0, ratio: 1, flags: [] };
  return { error: 0.06, ratio: 0.25, flags: ['ErrorAbsolute', 'LockBorder'] };
}
function reduce(data, p) {
  const positions = data.attrs.POSITION.array;
  if (p.error === 0 || data.indices.length <= 36) return { ...data, error: 0, policy: p };
  const extras = Object.entries(data.attrs).filter(([k]) => k !== 'POSITION');
  assert(extras.every(([, a]) => a.array instanceof Float32Array), 'Non-float attributes not supported by simplification');
  const stride = extras.reduce((n, [, a]) => n + a.n, 0), att = new Float32Array(positions.length / 3 * stride), weights = [];
  let offset = 0;
  for (const [name, a] of extras) {
    weights.push(...Array(a.n).fill(name === 'NORMAL' ? (p.normalWeight ?? 1) : (p.uvWeight ?? 2)));
    for (let i = 0; i < positions.length / 3; i++) att.set(a.array.subarray(i * a.n, (i + 1) * a.n), i * stride + offset);
    offset += a.n;
  }
  const target = Math.max(12, Math.floor(data.indices.length * p.ratio / 3) * 3);
  const locks = new Uint8Array(positions.length / 3);
  for (let i = 0; i < data.indices.length; i += 3) {
    const t = data.indices.subarray(i, i + 3);
    if (t.some(v => positions[v * 3 + 1] <= 4)) for (const v of t) locks[v] = 1;
  }
  p = { ...p, protectedLocalHeightM: 4 };
  const [indices, error] = simplify.simplifyWithAttributes(data.indices, positions, 3, att, stride, weights, locks, target, p.error, p.flags);
  assert(indices.length > 0 && indices.length <= data.indices.length && error <= p.error + 1e-6, 'Simplification violated count/error bound');
  return { ...data, indices, error, policy: p };
}
function bounds(a) {
  const min = Array(a.n).fill(Infinity), max = Array(a.n).fill(-Infinity);
  for (let i = 0; i < a.array.length; i++) { const v = a.array[i]; assert(Number.isFinite(v), 'Non-finite attribute'); min[i % a.n] = Math.min(min[i % a.n], v); max[i % a.n] = Math.max(max[i % a.n], v); }
  return { min, max };
}
function compact(data) {
  const indices = data.indices.slice();
  const [remap, count] = encoder.reorderMesh(indices, true, false), attrs = {};
  for (const [name, a] of Object.entries(data.attrs)) {
    const array = new a.array.constructor(count * a.n);
    for (let i = 0; i < remap.length; i++) if (remap[i] !== 0xffffffff) array.set(a.array.subarray(i * a.n, (i + 1) * a.n), remap[i] * a.n);
    attrs[name] = { ...a, array };
  }
  return { ...data, indices: count <= 65535 ? Uint16Array.from(indices) : indices, attrs };
}
function pack(j, bins) {
  const bin = Buffer.concat(bins); j.buffers = [{ byteLength: bin.length }];
  const str = Buffer.from(JSON.stringify(j)); const json = Buffer.alloc((str.length + 3) & ~3, 32); str.copy(json);
  const head = Buffer.alloc(20); head.writeUInt32LE(0x46546c67, 0); head.writeUInt32LE(2, 4); head.writeUInt32LE(28 + json.length + bin.length, 8); head.writeUInt32LE(json.length, 12); head.writeUInt32LE(0x4e4f534a, 16);
  const bh = Buffer.alloc(8); bh.writeUInt32LE(bin.length); bh.writeUInt32LE(0x004e4942, 4);
  return Buffer.concat([head, json, bh, bin]);
}
function loadChunk(id) {
  const master = JSON.parse(fs.readFileSync(path.join(ROOT, 'public/streets/master/manifest.json')));
  const entry = master.chunks.find(c => c.id === id); assert(entry, `Missing ${id}`);
  const sourcePath = path.join(ROOT, 'public', entry.file), bytes = fs.readFileSync(sourcePath), sourceSha256 = sha(bytes);
  assert(sourceSha256 === entry.sha256 && bytes.length === entry.bytes, `Source ${id} differs from frozen master manifest`);
  const src = parse(bytes), names = namesFor(src.j);
  for (const n of src.j.nodes) {
    assert(!n.matrix && (n.translation?.[1] ?? 0) >= 0 && (n.scale || [1, 1, 1]).every(v => Math.abs(v - 1) < 1e-6), 'Near-ground locks require nonnegative vertical translation and unit scale');
    const r = n.rotation || [0, 0, 0, 1];
    assert((Math.abs(r[0]) < 1e-6 && Math.abs(r[2]) < 1e-6) || (n.mesh !== undefined && !n.children?.length && policy(id, names[n.mesh]).error === 0), 'Tilted geometry must remain exact');
  }
  return { id, entry, sourcePath, sourceSha256, sourceBytes: bytes.length, src };
}
function writeJson(file, data) { fs.mkdirSync(OUT, { recursive: true }); fs.writeFileSync(path.join(OUT, file), JSON.stringify(data, null, 2) + '\n'); }
function saveManifest(manifest) {
  fs.mkdirSync(path.dirname(EVIDENCE), { recursive: true });
  fs.writeFileSync(EVIDENCE, JSON.stringify(manifest, null, 2) + '\n');
  writeJson('manifest.json', { version: manifest.version, generator: manifest.generator, variants: manifest.variants });
}
async function probe() {
  const candidates = { context: ['context-tunnel-rib', 'context-curb', 'context-lowrise'], skyline: ['shanghai-tower-pd-aluminium-satin', 'pearl-pearl-rose-glass', 'financial-center-pd-aluminium-satin'] };
  const report = { generator: 'scripts/build_performance_streets.mjs --probe', generated: new Date().toISOString(), primitives: [] };
  for (const id of ['context', 'skyline']) {
    const chunk = loadChunk(id), names = namesFor(chunk.src.j);
    for (const name of candidates[id]) {
      const mi = names.indexOf(name); assert(mi >= 0, `Probe primitive missing: ${name}`);
      const data = weld(readPrimitive(chunk.src, chunk.src.j.meshes[mi].primitives[0]));
      for (const variant of ['strict', 'permissive', 'seam-tolerant', 'detail-normals']) {
        const p = policy(id, name);
        if (variant !== 'strict') p.flags = [...p.flags, 'Permissive'];
        if (['seam-tolerant', 'detail-normals'].includes(variant)) p.flags = p.flags.filter(f => f !== 'LockBorder');
        if (variant === 'detail-normals') { p.normalWeight = 0.01; p.uvWeight = 0.01; }
        const r = reduce(data, p);
        const row = { chunk: id, name, variant, sourceSha256: chunk.sourceSha256, sourceTriangles: data.indices.length / 3, sourceVertices: data.sourceVertices, weldedVertices: data.weldedVertices, outputTriangles: r.indices.length / 3, retainedRatio: r.indices.length / data.indices.length, estimatedAbsoluteErrorM: r.error, policy: p };
        report.primitives.push(row); console.log(JSON.stringify(row));
      }
    }
  }
  if (fs.existsSync(path.join(OUT, 'candidate-probe.json'))) fs.copyFileSync(path.join(OUT, 'candidate-probe.json'), path.join(OUT, `candidate-probe-${Date.now()}.previous.json`));
  writeJson('candidate-probe.json', report);
}
async function build(repairGround = false) {
  assert(fs.existsSync(path.join(OUT, 'candidate-probe.json')), 'Run --probe and inspect feasibility first');
  const previous = repairGround ? JSON.parse(fs.readFileSync(fs.existsSync(EVIDENCE) ? EVIDENCE : path.join(OUT, 'manifest.json'))) : null;
  const manifest = { version: 1, generated: new Date().toISOString(), generator: 'scripts/build_performance_streets.mjs', meshoptimizerVersion: '1.1.1', method: 'Exact attribute welding; quadric meshoptimizer simplifyWithAttributes; estimated absolute error in metres; topology borders and attribute seams preserved; no component pruning; vertex cache reorder and compact indexed buffers.', errorMeaning: 'Meshoptimizer quadric appearance error is an estimate, not a measured Hausdorff bound. Output uses a subset of original vertices with their exact attributes. Per-primitive AABB movement is checked against the same cap. Driving surfaces and protected materials use zero geometric simplification.', sourceFilesPreserved: true, ordinaryGlbNoNewDecoder: true, imageBytesPreserved: true, browserAcceptance: 'pending-root', variants: [], chunks: [] };
  for (const id of ['context', 'skyline']) {
    const chunk = loadChunk(id), { src } = chunk, j = structuredClone(src.j), names = namesFor(src.j);
    const previousChunk = previous?.chunks.find(c => c.id === id);
    const previousSrc = previousChunk ? parse(fs.readFileSync(path.join(ROOT, 'public', previousChunk.file))) : null;
    j.bufferViews = []; j.accessors = []; const bins = []; let byteOffset = 0;
    function addView(buf, target) {
      const b = Buffer.from(buf.buffer, buf.byteOffset, buf.byteLength); const ix = j.bufferViews.length;
      j.bufferViews.push({ buffer: 0, byteOffset, byteLength: b.length, ...(target ? { target } : {}) }); bins.push(b); byteOffset += b.length;
      const pad = (4 - byteOffset % 4) % 4; if (pad) { bins.push(Buffer.alloc(pad)); byteOffset += pad; } return ix;
    }
    function addAccessor(a, isIndex = false) {
      const C = a.array.constructor; const ct = C === Float32Array ? 5126 : C === Uint32Array ? 5125 : C === Uint16Array ? 5123 : 5121;
      const next = { bufferView: addView(a.array, isIndex ? 34963 : 34962), componentType: ct, count: a.array.length / a.n, type: Object.entries(components).find(([, n]) => n === a.n)[0] };
      if (!isIndex) Object.assign(next, bounds(a)); const ai = j.accessors.length; j.accessors.push(next); return ai;
    }
    let before = 0, after = 0, maximumError = 0; const primitives = [];
    for (let mi = 0; mi < src.j.meshes.length; mi++) {
      for (let pi = 0; pi < src.j.meshes[mi].primitives.length; pi++) {
        const sourcePrimitive = src.j.meshes[mi].primitives[pi], original = readPrimitive(src, sourcePrimitive);
        const previousRow = previousChunk?.primitives.find(p => p.mesh === mi && p.primitive === pi);
        const needsGroundRepair = previousRow && previousRow.sourceTriangles !== previousRow.triangles && bounds(original.attrs.POSITION).min[1] <= 4;
        const data = previousRow && !needsGroundRepair ? { ...readPrimitive(previousSrc, previousSrc.j.meshes[mi].primitives[pi]), sourceVertices: previousRow.sourceVertices } : weld(original);
        const reduced = previousRow && !needsGroundRepair ? { ...data, error: previousRow.estimatedAbsoluteErrorM, policy: previousRow.policy } : reduce(data, policy(id, names[mi]));
        const result = compact(reduced);
        const oldBound = bounds(original.attrs.POSITION), newBound = bounds(result.attrs.POSITION), boundsDeltaM = Math.max(...oldBound.min.map((v, k) => Math.abs(v - newBound.min[k])), ...oldBound.max.map((v, k) => Math.abs(v - newBound.max[k])));
        // An error estimate alone is insufficient to protect long silhouettes; also preserve each primitive AABB within the same cap.
        const accepted = boundsDeltaM <= reduced.policy.error + 0.00001 ? result : compact({ ...data, error: 0, policy: { ...reduced.policy, rejectedByBounds: true } });
        const row = { name: names[mi], mesh: mi, primitive: pi, sourceTriangles: original.indices.length / 3, triangles: accepted.indices.length / 3, sourceVertices: data.sourceVertices, vertices: accepted.attrs.POSITION.array.length / 3, estimatedAbsoluteErrorM: accepted.error, boundsDeltaM: boundsDeltaM <= reduced.policy.error + 0.00001 ? boundsDeltaM : 0, policy: accepted.policy };
        before += row.sourceTriangles; after += row.triangles; maximumError = Math.max(maximumError, row.estimatedAbsoluteErrorM); primitives.push(row);
        const outPrimitive = j.meshes[mi].primitives[pi]; outPrimitive.attributes = Object.fromEntries(Object.entries(accepted.attrs).map(([k, a]) => [k, addAccessor(a)])); outPrimitive.indices = addAccessor({ array: accepted.indices, n: 1 }, true);
        if (mi % 20 === 0) console.log(JSON.stringify({ chunk: id, mesh: mi, name: names[mi], triangles: row.triangles, sourceTriangles: row.sourceTriangles }));
      }
    }
    const imageHashes = [];
    for (let i = 0; i < (j.images?.length || 0); i++) {
      const image = src.j.images[i]; assert(image.bufferView !== undefined && !image.uri, 'Only embedded source images supported'); const v = src.j.bufferViews[image.bufferView]; const bytes = src.bin.subarray(v.byteOffset || 0, (v.byteOffset || 0) + v.byteLength);
      j.images[i].bufferView = addView(bytes); imageHashes.push({ name: image.name, bytes: bytes.length, sha256: sha(bytes) });
    }
    j.asset.extras = { ...(j.asset.extras || {}), performanceDerivative: { sourceFile: chunk.entry.file, sourceSha256: chunk.sourceSha256, maxEstimatedErrorM: maximumError, noComponentPruning: true } };
    assert(JSON.stringify(j.materials) === JSON.stringify(src.j.materials) && JSON.stringify(j.nodes) === JSON.stringify(src.j.nodes), 'Materials/nodes changed');
    const glb = pack(j, bins); const readback = parse(glb); let verifiedTriangles = 0;
    for (const mesh of readback.j.meshes) for (const primitive of mesh.primitives) verifiedTriangles += readPrimitive(readback, primitive).indices.length / 3;
    assert(verifiedTriangles === after && before === chunk.entry.triangles, 'Triangle readback/source manifest mismatch');
    assert(sha(fs.readFileSync(chunk.sourcePath)) === chunk.sourceSha256, 'Source changed while building');
    const file = `/streets/performance/${id}.glb`; fs.mkdirSync(OUT, { recursive: true });
    const finalPath = path.join(ROOT, 'public', file), tempPath = finalPath + '.tmp';
    fs.writeFileSync(tempPath, glb); assert(sha(fs.readFileSync(tempPath)) === sha(glb), 'Disk write SHA mismatch');
    if (fs.existsSync(finalPath)) fs.renameSync(finalPath, finalPath + '.' + Date.now() + '.previous'); fs.renameSync(tempPath, finalPath);
    manifest.variants.push({ id, file, bytes: glb.length, triangles: after, sha256: sha(glb), sourceFile: chunk.entry.file, sourceSha256: chunk.sourceSha256, sourceBytes: chunk.sourceBytes, sourceTriangles: before });
    manifest.chunks.push({ ...chunk.entry, file, bytes: glb.length, triangles: after, sha256: sha(glb), sourceFile: chunk.entry.file, sourceSha256: chunk.sourceSha256, sourceBytes: chunk.sourceBytes, sourceTriangles: before, byteReductionRatio: 1 - glb.length / chunk.sourceBytes, triangleReductionRatio: 1 - after / before, maxEstimatedAbsoluteErrorM: maximumError, materialsPreserved: j.materials.length, nodesPreserved: j.nodes.length, images: imageHashes, primitives });
    saveManifest(manifest); console.log(JSON.stringify({ complete: id, sourceBytes: chunk.sourceBytes, bytes: glb.length, sourceTriangles: before, triangles: after, maxEstimatedAbsoluteErrorM: maximumError }));
  }
}
function topologyDigest(data) {
  const attrs = Object.entries(data.attrs).sort(([a], [b]) => a.localeCompare(b)).map(([, a]) => a);
  const count = data.attrs.POSITION.array.length / 3, vertexHash = new Array(count);
  for (const i of data.indices) {
    if (vertexHash[i] !== undefined) continue;
    const h = crypto.createHash('sha256');
    for (const a of attrs) h.update(Buffer.from(a.array.buffer, a.array.byteOffset + i * a.n * a.array.BYTES_PER_ELEMENT, a.n * a.array.BYTES_PER_ELEMENT));
    vertexHash[i] = h.digest('hex');
  }
  const triangles = [];
  for (let i = 0; i < data.indices.length; i += 3) {
    const t = [vertexHash[data.indices[i]], vertexHash[data.indices[i + 1]], vertexHash[data.indices[i + 2]]];
    // Cyclic rotation keeps winding; sorting the complete triangle list ignores only draw order.
    const cycle = [t.join(''), [t[1], t[2], t[0]].join(''), [t[2], t[0], t[1]].join('')].sort()[0];
    triangles.push(sha(Buffer.from(cycle)));
  }
  return sha(Buffer.from(triangles.sort().join('')));
}
async function verify() {
  const manifest = JSON.parse(fs.readFileSync(EVIDENCE));
  assert(manifest.variants.length === 2 && manifest.chunks.length === 2, 'Both derivatives required');
  const report = { generated: new Date().toISOString(), sourcePreserved: true, materialsNodesAndImageBytesPreserved: true, finiteAttributesAndInRangeIndices: true, exactProtectedSurfaceTopology: true, noRenderPerformed: true, browserAcceptance: 'pending-root', chunks: [] };
  for (const c of manifest.chunks) {
    const source = loadChunk(c.id), bytes = fs.readFileSync(path.join(ROOT, 'public', c.file)), result = parse(bytes);
    assert(sha(bytes) === c.sha256 && bytes.length === c.bytes && source.sourceSha256 === c.sourceSha256, 'Derivative/source SHA or byte mismatch');
    const a = source.src, b = result;
    for (const key of ['nodes', 'materials', 'textures', 'samplers', 'scenes']) assert(JSON.stringify(a.j[key]) === JSON.stringify(b.j[key]), `Changed ${key}`);
    assert(a.j.meshes.length === b.j.meshes.length && a.j.images.length === b.j.images.length, 'Mesh or image removed');
    for (let i = 0; i < a.j.images.length; i++) {
      const imageBytes = s => { const v = s.j.bufferViews[s.j.images[i].bufferView]; return s.bin.subarray(v.byteOffset || 0, (v.byteOffset || 0) + v.byteLength); };
      assert(imageBytes(a).equals(imageBytes(b)), 'Source image bytes changed');
    }
    let tris = 0, protectedTriangles = 0, nearGroundTriangles = 0, geometryBytes = 0, sourceGeometryBytes = 0, maxBoundsDeltaM = 0;
    for (const row of c.primitives) {
      const sp = a.j.meshes[row.mesh].primitives[row.primitive], dp = b.j.meshes[row.mesh].primitives[row.primitive];
      assert(sp.material === dp.material, 'Material assignment changed');
      const original = readPrimitive(a, sp), derived = readPrimitive(b, dp);
      assert(JSON.stringify(Object.keys(original.attrs).sort()) === JSON.stringify(Object.keys(derived.attrs).sort()), 'Attribute removed');
      for (const attr of Object.values(derived.attrs)) bounds(attr);
      const beforeBounds = bounds(original.attrs.POSITION), afterBounds = bounds(derived.attrs.POSITION);
      const delta = Math.max(...beforeBounds.min.map((v, k) => Math.abs(v - afterBounds.min[k])), ...beforeBounds.max.map((v, k) => Math.abs(v - afterBounds.max[k])));
      assert(delta <= row.policy.error + 0.00001, 'Primitive silhouette AABB moved beyond cap'); maxBoundsDeltaM = Math.max(maxBoundsDeltaM, delta);
      assert(derived.indices.length / 3 === row.triangles, 'Primitive triangle mismatch'); tris += row.triangles;
      if (row.policy.error === 0) { assert(topologyDigest(original) === topologyDigest(derived), 'Protected surface topology or vertex attributes changed'); protectedTriangles += row.triangles; }
      const nearGround = data => {
        const selected = [], pos = data.attrs.POSITION.array;
        for (let i = 0; i < data.indices.length; i += 3) {
          const t = data.indices.subarray(i, i + 3);
          if (t.some(v => pos[v * 3 + 1] <= 4)) selected.push(...t);
        }
        return { ...data, indices: Uint32Array.from(selected) };
      };
      if (row.policy.error > 0) {
        const lo = nearGround(original), ld = nearGround(derived);
        assert(topologyDigest(lo) === topologyDigest(ld), `Near-ground topology changed: ${row.name}`);
        nearGroundTriangles += lo.indices.length / 3;
      }
      geometryBytes += Object.values(derived.attrs).reduce((n, x) => n + x.array.byteLength, 0) + b.j.accessors[dp.indices].count * types[b.j.accessors[dp.indices].componentType].BYTES_PER_ELEMENT;
      sourceGeometryBytes += Object.values(original.attrs).reduce((n, x) => n + x.array.byteLength, 0) + (sp.indices === undefined ? 0 : a.j.accessors[sp.indices].count * types[a.j.accessors[sp.indices].componentType].BYTES_PER_ELEMENT);
    }
    assert(tris === c.triangles, 'Chunk triangle mismatch');
    report.chunks.push({ id: c.id, sha256: c.sha256, triangles: tris, protectedTrianglesVerifiedExactly: protectedTriangles, additionalNearGroundTrianglesVerifiedExactly: nearGroundTriangles, sourceGeometryBufferBytes: sourceGeometryBytes, geometryBufferBytes: geometryBytes, maxPrimitiveBoundsDeltaM: maxBoundsDeltaM, meshesRetained: b.j.meshes.length, nodesRetained: b.j.nodes.length, materialsRetained: b.j.materials.length });
  }
  report.passed = true; writeJson('validation.json', report);
  manifest.validation = report; manifest.generatorSha256 = sha(fs.readFileSync(fileURLToPath(import.meta.url)));
  manifest.nearGroundPolicy = 'Every original triangle touching local Y <= 4m has all three vertices locked. Exact original positions/normals/UVs and winding of protected and near-ground triangles are independently compared after disk readback. Source transforms are gated to keep this conservative in world coordinates; tilted nameplates remain exact.';
  saveManifest(manifest); console.log(JSON.stringify(report));
}
await simplify.ready; await encoder.ready;
if (process.argv.includes('--probe')) await probe();
else if (process.argv.includes('--build')) await build();
else if (process.argv.includes('--protect-ground')) await build(true);
else if (process.argv.includes('--verify')) await verify();
else throw new Error('Usage: node scripts/build_performance_streets.mjs --probe | --build | --verify');
