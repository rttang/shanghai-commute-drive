import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Path } from '../src/tour/drive.ts';
import { parseGlb, sha256 } from './model_collision_geometry.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SOURCE = 'public/streets/performance/context.glb';
const OUTPUT = 'public/streets/performance/context-portal-fixed.glb';
const EVIDENCE = 'docs/evidence/tourism/tunnel-surface-repair.json';
const SURFACES = new Set(['context-ground', 'context-asphalt', 'context-paving', 'context-markings', 'context-grass', 'context-curb']);
const assert = (condition, message) => { if (!condition) throw new Error(message); };
const cross = (a, b, p) => (b[0] - a[0]) * (p[2] - a[2]) - (b[2] - a[2]) * (p[0] - a[0]);
const areaXZ = polygon => polygon.reduce((s, a, i) => { const b = polygon[(i + 1) % polygon.length]; return s + a[0] * b[2] - b[0] * a[2]; }, 0) / 2;
const bbox = polygon => [Math.min(...polygon.map(p => p[0])), Math.min(...polygon.map(p => p[2])), Math.max(...polygon.map(p => p[0])), Math.max(...polygon.map(p => p[2]))];
const overlap = (a, b) => a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1];
function halfPlane(polygon, a, b, inside) {
  const output = [];
  for (let i = 0; i < polygon.length; i++) {
    const p = polygon[i], q = polygon[(i + 1) % polygon.length], dp = cross(a, b, p), dq = cross(a, b, q);
    const pi = inside ? dp >= 0 : dp <= 0, qi = inside ? dq >= 0 : dq <= 0;
    if (pi) output.push(p);
    if (pi !== qi) { const t = dp / (dp - dq); output.push(p.map((v, j) => v + (q[j] - v) * t)); }
  }
  return output.filter((p, i) => { const q = output[(i + 1) % output.length]; return !q || p.slice(0, 3).some((v, k) => Math.abs(v - q[k]) > 1e-10); });
}

/** Subtract a convex XZ opening from a convex 3D polygon. Attribute components
 * after XYZ are interpolated at every true edge intersection. Vertical curb
 * faces are supported too; no centroid classification discards whole triangles. */
export function subtractConvexXZ(subject, opening) {
  const clip = areaXZ(opening) < 0 ? [...opening].reverse() : opening;
  let intersection = subject;
  for (let i = 0; i < clip.length && intersection.length >= 3; i++) intersection = halfPlane(intersection, clip[i], clip[(i + 1) % clip.length], true);
  const polygonArea = poly => poly.slice(1, -1).reduce((sum, p, i) => sum + triangleArea3D(poly[0], p, poly[i + 2]), 0);
  if (intersection.length < 3 || polygonArea(intersection) <= Math.max(1e-10, polygonArea(subject) * 1e-12)) return [subject];
  let inside = subject; const outside = [];
  for (let i = 0; i < clip.length && inside.length >= 3; i++) {
    const a = clip[i], b = clip[(i + 1) % clip.length];
    // A surface coincident with a vertical opening boundary stays outside.
    // Without this case a vertical curb face could be returned twice.
    if (inside.every(p => cross(a, b, p) <= 1e-10)) { outside.push(inside); inside = []; break; }
    const part = halfPlane(inside, a, b, false);
    if (part.length >= 3) outside.push(part);
    inside = halfPlane(inside, a, b, true);
  }
  return outside;
}
export function triangleArea3D(a, b, c) {
  const u = b.slice(0, 3).map((v, i) => v - a[i]), v = c.slice(0, 3).map((v, i) => v - a[i]);
  return Math.hypot(u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]) / 2;
}
export function isGroundSurface(name, vertices) {
  const y = vertices.map(p => p[1]);
  if (name === 'context-curb') return y.every(v => v >= .0699 && v <= .2301);
  const levels = { 'context-ground': [-.18], 'context-asphalt': [.125], 'context-paving': [.07, .105], 'context-markings': [.15], 'context-grass': [.045] };
  return levels[name]?.some(level => y.every(v => Math.abs(v - level) < .00001)) ?? false;
}

