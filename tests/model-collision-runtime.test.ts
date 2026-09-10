import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Matrix4 } from 'three';
import { CollisionWorld, rectangle } from '../src/tour/collision';
import { transformLowHull, tunnelBarriersFromGeometry } from '../scripts/model_collision_runtime.mjs';
import type { ModelObstacle } from '../scripts/model_collision_geometry.mjs';

test('a real bench hull follows local X and removes the former empty-space blocker', () => {
  const local: ModelObstacle = { id: 'bench', kind: 'bench', minY: .3, maxY: 1.1, points: [[-.9, -.36], [.9, -.36], [.9, .36], [-.9, .36]] };
  const actual = transformLowHull(local, new Matrix4().makeTranslation(100, .14, -20), 'furniture-27', 'bench');
  const fixed = new CollisionWorld([actual]);
  const legacy = new CollisionWorld([{ ...actual, points: rectangle(100, -20, 0, 1.1, 2) }]);
  assert.equal(fixed.occupied({ x: 100.8, z: -20, y: 0, heading: 0 }, .05, .05), true);
  assert.equal(legacy.occupied({ x: 100.8, z: -20, y: 0, heading: 0 }, .05, .05), false);
  assert.equal(fixed.occupied({ x: 100, z: -19.15, y: 0, heading: 0 }, .05, .05), false);
  assert.equal(legacy.occupied({ x: 100, z: -19.15, y: 0, heading: 0 }, .05, .05), true);
  assert.ok(Math.abs(actual.minY - .44) < 1e-8);
});

test('separate real railing modules preserve their actual opening and rotation', () => {
  const module: ModelObstacle = { id: 'rail', kind: 'railing', minY: .25, maxY: 1.3, points: [[-1.5, -.095], [1.5, -.095], [1.5, .095], [-1.5, .095]] };
  const left = transformLowHull(module, new Matrix4().makeTranslation(-4, 0, 0), 'rail-left', 'railing');
  const right = transformLowHull(module, new Matrix4().makeTranslation(4, 0, 0), 'rail-right', 'railing');
  assert.equal(new CollisionWorld([left, right]).occupied({ x: 0, z: 0, y: 0, heading: 0 }, 1.96, 4.99), false);
  const turned = transformLowHull(module, new Matrix4().makeRotationY(Math.PI / 2), 'rail-turned', 'railing');
  const width = Math.max(...turned.points.map(p => p[0])) - Math.min(...turned.points.map(p => p[0]));
  const length = Math.max(...turned.points.map(p => p[1])) - Math.min(...turned.points.map(p => p[1]));
  assert.ok(Math.abs(width - .19) < 1e-7 && Math.abs(length - 3) < 1e-7);
});

const stripPositions = new Float32Array([3.25, -18, 0, 3.47, -17.32, 0, 4.2, -17.32, 0, 3.25, -18.2, 5, 3.47, -17.52, 5, 4.2, -17.52, 5]);
const stripIndices = new Uint32Array([0, 1, 4, 0, 4, 3, 1, 2, 5, 1, 5, 4]);
test('actual sloping tunnel barrier keeps its rendered ends and vertical layer', () => {
  const [barrier] = tunnelBarriersFromGeometry(stripPositions, stripIndices);
  const world = new CollisionWorld([barrier]);
  assert.ok(barrier.minY < -18.19 && barrier.maxY < -17.31);
  assert.equal(world.occupied({ x: 3.7, z: 2.5, y: -18, heading: 0 }, .2, .2), true);
  assert.equal(world.occupied({ x: 3.7, z: 2.5, y: 0, heading: 0 }, .2, .2), false);
  assert.equal(world.occupied({ x: 3.7, z: 5.4, y: -18, heading: 0 }, .2, .2), false);
});

test('corrupt tunnel topology fails instead of manufacturing an invisible barrier', () => {
  const corrupted = stripIndices.slice(); corrupted[3] = 2;
  assert.throws(() => tunnelBarriersFromGeometry(stripPositions, corrupted), /topology changed/);
});
