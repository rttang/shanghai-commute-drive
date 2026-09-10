/** Run with: node --import tsx scripts/prepare_street_placements.mjs */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import {
  RoadClearance,
  PLACEMENT_CLEARANCE as policy,
  pointInPolygon,
  polylineDistance,
  pointSegmentDistance,
  railingEndpoints,
} from "../src/tour/road-clearance.ts";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const mapBytes = readFileSync(resolve(root, "public/tour-city.json"));
const city = JSON.parse(mapBytes);
const clearance = new RoadClearance(city.roads);
const railings = [],
  curbs = [],
  streetObjects = [];
const counters = {
  railingCandidates: 0,
  railingsRemovedForRoads: 0,
  curbCandidates: 0,
  curbsRemovedForRoads: 0,
  objectCandidates: 0,
  objectsRemovedForRoads: 0,
  objectsRemovedForWaterOrBuildings: 0,
  objectsRemovedForSpacing: 0,
  treesOmittedForPhotoFrontage: 0,
};
const nearRoute = (p, range) =>
  city.routes.some((route) => polylineDistance(p, route.points) <= range);
const midpoint = (a, b) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
const length = (a, b) => Math.hypot(b[0] - a[0], b[1] - a[1]);

function samples(points, spacing, callback) {
  let next = spacing / 2,
    travelled = 0;
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1],
      b = points[i],
      distance = length(a, b);
    if (distance < 1e-6) continue;
    const dx = (b[0] - a[0]) / distance,
      dz = (b[1] - a[1]) / distance;
    while (next <= travelled + distance) {
      const t = next - travelled;
      callback(
        [a[0] + dx * t, a[1] + dz * t],
        [-dz, dx],
        Math.atan2(dx, dz),
        next,
      );
      next += spacing;
    }
    travelled += distance;
  }
}

const waterSeen = new Set();
for (const water of city.water) {
  if (waterSeen.has(water.id) || water.points.length < 4) continue;
  waterSeen.add(water.id);
  const polygon = [...water.points];
  if (length(polygon[0], polygon.at(-1)) > 0.01) polygon.push(polygon[0]);
  let twiceArea = 0;
  for (let i = 1; i < polygon.length; i++)
    twiceArea +=
      polygon[i - 1][0] * polygon[i][1] - polygon[i][0] * polygon[i - 1][1];
  if (Math.abs(twiceArea) < 40000) continue;
  for (let i = 1; i < polygon.length; i++) {
    const a = polygon[i - 1],
      b = polygon[i],
      segmentLength = length(a, b);
    if (segmentLength < 0.8) continue;
    const dx = (b[0] - a[0]) / segmentLength,
      dz = (b[1] - a[1]) / segmentLength;
    const center = midpoint(a, b),
      normal = [-dz, dx];
    const side = pointInPolygon(
      [center[0] + normal[0] * 0.6, center[1] + normal[1] * 0.6],
      polygon,
    )
      ? -1
      : 1;
    // Test and place the entire straight panel, including end posts and thickness.
    const count = Math.ceil(segmentLength / policy.railLength);
    const panelLength = segmentLength / count;
    for (let j = 0; j < count; j++) {
      const d = (j + 0.5) * panelLength;
      const rail = {
        x: a[0] + dx * d + normal[0] * side * 0.4,
        z: a[1] + dz * d + normal[1] * side * 0.4,
        heading: Math.atan2(dx, dz),
        length: panelLength,
      };
      if (!nearRoute([rail.x, rail.z], policy.nearWater)) continue;
      if (
        railings.some(
          (p) =>
            Math.hypot(p.x - rail.x, p.z - rail.z) <
            Math.min(p.length, rail.length) * 0.7,
        )
      )
        continue;
      counters.railingCandidates++;
      const [start, end] = railingEndpoints(rail);
      if (
        !clearance.clear(start, end, policy.railHalfDepth, policy.railMargin)
      ) {
        counters.railingsRemovedForRoads++;
        continue;
      }
      railings.push(rail);
    }
  }
}