export function portalOpenings(route, { halfWidth = 4.2, depth = 6.5, step = 5 } = {}) {
  const drivePath = new Path(route.points, !!route.closed, route.elevations), portals = [];
  for (const tunnel of route.tunnels ?? []) {
    const samples = [];
    for (let d = tunnel.start; d < tunnel.end; d += step) samples.push(d);
    samples.push(tunnel.end);
    for (const side of ['start', 'end']) {
      const direction = side === 'start' ? 1 : -1, mouth = tunnel[side];
      let a = mouth, b = mouth;
      while ((drivePath.at(b).y ?? 0) > -depth && b >= tunnel.start && b <= tunnel.end) b += direction * step;
      assert(b >= tunnel.start && b <= tunnel.end, 'Tunnel does not reach the clipping depth');
      a = b - direction * step;
      for (let i = 0; i < 40; i++) { const m = (a + b) / 2; if ((drivePath.at(m).y ?? 0) > -depth) a = m; else b = m; }
      const boundary = (a + b) / 2, start = Math.min(mouth, boundary), end = Math.max(mouth, boundary), quads = [];
      for (let i = 1; i < samples.length; i++) {
        const d0 = samples[i - 1], d1 = samples[i], lo = Math.max(d0, start), hi = Math.min(d1, end);
        if (lo >= hi) continue;
        // Interpolate the boundary of the existing 5m wall strip, rather than
        // constructing a new tangent that could cut past a curved wall.
        const edge = (d, s) => {
          const p = drivePath.pose(d, 0);
          return [p.x + Math.cos(p.heading) * s * halfWidth, 0, p.z - Math.sin(p.heading) * s * halfWidth];
        };
        const at = (d, s) => { const a = edge(d0, s), b = edge(d1, s), t = (d - d0) / (d1 - d0); return a.map((v, k) => v + (b[k] - v) * t); };
        const polygon = [at(lo, -1), at(lo, 1), at(hi, 1), at(hi, -1)];
        const order = areaXZ(polygon) < 0 ? [...polygon].reverse() : polygon;
        assert(order.every((p, i) => cross(order[(i + order.length - 1) % order.length], p, order[(i + 1) % order.length]) >= -1e-7), 'Nonconvex portal strip');
        quads.push({ d0: lo, d1: hi, polygon: order, bounds: bbox(order) });
      }
      portals.push({ id: `${tunnel.name}-${side}`, tunnel: tunnel.name, side, start, end, halfWidth, depth, quads });
    }
  }
  return { drivePath, portals };
}

