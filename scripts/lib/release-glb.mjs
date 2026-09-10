import assert from 'node:assert/strict';
import { MeshoptEncoder } from 'meshoptimizer/encoder';
import { MeshoptDecoder } from 'meshoptimizer/decoder';

export function parseGlb(bytes) {
  assert.equal(bytes.readUInt32LE(0), 0x46546c67);
  assert.equal(bytes.readUInt32LE(4), 2);
  assert.equal(bytes.readUInt32LE(8), bytes.length);
  assert.equal(bytes.readUInt32LE(16), 0x4e4f534a);
  const length = bytes.readUInt32LE(12);
  const json = JSON.parse(bytes.subarray(20, 20 + length));
  assert.equal(bytes.readUInt32LE(24 + length), 0x004e4942);
  return { json, bin: bytes.subarray(28 + length, 28 + length + bytes.readUInt32LE(20 + length)) };
}
export function packGlb(json, bin) {
  const text = Buffer.from(JSON.stringify(json));
  const j = Buffer.alloc((text.length + 3) & ~3, 32); text.copy(j);
  const b = Buffer.alloc((bin.length + 3) & ~3); bin.copy(b);
  const header = Buffer.alloc(20), bh = Buffer.alloc(8);
  header.writeUInt32LE(0x46546c67); header.writeUInt32LE(2, 4); header.writeUInt32LE(28 + j.length + b.length, 8);
  header.writeUInt32LE(j.length, 12); header.writeUInt32LE(0x4e4f534a, 16);
  bh.writeUInt32LE(b.length); bh.writeUInt32LE(0x004e4942, 4);
  return Buffer.concat([header, j, bh, b]);
}

/** Lossless buffer compression. No quantization, geometry reduction or image re-encoding.
 * Decode every encoded view and byte-compare before accepting the result.
 */
export async function compressGlb(bytes) {
  await Promise.all([MeshoptEncoder.ready, MeshoptDecoder.ready]);
  const { json: source, bin } = parseGlb(bytes);
  if (source.extensionsUsed?.some(e => e === 'KHR_draco_mesh_compression' || e.includes('meshopt'))) return { bytes, verifiedViews: 0 };
  assert.equal(source.buffers.length, 1);
  assert.ok(!source.buffers[0].uri);
  const json = structuredClone(source), parts = [];
  let offset = 0, fallback = 0, verifiedViews = 0;
  const dimensions = { SCALAR:1, VEC2:2, VEC3:3, VEC4:4, MAT4:16 };
  const sizes = { 5120:1, 5121:1, 5122:2, 5123:2, 5125:4, 5126:4 };
  const indices = new Set(source.meshes.flatMap(m => m.primitives.map(p => p.indices)).filter(i => i !== undefined));
  const add = data => { const start = offset; const b = Buffer.from(data); parts.push(b); offset += b.length; const pad = (4-offset%4)%4; if(pad){parts.push(Buffer.alloc(pad));offset+=pad;} return start; };
  for (let i = 0; i < source.bufferViews.length; i++) {
    const view = source.bufferViews[i];
    assert.equal(view.buffer ?? 0, 0);
    const raw = bin.subarray(view.byteOffset || 0, (view.byteOffset || 0) + view.byteLength);
    assert.equal(raw.length, view.byteLength);
    const ai = source.accessors.findIndex(a => a.bufferView === i);
    const a = source.accessors[ai];
    const stride = view.byteStride || (a && dimensions[a.type] * sizes[a.componentType]);
    const mode = indices.has(ai) ? 'INDICES' : 'ATTRIBUTES';
    const valid = a && !a.sparse && !view.extensions && stride && raw.length % stride === 0 && (mode === 'INDICES' ? [2,4].includes(stride) : stride % 4 === 0 && stride <= 256);
    if (!valid) { json.bufferViews[i] = {...view, buffer:0, byteOffset:add(raw)}; continue; }
    const count = raw.length / stride;
    const encoded = MeshoptEncoder.encodeGltfBuffer(raw, count, stride, mode);
    const decoded = Buffer.alloc(raw.length);
    MeshoptDecoder.decodeGltfBuffer(decoded, count, stride, encoded, mode);
    assert.ok(decoded.equals(raw), `Lossless decode mismatch at view ${i}`);
    verifiedViews++;
    if (encoded.length >= raw.length) { json.bufferViews[i] = {...view,buffer:0,byteOffset:add(raw)}; continue; }
    json.bufferViews[i] = {...view,buffer:1,byteOffset:fallback,extensions:{EXT_meshopt_compression:{buffer:0,byteOffset:add(encoded),byteLength:encoded.length,byteStride:stride,count,mode}}};
    fallback += (raw.length + 3) & ~3;
  }
  json.buffers = [{byteLength:offset}];
  if (fallback) {
    json.buffers.push({byteLength:fallback,extensions:{EXT_meshopt_compression:{fallback:true}}});
    json.extensionsUsed = [...new Set([...(json.extensionsUsed || []),'EXT_meshopt_compression'])];
    json.extensionsRequired = [...new Set([...(json.extensionsRequired || []),'EXT_meshopt_compression'])];
  }
  const result = packGlb(json, Buffer.concat(parts));
  assert.deepEqual(json.nodes, source.nodes); assert.deepEqual(json.materials, source.materials);
  return { bytes: result.length < bytes.length ? result : bytes, verifiedViews };
}
