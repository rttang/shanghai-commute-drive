import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import type { City, Point, Road } from "../src/tour/data";
import {
  RoadClearance,
  PLACEMENT_CLEARANCE as policy,
  pointSegmentDistance,
  segmentDistance,
  polylineDistance,
  railingEndpoints,
  type StreetPlacements,
} from "../src/tour/road-clearance";

const mapBytes = readFileSync(
  new URL("../public/tour-city.json", import.meta.url),
);
const city = JSON.parse(mapBytes.toString()) as City;
const placements = JSON.parse(
  readFileSync(
    new URL("../public/streets/master/placements.json", import.meta.url),
    "utf8",
  ),
) as StreetPlacements;
const road = (
  id: number,
  points: Point[],
  width = 8,
  extra: Partial<Road> = {},
): Road => ({
  id,
  points,
  width,
  name: "test road",
  kind: "tertiary",
  foot: false,
  bridge: false,
  tunnel: false,
  ...extra,
});

test("exact segment distance catches interior crossings, endpoints and collinear overlap", () => {
  assert.equal(segmentDistance([-10, 0], [10, 0], [0, -10], [0, 10]), 0);
  assert.equal(segmentDistance([0, 0], [10, 0], [3, 0], [20, 0]), 0);
  assert.equal(segmentDistance([0, 0], [10, 0], [12, 0], [20, 0]), 2);
  assert.equal(segmentDistance([3, 4], [3, 4], [-10, 0], [10, 0]), 4);
  assert.equal(segmentDistance([0, 0], [10, 0], [10, 0], [10, 10]), 0);
  assert.equal(pointSegmentDistance([3, 4], [0, 0], [0, 0]), 5);
});

test("a safe railing centre never overrides an unsafe endpoint or interior segment", () => {
  const roads = new RoadClearance([
    road(
      1,
      [
        [0, -50],
        [0, 50],
      ],
      4,
    ),
  ]);
  const a: Point = [-8, 0],
    b: Point = [-1, 0],
    center: Point = [-4.5, 0];
  assert.equal(roads.clear(center, center, 0.2, 0.5), true);
  assert.equal(roads.clear(a, b, 0.2, 0.5), false);
  assert.equal(roads.clear([-10, 5], [10, 5], 0.2, 0.5), false);
});

test("actual road width, solid thickness and safety margins govern placement, including bridge roads", () => {
  const roads = new RoadClearance([
    road(
      1,
      [
        [0, -100],
        [0, 100],
      ],
      14,
      { bridge: true },
    ),
  ]);
  assert.equal(roads.clear([7.6, -10], [7.6, 10], 0.2, 0.5), false);
  assert.equal(roads.clear([7.8, -10], [7.8, 10], 0.2, 0.5), true);
  const ignored = new RoadClearance([
    road(
      2,
      [
        [0, -100],
        [0, 100],
      ],
      14,
      { tunnel: true },
    ),
    road(
      3,
      [
        [0, -100],
        [0, 100],
      ],
      14,
      { foot: true },
    ),
  ]);
  assert.equal(ignored.clear([0, -10], [0, 10]), true);
});

test("curb panels leave junction openings while safe portions of the same roadside remain", () => {
  const roads = new RoadClearance([
    road(
      1,
      [
        [0, -100],
        [0, 100],
      ],
      8,
    ),
    road(
      2,
      [
        [-100, 0],
        [100, 0],
      ],
      10,
    ),
  ]);
  const self = new Set([1]);
  assert.equal(
    roads.clear(
      [4.42, 1],
      [4.42, 3],
      policy.curbHalfWidth,
      policy.curbJunctionMargin,
      self,
    ),
    false,
  );
  assert.equal(
    roads.clear(
      [4.42, 8],
      [4.42, 10],
      policy.curbHalfWidth,
      policy.curbJunctionMargin,
      self,
    ),
    true,
  );
  assert.equal(
    roads.clear([4.42, 8], [4.42, 10], policy.curbHalfWidth, policy.curbMargin),
    true,
  );
});

test("spatial road index agrees with exhaustive road-segment checks across grid boundaries", () => {
  const source = [
    road(
      1,
      [
        [-150, -90],
        [130, 80],
      ],
      9.6,
    ),
    road(
      2,
      [
        [-80, 130],
        [145, -75],
      ],
      18,
    ),
    road(
      3,
      [
        [-64, -150],
        [-64, 150],
      ],
      6.4,
    ),
    road(
      4,
      [
        [110, -64],
        [-120, -64],
      ],
      3.2,
    ),
  ];
  const roads = new RoadClearance(source);
  for (let i = 0; i < 300; i++) {
    const a: Point = [-160 + ((i * 37) % 320), -160 + ((i * 83) % 320)];
    const b: Point = [a[0] + ((i * 13) % 41) - 20, a[1] + ((i * 17) % 51) - 25];
    const radius = (i % 4) * 0.3,
      margin = 0.5;
    const expected = source
      .filter(
        (r) =>
          segmentDistance(a, b, r.points[0], r.points[1]) <
          r.width / 2 + radius + margin - 1e-7,
      )
      .map((r) => r.id)
      .sort();
    assert.deepEqual(
      roads
        .conflicts(a, b, radius, margin)
        .map((r) => r.roadId)
        .sort(),
      expected,
      `query ${i}`,
    );
  }
});