const widths = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4 };
const formats = { 5126: Float32Array, 5123: Uint16Array, 5125: Uint32Array, 5121: Uint8Array };
function readAccessor(src, id) {
  const a = src.doc.accessors[id], v = src.doc.bufferViews[a.bufferView], C = formats[a.componentType], size = widths[a.type];
  assert(C && size && !a.sparse && !a.normalized && !v.extensions && !a.byteOffset && (!v.byteStride || v.byteStride === size * C.BYTES_PER_ELEMENT), 'Only packed ordinary accessors supported');
  const start = v.byteOffset ?? 0, length = a.count * size * C.BYTES_PER_ELEMENT;
  assert(start + length <= src.binary.length, 'Accessor overflow');
  const bytes = src.binary.subarray(start, start + length);
  return { array: new C(bytes.buffer, bytes.byteOffset, a.count * size), size, id };
}
function primitiveData(src, p) {
  assert((p.mode ?? 4) === 4 && !p.extensions, 'Ordinary triangle GLB required');
  const attrs = Object.fromEntries(Object.entries(p.attributes).map(([k, a]) => [k, readAccessor(src, a)]));
  return { attrs, indices: p.indices === undefined ? Uint32Array.from({ length: attrs.POSITION.array.length / 3 }, (_, i) => i) : readAccessor(src, p.indices).array };
}
function eligibleGeometry(src) {
  const output = [];
  for (const node of src.doc.nodes) if (node.mesh !== undefined && SURFACES.has(node.name)) {
    assert(!node.matrix && !node.translation && !node.rotation && !node.scale, 'Surface mesh must already use world coordinates');
    for (const primitive of src.doc.meshes[node.mesh].primitives) output.push({ name: node.name, ...primitiveData(src, primitive) });
  }
  return output;
}
export function heightsAt(x, z, geometry) {
  const { array: positions } = geometry.attrs.POSITION, hits = [];
  if (!geometry.rayIndex) {
    const grid = new Map(), large = [], size = 25;
    for (let i = 0; i < geometry.indices.length; i += 3) {
      const vertices = [0, 1, 2].map(k => { const v = geometry.indices[i + k] * 3; return [positions[v], positions[v + 1], positions[v + 2]]; });
      if (!isGroundSurface(geometry.name, vertices)) continue;
      const b = bbox(vertices), x0 = Math.floor(b[0] / size), x1 = Math.floor(b[2] / size), z0 = Math.floor(b[1] / size), z1 = Math.floor(b[3] / size);
      if ((x1 - x0 + 1) * (z1 - z0 + 1) > 100) { large.push(i); continue; }
      for (let cx = x0; cx <= x1; cx++) for (let cz = z0; cz <= z1; cz++) { const key = `${cx},${cz}`, list = grid.get(key) ?? []; list.push(i); grid.set(key, list); }
    }
    geometry.rayIndex = { grid, large, size };
  }
  const { grid, large, size } = geometry.rayIndex;
  const candidates = [...large, ...(grid.get(`${Math.floor(x / size)},${Math.floor(z / size)}`) ?? [])];
  for (const i of candidates) {
    const [a, b, c] = [0, 1, 2].map(k => geometry.indices[i + k] * 3);
    const x0 = positions[a], z0 = positions[a + 2], x1 = positions[b], z1 = positions[b + 2], x2 = positions[c], z2 = positions[c + 2];
    if (x < Math.min(x0, x1, x2) || x > Math.max(x0, x1, x2) || z < Math.min(z0, z1, z2) || z > Math.max(z0, z1, z2)) continue;
    const denominator = (z1 - z2) * (x0 - x2) + (x2 - x1) * (z0 - z2);
    if (Math.abs(denominator) < 1e-10) continue;
    const u = ((z1 - z2) * (x - x2) + (x2 - x1) * (z - z2)) / denominator;
    const v = ((z2 - z0) * (x - x2) + (x0 - x2) * (z - z2)) / denominator, w = 1 - u - v;
    if (Math.min(u, v, w) >= -1e-8) {
      const vertices = [a, b, c].map(k => [positions[k], positions[k + 1], positions[k + 2]]);
      if (isGroundSurface(geometry.name, vertices)) hits.push(u * positions[a + 1] + v * positions[b + 1] + w * positions[c + 1]);
    }
  }
  return [...new Set(hits.map(y => +y.toFixed(5)))].sort((a, b) => a - b);
}
function raySamples(src, plan, route) {
  const geometries = eligibleGeometry(src), openings = [], sides = [], deep = [];
  const layers = q => geometries.flatMap(g => heightsAt(q.x, q.z, g).map(y => ({ name: g.name, y })));
  for (const portal of plan.portals) {
    const distances = [portal.start + .5];
    for (let d = portal.start + 2.5; d < portal.end; d += 5) distances.push(d);
    distances.push(portal.end - .5);
    for (const distance of distances) {
      for (const lateral of [-3.15, -2.4, -1.4, 0, 1.4, 2.4, 3.15]) {
        const q = plan.drivePath.pose(distance, lateral);
        openings.push({ portal: portal.id, distance, lateral, x: q.x, z: q.z, floorY: q.y + .12, hits: layers(q).filter(hit => hit.y > q.y + .14) });
      }
      for (const lateral of [-6.2, -4.7, 4.7, 6.2]) {
        const q = plan.drivePath.pose(distance, lateral); sides.push({ portal: portal.id, distance, lateral, hits: layers(q) });
      }
    }
  }
  for (const tunnel of route.tunnels) for (let distance = tunnel.start + 180; distance < tunnel.end - 180; distance += 50) {
    if (plan.drivePath.at(distance).y > -7) continue;
    for (const lateral of [-2.4, 0, 2.4]) { const q = plan.drivePath.pose(distance, lateral); deep.push({ tunnel: tunnel.name, distance, lateral, hits: layers(q) }); }
  }
  return { openings, sides, deep };
}
function pack(doc, buffers) {
  const bins = []; let offset = 0;
  buffers.forEach((bytes, i) => { doc.bufferViews[i].byteOffset = offset; doc.bufferViews[i].byteLength = bytes.length; bins.push(bytes); offset += bytes.length; const pad = (4 - offset % 4) % 4; if (pad) { bins.push(Buffer.alloc(pad)); offset += pad; } });
  const binary = Buffer.concat(bins); doc.buffers = [{ byteLength: binary.length }];
  const text = Buffer.from(JSON.stringify(doc)), json = Buffer.alloc((text.length + 3) & ~3, 32); text.copy(json);
  const head = Buffer.alloc(20), bh = Buffer.alloc(8); head.writeUInt32LE(0x46546c67, 0); head.writeUInt32LE(2, 4); head.writeUInt32LE(28 + json.length + binary.length, 8); head.writeUInt32LE(json.length, 12); head.writeUInt32LE(0x4e4f534a, 16); bh.writeUInt32LE(binary.length); bh.writeUInt32LE(0x004e4942, 4);
  return Buffer.concat([head, json, bh, binary]);
}

