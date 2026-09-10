import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { CollisionWorld } from '../src/tour/collision';
import { extractModelCollisions, lowSlice, rasterizeSlice, mergeCells, parseGlb, MODEL_COLLISION_POLICY as policy } from '../scripts/model_collision_geometry.mjs';

test('ground geometry slicing excludes elevated canopy, underground floor and ground paving', () => {
  for (const y of [3.4, -3, .12, .24]) assert.deepEqual(lowSlice([[0, y, 0], [5, y, 0], [0, y, 5]]), []);
  assert.equal(lowSlice([[0, .32, 0], [5, .32, 0], [0, .32, 5]]).length, 3);
});

test('long vertical faces crossing the entire car height remain despite having no vertices in the slab', () => {
  const cut = lowSlice([[0, 0, 0], [0, 8, 0], [2, 8, 0]]);
  assert.ok(cut.length >= 3);
  assert.ok(cut.every(p => p[1] >= policy.minY - 1e-9 && p[1] <= policy.maxY + 1e-9));
});

test('triangle rasterization preserves an open courtyard and separate pillars without a convex hull', () => {
  const cells = new Map();
  for (const x of [-2, 2]) {
    rasterizeSlice([[x, .5, -1], [x + .4, .5, -1], [x, .5, 1]], cells);
    rasterizeSlice([[x + .4, .5, -1], [x + .4, .5, 1], [x, .5, 1]], cells);
  }
  const world = new CollisionWorld(mergeCells(cells, 'pillars'));
  assert.equal(world.occupied({ x: 0, z: 0, heading: 0, y: 0 }, 1.8, 1), false);
  assert.equal(world.occupied({ x: 2.2, z: 0, heading: 0, y: 0 }, .1, .1), true);
  assert.equal(world.occupied({ x: 2.2, z: 0, heading: 0, y: -5 }, .1, .1), false);
});

test('an oblique narrow surface occupies only touched cells and does not fill its bounding box', () => {
  const cells = new Map();
  rasterizeSlice([[0, .5, 0], [4, .5, 4], [4, .8, 4]], cells);
  const world = new CollisionWorld(mergeCells(cells, 'diagonal'));
  assert.equal(world.occupied({ x: .5, z: 3.5, heading: 0 }, .1, .1), false);
  assert.equal(world.occupied({ x: 2, z: 2, heading: 0 }, .1, .1), true);
  assert.ok(cells.size < 70);
});

test('cell merging preserves an L shaped opening exactly and does not introduce new cells', () => {
  const cells = new Map();
  for (const [x, z] of [[0, 0], [1, 0], [2, 0], [0, 1], [0, 2]])
    cells.set(`${x},${z}`, { x, z, minY: .3, maxY: 1 });
  const rectangles = mergeCells(cells, 'concave');
  const area = rectangles.reduce((sum, r) => sum + (r.points[1][0] - r.points[0][0]) * (r.points[2][1] - r.points[1][1]), 0);
  assert.ok(Math.abs(area - 5 * policy.cellMetres ** 2) < 1e-10);
  assert.equal(new CollisionWorld(rectangles).occupied({ x: .5, z: .5, heading: 0 }, .05, .05), false);
});

test('entirely interior cells need no duplicate collider while protruding steps remain', () => {
  const cells = new Map(), footprint = [[-5, -5], [0, -5], [0, 5], [-5, 5]];
  rasterizeSlice([[-2, .4, -1], [2, .4, -1], [-2, .4, 1]], cells, policy, [footprint]);
  assert.equal(cells.has('-8,0'), false);
  assert.ok([...cells.values()].some(cell => cell.x > 0));
});

test('detail already covered by the original wall thickness creates no new obstacle', () => {
  const cells = new Map(), footprint = [[-5, -5], [0, -5], [0, 5], [-5, 5]];
  rasterizeSlice([[.018, .3, -1], [.018, 1.2, -1], [.018, 1.2, 1]], cells, policy, [footprint]);
  assert.equal(cells.size, 0);
});

test('invalid and truncated GLBs fail closed', () => {
  assert.throws(() => parseGlb(Buffer.alloc(24)), /Invalid/);
});

test('real compressed signal tower decodes into ground surfaces with the runtime assembly placement', async () => {
  const root = new URL('../', import.meta.url).pathname;
  const manifest = JSON.parse(readFileSync(new URL('../public/streets/districts/bund/manifest.json', import.meta.url), 'utf8'));
  const model = manifest.models.find((m: { id: string }) => m.id === 'signal-tower');
  const raw = readFileSync(new URL(`../public/${model.file.replace(/^\//, '')}`, import.meta.url));
  const result = await extractModelCollisions({ root: decodeURIComponent(root), model, raw });
  assert.ok(result.stats.triangles > 1000);
  assert.ok(result.stats.lowTriangles > 0);
  assert.ok(result.obstacles.length > 0);
  for (const obstacle of result.obstacles) {
    assert.ok(obstacle.minY >= policy.minY - 1e-8 && obstacle.maxY <= policy.maxY + 1e-8);
    for (const point of obstacle.points) assert.ok(Math.hypot(point[0] - model.center[0], point[1] - model.center[1]) < 30);
  }
});
