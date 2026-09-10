/** CPU-only collision extraction from the same GLB node transforms as the street
 * assembler. A cell is occupied only if a real triangle intersects the vehicle
 * height slab and that cell. No building hull, mesh AABB or hole filling. */
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { Matrix4, Vector3, Quaternion } from 'three';

export const MODEL_COLLISION_POLICY = Object.freeze({
  cellMetres: .2, minY: .2501, maxY: 1.6499, assemblyY: .12,
  existingWallHalfThickness: .05,
  maximumHorizontalOverreachMetres: Math.SQRT2 * .2,
});
export const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');

export function convexHull(points) {
  const ordered = [...new Map(points.map(p => [p.map(v => v.toFixed(7)).join(','), p])).values()].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  if (ordered.length < 3) return ordered;
  const cross = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  const lower = [], upper = [];
  for (const p of ordered) { while (lower.length > 1 && cross(lower.at(-2), lower.at(-1), p) <= 1e-10) lower.pop(); lower.push(p); }
  for (const p of ordered.reverse()) { while (upper.length > 1 && cross(upper.at(-2), upper.at(-1), p) <= 1e-10) upper.pop(); upper.push(p); }
  lower.pop(); upper.pop(); return [...lower, ...upper];
}
let dracoPromise;
async function dracoModule(root) {
  if (!dracoPromise) {
    const dir = path.join(root, 'node_modules/three/examples/jsm/libs/draco/gltf');
    const sandbox = { module: { exports: {} }, exports: {}, console, TextDecoder,
      setTimeout, clearTimeout, WebAssembly };
    vm.runInNewContext(fs.readFileSync(path.join(dir, 'draco_wasm_wrapper.js'), 'utf8'), sandbox);
    dracoPromise = sandbox.module.exports({ wasmBinary: fs.readFileSync(path.join(dir, 'draco_decoder.wasm')) });
  }
  return dracoPromise;
}

export function parseGlb(raw) {
  if (raw.readUInt32LE(0) !== 0x46546c67 || raw.readUInt32LE(4) !== 2 || raw.readUInt32LE(8) !== raw.length)
    throw new Error('Invalid or partially written GLB');
  let doc, binary;
  for (let offset = 12; offset < raw.length;) {
    const length = raw.readUInt32LE(offset), type = raw.readUInt32LE(offset + 4);
    const bytes = raw.subarray(offset + 8, offset + 8 + length);
    if (bytes.length !== length) throw new Error('Truncated GLB chunk');
    if (type === 0x4e4f534a) doc = JSON.parse(bytes.toString('utf8'));
    if (type === 0x004e4942) binary = bytes;
    offset += 8 + length;
  }
  if (!doc || !binary) throw new Error('GLB needs JSON and binary chunks');
  if (doc.animations?.length || doc.skins?.length) throw new Error('Animated architecture is unsupported');
  return { doc, binary };
}

function accessor(doc, binary, id) {
  const a = doc.accessors[id], view = doc.bufferViews[a.bufferView];
  const sizes = { SCALAR: 1, VEC3: 3 }, formats = {
    5126: [4, 'readFloatLE'], 5125: [4, 'readUInt32LE'],
    5123: [2, 'readUInt16LE'], 5121: [1, 'readUInt8'],
  };
  if (!view || a.sparse || a.normalized || !sizes[a.type] || !formats[a.componentType])
    throw new Error(`Unsupported geometry accessor ${id}`);
  const [bytes, read] = formats[a.componentType], size = sizes[a.type];
  const result = new Float64Array(a.count * size), stride = view.byteStride ?? size * bytes;
  const start = (view.byteOffset ?? 0) + (a.byteOffset ?? 0);
  for (let i = 0; i < a.count; i++) for (let j = 0; j < size; j++)
    result[i * size + j] = binary[read](start + i * stride + j * bytes);
  return result;
}

