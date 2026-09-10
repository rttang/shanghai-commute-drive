import type { Point, Road } from "./data";

/** Dimensions in metres, in the same east-X / south-Z coordinates as tour-city. */
export const PLACEMENT_CLEARANCE = {
  railLength: 3,
  railHalfDepth: 0.2,
  railMargin: 0.5,
  curbHalfWidth: 0.14,
  curbMargin: 0.12,
  curbJunctionMargin: 1.25,
  nearRoute: 120,
  nearWater: 150,
  bridgeSideMargin: 0.5,
  bridgeWalkwayWidth: 2,
  bridgeClearHeight: 5.2,
  minimumStreetOverhangHeight: 4.5,
  objects: {
    "plane-tree": { radius: 1, margin: 1 },
    streetlamp: { radius: 0.45, margin: 0.75 },
    "road-sign": { radius: 0.9, margin: 0.75 },
    bench: { radius: 1.15, margin: 0.75 },
    "litter-bin": { radius: 0.45, margin: 0.75 },
  },
} as const;

export type StreetObjectId = keyof typeof PLACEMENT_CLEARANCE.objects;
export interface RailingPlacement {
  x: number;
  z: number;
  /** Rotation around Three Y; the asset's longitudinal axis is local +Z. */
  heading: number;
  length: number;
}
export interface StreetPlacements {
  version: number;
  railings: RailingPlacement[];
  curbs: { a: Point; b: Point }[];
  streetObjects: {
    id: StreetObjectId;
    x: number;
    z: number;
    heading: number;
  }[];
  bridge: {
    roadId: number;
    center: Point;
    heading: number;
    length: number;
    carriagewayWidth: number;
    walkwayWidth: number;
    clearHeight: number;
  };
  diagnostics: Record<string, unknown>;
}

export function pointSegmentDistance(p: Point, a: Point, b: Point): number {
  const dx = b[0] - a[0],
    dz = b[1] - a[1];
  const length2 = dx * dx + dz * dz;
  const t = length2
    ? Math.max(
        0,
        Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / length2),
      )
    : 0;
  return Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dz);
}

/** Exact segment distance, including interior crossings and degenerate points. */
export function segmentDistance(
  a: Point,
  b: Point,
  c: Point,
  d: Point,
): number {
  const cross = (p: Point, q: Point, r: Point) =>
    (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]);
  const abC = cross(a, b, c),
    abD = cross(a, b, d);
  const cdA = cross(c, d, a),
    cdB = cross(c, d, b);
  if (abC * abD < 0 && cdA * cdB < 0) return 0;
  return Math.min(
    pointSegmentDistance(a, c, d),
    pointSegmentDistance(b, c, d),
    pointSegmentDistance(c, a, b),
    pointSegmentDistance(d, a, b),
  );
}

export function polylineDistance(p: Point, points: Point[]): number {
  let distance = Infinity;
  for (let i = 1; i < points.length; i++)
    distance = Math.min(
      distance,
      pointSegmentDistance(p, points[i - 1], points[i]),
    );
  return distance;
}

export function pointInPolygon(p: Point, polygon: Point[]): boolean {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const a = polygon[i],
      b = polygon[j];
    if (
      a[1] > p[1] !== b[1] > p[1] &&
      p[0] < ((b[0] - a[0]) * (p[1] - a[1])) / (b[1] - a[1]) + a[0]
    )
      inside = !inside;
  }
  return inside;
}

export function railingEndpoints(rail: RailingPlacement): [Point, Point] {
  const dx = (Math.sin(rail.heading) * rail.length) / 2;
  const dz = (Math.cos(rail.heading) * rail.length) / 2;
  return [
    [rail.x - dx, rail.z - dz],
    [rail.x + dx, rail.z + dz],
  ];
}

interface RoadSegment {
  roadId: number;
  index: number;
  a: Point;
  b: Point;
  halfWidth: number;
}
export interface RoadConflict {
  roadId: number;
  segment: number;
  separation: number;
  required: number;
}

/** A road is a union of capsules, never merely a series of sampled road points. */
export class RoadClearance {
  readonly segments: RoadSegment[] = [];
  private readonly cells = new Map<string, number[]>();
  private readonly cellSize = 64;
  constructor(roads: Road[]) {
    for (const road of roads) {
      if (road.foot || road.tunnel || road.kind === "steps") continue;
      if (!Number.isFinite(road.width) || road.width <= 0)
        throw new Error(`Invalid road width: ${road.id}`);
      for (let i = 1; i < road.points.length; i++) {
        const a = road.points[i - 1],
          b = road.points[i];
        if (![...a, ...b].every(Number.isFinite))
          throw new Error(`Invalid road coordinates: ${road.id}`);
        const halfWidth = road.width / 2;
        const id =
          this.segments.push({
            roadId: road.id,
            index: i - 1,
            a,
            b,
            halfWidth,
          }) - 1;
        this.visitCells(a, b, halfWidth, (key) => {
          const cell = this.cells.get(key) || [];
          cell.push(id);
          this.cells.set(key, cell);
        });
      }
    }
  }
  private visitCells(
    a: Point,
    b: Point,
    radius: number,
    fn: (key: string) => void,
  ) {
    const x0 = Math.floor((Math.min(a[0], b[0]) - radius) / this.cellSize);
    const x1 = Math.floor((Math.max(a[0], b[0]) + radius) / this.cellSize);
    const z0 = Math.floor((Math.min(a[1], b[1]) - radius) / this.cellSize);
    const z1 = Math.floor((Math.max(a[1], b[1]) + radius) / this.cellSize);
    for (let x = x0; x <= x1; x++)
      for (let z = z0; z <= z1; z++) fn(`${x}:${z}`);
  }
  conflicts(
    a: Point,
    b: Point,
    radius = 0,
    margin = 0.5,
    ignoreRoadIds: ReadonlySet<number> = new Set(),
  ): RoadConflict[] {
    if (
      ![...a, ...b, radius, margin].every(Number.isFinite) ||
      radius < 0 ||
      margin < 0
    )
      throw new Error("Invalid clearance query");
    const ids = new Set<number>();
    this.visitCells(a, b, radius + margin, (key) =>
      this.cells.get(key)?.forEach((id) => ids.add(id)),
    );
    const conflicts: RoadConflict[] = [];
    for (const id of ids) {
      const road = this.segments[id];
      if (ignoreRoadIds.has(road.roadId)) continue;
      const separation = segmentDistance(a, b, road.a, road.b);
      const required = road.halfWidth + radius + margin;
      if (separation < required - 1e-7)
        conflicts.push({
          roadId: road.roadId,
          segment: road.index,
          separation,
          required,
        });
    }
    return conflicts;
  }
  clear(
    a: Point,
    b: Point,
    radius = 0,
    margin = 0.5,
    ignoreRoadIds?: ReadonlySet<number>,
  ): boolean {
    return this.conflicts(a, b, radius, margin, ignoreRoadIds).length === 0;
  }
}