// Split road edges into short panels; reject each complete panel near crossings.
for (const road of city.roads) {
  if (road.foot || road.tunnel || road.bridge || road.points.length < 2)
    continue;
  const self = new Set([road.id]);
  for (let i = 1; i < road.points.length; i++) {
    const a = road.points[i - 1],
      b = road.points[i],
      distance = length(a, b);
    if (distance < 0.5) continue;
    const count = Math.ceil(distance / 2),
      dx = (b[0] - a[0]) / distance,
      dz = (b[1] - a[1]) / distance;
    for (const side of [-1, 1]) {
      const offset = side * (road.width / 2 + 0.42);
      for (let j = 0; j < count; j++) {
        const segment = {
          a: [
            a[0] + (dx * distance * j) / count - dz * offset,
            a[1] + (dz * distance * j) / count + dx * offset,
          ],
          b: [
            a[0] + (dx * distance * (j + 1)) / count - dz * offset,
            a[1] + (dz * distance * (j + 1)) / count + dx * offset,
          ],
        };
        if (!nearRoute(midpoint(segment.a, segment.b), policy.nearRoute))
          continue;
        counters.curbCandidates++;
        if (
          !clearance.clear(
            segment.a,
            segment.b,
            policy.curbHalfWidth,
            policy.curbMargin,
          ) ||
          !clearance.clear(
            segment.a,
            segment.b,
            policy.curbHalfWidth,
            policy.curbJunctionMargin,
            self,
          )
        ) {
          counters.curbsRemovedForRoads++;
          continue;
        }
        curbs.push(segment);
      }
    }
  }
}

const blocks = city.buildings.map((building) => ({
  points: building.points,
  x0: Math.min(...building.points.map((p) => p[0])),
  x1: Math.max(...building.points.map((p) => p[0])),
  z0: Math.min(...building.points.map((p) => p[1])),
  z1: Math.max(...building.points.map((p) => p[1])),
}));
const conflictsBuilding = (p, radius) =>
  blocks.some((b) => {
    if (
      p[0] < b.x0 - radius ||
      p[0] > b.x1 + radius ||
      p[1] < b.z0 - radius ||
      p[1] > b.z1 + radius
    )
      return false;
    if (pointInPolygon(p, b.points)) return true;
    for (let i = 0; i < b.points.length; i++)
      if (
        pointSegmentDistance(
          p,
          b.points[i],
          b.points[(i + 1) % b.points.length],
        ) < radius
      )
        return true;
    return false;
  });
function addObject(id, p, heading) {
  const dimensions = policy.objects[id];
  counters.objectCandidates++;
  if (!clearance.clear(p, p, dimensions.radius, dimensions.margin)) {
    counters.objectsRemovedForRoads++;
    return;
  }
  if (
    city.water.some((w) => pointInPolygon(p, w.points)) ||
    conflictsBuilding(p, dimensions.radius + 0.25)
  ) {
    counters.objectsRemovedForWaterOrBuildings++;
    return;
  }
  if (
    streetObjects.some(
      (o) =>
        Math.hypot(o.x - p[0], o.z - p[1]) <
        (o.id === "plane-tree" && id === "plane-tree"
          ? 12
          : policy.objects[o.id].radius + dimensions.radius + 1),
    )
  ) {
    counters.objectsRemovedForSpacing++;
    return;
  }
  streetObjects.push({ id, x: p[0], z: p[1], heading });
}

const priorityRoadIds = new Set(city.routes.flatMap((r) => r.sourceWays));
let furnitureIndex = 0;
for (const road of city.roads) {
  if (road.foot || road.tunnel || road.bridge || !priorityRoadIds.has(road.id))
    continue;
  samples(road.points, 18, (p, normal, heading, distance) => {
    for (const side of [-1, 1]) {
      const offset = side * (road.width / 2 + 2.4);
      const position=[p[0] + normal[0] * offset, p[1] + normal[1] * offset];
      // The actual Bund photographs show an open pavement against the heritage
      // fronts (Peace Hotel through the southern banking buildings), rather
      // than a continuous row of large plane trees against their entrances.
      if(road.name==='中山东一路' && p[1]>=-328.2 && p[1]<=421 && position[0]<p[0]){
        counters.treesOmittedForPhotoFrontage++;continue;
      }
      addObject(
        "plane-tree",
        position,
        heading,
      );
    }
  });
  samples(road.points, 36, (p, normal, heading) => {
    for (const side of [-1, 1]) {
      const offset = side * (road.width / 2 + 1.8);
      const shifted = [
        p[0] + normal[0] * offset + Math.sin(heading) * 5,
        p[1] + normal[1] * offset + Math.cos(heading) * 5,
      ];
      addObject("streetlamp", shifted, heading + (side < 0 ? Math.PI : 0));
    }
  });
  samples(road.points, 60, (p, normal, heading) => {
    const id = ["road-sign", "bench", "litter-bin"][furnitureIndex++ % 3];
    const offset = road.width / 2 + (id === "bench" ? 3.8 : 2.2);
    addObject(
      id,
      [p[0] + normal[0] * offset, p[1] + normal[1] * offset],
      heading,
    );
  });
}

