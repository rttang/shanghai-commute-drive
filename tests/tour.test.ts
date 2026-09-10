import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, statSync } from "node:fs";
import {
  Drive,
  Path,
  angleDifference,
  readPreferences,
  savePreferences,
} from "../src/tour/drive";
import { CARS, type City, type Point, type Route } from "../src/tour/data";
import vehicleAssets from "../src/tour/vehicle-assets.json";
const city = JSON.parse(
  readFileSync(new URL("../public/tour-city.json", import.meta.url), "utf8"),
) as City;
const oldRoutes=city.legacyRoutes??city.routes;
const neutral = { throttle: false, brake: false, steer: 0 };
const throttle = { ...neutral, throttle: true };
const routeWith = (points: Point[]): Route => ({
  ...oldRoutes[0],
  points,
  length: new Path(points).total,
});
const straight = () =>
  routeWith([
    [0, 0],
    [0, 2000],
  ]);
const run = (drive: Drive, seconds: number, input = neutral, fps = 60) => {
  for (let i = 0; i < Math.round(seconds * fps); i++)
    drive.update(1 / fps, input);
};
test("positive lane offset follows right-hand traffic in both directions", () => {
  const south = new Path([
    [0, 0],
    [0, 100],
  ]).pose(50, 1.4);
  const north = new Path([
    [0, 100],
    [0, 0],
  ]).pose(50, 1.4);
  assert.equal(south.x, -1.4);
  assert.equal(north.x, 1.4);
});
test("two mapped tours have continuous road segments and bounded coordinates", () => {
  assert.equal(oldRoutes.length, 2);
  for (const r of oldRoutes) {
    assert.ok(r.directed);
    assert.ok(r.sourceWays.length > 1);
    const p = new Path(r.points);
    assert.ok(Math.abs(p.total - r.length) < 3);
    assert.ok(p.total > 1500 && p.total < 4500);
    for (const point of r.points) assert.ok(point.every(Number.isFinite));
    for (const id of r.sourceWays) {
      const road = city.roads.find((x) => x.id === id);
      assert.ok(road);
      assert.equal(road.foot, false);
      assert.equal(road.tunnel, false);
    }
  }
});
test("automatic sightseeing completes both entire tours without an off-road jump", () => {
  for (const r of oldRoutes) {
    const d = new Drive(r);
    d.start("auto");
    let last = d.pose;
    for (let i = 0; i < 60000 && d.phase !== "complete"; i++) {
      d.update(1 / 60, neutral);
      const p = d.pose;
      assert.ok(Number.isFinite(p.heading));
      assert.ok(Math.hypot(last.x - p.x, last.z - p.z) < 4);
      last = p;
    }
    assert.equal(d.phase, "complete", r.name);
    assert.equal(d.distance, d.path.total);
    assert.equal(d.speed, 0);
  }
});
test("manual throttle accelerates, release coasts, braking stops and pause freezes the complete pose", () => {
  const d = new Drive(straight());
  d.start("manual");
  run(d, 5, throttle);
  assert.ok(d.speed > 8);
  const speed = d.speed,
    travelled = d.travelled,
    z = d.pose.z;
  run(d, 1);
  assert.ok(
    d.speed < speed && d.speed > speed * 0.8,
    "release should coast, not stop abruptly",
  );
  assert.ok(d.pose.z > z && d.travelled > travelled);
  d.togglePause();
  const snapshot = {
    pose: d.pose,
    distance: d.distance,
    speed: d.speed,
    lateral: d.lateral,
    steering: d.steering,
    travelled: d.travelled,
  };
  run(d, 2, { ...throttle, steer: 1 });
  assert.deepEqual(
    {
      pose: d.pose,
      distance: d.distance,
      speed: d.speed,
      lateral: d.lateral,
      steering: d.steering,
      travelled: d.travelled,
    },
    snapshot,
  );
  d.togglePause();
  run(d, 3, { ...neutral, brake: true });
  assert.equal(d.speed, 0);
  const stopped = { pose: d.pose, travelled: d.travelled };
  run(d, 2, { ...neutral, brake: true });
  assert.deepEqual({ pose: d.pose, travelled: d.travelled }, stopped);
});
test("steering turns the front axle gradually and right/left produce mirrored independent trajectories", () => {
  const left = new Drive(straight()),
    right = new Drive(straight());
  left.start("manual");
  right.start("manual");
  const origin = right.pose;
  right.update(1 / 60, { ...neutral, steer: 1 });
  assert.ok(
    right.steering > 0 && right.steering < 0.03,
    "wheel steering should slew, not snap",
  );
  assert.deepEqual(
    right.pose,
    origin,
    "steering at rest must not rotate the car body",
  );
  right.reset();
  right.start("manual");
  run(left, 3, { ...throttle, steer: -1 });
  run(right, 3, { ...throttle, steer: 1 });
  assert.ok(right.pose.x < origin.x - 3 && right.pose.heading < 0);
  assert.ok(left.pose.x > origin.x + 3 && left.pose.heading > 0);
  assert.ok(
    right.routeDeviation > 2.4,
    "manual driving must not be clamped into the lane",
  );
  assert.ok(
    Math.abs(left.pose.x - origin.x + (right.pose.x - origin.x)) < 1e-6,
  );
  assert.ok(Math.abs(left.pose.z - right.pose.z) < 1e-6);
  run(right, 1);
  assert.equal(right.steering, 0, "steering returns gradually when released");
});
test("manual driving is stable at 20, 30 and 60 FPS and ignores the sightseeing multiplier", () => {
  const snapshots = [20, 30, 60].map((fps) => {
    const d = new Drive(straight());
    d.rate = fps === 20 ? 3 : 1;
    d.start("manual");
    run(d, 3, throttle, fps);
    run(d, 2, { ...throttle, steer: 0.35 }, fps);
    run(d, 2, neutral, fps);
    run(d, 1, { ...neutral, brake: true }, fps);
    return {
      pose: d.pose,
      speed: d.speed,
      steering: d.steering,
      travelled: d.travelled,
    };
  });
  for (const actual of snapshots.slice(1)) {
    const expected = snapshots[0];
    assert.ok(
      Math.hypot(
        actual.pose.x - expected.pose.x,
        actual.pose.z - expected.pose.z,
      ) < 0.01,
    );
    assert.ok(
      Math.abs(angleDifference(actual.pose.heading, expected.pose.heading)) <
        0.001,
    );
    assert.ok(Math.abs(actual.speed - expected.speed) < 0.001);
    assert.ok(Math.abs(actual.travelled - expected.travelled) < 0.01);
    assert.ok(Math.abs(actual.steering - expected.steering) < 0.001);
  }
});
test("a driver who does not steer at a bend leaves the road instead of following the route", () => {
  const d = new Drive(
    routeWith([
      [0, 0],
      [0, 30],
      [200, 30],
    ]),
  );
  d.start("manual");
  run(d, 4, throttle);
  run(d, 5);
  assert.ok(
    d.pose.z > 50,
    "the car should continue beyond the corner under its own inertia",
  );
  assert.equal(d.pose.x, -1.4);
  assert.equal(d.pose.heading, 0);
  assert.ok(d.routeDeviation > 20);
  assert.equal(d.phase, "running");
});
test("automatic and manual handoffs preserve pose; off-road or opposing handoffs are rejected", () => {
  const d = new Drive(straight());
  d.start("auto");
  run(d, 3);
  const automatic = d.pose;
  assert.equal(d.setMode("manual"), true);
  assert.deepEqual(d.pose, automatic);
  run(d, 0.3, { ...throttle, steer: 0.15 });
  const manual = d.pose;
  assert.equal(d.setMode("auto"), true);
  assert.deepEqual(
    d.pose,
    manual,
    "automatic takeover must not teleport the car",
  );
  d.update(1 / 60, neutral);
  assert.ok(Math.hypot(d.pose.x - manual.x, d.pose.z - manual.z) < 0.5);
  assert.equal(d.setMode("manual"), true);
  run(d, 3, { ...throttle, steer: 1 });
  const offRoad = {
    pose: d.pose,
    distance: d.distance,
    speed: d.speed,
    mode: d.mode,
  };
  assert.equal(d.setMode("auto"), false);
  assert.deepEqual(
    { pose: d.pose, distance: d.distance, speed: d.speed, mode: d.mode },
    offRoad,
  );

  const wrongDirection = new Drive(straight());
  wrongDirection.start("manual");
  // A low-speed turn can leave the vehicle near its lane but misaligned.
  run(wrongDirection, 1.2, { ...throttle, steer: 1 });
  const lane = wrongDirection.path.pose(wrongDirection.distance);
  assert.ok(
    Math.hypot(wrongDirection.pose.x - lane.x, wrongDirection.pose.z - lane.z) <
      3,
  );
  assert.ok(Math.abs(wrongDirection.pose.heading) > 0.45);
  assert.equal(wrongDirection.setMode("auto"), false);
});
test("passing a destination off-road does not complete the tour", () => {
  const d = new Drive(
    routeWith([
      [0, 0],
      [0, 40],
    ]),
  );
  d.start("manual");
  run(d, 1.5, { ...throttle, steer: 0.5 });
  run(d, 8, throttle);
  assert.equal(
    d.distance,
    d.path.total,
    "projection can reach the route end while the vehicle is elsewhere",
  );
  assert.ok(d.routeDeviation > 10);
  assert.equal(d.phase, "running");
});
test("reset and restart discard old manual pose and joining offsets in either mode", () => {
  const d = new Drive(straight());
  const start = d.pose;
  d.start("manual");
  run(d, 3, { ...throttle, steer: 1 });
  d.reset();
  assert.equal(d.phase, "ready");
  assert.equal(d.distance, 0);
  assert.equal(d.speed, 0);
  assert.equal(d.travelled, 0);
  assert.equal(d.steering, 0);
  assert.deepEqual(d.pose, start);
  assert.equal(d.start("manual"), true);
  assert.deepEqual(d.pose, start);
  run(d, 1, throttle);
  assert.ok(d.pose.z > start.z);
  d.reset();
  assert.equal(d.start("auto"), true);
  assert.deepEqual(d.pose, start);
  run(d, 1);
  assert.ok(d.pose.z > start.z);

  const completed = new Drive(
    routeWith([
      [0, 0],
      [0, 20],
    ]),
  );
  completed.start("manual");
  run(completed, 6, throttle);
  assert.equal(completed.phase, "complete");
  assert.equal(completed.start("auto"), true);
  assert.equal(completed.phase, "running");
  assert.equal(completed.distance, 0);
  assert.equal(completed.speed, 0);
  assert.deepEqual(completed.pose, completed.path.pose(0));
});
test("invalid and zero frame intervals do not corrupt a running drive", () => {
  const d = new Drive(straight());
  d.start("manual");
  run(d, 1, throttle);
  const before = { pose: d.pose, speed: d.speed, travelled: d.travelled };
  for (const dt of [0, -1, NaN, Infinity]) d.update(dt, throttle);
  assert.deepEqual(
    { pose: d.pose, speed: d.speed, travelled: d.travelled },
    before,
  );
});
test("speed multiplier changes tour progression only in automatic mode", () => {
  const a = new Drive(city.routes[0]),
    b = new Drive(city.routes[0]);
  a.start("auto");
  b.start("auto");
  b.rate = 3;
  for (let i = 0; i < 600; i++) {
    a.update(1 / 60, neutral);
    b.update(1 / 60, neutral);
  }
  assert.ok(b.distance > a.distance * 2.5);
});
test("the curated fleet has five retained and five luxury vehicles with loadable assets", () => {
  assert.equal(CARS.length, 10);
  assert.deepEqual(CARS.map(c=>c.id).sort(),['su7','model-3','model-y','dolphin','yuan-up','g63','urus','porsche-911','ferrari-488','alphard'].sort());
  assert.deepEqual(Object.keys(vehicleAssets).sort(),CARS.map(c=>c.id).sort());
  for (const c of CARS) {
    const asset=(vehicleAssets as Record<string,{file:string;preview:string}>)[c.id];
    assert.ok(new URL(c.source).protocol==='https:');
    assert.ok(c.dimensions[0] > 4000 && c.dimensions[0] < 5300);
    assert.ok(c.wheelbase < c.dimensions[0]);
    const bounds=(c as typeof c & {collisionDimensions?:number[]}).collisionDimensions??c.dimensions;
    assert.ok(bounds[0]<=5200 && bounds[1]<=2300,'Fits the verified wide-vehicle collision envelope: '+c.id);
    const file = new URL(
      "../public" + asset.file,
      import.meta.url,
    );
    const bytes = readFileSync(file);
    assert.equal(bytes.subarray(0, 4).toString(), "glTF");
    assert.equal(bytes.readUInt32LE(8), bytes.length);
    assert.ok(
      statSync(new URL("../public" + asset.preview, import.meta.url))
        .size > 10000,
    );
  }
});
test("detailed exterior assets fit the size budget and contain self-contained compressed geometry", () => {
  let totalBytes=0;
  for (const [id, asset] of Object.entries(vehicleAssets)) {
    const bytes = readFileSync(
      new URL("../public" + asset.file, import.meta.url),
    );
    assert.equal(bytes.subarray(0, 4).toString(), "glTF");
    assert.equal(bytes.readUInt32LE(8), bytes.length);
    totalBytes+=bytes.length;
    assert.ok(bytes.length <= 25_000_000, id);
    const gltf = JSON.parse(
      bytes.subarray(20, 20 + bytes.readUInt32LE(12)).toString(),
    );
    assert.ok(
      gltf.extensionsRequired.includes("KHR_draco_mesh_compression"),
      id,
    );
    assert.ok(gltf.buffers.every((b: { uri?: string }) => !b.uri));
    assert.ok((gltf.images || []).every((i: { uri?: string }) => !i.uri));
    const quality = JSON.parse(
      readFileSync(
        new URL("../public" + asset.quality, import.meta.url),
        "utf8",
      ),
    );
    const triangles = gltf.meshes.reduce(
      (n: number, m: { primitives: { indices: number }[] }) =>
        n +
        m.primitives.reduce(
          (n, p) => n + gltf.accessors[p.indices].count / 3,
          0,
        ),
      0,
    );
    assert.equal(triangles, quality.runtimeTriangles, id);
    assert.equal(bytes.length, quality.runtimeBytes, id);
    assert.ok(quality.runtimeTriangles <= quality.sourceTriangles);
    assert.equal(asset.sourceYear, quality.sourceYear);
    assert.equal(asset.license, id === "yuan-up" ? "CC-BY-NC-SA-4.0" : id === "g63" ? "CC-BY-NC-4.0" : "CC-BY-4.0", id);
    assert.equal(Object.keys(quality.wheelRig).length, 4);
    const wheels = gltf.nodes.filter(
      (n: { extras?: { wheelPosition?: string } }) => n.extras?.wheelPosition,
    );
    assert.deepEqual(
      wheels
        .map(
          (n: { extras: { wheelPosition: string } }) => n.extras.wheelPosition,
        )
        .sort(),
      ["FL", "FR", "RL", "RR"],
    );
  }
  assert.ok(totalBytes/Object.keys(vehicleAssets).length<10_000_000,'Average exterior asset must stay under 10 MB');
});
test('luxury traffic assets retain four wheels with bounded geometry and independent files',()=>{
  const ids=['g63','urus','porsche-911','ferrari-488','alphard'];
  let total=0;
  for(const id of ids){
    const asset=(vehicleAssets as Record<string,{file:string;trafficFile?:string;quality:string}>)[id];
    assert.ok(asset?.trafficFile,id);assert.notEqual(asset.trafficFile,asset.file);
    const bytes=readFileSync(new URL('../public'+asset.trafficFile,import.meta.url));total+=bytes.length;
    assert.equal(bytes.readUInt32LE(8),bytes.length);assert.ok(bytes.length<3_000_000,id);
    const gltf=JSON.parse(bytes.subarray(20,20+bytes.readUInt32LE(12)).toString());
    const quality=JSON.parse(readFileSync(new URL('../public'+asset.quality,import.meta.url),'utf8'));
    assert.equal(bytes.length,quality.traffic.bytes,id);assert.ok(quality.traffic.triangles<=30_000,id);
    assert.deepEqual(gltf.nodes.filter((n:{extras?:{wheelPosition?:string}})=>n.extras?.wheelPosition).map((n:{extras:{wheelPosition:string}})=>n.extras.wheelPosition).sort(),['FL','FR','RL','RR']);
    assert.ok(quality.traffic.rigValidation.fourIndependentRolls && quality.traffic.rigValidation.frontSteerOnly && quality.traffic.rigValidation.bodyStationary,id);
  }
  assert.ok(total/ids.length<2_000_000,'Traffic models must average below 2 MB; uncompressed geometry fallback retains valid faces');
});
test("preferences tolerate malformed storage and never overwrite the prior game save", () => {
  assert.equal(readPreferences({ getItem: () => "{bad" }).car, "su7");
  assert.equal(
    readPreferences({ getItem: () => '{"quality":"bad","route":"missing"}' })
      .route,
    "shanghai-loop",
  );
  let key = "";
  assert.ok(
    savePreferences(
      {
        setItem: (k) => {
          key = k;
        },
      },
      { car: "su7", route: "pudong", quality: "high" },
    ),
  );
  assert.equal(key, "shanghai-sightseeing-v3");
  assert.equal(
    savePreferences(
      {
        setItem: () => {
          throw new Error("quota");
        },
      },
      { car: "su7", route: "bund", quality: "high" },
    ),
    false,
  );
});