test("all generated railing and curb solids remain outside every drivable road envelope", () => {
  assert.equal(placements.version, 1);
  assert.equal(
    placements.diagnostics.sourceMapSha256,
    createHash("sha256").update(mapBytes).digest("hex"),
  );
  const roads = new RoadClearance(city.roads);
  assert.ok(
    placements.railings.length > 500,
    "safe waterfront railings must be retained",
  );
  assert.ok(
    placements.curbs.length > 1000,
    "roadside detail must not disappear to pass clearance",
  );
  assert.ok(Number(placements.diagnostics.railingsRemovedForRoads) > 0);
  assert.ok(Number(placements.diagnostics.curbsRemovedForRoads) > 0);
  for (const [i, rail] of placements.railings.entries()) {
    assert.ok(
      [rail.x, rail.z, rail.heading, rail.length].every(Number.isFinite),
    );
    assert.ok(rail.length > 0 && rail.length <= policy.railLength + 1e-6);
    const [a, b] = railingEndpoints(rail);
    assert.deepEqual(
      roads.conflicts(a, b, policy.railHalfDepth, policy.railMargin),
      [],
      `railing ${i}`,
    );
    assert.ok(
      city.routes.some(
        (r) => polylineDistance([rail.x, rail.z], r.points) <= policy.nearWater,
      ),
    );
  }
  for (const [i, curb] of placements.curbs.entries()) {
    assert.ok([...curb.a, ...curb.b].every(Number.isFinite));
    assert.deepEqual(
      roads.conflicts(curb.a, curb.b, policy.curbHalfWidth, policy.curbMargin),
      [],
      `curb ${i}`,
    );
  }
  for (const route of city.routes)
    assert.ok(
      placements.railings.filter(
        (rail) =>
          polylineDistance([rail.x, rail.z], route.points) <= policy.nearWater,
      ).length > 20,
      route.name,
    );
});

test("every generated tree, lamp, sign, bench and bin has its entire low-level footprint clear of traffic", () => {
  const roads = new RoadClearance(city.roads);
  assert.ok(placements.streetObjects.length > 200);
  for (const [i, object] of placements.streetObjects.entries()) {
    const footprint = policy.objects[object.id];
    assert.ok(footprint, object.id);
    assert.ok([object.x, object.z, object.heading].every(Number.isFinite));
    const p: Point = [object.x, object.z];
    assert.deepEqual(
      roads.conflicts(p, p, footprint.radius, footprint.margin),
      [],
      `${object.id} ${i}`,
    );
  }
  for (const id of Object.keys(policy.objects))
    assert.ok(
      placements.streetObjects.some((object) => object.id === id),
      `retain ${id}`,
    );
});

test("bridge coordinates follow the actual road and preserve lane, walkway and overhead clearances", () => {
  const bridge = placements.bridge,
    source = city.roads.find((r) => r.id === bridge.roadId)!;
  assert.equal(bridge.roadId, 27498117);
  assert.equal(source.bridge, true);
  assert.equal(bridge.carriagewayWidth, source.width);
  assert.ok(bridge.walkwayWidth >= 1.5);
  assert.ok(bridge.clearHeight >= 4.5);
  const dx = (Math.sin(bridge.heading) * bridge.length) / 2,
    dz = (Math.cos(bridge.heading) * bridge.length) / 2;
  const start: Point = [bridge.center[0] - dx, bridge.center[1] - dz];
  const end: Point = [bridge.center[0] + dx, bridge.center[1] + dz];
  assert.ok(
    Math.hypot(start[0] - source.points[0][0], start[1] - source.points[0][1]) <
      1e-6,
  );
  assert.ok(
    Math.hypot(
      end[0] - source.points.at(-1)![0],
      end[1] - source.points.at(-1)![1],
    ) < 1e-6,
  );
  const contract = placements.diagnostics.bridgeModelContract as {
    minSideStructureInnerFaceX: number;
    minOverheadBeamBottom: number;
    oldFixedWidthScaleAllowed: boolean;
  };
  assert.ok(contract.minSideStructureInnerFaceX >= source.width / 2 + 0.5);
  assert.equal(contract.minOverheadBeamBottom, bridge.clearHeight);
  assert.equal(contract.oldFixedWidthScaleAllowed, false);
  const roadIndex = new RoadClearance([source]);
  for (const side of [-1, 1]) {
    const offset =
      side * (contract.minSideStructureInnerFaceX + policy.railHalfDepth);
    const nx = -Math.cos(bridge.heading) * offset,
      nz = Math.sin(bridge.heading) * offset;
    assert.equal(
      roadIndex.clear(
        [start[0] + nx, start[1] + nz],
        [end[0] + nx, end[1] + nz],
        policy.railHalfDepth,
        0.5,
      ),
      true,
    );
  }
});
