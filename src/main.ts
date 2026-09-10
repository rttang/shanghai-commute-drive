import "./style.css";
import { CARS, LANDMARKS, loadCity } from "./tour/data";
import { Drive, readPreferences, savePreferences } from "./tour/drive";
import { World, type CameraMode } from "./tour/world";
import { UI } from "./tour/ui";
import { Journey, type JourneyData } from "./tour/journey";
import { Missions } from "./tour/missions";
import { MissionsWorld } from "./tour/missions-world";
import { DriveAudio } from "./tour/audio";
import { storePhoto, readPhotos } from "./tour/album";
import { Controls } from "./core/input";
import { PausePolicy, type PauseEvent } from "./core/pause-policy";
let world: World,
  ui: UI,
  drive: Drive,
  ready = false,
  home = true,
  completionShown = false;
let launchRequest = 0;
let preparing = false;
let lastLaunchMode: "auto" | "manual" = "auto";
let journey: Journey;
let missions: Missions;
let missionsWorld: MissionsWorld;
const audio = new DriveAudio();
let playedImpact=0;
let capturing=false;
let captureName: string | undefined;
const preferences = readPreferences(localStorage);
const pausePolicy = new PausePolicy();
const controls = new Controls((action) => act(action));
function resetPause() {
  pausePolicy.reset(document.hidden, document.hasFocus());
}
function pauseEvent(event: PauseEvent) {
  const before = pausePolicy.reason;
  const change = pausePolicy.handle(event, drive);
  if (change) drive.togglePause();
  if (drive.phase !== 'running') missions?.suspend();
  if (drive.phase === "paused" && pausePolicy.reason !== before)
    ui.pauseFeedback(pausePolicy.reason);
  controls.clear();
  ui.update(drive, world.nearest().id, world.mode, pausePolicy.reason);
}
function persist() {
  if (!savePreferences(localStorage, preferences))
    ui.toast("浏览器暂时无法保存偏好，本次游览不受影响");
}
function choose(index: number) {
  launchRequest++;
  if (!Number.isInteger(index) || !world.city.routes[index]) return;
  drive = new Drive(world.city.routes[index]);
  journey?.restore(drive);
  missions?.suspend();
  world.setDrive(drive);
  ui.select(index);
  controls.clear();
  resetPause();
  completionShown = false;
  preferences.route = drive.route.id;
  persist();
}
async function begin(mode: "auto" | "manual") {
  if (preparing) return;
  lastLaunchMode = mode;
  preparing = true;
  void audio.start();
  const request = ++launchRequest;
  const requestedDrive = drive;
  ui.close();
  controls.clear();
  ui.preparing("正在准备出发地的街道与车辆");
  try {
    await world.load((text) => ui.loading(text));
    const preparation = world.prepareDrive();
    if (world.stats.streetStreaming?.pendingChunkIds.length)
      ui.toast("正在准备沿途景色…");
    await preparation;
  } catch (error) {
    if (request !== launchRequest || drive !== requestedDrive) return;
    preparing = false;
    ui.loadFailed();
    console.error(error);
    return;
  }
  if (request !== launchRequest || drive !== requestedDrive) return;
  preparing = false;
  ui.ready();
  document.body.classList.remove("scene-pending");
  if (!drive.start(mode)) {
    ui.toast("请回到观光车道并顺向行驶后开启自动观光，或按 R 回到附近车道");
    return;
  }
  resetPause();
  if (document.hidden) pauseEvent("hidden");
  else if (mode === "manual" && !document.hasFocus()) pauseEvent("blur");
  home = false;
  world.home = false;
  ui.home(false);
  completionShown = false;
}
function act(action: string, value?: string) {
  if (action === "reload") {
    location.reload();
    return;
  }
  if (!ready) return;
  if (preparing && !["home", "hidden", "visible", "blur", "window-focus", "dialog-closed"].includes(action)) return;
  switch (action) {
    case "retry-load":
      void begin(lastLaunchMode);
      break;
    case "route":
      choose(Number(value));
      break;
    case "auto":
      begin("auto");
      break;
    case "manual":
      begin("manual");
      break;
    case "home":
      launchRequest++;
      preparing = false;
      ui.ready();
      ui.close();
      journey.save.distance=drive.distance;journey.save.lap=drive.laps;journey.save.progress=drive.progress;journey.persist();
      missions.suspend();
      if(drive.phase==='running')drive.phase='paused';
      journey.resetParking();
      resetPause();
      home = true;
      world.home = true;
      ui.home(true);
      controls.clear();
      break;
    case "next":
      ui.close();
      choose((ui.selected + 1) % world.city.routes.length);
      begin("auto");
      break;
    case "restart": {
      const mode = drive.mode;
      ui.close();
      missions.abandon();
      drive.reset();
      journey.resetParking();
      world.setDrive(drive);
      begin(mode);
      break;
    }
    case "gear":
      if(drive.mode==='manual')ui.toast(drive.shiftGear() ? `已切换${drive.gear===1?'前进挡 D':'倒挡 R'}` : '请先停车再换挡');
      break;
    case "recover": {
      const recovered=drive.recover();
      if(recovered){journey.resetParking();missions.noteRecovery();}
      ui.toast(recovered?'车辆已回到附近空闲车道':'附近车道暂时被占用，请稍后再试');controls.clear();
      break;
    }
    case "lighting": {
      const modes=['day','dusk','night'] as const;
      world.setLighting(modes[(modes.indexOf(world.lighting)+1)%modes.length]);
      ui.setLighting(world.lighting);break;
    }
    case "sound":
      audio.muted=!audio.muted;ui.toast(audio.muted?'已关闭驾驶声音':'已开启驾驶声音');break;
    case "horn":
      audio.horn();break;
    case "album":
      void readPhotos().then(photos=>ui.album(journey,photos)).catch(()=>{
        ui.album(journey,[]);
        ui.toast('照片暂时无法读取，收藏进度仍保留，请稍后重试');
      });break;
    case 'missions':
      ui.missionBoard(missions,drive);
      break;
    case 'mission-accept':
      if(missions.accept(value??'',drive,journey.save.penalties)){
        controls.clear();ui.close();void begin('manual');
      }else ui.toast('请先完成或结束当前委托，再接取下一份。');
      break;
    case 'mission-resume':
      ui.close();void begin(home?'manual':drive.mode);
      break;
    case 'mission-retry':
      if(missions.retry(drive,journey.save.penalties)){
        controls.clear();ui.close();void begin('manual');
      }
      break;
    case 'mission-abandon':
      missions.abandon();controls.clear();ui.close();
      break;
    case 'mission-event-accept':
    case 'mission-event-skip':
      if(missions.chooseEvent(action==='mission-event-accept')){
        controls.clear();ui.close();if(home)void begin('manual');
      }
      break;
    case 'mission-dismiss':
      missions.dismissResult();
      break;
    case "capture": {
      if(capturing)break;
      const capture=journey.prepareCapture();
      if(!capture){ui.toast(journey.photoGuidance(drive).instruction);break;}
      capturing=true;
      captureName=capture.stop.name;
      controls.clear();
      ui.journey(journey,drive,captureName);
      void world.capturePhoto().then(async blob=>{
        const stop=capture.stop;
        await storePhoto(stop.id,stop.name,blob);
        if(capture.commit())ui.toast(journey.consumeNotice());
      }).catch(()=>ui.toast('照片保存失败，请检查浏览器存储空间后重试')).finally(()=>{
        capturing=false;captureName=undefined;ui.journey(journey,drive);
      });
      break;
    }
    case "pause":
      if (!home) pauseEvent("pause");
      break;
    case "blur":
    case "hidden":
    case "visible":
      pauseEvent(action);
      break;
    case "window-focus":
      pauseEvent("focus");
      break;
    case "mode":
      if (!drive.setMode(drive.mode === "auto" ? "manual" : "auto")) {
        controls.clear();
        ui.toast("请回到观光车道并顺向行驶后开启自动观光，或按 R 回到附近车道");
        break;
      }
      controls.clear();
      if (drive.mode === "manual" && !document.hasFocus()) pauseEvent("blur");
      ui.toast(
        drive.mode === "auto"
          ? "已开启自动观光"
          : "W / S 加速与刹车，A / D 转向；弯道需要主动转向",
      );
      break;
    case "camera": {
      const cameras: CameraMode[] = ["follow", "vehicle", "hood", "panorama"];
      world.setCamera(
        cameras[(cameras.indexOf(world.mode) + 1) % cameras.length],
      );
      break;
    }
    case "rate":
      drive.rate = drive.rate === 1 ? 2 : drive.rate === 2 ? 3 : 1;
      break;
    case "garage":
      ui.garage();
      break;
    case "car": {
      const c = CARS.find((c) => c.id === value);
      if (!c) return;
      if (!world.isLoaded) {
        world.selectedCar = c;
        ui.setCar(c);
        preferences.car = c.id;
        persist();
        ui.close();
        break;
      }
      void world
        .setCar(c)
        .then((changed) => {
          if (!changed) return;
          ui.setCar(c);
          preferences.car = c.id;
          persist();
          ui.close();
        })
        .catch((error) => {
          console.error(error);
          ui.toast("车辆加载失败，请重试");
        });
      break;
    }
    case "sources":
      ui.sources();
      break;
    case "quality":
      preferences.quality = value === "high" ? "high" : "balanced";
      world.setQuality(preferences.quality);
      document.body.dataset.quality = preferences.quality;
      persist();
      break;
    case "landmark":
      ui.landmark(world.nearest().id);
      break;
    case "focus": {
      const l = LANDMARKS.find((l) => l.id === value);
      if (l) {
        ui.close();
        world.focus(l);
      }
      break;
    }
    case "photo":
      ui.photo();
      break;
    case "dialog-opened":
    case "dialog-closed":
      pauseEvent(action);
      break;
  }
}
async function boot() {
  try {
    const city = await loadCity();
    const journeyResponse=await fetch('/journey.json');
    if(!journeyResponse.ok)throw new Error('观光任务加载失败');
    journey=new Journey(await journeyResponse.json() as JourneyData,localStorage);
    missions=new Missions(journey.data.stops,city.routes[0].length,localStorage);
    ui = new UI(city, act);
    world = new World(document.getElementById("scene")!, city);
    missionsWorld=new MissionsWorld();world.scene.add(missionsWorld.group);
    const selected = CARS.find((c) => c.id === preferences.car) || CARS[0];
    world.selectedCar = selected;
    world.journey=journey;
    world.setQuality(preferences.quality);
    document.body.dataset.quality = preferences.quality;
    choose(
      Math.max(0, city.routes.findIndex((r) => r.id === preferences.route)),
    );
    ui.setCar(selected);
    document.body.classList.add("scene-pending");
    ui.ready();
    ready = true;
    const saveSession=()=>{
      journey.save.distance=drive.distance;journey.save.lap=drive.laps;journey.save.progress=drive.progress;
      journey.persist();missions.suspend();
    };
    window.addEventListener('pagehide',saveSession);
    document.addEventListener('visibilitychange',()=>{if(document.hidden)saveSession();});
    const observation=document.createElement('output');
    observation.id='tour-observation';observation.hidden=true;observation.setAttribute('aria-hidden','true');
    document.body.append(observation);
    let observationElapsed=0;
    let previous = performance.now(),
      uiElapsed = 0;
    function frame(time: number) {
      const dt = Math.min(0.25, Math.max(0, (time - previous) / 1000));
      previous = time;
      observationElapsed+=dt;
      const steps=Math.max(1,Math.ceil(dt/.05));
      for(let i=0;i<steps;i++){
        const step=dt/steps;
        if (world.isLoaded) world.simulateTraffic(step);
        if (!home) {drive.update(step, controls.state);journey.update(step,drive);missions.update(step,drive,journey.save.penalties);}
      }
      audio.update(drive.speed,!home&&drive.phase==='running',(drive.pose.y??0)<-1);
      if(drive.lastImpact && drive.lastImpact.sequence!==playedImpact){playedImpact=drive.lastImpact.sequence;audio.impact(drive.lastImpact.speed);}
      const notice=journey.consumeNotice();if(notice)ui.toast(notice);
      const missionNotice=missions.consumeNotice();if(missionNotice)ui.toast(missionNotice);
      missionsWorld.update(missions.navigation(drive),drive,!home);
      if (world.isLoaded) world.update(dt, time);
      if(observationElapsed>=1){
        observationElapsed=0;
        observation.textContent=JSON.stringify({route:drive.route.id,phase:drive.phase,mode:drive.mode,distance:drive.distance,total:drive.path.total,laps:drive.laps,pose:drive.pose,speed:drive.speed,travelled:drive.travelled,wheels:world.wheelState,collisions:drive.collisions,gear:drive.gear,journey:journey.save,missions:missions.save,...world.stats});
      }
      uiElapsed += dt;
      if (uiElapsed > 0.12) {
        ui.update(drive, world.nearest().id, world.mode, pausePolicy.reason);
        ui.missions(missions,drive);
        ui.journey(journey,drive,captureName);
        uiElapsed = 0;
      }
      if (drive.phase === "complete" && !completionShown) {
        completionShown = true;
        ui.completed();
      }
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
    // Read-only diagnostics support acceptance without controlling the simulation.
    Object.defineProperty(window, "tourDiagnostics", {
      get: () => ({
        route: drive.route.id,
        mode: drive.mode,
        phase: drive.phase,
        pauseReason: drive.phase === "paused" ? pausePolicy.reason : null,
        distance: drive.distance,
        total: drive.path.total,
        car: world.selectedCar.id,
        camera: world.mode,
        pose: drive.pose,
        speed: drive.speed,
        steering: drive.steering,
        travelled: drive.travelled,
        routeDeviation: drive.routeDeviation,
        laps: drive.laps,
        collisions:drive.collisions,
        lastImpact:drive.lastImpact,
        gear:drive.gear,
        journey:{...journey.save,active:journey.active?.id,parkedSeconds:journey.parkedSeconds,canCapture:journey.canCapture,time:journey.time},
        missions:{...missions.save,navigation:missions.navigation(drive),storageAvailable:missions.storageAvailable},
        wheels: world.wheelState,
        ...world.stats,
      }),
    });
  } catch (error) {
    console.error(error);
    if (ui) ui.error(error instanceof Error ? error.message : "加载失败");
    else {
      document.getElementById("app")!.innerHTML =
        '<div class="loading"><p>地图暂时无法加载</p><button class="primary" onclick="location.reload()">重新加载</button></div>';
    }
  }
}
void boot();
