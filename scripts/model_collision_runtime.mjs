/** Collision authoring from immutable, currently rendered master chunks.
 * Run sequentially with node --import tsx:
 *   scripts/model_collision_runtime.mjs --candidate
 *   scripts/model_collision_runtime.mjs --verify
 *   scripts/model_collision_runtime.mjs --publish
 * No district manifest, external context prototype or Blender input is used. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Matrix4, Quaternion, Vector3 } from 'three';
import { CollisionWorld } from '../src/tour/collision.ts';
import { Drive, Path } from '../src/tour/drive.ts';
import { RoadClearance } from '../src/tour/road-clearance.ts';
import { guardRuntimeRoute } from './model_collision_audit.mjs';
import { parseGlb, primitiveGeometry, extractModelCollisions, convexHull, sha256, MODEL_COLLISION_POLICY } from './model_collision_geometry.mjs';

export const ROOT = fileURLToPath(new URL('../', import.meta.url));
export const CANDIDATE = 'docs/evidence/tourism/model-collision-candidate.json';
export const VERIFICATION = 'docs/evidence/tourism/model-collision-runtime-verification.json';
export const RECEIPT = 'docs/evidence/tourism/model-collision-runtime-publication.json';
const PUBLIC_COLLISIONS = 'public/streets/collisions.json';
const MANIFEST = 'public/streets/master/manifest.json';
const number = n => Math.round(n * 1e7) / 1e7;
const jsonRead = file => JSON.parse(fs.readFileSync(path.join(ROOT, file), 'utf8'));
const need = (condition, message, details) => { if (!condition) throw new Error(`${message}${details ? ': ' + JSON.stringify(details) : ''}`); };
const nodeMatrix = n => n.matrix ? new Matrix4().fromArray(n.matrix) : new Matrix4().compose(new Vector3(...(n.translation ?? [0, 0, 0])), new Quaternion(...(n.rotation ?? [0, 0, 0, 1])), new Vector3(...(n.scale ?? [1, 1, 1])));
const bounds = points => [Math.min(...points.map(p => p[0])), Math.min(...points.map(p => p[1])), Math.max(...points.map(p => p[0])), Math.max(...points.map(p => p[1]))].map(number);
const kindFor = name => name.startsWith('river-railing-') ? 'railing' : name.replace(/-\d+$/, '');
const oldIdFor = name => name.startsWith('river-railing-') ? name.replace('river-railing-', 'rail-') : `furniture-${name.match(/-(\d+)$/)?.[1]}`;

export function transformLowHull(obstacle, matrix, id, kind) {
  need(Math.abs(matrix.elements[1]) < 1e-9 && Math.abs(matrix.elements[9]) < 1e-9 && Math.abs(matrix.elements[4]) < 1e-9 && Math.abs(matrix.elements[6]) < 1e-9,
    'Furniture placement has unexpected pitch/roll');
  const points = obstacle.points.map(([x, z]) => new Vector3(x, 0, z).applyMatrix4(matrix)).map(p => [number(p.x), number(p.z)]);
  const y0 = new Vector3(0, obstacle.minY, 0).applyMatrix4(matrix).y, y1 = new Vector3(0, obstacle.maxY, 0).applyMatrix4(matrix).y;
  return { id, kind, points: convexHull(points), minY: number(Math.min(y0, y1)), maxY: number(Math.max(y0, y1)) };
}

export function tunnelBarriersFromGeometry(positions, indices, matrix = new Matrix4()) {
  need(indices.length % 12 === 0, 'Tunnel barrier is not a complete pair of rendered strip faces');
  const vertex = i => { const index = indices[i]; need(index >= 0 && index * 3 + 2 < positions.length, 'Invalid tunnel index');
    const v = new Vector3(positions[index * 3], positions[index * 3 + 1], positions[index * 3 + 2]).applyMatrix4(matrix); return [v.x, v.y, v.z]; };
  const same = (a, b) => a.every((v, i) => Math.abs(v - b[i]) < 1e-5), result = [];
  for (let i = 0; i < indices.length; i += 12) {
    const points = Array.from({ length: 12 }, (_, j) => vertex(i + j));
    for (const [a, b] of [[0, 3], [1, 6], [1, 9], [2, 4], [2, 11], [8, 10]]) need(same(points[a], points[b]), 'Rendered tunnel strip topology changed', { index: i, a, b });
    const unique = [points[0], points[1], points[2], points[5], points[7], points[8]];
    const polygon = convexHull(unique.map(p => [number(p[0]), number(p[2])]));
    need(polygon.length >= 3, 'Tunnel barrier lost its actual sloping base footprint');
    result.push({ id: `runtime-tunnel-base-${i / 12}`, kind: 'tunnel', points: polygon,
      minY: number(Math.min(...unique.map(p => p[1]))), maxY: number(Math.max(...unique.map(p => p[1]))) });
  }
  return result;
}

function sourceCheck(sources) {
  for (const [file, expected] of Object.entries(sources)) need(sha256(fs.readFileSync(path.join(ROOT, file))) === expected.sha256, 'Frozen collision input changed', { file });
}
function writeVerified(file, bytes) {
  const target = path.join(ROOT, file), temporary = `${target}.pending-${process.pid}`;
  const descriptor = fs.openSync(temporary, 'wx');
  try { fs.writeFileSync(descriptor, bytes); fs.fsyncSync(descriptor); } finally { fs.closeSync(descriptor); }
  need(sha256(fs.readFileSync(temporary)) === sha256(bytes), 'Candidate write failed SHA readback', { temporary });
  fs.renameSync(temporary, target);
  need(sha256(fs.readFileSync(target)) === sha256(bytes), 'Atomic publication failed SHA readback', { file });
}

export async function createRuntimeCollisionCandidate({ progress = console.log, expectedManifestSha, includeArchitecture = false } = {}) {
  const sources = {}, read = file => { const raw = fs.readFileSync(path.join(ROOT, file)); sources[file] = { sha256: sha256(raw), bytes: raw.length }; return raw; };
  const manifest = JSON.parse(read(MANIFEST));
  if (expectedManifestSha) need(sources[MANIFEST].sha256 === expectedManifestSha, 'Master is not the coordinated frozen manifest');
  const city = JSON.parse(read('public/tour-city.json')), baselineRaw = fs.readFileSync(path.join(ROOT, PUBLIC_COLLISIONS)), baseline = JSON.parse(baselineRaw);
  const baselineSha = sha256(baselineRaw), old = new Map(baseline.obstacles.map(o => [o.id, o])), buildings = new Map(city.buildings.map(b => [b.id, b.points]));
  const replacedKinds = new Set(['railing', 'plane-tree', 'streetlamp', 'road-sign', 'bench', 'litter-bin', 'bridge', 'tunnel', 'building-detail']);
  const obstacles = baseline.obstacles.filter(o => !replacedKinds.has(o.kind));
  const furniture = [], architecture = [], bridges = [], tunnels = [], matchedOld = new Set(), rootIds = new Set();
  let chunkIndex = 0;
  for (const chunk of manifest.chunks) {
    const file = `public/${chunk.file.replace(/^\//, '')}`, raw = read(file);
    need(raw.length === chunk.bytes && sources[file].sha256 === chunk.sha256, 'Runtime chunk does not match its manifest', { file });
    const parsed = parseGlb(raw), { doc, binary } = parsed, geometryCache = new Map(), prototypeCache = new Map();
    const signature = id => { const n = doc.nodes[id]; return JSON.stringify({ mesh: n.mesh, matrix: n.matrix, translation: n.translation, rotation: n.rotation, scale: n.scale, children: (n.children ?? []).map(signature) }); };
    for (const rootId of doc.scenes[doc.scene ?? 0].nodes) {
      const node = doc.nodes[rootId], category = node.extras?.category, id = node.name, matrix = nodeMatrix(node);
      need(!rootIds.has(id), 'Duplicate runtime assembly object', { id }); rootIds.add(id);
      if (category === 'architecture') {
        const ways = node.extras?.ways ?? [], footprints = ways.map(id => buildings.get(id)).filter(Boolean);
        if (!includeArchitecture) { architecture.push({ id, chunk: chunk.id, rootNode: rootId, ways, matchedFootprints: footprints.length, obstacles: 0, extracted: false }); continue; }
        const result = await extractModelCollisions({ root: ROOT, model: { id }, parsed, rootNodeIds: [rootId], worldCoordinates: true, geometryCache, footprints });
        obstacles.push(...result.obstacles);
        architecture.push({ id, chunk: chunk.id, rootNode: rootId, ways, matchedFootprints: footprints.length, ...result.stats,
          occupiedCells: result.cells.size, obstacles: result.obstacles.length, sampleObstacle: result.obstacles[0] ?? null });
      } else if (category === 'furniture') {
        const kind = kindFor(id), oldId = oldIdFor(id), prior = old.get(oldId);
        need(['railing', 'plane-tree', 'streetlamp', 'road-sign', 'bench', 'litter-bin'].includes(kind), 'Unrecognized actual furniture needs an explicit physical treatment', { id });
        const y = matrix.elements[13], yScale = matrix.elements[5]; need(yScale > 0, 'Invalid vertical furniture scale');
        const policy = { ...MODEL_COLLISION_POLICY, minY: (MODEL_COLLISION_POLICY.minY - y) / yScale, maxY: (MODEL_COLLISION_POLICY.maxY - y) / yScale };
        const key = `${policy.minY},${policy.maxY}:` + (node.children ?? []).map(signature).join('|');
        let extracted = prototypeCache.get(key);
        if (!extracted) {
          extracted = await extractModelCollisions({ root: ROOT, model: { id, kind }, parsed, rootNodeIds: node.children, worldCoordinates: true,
            representation: 'object-hull', geometryCache, policy }); prototypeCache.set(key, extracted);
        }
        need(extracted.obstacles.length === 1, 'Visible furniture lost its low physical geometry', { id });
        const collider = transformLowHull(extracted.obstacles[0], matrix, oldId, kind); obstacles.push(collider); if (prior) matchedOld.add(oldId);
        const inverse = matrix.clone().invert(), oldLocal = prior?.points.map(([x, z]) => new Vector3(x, y, z).applyMatrix4(inverse)).map(p => [p.x, p.z]);
        const center = prior ? prior.points.reduce((p, q) => [p[0] + q[0] / prior.points.length, p[1] + q[1] / prior.points.length], [0, 0]) : null;
        furniture.push({ id, colliderId: oldId, kind, chunk: chunk.id, rootNode: rootId, priorPresent: !!prior,
          priorCenterToRuntimePlacementMetres: center ? number(Math.hypot(center[0] - matrix.elements[12], center[1] - matrix.elements[14])) : null,
          oldLocalBounds: oldLocal ? bounds(oldLocal) : null, actualLowLocalBounds: bounds(extracted.obstacles[0].points),
          actualMinY: collider.minY, actualMaxY: collider.maxY, actualHullVertices: collider.points.length,
          placement: { translation: node.translation, rotation: node.rotation, scale: node.scale } });
      } else if (category === 'bridge') {
        const result = await extractModelCollisions({ root: ROOT, model: { id }, parsed, rootNodeIds: node.children, worldCoordinates: true, geometryCache, representation: 'object-hull' });
        need(result.surfacePoints.length > 0, 'Bridge has no extracted side structure');
        const minimumAbsoluteLocalX = Math.min(...result.surfacePoints.map(p => Math.abs(p[0])));
        need(minimumAbsoluteLocalX >= 4.8, 'Bridge low geometry enters the actual carriageway', { minimumAbsoluteLocalX });
        const physical = [-1, 1].map(side => {
          const points = convexHull(result.surfacePoints.filter(p => p[0] * side > 0)); need(points.length >= 3, 'Bridge side is missing');
          return transformLowHull({ ...result.obstacles[0], points }, matrix, `bridge-${side}`, 'bridge');
        }); obstacles.push(...physical);
        bridges.push({ id, chunk: chunk.id, rootNode: rootId, ...result.stats, obstacles: physical.length, minimumAbsoluteLocalX,
          treatment: 'Independent left and right low continuous side structures; the carriageway is never enclosed in a hull.' });
      } else if (category === 'context') {
        async function visit(index, parent) {
          const n = doc.nodes[index], world = parent.clone().multiply(nodeMatrix(n));
          if (n.name === 'context-tunnel-base') for (const primitive of doc.meshes[n.mesh].primitives) {
            const geometry = await primitiveGeometry(doc, binary, primitive, ROOT), physical = tunnelBarriersFromGeometry(geometry.positions, geometry.indices, world);
            obstacles.push(...physical); tunnels.push({ chunk: chunk.id, meshNode: index, meshName: n.name, barriers: physical.length, sourceVertices: geometry.positions.length / 3 });
          }
          for (const child of n.children ?? []) await visit(child, world);
        }
        await visit(rootId, new Matrix4());
      } else throw new Error(`Unknown runtime object category: ${id}/${category}`);
    }
    progress({ chunk: chunk.id, completedChunks: ++chunkIndex, totalChunks: manifest.chunks.length, architecture: architecture.length, furniture: furniture.length, candidateObstacles: obstacles.length });
  }
  need(architecture.length === manifest.master.architectureModels, 'Missing runtime architecture roots');
  need(tunnels.length === 1 && tunnels[0].barriers > 1000 && bridges.length === 1, 'Missing physical bridge or tunnels');
  const missingFurniture = baseline.obstacles.filter(o => ['railing', 'plane-tree', 'streetlamp', 'road-sign', 'bench', 'litter-bin'].includes(o.kind) && !matchedOld.has(o.id));
  const evidence = { version: 2, generatedAt: new Date().toISOString(), sources, baseline: { file: PUBLIC_COLLISIONS, sha256: baselineSha, bytes: baselineRaw.length, obstacles: baseline.obstacles.length },
    coordinateContract: 'Actual runtime chunk scene roots, including all ancestor transforms; no district file or external context metadata imported.',
    methods: { architecture: '0.2 m exact low-triangle intersecting cells outside authoritative OSM walls; adjacent occupied runs only, no building hull.',
      furniture: 'One real placed object at a time: convex low-height physical envelope from its own immutable geometry; never merge distinct instances or openings.',
      bridge: 'Actual low surface points split into separate left/right continuous bridge side envelopes; clear carriageway verified before creating either hull.',
      tunnels: 'Actual six-vertex sloping base strip segments, topology-checked in the runtime context GLB; preserve each segment Y bounds and actual open ends.' },
    policy: MODEL_COLLISION_POLICY, architectureDetailsEnabled: includeArchitecture,
    totals: { obstacles: obstacles.length, authoritativeBuildingWalls: obstacles.filter(o => o.kind === 'building').length, architectureModels: architecture.length,
      architectureAdded: architecture.reduce((sum, m) => sum + m.obstacles, 0), physicalFurniture: furniture.length, bridgeObstacles: bridges.reduce((s, b) => s + b.obstacles, 0),
      actualTunnelSegments: tunnels.reduce((s, t) => s + t.barriers, 0), priorTunnelSegments: baseline.obstacles.filter(o => o.kind === 'tunnel').length, missingFurnitureRemoved: missingFurniture.length },
    baselineAudit: { removedMissingFurniture: missingFurniture.map(o => ({ id: o.id, kind: o.kind, reason: 'No corresponding root exists in any current runtime chunk.' })),
      maximumFurniturePlacementDifferenceMetres: Math.max(...furniture.map(o => o.priorCenterToRuntimePlacementMetres ?? 0)), furniture },
    architecture, bridges, tunnels,
    limits: ['Authoritative OSM wall interfaces retained.', 'Ground vehicle band remains the current collision engine band, 0.25 to 1.65 m above route elevation.',
      'Upper tunnel decoration is behind the complete low barriers; no overhead hull is projected down to the road.',
      'No geometry from unassembled district files or the 22 unassembled portal supports is included.'] };
  sourceCheck(sources); need(sha256(fs.readFileSync(path.join(ROOT, PUBLIC_COLLISIONS))) === baselineSha, 'Baseline collision file changed during extraction');
  const data = { version: 1, coordinates: 'metres, X east, Y up, Z south', obstacles }, candidate = { data, evidence };
  writeVerified(CANDIDATE, JSON.stringify(candidate));
  progress({ candidateReady: true, candidateFile: CANDIDATE, totals: evidence.totals }); return candidate;
}

export function verifyRuntimeCollisionCandidate({ progress = console.log } = {}) {
  const candidateBytes = fs.readFileSync(path.join(ROOT, CANDIDATE)), candidate = JSON.parse(candidateBytes), { data, evidence } = candidate;
  sourceCheck(evidence.sources); const city = jsonRead('public/tour-city.json'), cars = jsonRead('src/tour/cars.json');
  const width = Math.max(...cars.map(c => c.dimensions[1])) / 1000, length = Math.max(...cars.map(c => c.dimensions[0])) / 1000;
  need(new Set(data.obstacles.map(o => o.id)).size === data.obstacles.length, 'Duplicate collider IDs');
  for (const o of data.obstacles) need(o.points.length >= 3 && [o.minY, o.maxY, ...o.points.flat()].every(Number.isFinite) && o.maxY >= o.minY, 'Invalid candidate collider', { id: o.id });
  const route = city.routes[0], track = new Path(route.points, route.closed, route.elevations), world = new CollisionWorld(data.obstacles), checks = [];
  const check = (name, callback) => { const started = Date.now(); const result = callback(); checks.push({ name, passed: true, milliseconds: Date.now() - started, result }); progress({ check: name, passed: true }); };
  check('full-route-forward-sweep', () => { const result = guardRuntimeRoute(city, data.obstacles); need(result.passed, 'Actual geometry blocks the route', result.failures.slice(0, 15)); return result; });
  check('actual-furniture-and-railings-clear-of-every-drivable-road', () => {
    const roads = new RoadClearance(city.roads), kinds = new Set(['railing', 'plane-tree', 'streetlamp', 'road-sign', 'bench', 'litter-bin']); let objects = 0;
    for (const o of data.obstacles.filter(o => kinds.has(o.kind))) {
      for (let i = 0; i < o.points.length; i++) need(!roads.conflicts(o.points[i], o.points[(i + 1) % o.points.length], 0, 0).length, 'Actual low furniture enters a drivable road', { id: o.id });
      objects++;
    }
    return { objects, intrusions: 0, polygonEdgesCheckedAgainstActualRoadWidths: true };
  });
  check('all-real-benches-fix-missed-ends-and-empty-space-blocking', () => {
    const priorBytes = fs.readFileSync(path.join(ROOT, PUBLIC_COLLISIONS));
    need(sha256(priorBytes) === evidence.baseline.sha256, 'Baseline changed before the real-bench comparison');
    const prior = new Map(JSON.parse(priorBytes).obstacles.map(o => [o.id, o])), current = new Map(data.obstacles.map(o => [o.id, o]));
    let benches = 0;
    for (const row of evidence.baselineAudit.furniture.filter(o => o.kind === 'bench')) {
      const matrix = nodeMatrix(row.placement), before = new CollisionWorld([prior.get(row.colliderId)]), after = new CollisionWorld([current.get(row.colliderId)]);
      const sample = (x, z) => { const p = new Vector3(x, 0, z).applyMatrix4(matrix); return { x: p.x, z: p.z, y: 0, heading: 0 }; };
      need(before.occupied(sample(0, .85), .025, .025) && !after.occupied(sample(0, .85), .025, .025), 'A bench retains its former invisible rear extension', { id: row.id });
      need(!before.occupied(sample(.8, 0), .025, .025) && after.occupied(sample(.8, 0), .025, .025), 'A real bench end remains unprotected', { id: row.id }); benches++;
    }
    return { benches, correctedMissedEnds: benches, removedEmptySpaceBlockers: benches, probeMetres: .025 };
  });
  check('full-route-reverse-sweep-and-height-isolation', () => {
    let samples = 0, groundSamples = 0, undergroundSamples = 0;
    for (let d = track.total; d > 0; d--) {
      const from = track.pose(d), desired = track.pose(Math.max(0, d - 1)), moved = world.move(from, desired, width, length);
      need(!moved.contacts.length && Math.hypot(moved.pose.x - desired.x, moved.pose.z - desired.z) < .001 && !world.occupied(from, width, length), 'Reverse route is blocked', { d, contacts: moved.contacts });
      samples++; if (from.y < -5.9) undergroundSamples++; else if (Math.abs(from.y) < 1e-6) groundSamples++;
    }
    need(groundSamples > 1000 && undergroundSamples > 1000, 'Route did not cover both levels');
    const tunnel = data.obstacles.find(o => o.kind === 'tunnel' && o.maxY < -15), point = tunnel.points.reduce((p, q) => [p[0] + q[0] / tunnel.points.length, p[1] + q[1] / tunnel.points.length], [0, 0]);
    const isolated = new CollisionWorld([tunnel]); need(!isolated.occupied({ x: point[0], z: point[1], y: 0, heading: 0 }, width, length), 'Underground barrier blocks ground traffic');
    need(isolated.occupied({ x: point[0], z: point[1], y: tunnel.minY, heading: 0 }, width, length), 'Actual underground barrier has no contact');
    return { samples, groundSamples, undergroundSamples, minimumRouteY: -18, sameXZSeparatedByHeight: true };
  });
  check('real-geometry-forward-reverse-oblique-impact-matrix', () => {
    const edgeLength = o => Math.max(...o.points.map((p, i) => Math.hypot(p[0] - o.points[(i + 1) % o.points.length][0], p[1] - o.points[(i + 1) % o.points.length][1])));
    const fixtures = [...new Set(data.obstacles.map(o => o.kind))].map(kind => data.obstacles.filter(o => o.kind === kind).sort((a, b) => edgeLength(b) - edgeLength(a))[0]); let cases = 0;
    for (const o of fixtures) {
      let index = 0; for (let i = 1; i < o.points.length; i++) if (Math.hypot(o.points[i][0] - o.points[(i + 1) % o.points.length][0], o.points[i][1] - o.points[(i + 1) % o.points.length][1]) > Math.hypot(o.points[index][0] - o.points[(index + 1) % o.points.length][0], o.points[index][1] - o.points[(index + 1) % o.points.length][1])) index = i;
      const a = o.points[index], b = o.points[(index + 1) % o.points.length], center = o.points.reduce((p, q) => [p[0] + q[0] / o.points.length, p[1] + q[1] / o.points.length], [0, 0]);
      const edge = Math.atan2(b[0] - a[0], b[1] - a[1]);
      for (const angle of [0, .45]) for (const reverse of [false, true]) for (const speed of [20, 50, 80]) for (const hz of [10, 20, 60]) {
        const travel = edge + Math.PI / 2 + angle, direction = [Math.sin(travel), Math.cos(travel)], isolated = new CollisionWorld([o]);
        let pose = { x: center[0] - direction[0] * 15, z: center[1] - direction[1] * 15, y: o.minY, heading: travel + (reverse ? Math.PI : 0) }, hit = false;
        for (let frame = 0; frame < hz * 8 && !hit; frame++) {
          const moved = isolated.move(pose, { ...pose, x: pose.x + direction[0] * speed / 3.6 / hz, z: pose.z + direction[1] * speed / 3.6 / hz }, width, length); pose = moved.pose; hit = moved.contacts.length > 0;
        }
        need(hit && !isolated.occupied(pose, width, length), 'Actual collider failed an oblique/reverse impact', { id: o.id, angle, reverse, speed, hz }); cases++;
      }
    }
    return { cases, fixtureKinds: fixtures.map(o => o.kind), speedsKmh: [20, 50, 80], framesHz: [10, 20, 60], angles: [0, .45], directions: ['forward', 'reverse'] };
  });
  check('three-continuous-real-laps', () => {
    const drive = new Drive(route); drive.vehicleWidth = width; drive.vehicleLength = length; drive.wheelbase = Math.max(...cars.map(c => c.wheelbase)) / 1000;
    drive.collision = world; drive.start('auto'); drive.rate = 3; let frame = 0, lastAdvance = 0, advanced = 0;
    for (; frame < 50000 && drive.laps < 3; frame++) {
      drive.update(.05, { throttle: false, brake: false, steer: 0 }); const current = drive.laps * track.total + drive.distance;
      if (current > advanced + .01) { advanced = current; lastAdvance = frame; }
      need(frame - lastAdvance < 200 && drive.collisions === 0, 'Automatic drive hit/stalled on actual model geometry', { frame, distance: drive.distance, pose: drive.pose, lastImpact: drive.lastImpact });
    }
    need(drive.laps === 3, 'Three actual laps did not complete'); return { laps: drive.laps, frames: frame, collisions: drive.collisions, travelledMetres: drive.travelled };
  });
  sourceCheck(evidence.sources);
  const report = { version: 1, verifiedAt: new Date().toISOString(), candidateSha256: sha256(candidateBytes), colliderSha256: sha256(JSON.stringify(data)), sources: evidence.sources,
    executionSources: Object.fromEntries(['src/tour/collision.ts', 'src/tour/drive.ts', 'src/tour/cars.json', 'scripts/model_collision_runtime.mjs',
      'scripts/model_collision_geometry.mjs', 'node_modules/three/examples/jsm/libs/draco/gltf/draco_wasm_wrapper.js',
      'node_modules/three/examples/jsm/libs/draco/gltf/draco_decoder.wasm'].map(file => [file, { sha256: sha256(fs.readFileSync(path.join(ROOT, file))) }])), checks, passed: true };
  writeVerified(VERIFICATION, JSON.stringify(report, null, 2) + '\n'); return report;
}

export function publishRuntimeCollisionCandidate() {
  const raw = fs.readFileSync(path.join(ROOT, CANDIDATE)), candidate = JSON.parse(raw), report = jsonRead(VERIFICATION);
  need(report.passed && report.candidateSha256 === sha256(raw), 'Candidate lacks its exact successful verification');
  sourceCheck(candidate.evidence.sources); sourceCheck(report.executionSources);
  const previous = fs.readFileSync(path.join(ROOT, PUBLIC_COLLISIONS)); need(sha256(previous) === candidate.evidence.baseline.sha256, 'Current collision baseline changed before publication');
  const stamp = new Date().toISOString().replace(/[:.]/g, '-'), backup = `backups/model-collisions/${stamp}`; fs.mkdirSync(path.join(ROOT, backup), { recursive: true });
  writeVerified(`${backup}/collisions.json`, previous);
  writeVerified(`${backup}/receipt.json`, JSON.stringify(candidate.evidence.baseline, null, 2) + '\n');
  const bytes = JSON.stringify(candidate.data); need(sha256(bytes) === report.colliderSha256, 'Verified collider payload changed');
  sourceCheck(candidate.evidence.sources); writeVerified(PUBLIC_COLLISIONS, bytes);
  const receipt = { publishedAt: new Date().toISOString(), sourceManifestSha256: candidate.evidence.sources[MANIFEST].sha256, collisionSha256: sha256(bytes),
    bytes: Buffer.byteLength(bytes), obstacles: candidate.data.obstacles.length, verifiedCandidateSha256: report.candidateSha256, previousBackup: `${backup}/collisions.json`, verification: VERIFICATION };
  writeVerified(RECEIPT, JSON.stringify(receipt, null, 2) + '\n'); return receipt;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--candidate')) await createRuntimeCollisionCandidate({ expectedManifestSha: process.argv.find(v => v.startsWith('--expected-manifest='))?.split('=')[1], includeArchitecture: process.argv.includes('--include-architecture') });
  else if (process.argv.includes('--verify')) console.log(JSON.stringify(verifyRuntimeCollisionCandidate()));
  else if (process.argv.includes('--publish')) console.log(JSON.stringify(publishRuntimeCollisionCandidate()));
  else throw new Error('Specify one of --candidate, --verify or --publish');
}
