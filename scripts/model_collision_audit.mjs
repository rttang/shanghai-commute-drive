/** Run with node --import tsx scripts/model_collision_audit.mjs.
 * Defaults to read-only. --models=id,id bounds a diagnostic to selected GLBs.
 * prepare_collisions.mjs owns the final write after the complete route guard. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { CollisionWorld } from '../src/tour/collision.ts';
import { Path } from '../src/tour/drive.ts';
import { extractModelCollisions, MODEL_COLLISION_POLICY, sha256 } from './model_collision_geometry.mjs';

export const ROOT = fileURLToPath(new URL('../', import.meta.url));
export const EVIDENCE = 'docs/evidence/tourism/model-collision-audit.json';
const DISTRICTS = ['bund', 'pudong', 'north-bund', 'loop-frontages'];
export async function auditModelCollisions({ root = ROOT, modelIds, progress = () => {} } = {}) {
  const sources = {}, manifests = DISTRICTS.map(d => `public/streets/districts/${d}/manifest.json`);
  const readSource = file => {
    const bytes = fs.readFileSync(path.join(root, file));
    sources[file] = { sha256: sha256(bytes), bytes: bytes.length }; return bytes;
  };
  for (const file of ['scripts/model_collision_geometry.mjs', 'scripts/model_collision_audit.mjs',
    'scripts/prepare_collisions.mjs', 'scripts/assemble_street_master.py', 'scripts/street_glb.py',
    'src/tour/collision.ts', 'src/tour/drive.ts', 'src/tour/cars.json',
    'node_modules/three/examples/jsm/libs/draco/gltf/draco_wasm_wrapper.js',
    'node_modules/three/examples/jsm/libs/draco/gltf/draco_decoder.wasm']) readSource(file);
  const city = JSON.parse(readSource('public/tour-city.json')), byId = new Map(city.buildings.map(b => [b.id, b]));
  const entries = manifests.flatMap(file => JSON.parse(readSource(file)).models.map(model => ({ model, manifest: file })));
  if (new Set(entries.map(e => e.model.id)).size !== entries.length) throw new Error('Duplicate district model IDs');
  const models = [], obstacles = [];
  for (const { model, manifest } of entries) {
    if (modelIds && !modelIds.has(model.id)) continue;
    const file = `public/${model.file.replace(/^\//, '')}`, raw = readSource(file);
    if (model.sha256 && model.sha256 !== sources[file].sha256) throw new Error(`Manifest hash is stale: ${model.id}`);
    if (model.bytes !== undefined && model.bytes !== raw.length) throw new Error(`Manifest size is stale: ${model.id}`);
    const footprints = (model.ways ?? []).map(id => byId.get(id)?.points).filter(Boolean);
    const extracted = await extractModelCollisions({ root, model, footprints, raw });
    obstacles.push(...extracted.obstacles);
    const row = { id: model.id, manifest, file, sha256: sources[file].sha256, bytes: raw.length,
      center: model.center, heading: model.heading ?? 0, assemblyY: MODEL_COLLISION_POLICY.assemblyY,
      footprintWays: model.ways ?? [], matchedFootprints: footprints.length,
      ...extracted.stats, occupiedCells: extracted.cells.size, addedObstacles: extracted.obstacles.length,
      occupiedAreaSquareMetres: extracted.cells.size * MODEL_COLLISION_POLICY.cellMetres ** 2 };
    models.push(row); progress({ id: model.id, completed: models.length, total: modelIds ? modelIds.size : entries.length, obstacles: row.addedObstacles });
  }
  // Abort before publishing if an authoring process changes a manifest or GLB.
  assertSourcesStable(sources, root);
  return { obstacles, evidence: { version: 1, generatedAt: new Date().toISOString(),
    method: 'Actual static GLB triangle clipping in the ground vehicle height slab; intersecting 0.2 m cells; exactly matching occupied horizontal runs merged vertically. No hulls or gap filling. Existing map obstacles retained.',
    policy: MODEL_COLLISION_POLICY, sources, completeDistrictCoverage: !modelIds,
    totals: { models: models.length, triangles: models.reduce((n, m) => n + m.triangles, 0),
      lowTriangles: models.reduce((n, m) => n + m.lowTriangles, 0),
      compressedPrimitives: models.reduce((n, m) => n + m.compressedPrimitives, 0),
      addedObstacles: obstacles.length, modelsBeyondOldFootprint: models.filter(m => m.maximumBeyondFootprintMetres > .12).length }, models,
    limits: ['Ground vehicle vertical band only; high canopies, underground floors and geometry below the existing 0.25 m vehicle clearance excluded.',
      'Each occupied cell intersects real geometry; conservative horizontal expansion is bounded by 0.283 m. Small openings narrower than this may narrow further.',
      'Original map walls remain authoritative inside footprints; no new interior navigation or collision removal.',
      'District GLBs and assembler placement contract are checked; final master assembly and browser validation belong to the coordinated final acceptance.'] } };
}

export function assertSourcesStable(sources, root = ROOT) {
  for (const [file, expected] of Object.entries(sources)) {
    if (sha256(fs.readFileSync(path.join(root, file))) !== expected.sha256) throw new Error(`Input changed during collision generation: ${file}`);
  }
}

export function guardRuntimeRoute(city, obstacles, root = ROOT) {
  const cars = JSON.parse(fs.readFileSync(path.join(root, 'src/tour/cars.json')));
  const width = Math.max(...cars.map(c => c.dimensions[1])) / 1000, length = Math.max(...cars.map(c => c.dimensions[0])) / 1000;
  const world = new CollisionWorld(obstacles), failures = []; let samples = 0;
  for (const route of city.routes) {
    const track = new Path(route.points, route.closed, route.elevations);
    for (let distance = 0; distance < track.total; distance += 1) {
      const from = track.pose(distance), to = track.pose(Math.min(track.total, distance + 1));
      const result = world.move(from, to, width, length); samples++;
      if (result.contacts.length || world.occupied(from, width, length) || Math.hypot(result.pose.x - to.x, result.pose.z - to.z) > .001)
        failures.push({ routeId: route.id, distance, pose: from, contacts: result.contacts });
    }
  }
  return { passed: !failures.length, samples, width, length, failures };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const filter = process.argv.find(v => v.startsWith('--models='))?.slice(9);
  const { obstacles, evidence } = await auditModelCollisions({ modelIds: filter ? new Set(filter.split(',')) : undefined,
    progress: row => { if (row.completed % 10 === 0 || filter) console.error(JSON.stringify(row)); } });
  const city = JSON.parse(fs.readFileSync(path.join(ROOT, 'public/tour-city.json')));
  const base = JSON.parse(fs.readFileSync(path.join(ROOT, 'public/streets/collisions.json'))).obstacles.filter(o => !o.id.startsWith('model-solid-'));
  evidence.routeGuard = guardRuntimeRoute(city, [...base, ...obstacles]);
  console.log(JSON.stringify(evidence));
  if (!evidence.routeGuard.passed) process.exitCode = 1;
}
