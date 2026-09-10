import { test } from "node:test";
import assert from "node:assert/strict";
// @ts-expect-error Pure geometry script is also the offline GLB repair entrypoint.
import { subtractConvexXZ, triangleArea3D, isGroundSurface, portalOpenings } from "../scripts/repair_tunnel_surfaces.mjs";
type Vertex = number[];
const opening = [[1, 0, 1], [2, 0, 1], [2, 0, 2], [1, 0, 2]];
const area = (polygons: Vertex[][]) => polygons.reduce((sum, polygon) => sum + polygon.slice(1, -1).reduce((n, p, i) => n + triangleArea3D(polygon[0], p, polygon[i + 2]), 0), 0);

test("portal subtraction cuts a contained opening even when the triangle centroid is outside", () => {
  const triangle = [[0, .125, 0], [10, .125, 0], [0, .125, 10]];
  assert.ok(Math.abs(area(subtractConvexXZ(triangle, opening)) - 49) < 1e-8);
  assert.ok(Math.abs(area(subtractConvexXZ([...triangle].reverse(), [...opening].reverse())) - 49) < 1e-8);
});

test("triangle clipping preserves affine UVs and normals at actual edge intersections", () => {
  const triangle = [[0, .125, 0, 0, 1, 0, 0, 0], [10, .125, 0, 0, 1, 0, 5, 0], [0, .125, 10, 0, 1, 0, 0, 2.5]];
  const result: Vertex[][] = subtractConvexXZ(triangle, opening);
  for (const p of result.flat()) {
    assert.ok(Math.abs(p[6] - p[0] / 2) < 1e-8);
    assert.ok(Math.abs(p[7] - p[2] / 4) < 1e-8);
    assert.deepEqual(p.slice(3, 6), [0, 1, 0]);
    assert.equal(p[1], .125);
  }
});

test("overlapping strip subtraction removes the union once and preserves vertical boundary faces", () => {
  const triangle = [[0, 0, 0], [10, 0, 0], [0, 0, 10]];
  const a = subtractConvexXZ(triangle, opening);
  const b = a.flatMap((p: Vertex[]) => subtractConvexXZ(p, [[1.5, 0, 1], [2.5, 0, 1], [2.5, 0, 2], [1.5, 0, 2]]));
  assert.ok(Math.abs(area(b) - 48.5) < 1e-8);
  const vertical = [[1, .07, 1], [1, .23, 1], [1, .07, 2]];
  assert.ok(Math.abs(area(subtractConvexXZ(vertical, opening)) - triangleArea3D(...vertical)) < 1e-10);
});

test("surface eligibility never removes sloping underground lane markings or tunnel structure", () => {
  assert.equal(isGroundSurface("context-markings", [[0, .15, 0], [1, .15, 0], [0, .15, 1]]), true);
  assert.equal(isGroundSurface("context-markings", [[0, -.1, 0], [1, -.1, 0], [0, -.2, 1]]), false);
  assert.equal(isGroundSurface("context-markings", [[0, .132, 0], [1, .132, 0], [0, .132, 1]]), false);
  assert.equal(isGroundSurface("context-tunnel-floor", [[0, .12, 0], [1, .12, 0], [0, .12, 1]]), false);
  assert.equal(isGroundSurface("context-tunnel-base", [[0, .07, 0], [1, .23, 0], [0, .07, 1]]), false);
});

test("portal openings follow curved Path elevations and stop before the deep crossing", () => {
  const route = { points: [[0, 0], [0, 100], [50, 200], [50, 300], [0, 400]], elevations: [0, -10, -18, -10, 0], closed: false, tunnels: [{ start: 0, end: 423.60679774997897, name: "test", depth: 18 }] };
  const { portals, drivePath } = portalOpenings(route);
  assert.equal(portals.length, 2);
  assert.ok(Math.abs(drivePath.at(portals[0].end).y + 6.5) < 1e-8);
  assert.ok(Math.abs(drivePath.at(portals[1].start).y + 6.5) < 1e-8);
  for (const p of portals) for (const q of p.quads) {
    assert.ok(q.d1 - q.d0 <= 5 + 1e-8);
    assert.ok(q.d1 <= 100 || q.d0 >= 300, "Deep normal roads must not be included in a portal opening");
  }
});
