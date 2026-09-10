// Development-only visual evidence harness; does not use or change user preferences.
import { loadCity, CARS, LANDMARKS } from "./tour/data";
import { Drive } from "./tour/drive";
import { World, type CameraMode } from "./tour/world";
import { Journey } from "./tour/journey";
async function run() {
  const query = new URLSearchParams(location.search);
  const city = await loadCity();
  const route =
    [...city.routes, ...(city.legacyRoutes ?? [])].find((r) => r.id === query.get("route")) || city.routes[0];
  const drive = new Drive(route);
  const requestedDistance=Number(query.get('distance')??600);
  drive.distance = Math.max(
    0,
    Math.min(drive.path.total, Number.isFinite(requestedDistance)?requestedDistance:600),
  );
  drive.phase = "paused";
  const world = new World(document.getElementById("scene")!, city);
  world.continuousRendering = true;
  world.journey=new Journey(await (await fetch('/journey.json')).json());
  world.setDrive(drive);
  world.setQuality(query.get('quality')==='high'?'high':'balanced');
  await world.load((t) => (document.getElementById("status")!.textContent = t));
  await world.setCar(
    CARS.find((c) => c.id === query.get("car")) ||
      CARS.find((c) => c.id === "su7")!,
  );
  world.setDrive(drive);
  await world.prepareDrive();
  const lighting=query.get('lighting');
  if(lighting==='night'||lighting==='dusk')world.setLighting(lighting);
  const mode = query.get("view") || "hood";
  world.home = mode === "home";
  world.setCamera(
    (["follow", "vehicle", "hood", "panorama"].includes(mode)
      ? mode
      : "follow") as CameraMode,
  );
  world.orbit = Number(query.get("orbit")) || 0;
  world.pitch = Number(query.get("pitch") || ".1");
  const moving=query.get('drive')==='auto';
  const stopAt=Number(query.get('stopAt'))||Infinity;
  const stopLaps=Number(query.get('stopLaps'))||Infinity;
  if(moving){drive.start('auto');drive.rate=Math.max(1,Math.min(3,Number(query.get('rate'))||1));}
  const reference = LANDMARKS.find(l => l.id === query.get("landmark"));
  document.getElementById("status")!.textContent = "";
  document.body.dataset.review = JSON.stringify({
    route: route.id,
    distance: drive.distance,
    view: mode,
    orbit: world.orbit,
    pitch: world.pitch,
    car: world.selectedCar.id,
    landmark: reference?.id,
  });
  let last = performance.now(),
    count = 0;
  const intervals: number[] = [];
  const traversal={start:drive.distance,end:drive.distance,travelled:drive.travelled,laps:drive.laps,frames:0,minY:drive.pose.y??0,maxY:drive.pose.y??0,maxVerticalStep:0,maxSpatialStep:0,collisions:0,stopped:false};
  let previousPose={...drive.pose};
  function frame(now: number) {
    if (reference) world.focus(reference);
    else {
      // A fixed comparison pose must not drift if pointer events arrive while
      // an isolated headed browser is being used for acceptance.
      world.orbit = Number(query.get("orbit")) || 0;
      world.pitch = Number(query.get("pitch") || ".1");
    }
    if (count > 120) intervals.push(now - last);
    if (intervals.length > 600) intervals.shift();
    const dt=Math.min(.25,Math.max(0,(now-last)/1000));
    if(moving){
      const steps=Math.max(1,Math.ceil(dt/.05));
      for(let i=0;i<steps;i++){
        world.simulateTraffic(dt/steps);
        drive.update(dt/steps,{throttle:false,brake:false,steer:0});
        world.journey?.update(dt/steps,drive);
      }
      const pose=drive.pose;
      traversal.end=drive.distance;traversal.travelled=drive.travelled;traversal.laps=drive.laps;traversal.frames++;
      traversal.minY=Math.min(traversal.minY,pose.y??0);traversal.maxY=Math.max(traversal.maxY,pose.y??0);
      traversal.maxVerticalStep=Math.max(traversal.maxVerticalStep,Math.abs((pose.y??0)-(previousPose.y??0)));
      traversal.maxSpatialStep=Math.max(traversal.maxSpatialStep,Math.hypot(pose.x-previousPose.x,pose.z-previousPose.z));
      traversal.collisions=drive.collisions;previousPose={...pose};
      if(drive.distance>=stopAt||drive.laps>=stopLaps){drive.phase='paused';traversal.stopped=true;}
      document.body.dataset.traversal=JSON.stringify(traversal);
    }
    world.update(Math.min(0.05, dt), now);
    last = now;
    count++;
    if (count % 180 === 0 && intervals.length > 120) {
      const sorted = [...intervals].sort((a, b) => a - b);
      document.body.dataset.sample = JSON.stringify({
        frames: intervals.length,
        meanFps:
          1000 / (intervals.reduce((a, b) => a + b, 0) / intervals.length),
        p95FrameMs: sorted[Math.floor(sorted.length * 0.95)],
        width: innerWidth,
        height: innerHeight,
        cameraPosition: world.camera.position.toArray(),
        cameraMode: world.mode,
        orbit: world.orbit,
        distance:drive.distance,
        pose:drive.pose,
        phase:drive.phase,
        collisions:drive.collisions,
        car:world.selectedCar.id,
        wheels:world.wheelState,
        ...world.stats,
      });
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}
void run().catch((e) => {
  document.getElementById("status")!.textContent = String(e);
  console.error(e);
});
