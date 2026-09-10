import type { Point, Route } from "./data";
import { CollisionWorld, type Contact } from "./collision";
import { drivingSurfaceHeight } from "./driving-height";
import { VehicleDynamics } from "./vehicle-dynamics";
export interface Input {
  throttle: boolean;
  brake: boolean;
  steer: number;
  handbrake?: boolean;
}
export const angleDifference = (a: number, b: number) =>
  Math.atan2(Math.sin(a - b), Math.cos(a - b));
const clamp = (value: number, lo: number, hi: number) =>
  Math.max(lo, Math.min(hi, value));
type Pose = { x: number; z: number; heading: number; y?: number };
export class Path {
  readonly total: number;
  readonly distances: number[] = [0];
  constructor(readonly points: Point[], readonly closed = false, readonly elevations?: number[]) {
    if (points.length < 2) throw new Error("路线至少需要两个点");
    for (let i = 1; i < points.length; i++)
      this.distances.push(
        this.distances[i - 1] +
          Math.hypot(
            points[i][0] - points[i - 1][0],
            points[i][1] - points[i - 1][1],
          ),
      );
    this.total = this.distances.at(-1)!;
  }
  at(distance: number) {
    const d = this.closed ? ((distance % this.total) + this.total) % this.total : Math.max(0, Math.min(this.total, distance));
    let lo = 0,
      hi = this.points.length - 1;
    while (lo + 1 < hi) {
      const m = (lo + hi) >> 1;
      if (this.distances[m] <= d) lo = m;
      else hi = m;
    }
    const a = this.points[lo],
      b = this.points[hi],
      length = this.distances[hi] - this.distances[lo],
      t = length ? (d - this.distances[lo]) / length : 0;
    return {
      y: (this.elevations?.[lo] ?? 0) + ((this.elevations?.[hi] ?? 0) - (this.elevations?.[lo] ?? 0)) * t,
      x: a[0] + (b[0] - a[0]) * t,
      z: a[1] + (b[1] - a[1]) * t,
      dx: (b[0] - a[0]) / (length || 1),
      dz: (b[1] - a[1]) / (length || 1),
    };
  }
  pose(distance: number, lateral = 1.4) {
    const p = this.at(distance),
      a = this.at(distance - 3),
      b = this.at(distance + 5);
    const heading = Math.atan2(b.x - a.x, b.z - a.z);
    return {
      y: p.y,
      x: p.x - Math.cos(heading) * lateral,
      z: p.z + Math.sin(heading) * lateral,
      heading,
    };
  }
  project(p: { x: number; z: number }, hint = 0, full = false): { distance: number; separation: number; lateral: number; heading: number } {
    let best = { distance: 0, separation: Infinity, lateral: 0, heading: 0 };
    for (let i = 0; i < this.points.length - 1; i++) {
      const gap = Math.abs(this.distances[i] - hint);
      if (!full && this.closed && Math.min(gap, this.total - gap) > 250) continue;
      const a = this.points[i],
        b = this.points[i + 1];
      const dx = b[0] - a[0],
        dz = b[1] - a[1],
        length = Math.hypot(dx, dz);
      if (!length) continue;
      const t = clamp(
        ((p.x - a[0]) * dx + (p.z - a[1]) * dz) / (length * length),
        0,
        1,
      );
      const x = a[0] + dx * t,
        z = a[1] + dz * t;
      const separation = Math.hypot(p.x - x, p.z - z);
      const distance = this.distances[i] + t * length;
      // At intersections, preserve the nearby route segment on an exact tie.
      if (
        separation < best.separation - 0.001 ||
        (Math.abs(separation - best.separation) <= 0.001 &&
          Math.abs(distance - hint) < Math.abs(best.distance - hint))
      )
        best = {
          distance,
          separation,
          lateral: (-(p.x - x) * dz + (p.z - z) * dx) / length,
          heading: Math.atan2(dx, dz),
        };
    }
    if (this.closed && !full && best.separation > 30) return this.project(p, hint, true);
    return best;
  }
}
export class Drive {
  readonly path: Path;
  distance = 0;
  speed = 0;
  lateral = 1.4;
  phase: "ready" | "running" | "paused" | "complete" = "ready";
  mode: "auto" | "manual" = "auto";
  rate = 1;
  steering = 0;
  travelled = 0;
  wheelbase = 3;
  readonly dynamics = new VehicleDynamics();
  routeDeviation = 0;
  laps = 0;
  private unwrappedDistance?: number;
  gear: 1 | -1 = 1;
  vehicleWidth = 1.9;
  vehicleLength = 4.8;
  collision?: CollisionWorld;
  collisions = 0;
  lastImpact?: Contact & { speed: number; sequence: number };
  private impactCooldown = 0;
  autoStopDistance?: number;
  private manualPose?: Pose;
  private joinOffset = { x: 0, z: 0, heading: 0 };
  constructor(readonly route: Route) {
    this.path = new Path(route.points, !!route.closed, route.elevations);
    this.routeDeviation = this.path.project(this.pose).separation;
  }
  start(mode: "auto" | "manual") {
    if (this.phase === "complete") this.reset();
    if (!this.setMode(mode)) return false;
    this.phase = "running";
    this.dynamics.reset();
    return true;
  }
  setMode(mode: "auto" | "manual") {
    if (mode === this.mode && (mode === "auto" || this.manualPose)) return true;
    const current = this.pose;
    if (mode === "manual") {
      this.manualPose = { ...current };
      this.routeDeviation = this.path.project(
        current,
        this.distance,
      ).separation;
    } else {
      const near = this.path.project(current, this.distance);
      const lane = this.path.pose(near.distance, 1.4);
      // Automatic sightseeing can only take over near its lane, facing forward.
      // Reject distant handoffs instead of teleporting an off-road vehicle.
      if (
        Math.hypot(current.x - lane.x, current.z - lane.z) > 3 ||
        Math.abs(angleDifference(current.heading, lane.heading)) > 0.45 ||
        this.speed < -.2
      )
        return false;
      this.distance = near.distance;
      this.joinOffset = {
        x: current.x - lane.x,
        z: current.z - lane.z,
        heading: angleDifference(current.heading, lane.heading),
      };
      this.lateral = 1.4;
      this.gear = 1;
      this.speed = Math.max(0,this.speed);
    }
    this.mode = mode;
    this.dynamics.reset();
    return true;
  }
  reset() {
    this.dynamics.reset();
    this.distance = 0;
    this.laps = 0;
    this.unwrappedDistance=0;
    this.gear = 1;
    this.speed = 0;
    this.lateral = 1.4;
    this.steering = 0;
    this.travelled = 0;
    this.manualPose = undefined;
    this.joinOffset = { x: 0, z: 0, heading: 0 };
    this.phase = "ready";
    this.routeDeviation = this.path.project(this.pose).separation;
  }
  togglePause() {
    if (this.phase === "running") this.phase = "paused";
    else if (this.phase === "paused") this.phase = "running";
  }
  update(dt: number, input: Input) {
    if (this.phase !== "running" || !Number.isFinite(dt) || dt <= 0) return;
    dt = Math.min(0.25, Math.max(0, dt));
    if(dt>.05){
      const steps=Math.ceil(dt/.05);
      for(let i=0;i<steps;i++)this.update(dt/steps,input);
      return;
    }
    // Substeps keep steering/braking stable even on a slow rendering frame.
    const count = Math.max(1, Math.ceil(dt / (1 / 120)));
    for (let i = 0; i < count && this.phase === "running"; i++)
      this.step(dt / count, input);
  }
  private step(dt: number, input: Input) {
    const before = this.pose;
    this.unwrappedDistance??=this.laps*this.path.total+this.distance;
    this.impactCooldown = Math.max(0, this.impactCooldown - dt);
    if (this.mode === "manual") {
      this.manualPose ??= { ...before };
      const p = this.manualPose;
      const oldSpeed = this.speed;
      this.speed = this.dynamics.step(this.speed,this.gear,input,dt);
      const speed = (oldSpeed + this.speed) / 2;
      const limit = Math.min(
        0.58,
        Math.atan((4.8 * this.wheelbase) / Math.max(1, speed ** 2)),
      );
      const target = clamp(input.steer, -1, 1) * limit;
      const turnRate = input.steer ? 1.15 : 1.55;
      this.steering += clamp(
        target - this.steering,
        -turnRate * dt,
        turnRate * dt,
      );
      // Kinematic bicycle: pose is the axle midpoint, forward is (sin yaw, cos yaw).
      // Positive controls turn right, which decreases yaw in this map coordinate system.
      const beta = -Math.atan(0.5 * Math.tan(this.steering));
      const yawRate =
        (-speed * Math.cos(beta) * Math.tan(this.steering)) / this.wheelbase;
      const direction = p.heading + beta + (yawRate * dt) / 2;
      const desired = { ...p, x:p.x+Math.sin(direction)*speed*dt, z:p.z+Math.cos(direction)*speed*dt, heading:angleDifference(p.heading+yawRate*dt,0) };
      const targetSurface=this.path.project(desired,this.distance);
      const onTunnel=(this.route.tunnels??[]).some(t=>targetSurface.distance>=t.start && targetSurface.distance<=t.end);
      desired.y=drivingSurfaceHeight(p,desired,this.path.at(targetSurface.distance).y,targetSurface.separation,onTunnel);
      const response = this.collide(p, desired);
      Object.assign(p, response);
      const near = this.path.project(p, this.distance);
      this.trackProgress(this.distance,near.distance);
      this.distance = near.distance;
      p.y = drivingSurfaceHeight(before,p,this.path.at(this.distance).y,near.separation,
        (this.route.tunnels??[]).some(t=>this.distance>=t.start && this.distance<=t.end));
      this.lateral = near.lateral;
      this.routeDeviation = near.separation;
      this.travelled += Math.sign(speed) * Math.hypot(p.x-before.x,p.z-before.z);
      const end = this.path.pose(this.path.total);
      // Passing beside the destination far off-road must never finish the tour.
      if (
        !this.route.closed && this.distance > this.path.total - 1.5 &&
        Math.hypot(p.x - end.x, p.z - end.z) < 2.5
      ) {
        this.distance = this.path.total;
        this.speed = 0;
        this.phase = "complete";
      }
      return;
    }
    const step = dt * this.rate;
    const a = this.path.at(this.distance + 4),
      b = this.path.at(this.distance + 22),
      dot = Math.max(-1, Math.min(1, a.dx * b.dx + a.dz * b.dz));
    const bend = Math.acos(dot);
    const cruise = Math.max(3, (this.route.speed / 3.6) * (1 - bend * 0.55));
    const remaining = this.route.closed ? Infinity : this.path.total-this.distance;
    const stop = Math.min(remaining, this.autoStopDistance===undefined?Infinity:Math.max(0,this.autoStopDistance-3));
    const target = Math.min(cruise, Math.sqrt(Math.max(0,stop) * 3));
    this.speed += (target - this.speed) * Math.min(1, step * 1.5);
    this.lateral += (1.4 - this.lateral) * step * 2;
    const advance = Math.min(remaining, this.speed * step);
    // Rejoin gradually over travelled metres, avoiding lateral drift at rest.
    const decay = Math.exp(-advance / 8);
    this.joinOffset.x *= decay;
    this.joinOffset.z *= decay;
    this.joinOffset.heading *= decay;
    const oldDistance=this.distance;
    this.distance = this.route.closed ? (this.distance + advance) % this.path.total : Math.min(this.path.total,this.distance+advance);
    const desired=this.pose;
    const after=this.collide(before,desired);
    if (Math.hypot(after.x-desired.x,after.z-desired.z)>.001) {
      // Keep the physically resolved pose even when an automatic vehicle is blocked.
      this.distance=oldDistance;
      const lane=this.path.pose(oldDistance,this.lateral);
      this.joinOffset={x:after.x-lane.x,z:after.z-lane.z,heading:angleDifference(after.heading,lane.heading)};
    }
    this.trackProgress(oldDistance,this.distance);
    const movement = Math.hypot(after.x - before.x, after.z - before.z);
    this.travelled += movement;
    const curvature =
      movement > 0.0001
        ? angleDifference(after.heading, before.heading) / movement
        : 0;
    this.steering = clamp(-Math.atan(curvature * this.wheelbase), -0.58, 0.58);
    this.routeDeviation = Math.abs(this.lateral);
    if (!this.route.closed && (remaining < 0.25 || this.distance >= this.path.total)) {
      this.distance = this.path.total;
      this.speed = 0;
      this.phase = "complete";
    }
  }
  shiftGear() {
    if (Math.abs(this.speed)>.4) return false;
    this.dynamics.reset();
    this.speed=0;this.gear=this.gear===1 ? -1 : 1;return true;
  }
  private trackProgress(before:number,after:number){
    if(!this.route.closed)return;
    let advance=after-before;
    if(advance>this.path.total/2)advance-=this.path.total;
    if(advance<-this.path.total/2)advance+=this.path.total;
    this.unwrappedDistance=(this.unwrappedDistance??this.laps*this.path.total+before)+advance;
    this.laps=Math.max(0,Math.floor((this.unwrappedDistance+1e-7)/this.path.total));
  }
  get progress(){return this.unwrappedDistance??this.laps*this.path.total+this.distance;}
  restoreProgress(progress:number){
    if(!Number.isFinite(progress))return;
    this.unwrappedDistance=progress;
    this.distance=this.route.closed?(progress%this.path.total+this.path.total)%this.path.total:clamp(progress,0,this.path.total);
    this.laps=Math.max(0,Math.floor((progress+1e-7)/this.path.total));
    this.manualPose=undefined;this.joinOffset={x:0,z:0,heading:0};
  }
  recover() {
    const near=this.path.project(this.pose,this.distance);
    for(const offset of [0,...Array.from({length:10},(_,i)=>[(i+1)*8,-(i+1)*8]).flat()]){
      const distance=this.route.closed ? (near.distance+offset+this.path.total)%this.path.total : clamp(near.distance+offset,0,this.path.total);
      const pose=this.path.pose(distance);
      if(this.collision?.occupied(pose,this.vehicleWidth+.3,this.vehicleLength+.5))continue;
      this.trackProgress(this.distance,distance);
      this.distance=distance;this.speed=0;this.steering=0;this.lateral=1.4;this.dynamics.reset();
      this.manualPose=pose;this.joinOffset={x:0,z:0,heading:0};
      this.routeDeviation=1.4;this.gear=1;return true;
    }
    return false;
  }
  private collide(before: Pose, desired: Pose): Pose {
    if(!this.collision)return desired;
    const result=this.collision.move(before,desired,this.vehicleWidth,this.vehicleLength);
    if(result.contacts.length){
      const hit=result.contacts.reduce((a,b)=>a.strength>b.strength?a:b);
      const speed=Math.abs(this.speed)*hit.strength;
      if(speed>1.2 && this.impactCooldown<=0){this.collisions++;this.lastImpact={...hit,speed,sequence:this.collisions};this.impactCooldown=.8;}
      this.speed *= Math.max(0, 1-hit.strength*1.08);
      if(Math.abs(this.speed)<.12)this.speed=0;
    }
    return result.pose;
  }
  get pose() {
    if (this.mode === "manual" && this.manualPose)
      return { ...this.manualPose };
    const p = this.path.pose(this.distance, this.lateral);
    return {
      y: p.y,
      x: p.x + this.joinOffset.x,
      z: p.z + this.joinOffset.z,
      heading: p.heading + this.joinOffset.heading,
    };
  }
}
const KEY = "shanghai-sightseeing-v3";
export interface Preferences {
  car: string;
  route: string;
  quality: "high" | "balanced";
}
export function readPreferences(
  storage: Pick<Storage, "getItem">,
): Preferences {
  const base: Preferences = {
    car: "su7",
    route: "shanghai-loop",
    quality: "balanced",
  };
  try {
    const s = JSON.parse(storage.getItem(KEY) || "null");
    if (s && typeof s === "object")
      return {
        car: typeof s.car === "string" ? s.car : base.car,
        route: s.route === "pudong" || s.route === "bund" ? s.route : "shanghai-loop",
        quality: s.quality === "high" ? "high" : "balanced",
      };
  } catch {}
  return base;
}
export function savePreferences(
  storage: Pick<Storage, "setItem">,
  value: Preferences,
) {
  try {
    storage.setItem(KEY, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}