const bridgeRoad = city.roads.find((r) => r.id === 27498117);
if (!bridgeRoad || bridgeRoad.points.length !== 2)
  throw new Error(
    "Bridge alignment requires the two-point surveyed road source",
  );
const [bridgeStart, bridgeEnd] = bridgeRoad.points;
const bridge = {
  roadId: bridgeRoad.id,
  center: midpoint(bridgeStart, bridgeEnd),
  heading: Math.atan2(
    bridgeEnd[0] - bridgeStart[0],
    bridgeEnd[1] - bridgeStart[1],
  ),
  length: length(bridgeStart, bridgeEnd),
  carriagewayWidth: bridgeRoad.width,
  walkwayWidth: policy.bridgeWalkwayWidth,
  clearHeight: policy.bridgeClearHeight,
};
const placements = {
  version: 1,
  railings,
  curbs,
  streetObjects,
  bridge,
  diagnostics: {
    sourceMapSha256: createHash("sha256").update(mapBytes).digest("hex"),
    generator: "scripts/prepare_street_placements.mjs",
    coordinates:
      "Three world metres; X east, Z south; heading Y rotation; panels longitudinal local +Z",
    ...counters,
    retained: {
      railings: railings.length,
      curbs: curbs.length,
      streetObjects: streetObjects.length,
    },
    streetObjectCounts: Object.fromEntries(
      Object.keys(policy.objects).map((id) => [
        id,
        streetObjects.filter((o) => o.id === id).length,
      ]),
    ),
    roadSegmentsChecked: clearance.segments.length,
    clearancePolicy: policy,
    photoFrontageExceptions: [{
      road:'中山东一路',side:'west heritage frontage',zRange:[-328.2,421],
      rule:'Omit the generated continuous plane-tree row from the open heritage-side pavement',
      references:['assets/streets/reference-expansion/bund-street-wide.jpg','assets/streets/plane-tree-review/references/bund-zhongshan-2015.jpg'],
      precision:'Photograph-matched corridor treatment, not a surveyed tree inventory',
    }],
    bridgeModelContract: {
      minSideStructureInnerFaceX:
        bridge.carriagewayWidth / 2 + policy.bridgeSideMargin,
      minOverheadBeamBottom: bridge.clearHeight,
      walkwayWidthPerSide: bridge.walkwayWidth,
      carriagewayFollowsSourceRoad: true,
      oldFixedWidthScaleAllowed: false,
    },
    assetAxisAdapter: {
      "river-railing": "local X; rotationY=heading-PI/2; scaleX=length/3",
      curb: "local X; heading=atan2(b.x-a.x,b.z-a.z); rotationY=heading-PI/2; scaleX=distance(a,b)/3",
    },
    limitations:
      "Conservative plan-view exclusion of every non-tunnel motor road. Tree crowns and lamp arms may overhang only above minimumStreetOverhangHeight (4.5m); recorded radii bound solid structures below that height. Street furniture positions are road-safe procedural placements, not surveyed historic positions.",
  },
};
if (!railings.length || !curbs.length || !streetObjects.length)
  throw new Error(
    "Placement generation unexpectedly removed an entire category",
  );
const target = resolve(root, "public/streets/master/placements.json");
mkdirSync(dirname(target), { recursive: true });
writeFileSync(target, JSON.stringify(placements, null, 2) + "\n");
console.log(
  JSON.stringify({ output: target, ...placements.diagnostics }, null, 2),
);