export async function primitiveGeometry(doc, binary, primitive, root) {
  if ((primitive.mode ?? 4) !== 4 || primitive.targets) throw new Error('Only static triangles are supported');
  const extension = primitive.extensions?.KHR_draco_mesh_compression;
  if (!extension) {
    const positions = accessor(doc, binary, primitive.attributes.POSITION);
    return { positions, indices: primitive.indices === undefined
      ? Uint32Array.from({ length: positions.length / 3 }, (_, i) => i)
      : accessor(doc, binary, primitive.indices), compressed: false };
  }
  const draco = await dracoModule(root), decoder = new draco.Decoder(), mesh = new draco.Mesh();
  const view = doc.bufferViews[extension.bufferView], bytes = binary.subarray(view.byteOffset ?? 0, (view.byteOffset ?? 0) + view.byteLength);
  try {
    const status = decoder.DecodeArrayToMesh(new Int8Array(bytes.buffer, bytes.byteOffset, bytes.length), bytes.length, mesh);
    if (!status.ok() || !mesh.ptr) throw new Error(`Draco decode failed: ${status.error_msg()}`);
    const attr = decoder.GetAttributeByUniqueId(mesh, extension.attributes.POSITION);
    if (attr.num_components() !== 3) throw new Error('Draco POSITION is not VEC3');
    const positionBytes = mesh.num_points() * 12, indexBytes = mesh.num_faces() * 12;
    let pointer = draco._malloc(positionBytes), positions, indices;
    try {
      decoder.GetAttributeDataArrayForAllPoints(mesh, attr, draco.DT_FLOAT32, positionBytes, pointer);
      positions = new Float32Array(draco.HEAPF32.buffer, pointer, positionBytes / 4).slice();
    } finally { draco._free(pointer); }
    pointer = draco._malloc(indexBytes);
    try {
      decoder.GetTrianglesUInt32Array(mesh, indexBytes, pointer);
      indices = new Uint32Array(draco.HEAPF32.buffer, pointer, indexBytes / 4).slice();
    } finally { draco._free(pointer); }
    return { positions, indices, compressed: true };
  } finally { draco.destroy(mesh); draco.destroy(decoder); }
}

export function clipPlane(polygon, axis, bound, above) {
  const output = [];
  for (let i = 0; i < polygon.length; i++) {
    const a = polygon[i], b = polygon[(i + 1) % polygon.length];
    const ai = above ? a[axis] >= bound : a[axis] <= bound;
    const bi = above ? b[axis] >= bound : b[axis] <= bound;
    if (ai) output.push(a);
    if (ai !== bi) {
      const t = (bound - a[axis]) / (b[axis] - a[axis]);
      output.push(a.map((v, j) => v + (b[j] - v) * t));
    }
  }
  return output;
}
export function lowSlice(triangle, policy = MODEL_COLLISION_POLICY) {
  if (Math.min(...triangle.map(p => p[1])) > policy.maxY || Math.max(...triangle.map(p => p[1])) < policy.minY) return [];
  return clipPlane(clipPlane(triangle, 1, policy.minY, true), 1, policy.maxY, false);
}
export function pointInside(point, polygon) {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const a = polygon[i], b = polygon[j];
    if ((a[1] > point[1]) !== (b[1] > point[1]) && point[0] < (b[0] - a[0]) * (point[1] - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
  }
  return inside;
}
function edgeDistance(p, a, b) {
  const dx = b[0] - a[0], dz = b[1] - a[1];
  const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / (dx * dx + dz * dz || 1)));
  return Math.hypot(p[0] - a[0] - dx * t, p[1] - a[1] - dz * t);
}
function footprintCovered(x, z, size, footprints) {
  // The centre must be farther than the cell circumradius from every boundary.
  // This sufficient test also handles concave footprints without bridging cuts.
  const p = [(x + .5) * size, (z + .5) * size], radius = size / Math.SQRT2;
  return footprints.some(poly => pointInside(p, poly) && poly.every((a, i) => edgeDistance(p, a, poly[(i + 1) % poly.length]) > radius));
}