async function prepare() {
  const input = fs.readFileSync(path.join(ROOT, SOURCE)), src = parseGlb(input), sourceHash = sha256(input);
  const routeBytes = fs.readFileSync(path.join(ROOT, 'public/tour-city.json')), route = JSON.parse(routeBytes).routes.find(r => r.id === 'shanghai-loop'), plan = portalOpenings(route);
  const doc = structuredClone(src.doc), buffers = src.doc.bufferViews.map(v => src.binary.subarray(v.byteOffset ?? 0, (v.byteOffset ?? 0) + v.byteLength));
  const cuts = plan.portals.flatMap(p => p.quads), portalBounds = plan.portals.map(p => bbox(p.quads.flatMap(q => q.polygon))), edited = [], replacedViews = new Set();
  const before = raySamples(src, plan, route); console.log(JSON.stringify({ stage: 'source-rays', coveredSamples: before.openings.filter(s => s.hits.length).length, samples: before.openings.length }));
  for (const node of src.doc.nodes) {
    if (node.mesh === undefined || !SURFACES.has(node.name)) continue;
    for (const p of src.doc.meshes[node.mesh].primitives) {
      const data = primitiveData(src, p), names = Object.keys(data.attrs), fields = names.map(k => data.attrs[k]), offsets = []; let stride = 0;
      for (const a of fields) { assert(a.array instanceof Float32Array, 'Surface attributes must be Float32'); offsets.push(stride); stride += a.size; }
      assert(names[0] === 'POSITION', 'Position must be first');
      const count = data.attrs.POSITION.array.length / 3, additional = [], fresh = new Map(), indices = []; let affectedTriangles = 0, removedArea = 0, addedTriangles = 0;
      const vertex = index => { const v = fields.flatMap(a => Array.from(a.array.subarray(index * a.size, (index + 1) * a.size))); v.sourceIndex = index; return v; };
      const emit = v => {
        if (v.sourceIndex !== undefined) return v.sourceIndex;
        const values = [...v], ni = names.indexOf('NORMAL');
        if (ni >= 0) { const o = offsets[ni], length = Math.hypot(...values.slice(o, o + 3)); if (length) for (let k = o; k < o + 3; k++) values[k] /= length; }
        const packed = Float32Array.from(values); assert(packed.every(Number.isFinite), 'Non-finite clipping intersection');
        const key = Buffer.from(packed.buffer).toString('hex'); if (fresh.has(key)) return fresh.get(key);
        const index = count + additional.length; additional.push(packed); fresh.set(key, index); return index;
      };
      for (let i = 0; i < data.indices.length; i += 3) {
        const ix = Array.from(data.indices.subarray(i, i + 3)), pos = ix.map(k => Array.from(data.attrs.POSITION.array.subarray(k * 3, k * 3 + 3))), bound = bbox(pos);
        if (!portalBounds.some(b => overlap(b, bound)) || !isGroundSurface(node.name, pos)) { indices.push(...ix); continue; }
        const relevant = cuts.filter(q => overlap(q.bounds, bound)); if (!relevant.length) { indices.push(...ix); continue; }
        let polygons = [ix.map(vertex)];
        for (const cut of relevant) polygons = polygons.flatMap(poly => overlap(bbox(poly), cut.bounds) ? subtractConvexXZ(poly, cut.polygon) : [poly]);
        const result = [];
        for (const poly of polygons) for (let k = 1; k + 1 < poly.length; k++) if (triangleArea3D(poly[0], poly[k], poly[k + 1]) > 1e-10) result.push([poly[0], poly[k], poly[k + 1]]);
        const originalArea = triangleArea3D(...pos), keptArea = result.reduce((n, t) => n + triangleArea3D(...t), 0);
        assert(keptArea <= originalArea + Math.max(1e-6, originalArea * 1e-7), 'Clipping duplicated surface area');
        if (Math.abs(originalArea - keptArea) < Math.max(1e-9, originalArea * 1e-12)) { indices.push(...ix); continue; }
        affectedTriangles++; removedArea += originalArea - keptArea; addedTriangles += result.length;
        for (const triangle of result) indices.push(...triangle.map(emit));
      }
      if (!affectedTriangles) continue;
      fields.forEach((a, field) => {
        const array = new Float32Array(a.array.length + additional.length * a.size); array.set(a.array);
        additional.forEach((v, i) => array.set(v.subarray(offsets[field], offsets[field] + a.size), (count + i) * a.size));
        const accessor = doc.accessors[a.id]; accessor.count = array.length / a.size;
        buffers[accessor.bufferView] = Buffer.from(array.buffer); replacedViews.add(accessor.bufferView);
      });
      const C = count + additional.length <= 65535 ? Uint16Array : Uint32Array, array = C.from(indices), ai = doc.accessors[p.indices];
      ai.componentType = C === Uint16Array ? 5123 : 5125; ai.count = indices.length;
      buffers[ai.bufferView] = Buffer.from(array.buffer); replacedViews.add(ai.bufferView);
      edited.push({ name: node.name, inputTriangles: data.indices.length / 3, triangles: indices.length / 3, affectedTriangles, replacementTriangles: addedTriangles, newVertices: additional.length, removedAreaSquareMetres: removedArea });
      console.log(JSON.stringify(edited.at(-1)));
    }
  }
  assert(edited.length > 0, 'No covering surfaces were repaired');
  const output = pack(doc, buffers), candidate = parseGlb(output), outPath = path.join(ROOT, OUTPUT);
  if (fs.existsSync(outPath)) fs.copyFileSync(outPath, outPath + '.' + Date.now() + '.previous');
  fs.writeFileSync(outPath + '.tmp', output); assert(sha256(fs.readFileSync(outPath + '.tmp')) === sha256(output), 'Disk SHA mismatch'); fs.renameSync(outPath + '.tmp', outPath);
  const actual = parseGlb(fs.readFileSync(outPath)), after = raySamples(actual, plan, route);
  const remaining = after.openings.filter(s => s.hits.length), sideChanges = before.sides.filter((s, i) => JSON.stringify(s.hits) !== JSON.stringify(after.sides[i].hits)), deepChanges = before.deep.filter((s, i) => JSON.stringify(s.hits) !== JSON.stringify(after.deep[i].hits));
  const originalMaster = fs.readFileSync(path.join(ROOT, 'public/streets/master/chunks/context.glb')), master = parseGlb(originalMaster), masterRays = raySamples(master, plan, route);
  assert(JSON.stringify(masterRays) === JSON.stringify(before), 'Performance input surface rays differ from original master');
  const protectedViews = [];
  for (let i = 0; i < src.doc.bufferViews.length; i++) if (!replacedViews.has(i)) {
    const av = src.doc.bufferViews[i], bv = actual.doc.bufferViews[i], original = src.binary.subarray(av.byteOffset ?? 0, (av.byteOffset ?? 0) + av.byteLength), next = actual.binary.subarray(bv.byteOffset, bv.byteOffset + bv.byteLength);
    assert(original.equals(next), 'Untouched geometry/image bytes changed'); protectedViews.push({ bufferView: i, bytes: original.length, sha256: sha256(original) });
  }
  for (const key of ['nodes', 'meshes', 'materials', 'textures', 'samplers', 'images', 'scenes']) assert(JSON.stringify(src.doc[key]) === JSON.stringify(actual.doc[key]), `${key} changed`);
  let triangles = 0;
  for (const mesh of actual.doc.meshes) for (const primitive of mesh.primitives) {
    const data = primitiveData(actual, primitive), n = data.attrs.POSITION.array.length / 3;
    assert(data.indices.length % 3 === 0 && data.indices.every(i => i < n), 'Invalid output indices');
    for (const attr of Object.values(data.attrs)) assert(attr.array.every(Number.isFinite) && attr.array.length / attr.size === n, 'Invalid output attribute');
    triangles += data.indices.length / 3;
  }
  const currentManifest = JSON.parse(fs.readFileSync(path.join(ROOT, 'public/streets/performance/manifest.json'))), base = currentManifest.variants.find(v => v.id === 'context');
  assert(output.length <= base.sourceBytes && triangles <= base.sourceTriangles * 1.03, 'Repair exceeds approved byte/triangle bounds');
  assert(sha256(fs.readFileSync(path.join(ROOT, SOURCE))) === sourceHash, 'Original performance input changed');
  const report = { version: 1, state: remaining.length || sideChanges.length || deepChanges.length ? 'validation-failed' : 'verified-candidate', generated: new Date().toISOString(), generator: 'scripts/repair_tunnel_surfaces.mjs', sourceFile: '/streets/performance/context.glb', sourceSha256: sha256(originalMaster), repairSourceSha256: sourceHash, routeSha256: sha256(routeBytes), sourceBytes: input.length, file: '/streets/performance/context-portal-fixed.glb', bytes: output.length, triangles, sha256: sha256(output), purpose: 'portal-surface-repair', method: 'Subtract union of convex 5m wall-aligned XZ strips from actual surface triangles; retain/interpolate all vertex attributes; no centroid filtering; depth capped at actual route -6.5m; markings only global y=.15.', portals: plan.portals, edited, validation: { sampleSpacingMetres: 5, vehicleAndCameraLateralMetres: [-3.15, -2.4, -1.4, 0, 1.4, 2.4, 3.15], sourceCoveredSamples: before.openings.filter(s => s.hits.length).length, remainingCoveredSamples: remaining.length, totalOpeningSamples: before.openings.length, outsideSurfaceSamples: before.sides.length, outsideChangedSamples: sideChanges.length, deepSurfaceSamples: before.deep.length, deepChangedSamples: deepChanges.length, masterMatchesPerformanceBefore: true, retainedBufferViews: protectedViews, exactMaterialsAndNodes: true, originalImageBytesPreserved: true, finiteAttributesAndCompleteIndices: true, browserAcceptance: 'pending-root' }, before, after, remaining, sideChanges, deepChanges, previousRuntimeManifest: currentManifest };
  fs.mkdirSync(path.dirname(path.join(ROOT, EVIDENCE)), { recursive: true }); fs.writeFileSync(path.join(ROOT, EVIDENCE), JSON.stringify(report, null, 2) + '\n');
  assert(report.state === 'verified-candidate', `Portal ray validation failed: remaining=${remaining.length}, sides=${sideChanges.length}, deep=${deepChanges.length}`);
  console.log(JSON.stringify({ state: report.state, bytes: report.bytes, triangles, remaining: remaining.length, sides: sideChanges.length, deep: deepChanges.length }));
}
function publish() {
  const report = JSON.parse(fs.readFileSync(path.join(ROOT, EVIDENCE))), file = path.join(ROOT, 'public/streets/performance/manifest.json'), runtime = JSON.parse(fs.readFileSync(file));
  assert(report.state === 'verified-candidate' && sha256(fs.readFileSync(path.join(ROOT, OUTPUT))) === report.sha256, 'No verified current candidate');
  assert(report.validation.newIntersectionAttributeReadback, 'Verify actual intersection UVs and normals before publication');
  const variant = runtime.variants.find(v => v.id === 'context');
  assert(variant.sourceSha256 === report.sourceSha256 && sha256(fs.readFileSync(path.join(ROOT, SOURCE))) === report.repairSourceSha256, 'Source changed before publication');
  Object.assign(variant, { file: report.file, bytes: report.bytes, triangles: report.triangles, sha256: report.sha256, purpose: report.purpose, repairSourceSha256: report.repairSourceSha256 });
  fs.writeFileSync(file + '.tmp', JSON.stringify(runtime, null, 2) + '\n'); fs.renameSync(file + '.tmp', file);
  report.state = 'published'; report.published = new Date().toISOString(); fs.writeFileSync(path.join(ROOT, EVIDENCE), JSON.stringify(report, null, 2) + '\n'); console.log(JSON.stringify({ published: report.file, sha256: report.sha256 }));
}
function verifyAttributes() {
  const source = parseGlb(fs.readFileSync(path.join(ROOT, SOURCE))), output = parseGlb(fs.readFileSync(path.join(ROOT, OUTPUT))), reportPath = path.join(ROOT, EVIDENCE), report = JSON.parse(fs.readFileSync(reportPath));
  const before = eligibleGeometry(source), after = eligibleGeometry(output);
  let checkedVertices = 0, maxUvError = 0, maxNormalError = 0, maxPlaneDistanceMetres = 0;
  for (const edit of report.edited) {
    const original = before.find(g => g.name === edit.name), derived = after.find(g => g.name === edit.name), start = original.attrs.POSITION.array.length / 3;
    heightsAt(0, 0, original); const { grid, large, size } = original.rayIndex;
    const get = (g, name, i) => { const a = g.attrs[name]; return Array.from(a.array.subarray(i * a.size, (i + 1) * a.size)); };
    for (let index = start; index < derived.attrs.POSITION.array.length / 3; index++) {
      const p = get(derived, 'POSITION', index), uv = get(derived, 'TEXCOORD_0', index), normal = get(derived, 'NORMAL', index), ids = new Set(large);
      const gx = Math.floor(p[0] / size), gz = Math.floor(p[2] / size);
      for (let x = gx - 1; x <= gx + 1; x++) for (let z = gz - 1; z <= gz + 1; z++) for (const tri of grid.get(`${x},${z}`) ?? []) ids.add(tri);
      let best;
      for (const tri of ids) {
        const indices = Array.from(original.indices.subarray(tri, tri + 3)), vertices = indices.map(i => get(original, 'POSITION', i)), [a, b, c] = vertices;
        if (p.some((v, axis) => v < Math.min(a[axis], b[axis], c[axis]) - .0003 || v > Math.max(a[axis], b[axis], c[axis]) + .0003)) continue;
        const u = b.map((v, i) => v - a[i]), v = c.map((v, i) => v - a[i]), n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]], length = Math.hypot(...n);
        if (length < 1e-12) continue;
        const planeError = Math.abs(n.reduce((s, q, i) => s + q * (p[i] - a[i]), 0)) / length;
        const drop = n.map(Math.abs).indexOf(Math.max(...n.map(Math.abs))), [x, y] = [0, 1, 2].filter(i => i !== drop), determinant = u[x] * v[y] - u[y] * v[x];
        const wb = ((p[x] - a[x]) * v[y] - (p[y] - a[y]) * v[x]) / determinant, wc = (u[x] * (p[y] - a[y]) - u[y] * (p[x] - a[x])) / determinant, weights = [1 - wb - wc, wb, wc];
        if (Math.min(...weights) < -.003 || planeError > .0003) continue;
        const interpolate = name => get(original, name, indices[0]).map((_, k) => indices.reduce((s, i, j) => s + weights[j] * get(original, name, i)[k], 0));
        const expectedUv = interpolate('TEXCOORD_0'), expectedNormal = interpolate('NORMAL'), normalLength = Math.hypot(...expectedNormal);
        const uvError = Math.hypot(...uv.map((v, i) => v - expectedUv[i])), normalError = Math.hypot(...normal.map((v, i) => v - expectedNormal[i] / (normalLength || 1)));
        const score = Math.max(uvError / .002, normalError / .00001, planeError / .0003);
        if (!best || score < best.score) best = { score, uvError, normalError, planeError };
      }
      assert(best && best.score <= 1, `New vertex does not match source triangle UV/normal/plane: ${edit.name}/${index}: ${JSON.stringify(best)}`);
      checkedVertices++; maxUvError = Math.max(maxUvError, best.uvError); maxNormalError = Math.max(maxNormalError, best.normalError); maxPlaneDistanceMetres = Math.max(maxPlaneDistanceMetres, best.planeError);
    }
  }
  report.validation.newIntersectionAttributeReadback = { checkedVertices, maxUvError, maxNormalError, maxPlaneDistanceMetres, tolerance: { uv: .002, normal: .00001, planeMetres: .0003 }, method: 'For every appended Float32 vertex, locate an original surface triangle and independently compare barycentric UV, normalized normal, and plane distance; no output geometry regeneration.' };
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n'); console.log(JSON.stringify(report.validation.newIntersectionAttributeReadback));
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--prepare')) await prepare();
  else if (process.argv.includes('--publish')) publish();
  else if (process.argv.includes('--verify-attributes')) verifyAttributes();
  else throw new Error('Run with node --import tsx scripts/repair_tunnel_surfaces.mjs --prepare | --publish');
}