export function rasterizeSlice(polygon, cells, { cellMetres: size, existingWallHalfThickness = .05 } = MODEL_COLLISION_POLICY, footprints = [], source = '', coverage = new Map()) {
  if (!polygon.length) return;
  const zs = polygon.map(p => p[2]);
  const loZ = Math.floor(Math.min(...zs) / size), hiZ = Math.floor(Math.max(...zs) / size);
  // Clip each scanline before choosing its X range. A long diagonal wall
  // touches a narrow run; iterating its full AABB would be quadratic.
  for (let z = loZ; z <= hiZ; z++) {
    const row = clipPlane(clipPlane(polygon, 2, z * size, true), 2, (z + 1) * size, false);
    if (!row.length) continue;
    const xs = row.map(p => p[0]), loX = Math.floor(Math.min(...xs) / size), hiX = Math.floor(Math.max(...xs) / size);
    for (let x = loX; x <= hiX; x++) {
    const key = `${x},${z}`;
    let covered = coverage.get(key);
    if (covered === undefined) { covered = footprintCovered(x, z, size, footprints); coverage.set(key, covered); }
    if (covered) continue;
    let cut = row;
    for (const [axis, bound, above] of [[0, x * size, true], [0, (x + 1) * size, false]]) {
      cut = clipPlane(cut, axis, bound, above);
      if (!cut.length) break;
    }
    if (!cut.length) continue;
    // Do not add padding around surfaces already inside a building or its
    // existing 0.1 m map wall. Require an actual uncovered surface witness.
    const samples = [...cut, ...cut.map((a, i) => a.map((v, j) => (v + cut[(i + 1) % cut.length][j]) / 2))];
    const uncovered = samples.find(point => {
      const p = [point[0], point[2]];
      return !footprints.some(poly => pointInside(p, poly) || poly.some((a, i) => edgeDistance(p, a, poly[(i + 1) % poly.length]) <= existingWallHalfThickness + 1e-6));
    });
    if (!uncovered) continue;
    const minY = Math.min(...cut.map(p => p[1])), maxY = Math.max(...cut.map(p => p[1]));
    const cell = cells.get(key);
    if (cell) { cell.minY = Math.min(cell.minY, minY); cell.maxY = Math.max(cell.maxY, maxY); }
    else cells.set(key, { x, z, minY, maxY, source, sample: uncovered });
    }
  }
}

export function mergeCells(cells, modelId, policy = MODEL_COLLISION_POLICY) {
  const rows = new Map(), rectangles = [], size = policy.cellMetres;
  for (const cell of cells.values()) { const row = rows.get(cell.z) ?? []; row.push(cell); rows.set(cell.z, row); }
  let prior = new Map();
  for (const [z, row] of [...rows].sort((a, b) => a[0] - b[0])) {
    row.sort((a, b) => a.x - b.x); const runs = [];
    for (const cell of row) {
      const last = runs.at(-1);
      if (last && cell.x === last.end + 1) {
        last.end = cell.x; last.minY = Math.min(last.minY, cell.minY); last.maxY = Math.max(last.maxY, cell.maxY);
      } else runs.push({ start: cell.x, end: cell.x, minY: cell.minY, maxY: cell.maxY });
    }
    const current = new Map();
    for (const run of runs) {
      const key = `${run.start},${run.end}`, previous = prior.get(key);
      if (previous && previous.toZ === z - 1) {
        previous.toZ = z; previous.minY = Math.min(previous.minY, run.minY); previous.maxY = Math.max(previous.maxY, run.maxY); current.set(key, previous);
      } else { const rect = { ...run, fromZ: z, toZ: z }; rectangles.push(rect); current.set(key, rect); }
    }
    prior = current;
  }
  return rectangles.map((r, i) => ({ id: `model-solid-${modelId}-${i}`, kind: 'building-detail', minY: r.minY, maxY: r.maxY,
    points: [[r.start * size, r.fromZ * size], [(r.end + 1) * size, r.fromZ * size], [(r.end + 1) * size, (r.toZ + 1) * size], [r.start * size, (r.toZ + 1) * size]] }));
}

export async function extractModelCollisions({ root, model, footprints = [], raw, parsed, rootNodeIds, worldCoordinates = false,
  representation = 'cells', geometryCache, policy = MODEL_COLLISION_POLICY }) {
  const { doc, binary } = parsed ?? parseGlb(raw), cells = new Map(), cache = geometryCache ?? new Map(), coverage = new Map();
  const hullPoints = new Map(); let lowMinY = Infinity, lowMaxY = -Infinity;
  const stats = { triangles: 0, lowTriangles: 0, compressedPrimitives: 0, maximumBeyondFootprintMetres: 0, example: null };
  const placement = worldCoordinates ? new Matrix4() : new Matrix4().compose(new Vector3(model.center[0], policy.assemblyY, model.center[1]),
    new Quaternion().setFromAxisAngle(new Vector3(0, 1, 0), model.heading ?? 0), new Vector3(...(model.scale ?? [1, 1, 1])));
  async function visit(id, parent) {
    const node = doc.nodes[id];
    const local = node.matrix ? new Matrix4().fromArray(node.matrix) : new Matrix4().compose(
      new Vector3(...(node.translation ?? [0, 0, 0])), new Quaternion(...(node.rotation ?? [0, 0, 0, 1])), new Vector3(...(node.scale ?? [1, 1, 1])));
    const matrix = parent.clone().multiply(local);
    if (node.mesh !== undefined) for (const primitive of doc.meshes[node.mesh].primitives) {
      const positionAccessor = doc.accessors[primitive.attributes.POSITION];
      if (positionAccessor.min && positionAccessor.max) {
        const heights = [];
        for (const x of [positionAccessor.min[0], positionAccessor.max[0]]) for (const y of [positionAccessor.min[1], positionAccessor.max[1]]) for (const z of [positionAccessor.min[2], positionAccessor.max[2]])
          heights.push(new Vector3(x, y, z).applyMatrix4(matrix).y);
        if (Math.min(...heights) > policy.maxY || Math.max(...heights) < policy.minY) {
          stats.triangles += (primitive.indices === undefined ? positionAccessor.count : doc.accessors[primitive.indices].count) / 3;
          continue;
        }
      }
      let geometry = cache.get(primitive);
      if (!geometry) {
        geometry = await primitiveGeometry(doc, binary, primitive, root);
        if (geometry.indices.length % 3 || !geometry.positions.every(Number.isFinite) || !geometry.indices.every(i => Number.isInteger(i) && i >= 0 && i < geometry.positions.length / 3))
          throw new Error(`Invalid actual GLB geometry: ${model.id}/${node.name}`);
        cache.set(primitive, geometry);
      }
      stats.compressedPrimitives += Number(geometry.compressed);
      const { positions, indices } = geometry, transformed = new Float64Array(positions.length), v = new Vector3();
      for (let i = 0; i < positions.length; i += 3) { v.set(positions[i], positions[i + 1], positions[i + 2]).applyMatrix4(matrix); transformed.set([v.x, v.y, v.z], i); }
      for (let i = 0; i < indices.length; i += 3) {
        stats.triangles++;
        const a = indices[i] * 3, b = indices[i + 1] * 3, c = indices[i + 2] * 3;
        if (Math.min(transformed[a + 1], transformed[b + 1], transformed[c + 1]) > policy.maxY || Math.max(transformed[a + 1], transformed[b + 1], transformed[c + 1]) < policy.minY) continue;
        const slice = lowSlice([a, b, c].map(j => Array.from(transformed.subarray(j, j + 3))), policy);
        if (!slice.length) continue; stats.lowTriangles++;
        for (const point of slice) {
          const p = [point[0], point[2]];
          if (!footprints.length || footprints.some(poly => pointInside(p, poly))) continue;
          let distance = Infinity;
          for (const poly of footprints) for (let j = 0; j < poly.length; j++) distance = Math.min(distance, edgeDistance(p, poly[j], poly[(j + 1) % poly.length]));
          if (distance > stats.maximumBeyondFootprintMetres) { stats.maximumBeyondFootprintMetres = distance; stats.example = { node: node.name, point }; }
        }
        if (representation === 'object-hull') {
          for (const point of slice) {
            const p = [point[0], point[2]]; hullPoints.set(p.map(v => v.toFixed(7)).join(','), p);
            lowMinY = Math.min(lowMinY, point[1]); lowMaxY = Math.max(lowMaxY, point[1]);
          }
        } else rasterizeSlice(slice, cells, policy, footprints, node.name, coverage);
      }
    }
    for (const child of node.children ?? []) await visit(child, matrix);
  }
  for (const node of rootNodeIds ?? doc.scenes[doc.scene ?? 0].nodes) await visit(node, placement);
  const hull = convexHull([...hullPoints.values()]);
  return { obstacles: representation === 'object-hull' ? (hull.length >= 3 ? [{ id: model.id, kind: model.kind ?? 'furniture', minY: lowMinY, maxY: lowMaxY, points: hull }] : [])
    : mergeCells(cells, model.id, policy), cells, stats, surfacePoints: representation === 'object-hull' ? [...hullPoints.values()] : undefined };
}
