import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "meshoptimizer/decoder";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import { HDRLoader } from "three/addons/loaders/HDRLoader.js";
import {
  CARS,
  LANDMARKS,
  project,
  type City,
  type Point,
  type Car,
  type Landmark,
} from "./data";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { Drive, angleDifference } from "./drive";
import { WheelRig } from "./wheels";
import { CollisionWorld, rectangle } from "./collision";
import { JourneyWorld } from "./journey-world";
import { signalState, type Journey } from "./journey";
import vehicleAssets from "./vehicle-assets.json";
import { vehiclePitch } from "./vehicle-pitch";
import { prepareVehicleMaterials } from "./vehicle-materials";
import { StreetStreaming, type StreetManifest } from "./street-streaming";
import { renderBudget, renderPixelRatio } from "./render-budget";
import { usePerformanceStreets } from "./performance-streets";
import { trafficRespawnDistance } from "./traffic-visibility";
import { VehicleModelCache } from "./vehicle-model-cache";
const detailedAssets: Record<string, { file: string; trafficFile?: string }> = vehicleAssets;
export type CameraMode = "follow" | "vehicle" | "hood" | "panorama";
export class World {
  private composer!: EffectComposer;
  readonly scene = new THREE.Scene();
  readonly camera = new THREE.PerspectiveCamera(52, 1, 0.25, 7500);
  readonly renderer: THREE.WebGLRenderer;
  readonly sun = new THREE.DirectionalLight(0xfff2db, 3.1);
  readonly models = new Map<string, THREE.Group>();
  readonly car = new THREE.Group();
  readonly routeVisual = new THREE.Group();
  mode: CameraMode = "follow";
  orbit = 0;
  pitch = 0.1;
  quality = "balanced";
  home = true;
  /** Fixed-camera acceptance can measure full throughput without the idle cap. */
  continuousRendering = false;
  selectedCar = CARS[0];
  collision?: CollisionWorld;
  journey?: Journey;
  private journeyWorld?: JourneyWorld;
  private trafficDistances: number[] = [];
  private impactShake = 0;
  private impactSequence = 0;
  lighting: "day" | "dusk" | "night" = "day";
  private daylight?: THREE.Texture | THREE.Color | THREE.CubeTexture | null;
  private headlights: THREE.SpotLight[]=[];
  private water?: THREE.Mesh;
  private streets?: StreetStreaming;
  private readonly reflectionResources = new Set<object>();
  private readonly streetReflections = new Map<string, THREE.Texture>();
  private streetDecoder?: DRACOLoader;
  private readonly streetGroup = new THREE.Group();
  private readonly tunnelInteriors: THREE.Mesh[] = [];
  private detailedModels = new VehicleModelCache({
    protectedRoots: () => [this.car, ...this.models.values()],
    protectedResources: () => [this.scene.environment, this.scene.background, this.daylight, ...this.reflectionResources],
  });
  private frames = 0;
  private elapsed = 0;
  private lastFrameTime = 0;
  fps = 0;
  private target = new THREE.Vector3();
  private desired = new THREE.Vector3();
  private cameraReady = false;
  private traffic: THREE.Group[] = [];
  private trafficFleet=CARS.filter(c=>c.id==='model-y'||c.id==='model-3'||!!detailedAssets[c.id]?.trafficFile).slice(0,7);
  private trafficRigs: WheelRig[] = [];
  private trafficTravel = 0;
  private trafficWheelTravel: number[] = [];
  private wheels?: WheelRig;
  private drive?: Drive;
  private lightTarget = new THREE.Object3D();
  private shadowState = "";
  constructor(
    readonly host: HTMLElement,
    readonly city: City,
  ) {
    const canvas=document.createElement("canvas");
    const context=canvas.getContext("webgl2",{antialias:true,alpha:false,powerPreference:"high-performance"});
    if(!context)throw new Error("当前浏览器无法创建三维图形环境");
    const reversedDepth=!!context.getExtension("EXT_clip_control");
    this.renderer = new THREE.WebGLRenderer({
      canvas,
      context,
      antialias: true,
      alpha: false,
      powerPreference: "high-performance",
      reversedDepthBuffer: reversedDepth,
      logarithmicDepthBuffer: !reversedDepth,
    });
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 0.98;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.autoUpdate = false;
    this.renderer.shadowMap.type = THREE.PCFShadowMap;
    for(let i=0;i<2;i++){
      const lamp=new THREE.SpotLight('#e8f2ff',0,65,.43,.65,1.5);
      this.headlights.push(lamp);this.scene.add(lamp,lamp.target);
    }
    this.host.append(this.renderer.domElement);
    this.renderer.domElement.setAttribute(
      "aria-label",
      "上海三维观光场景，拖动可环顾",
    );
    this.scene.background = new THREE.Color("#b6c9d4");
    this.scene.fog = new THREE.FogExp2("#bbcbd2", 0.00014);
    this.scene.add(new THREE.HemisphereLight("#cee3f2", "#79786a", 1.0));
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(2048, 2048);
    Object.assign(this.sun.shadow.camera, {
      left: -90,
      right: 90,
      top: 90,
      bottom: -90,
      near: 1,
      far: 1500,
    });
    // PCF compares reversed depth with GreaterEqual; its bias is not flipped by Three.
    this.sun.shadow.bias = this.renderer.capabilities.reversedDepthBuffer ? 0.00006 : -0.00006;
    this.sun.shadow.normalBias = 0.035;
    this.sun.target = this.lightTarget;
    this.sun.position.set(450, 450, 300);
    this.scene.add(this.sun, this.lightTarget, this.car, this.routeVisual);
    const target = new THREE.WebGLRenderTarget(1, 1, {
      type: THREE.HalfFloatType,
      samples: Math.min(2, this.renderer.capabilities.maxSamples),
    });
    // Reversed floating-point depth retains precision for centimetre facade
    // offsets across the river and preserves hardware early-depth rejection.
    target.depthTexture=new THREE.DepthTexture(1,1,THREE.FloatType);
    this.composer = new EffectComposer(this.renderer, target);
    this.composer.addPass(new RenderPass(this.scene, this.camera));
    this.composer.addPass(new OutputPass());
    this.renderer.info.autoReset = false;
    this.resize();
    window.addEventListener("resize", () => this.resize());
    let last: Point | undefined;
    this.renderer.domElement.addEventListener("pointerdown", (e) => {
      last = [e.clientX, e.clientY];
      this.renderer.domElement.setPointerCapture(e.pointerId);
    });
    this.renderer.domElement.addEventListener("pointermove", (e) => {
      if (!last) return;
      this.orbit -= (e.clientX - last[0]) * 0.005;
      this.pitch = THREE.MathUtils.clamp(
        this.pitch + (e.clientY - last[1]) * 0.003,
        -0.12,
        0.65,
      );
      last = [e.clientX, e.clientY];
    });
    this.renderer.domElement.addEventListener(
      "pointerup",
      () => (last = undefined),
    );
    this.renderer.domElement.addEventListener(
      "pointercancel",
      () => (last = undefined),
    );
  }
  private loading?: Promise<void>;
  isLoaded = false;
  load(progress: (text: string) => void): Promise<void> {
    if (this.isLoaded) return Promise.resolve();
    if (!this.loading) this.loading = this.loadScene(progress).then(() => { this.isLoaded = true; }).catch(error => {
      this.loading = undefined;
      throw error;
    });
    return this.loading;
  }
  private async loadScene(progress: (text: string) => void) {
    progress("铺设上海江岸与街道");
    if (!this.streets) {
    const collisionResponse=await fetch('/streets/collisions.json');
    if(!collisionResponse.ok)throw new Error('道路碰撞数据加载失败');
    this.collision=new CollisionWorld((await collisionResponse.json()).obstacles);
    if(this.drive)this.drive.collision=this.collision;
    const response = await fetch(import.meta.env.VITE_STREET_MANIFEST || "/streets/master/manifest.json");
    if (!response.ok) throw new Error("街景资源暂时无法读取，请重新加载");
    let manifest: StreetManifest = await response.json();
    if (manifest.version !== 1 || !manifest.chunks.length)
      throw new Error("街景资源清单不完整");
    if (!manifest.delivery) try {
      const compact = await fetch("/streets/performance/manifest.json");
      if (compact.ok) manifest = usePerformanceStreets(manifest, (await compact.json()).variants);
    } catch {
      // Original assets remain usable if the optional derived manifest is absent.
    }
    const hdr = await new HDRLoader().loadAsync("/environment/sky.hdr");
    hdr.mapping = THREE.EquirectangularReflectionMapping;
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    this.scene.environment = pmrem.fromEquirectangular(hdr).texture;
    this.scene.background = hdr;
    this.daylight=hdr;
    this.scene.backgroundIntensity = 0.9;
    pmrem.dispose();
    this.streetDecoder = new DRACOLoader().setDecoderPath("/decoders/draco/").setWorkerLimit(1);
    const loader = new GLTFLoader().setDRACOLoader(this.streetDecoder).setMeshoptDecoder(MeshoptDecoder);
    this.streetGroup.name = "Shanghai street master runtime";
    this.scene.add(this.streetGroup);
    const streetLoader = {
      loadAsync: async (file: string) => {
        // Absolute base URL lets GLTFLoader resolve host-relative shared textures.
        const gltf = await loader.loadAsync(new URL(file, location.href).href);
        const textures = await gltf.parser.getDependencies("texture");
        if (textures.some((texture: THREE.Texture | null) => !texture))
          gltf.scene.userData.textureFailure = true;
        return gltf;
      },
    };
    this.streets = new StreetStreaming(this.streetGroup, streetLoader, manifest, {
      loadRadius: renderBudget(this.quality).loadRadius,
      unloadRadius: renderBudget(this.quality).unloadRadius,
      maxConcurrent: 1, anisotropy: renderBudget(this.quality).anisotropy,
      protectedResources: this.reflectionResources,
      prepareScene: (scene, chunk) => {
        // GLTFLoader can resolve a scene after an image decode failure. Reject
        // that partial scene so missing facades cannot silently look complete.
        if (scene.userData.textureFailure)
          throw new Error(`街景纹理未能解码：${chunk.id}`);
        scene.traverse((object) => {
          if (!(object instanceof THREE.Mesh)) return;
          object.receiveShadow = true;
          if (/^context-tunnel-(shell|rib|panel|cream|joint|light|fixture|fire|green)$/.test(object.name))
            this.tunnelInteriors.push(object);
          this.applyStreetReflection(object);
          this.applyWindowLighting(object);
          object.castShadow = !object.name.startsWith("context-") ||
            /context-(heritage|modern|lowrise|roof)/.test(object.name);
          if (object.name === "context-water") {
            this.water = object;
            const material = object.material as THREE.MeshStandardMaterial;
            material.metalness = 0.12;
            material.roughness = 0.24;
            material.onBeforeCompile = (shader) => {
              shader.uniforms.uTime = { value: 0 };
              material.userData.shader = shader;
              shader.vertexShader = shader.vertexShader
                .replace("#include <common>", "#include <common>\nuniform float uTime;")
                .replace("#include <begin_vertex>", "#include <begin_vertex>\ntransformed.y += sin(position.x * .11 + uTime) * .035 + sin(position.z * .15 + uTime * .8) * .025;");
              shader.fragmentShader = shader.fragmentShader.replace("#include <normal_fragment_begin>", "#include <normal_fragment_begin>\nnormal = normalize(normal + vec3(sin(vViewPosition.x * .3) * .06, 0.0, cos(vViewPosition.z * .3) * .06));");
            };
          }
        });
        progress(`还原沿街建筑 · ${chunk.id === "context" ? "道路与江面" : chunk.id === "skyline" ? "上海天际线" : "街区"}`);
      },
      onError: (failure) => {
        document.body.dataset.streetError = failure.error;
        console.error("Street chunk failed", failure.id, failure.error);
      },
      onUnload: (scene) => {
        const removed = new Set<THREE.Object3D>();
        scene.traverse(object => removed.add(object));
        for (let i = this.tunnelInteriors.length - 1; i >= 0; i--)
          if (removed.has(this.tunnelInteriors[i])) this.tunnelInteriors.splice(i, 1);
      },
    });
    }
    this.streets!.retryFailed();
    const loader = new GLTFLoader().setDRACOLoader(this.streetDecoder!).setMeshoptDecoder(MeshoptDecoder);
    let count = 0;
    const preparation = await Promise.allSettled([
      this.streets!.readyAt(this.drive?.pose.x ?? 0, this.drive?.pose.z ?? 0),
      ...this.trafficFleet.map(async (car) => {
        if (this.models.has(car.id)) return;
        // Traffic uses inexpensive exterior proxies. Load a detailed vehicle
        // only when the player selects it, instead of decoding the whole garage.
        const model = (await loader.loadAsync(detailedAssets[car.id]?.trafficFile??`/vehicles/rigged/prototypes/${car.id}.glb`)).scene;
        prepareVehicleMaterials(model,car.id);
        model.traverse((object) => {
          if (object instanceof THREE.Mesh) { object.castShadow = true; object.receiveShadow = true; }
        });
        this.models.set(car.id, model);
        progress(`加载观光车辆 ${++count} / ${this.trafficFleet.length}`);
      }),
    ]);
    const failure = preparation.find(result => result.status === "rejected");
    if (failure?.status === "rejected") throw failure.reason;
    if (this.quality === "high") this.captureStreetReflections();
    await this.setCar(this.selectedCar);
    if (!this.traffic.length) for (const car of this.trafficFleet) {
      const g = this.clone(car.id);
      this.traffic.push(g);
      this.trafficRigs.push(new WheelRig(g));
      this.scene.add(g);
    }
    if(!this.journeyWorld && this.journey && this.drive){this.journeyWorld=new JourneyWorld(this.journey.data,this.drive.path);this.scene.add(this.journeyWorld.group);}
    this.setLighting(this.lighting);
    progress("上海已准备好");
  }
  private applyStreetReflection(object: THREE.Mesh) {
    const region = object.getWorldPosition(new THREE.Vector3()).x < -350 ? "bund" : "pudong";
    const reflection = this.streetReflections.get(region);
    if (!reflection) return;
    for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
      if (material instanceof THREE.MeshStandardMaterial && /glass|glaz/i.test(material.name)) {
        material.envMap = reflection;
        material.envMapIntensity = 0.85;
        material.needsUpdate = true;
      }
    }
  }
  private captureStreetReflections() {
    // One static neighbouring-building reflection per river bank. No per-frame
    // cubemap rendering, and no recursion into an unfinished reflection map.
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    // CubeCamera renders before the driving loop's first frame. Allocate the
    // depth comparison texture before any shadow sampler can read it.
    this.renderer.shadowMap.needsUpdate = true;
    for (const [region, x, y, z] of [["bund", -730, 24, -60], ["pudong", 490, 34, 20]] as const) {
      const target = new THREE.WebGLCubeRenderTarget(256, { type: THREE.HalfFloatType });
      const camera = new THREE.CubeCamera(1, 3500, target);
      camera.position.set(x, y, z);
      camera.update(this.renderer, this.scene);
      const reflection = pmrem.fromCubemap(target.texture).texture;
      this.streetReflections.set(region, reflection);
      this.reflectionResources.add(reflection);
      target.dispose();
    }
    pmrem.dispose();
    this.streetGroup.traverse(object => { if (object instanceof THREE.Mesh) this.applyStreetReflection(object); });
  }
  async prepareDrive() {
    if (this.drive && this.streets) {
      const p = this.drive.pose;
      this.streets.retryFailed();
      await this.streets.readyAt(p.x, p.z);
    }
  }
  private clone(id: string) {
    const group = this.models.get(id);
    if (!group) throw new Error("缺少模型 " + id);
    return group.clone(true);
  }

  async setCar(c: Car) {
    const install = (model: THREE.Group) => {
      if (this.selectedCar.id === c.id && this.car.children.length) return;
      // Validate the independent wheel hierarchy before detaching the current car.
      // Three.clone shares geometry/material/texture with the cache-owned template.
      const instance = model.clone(true);
      const wheels = new WheelRig(instance);
      if (this.drive) wheels.update(this.drive.travelled, this.drive.steering, c.wheelbase / 1000);
      this.car.clear();this.car.add(instance);
      this.selectedCar = c;this.wheels = wheels;
      if (this.drive) {
        this.drive.dynamics.setVehicle(c.id);
        this.drive.wheelbase = c.wheelbase / 1000;
        const bounds=(c as Car & {collisionDimensions?:number[]}).collisionDimensions??c.dimensions;
        this.drive.vehicleWidth = bounds[1]/1000;
        this.drive.vehicleLength = bounds[0]/1000;
      }
    };
    const asset = detailedAssets[c.id];
    if (asset) {
      return this.detailedModels.select(c.id, async () => {
        const decoder = new DRACOLoader()
          .setDecoderPath("/decoders/draco/")
          .setWorkerLimit(1);
        try {
          const model = (
            await new GLTFLoader()
              .setDRACOLoader(decoder)
              .loadAsync(asset.file)
          ).scene;
          prepareVehicleMaterials(model,c.id);
          model.traverse((o) => {
            if (o instanceof THREE.Mesh) { o.castShadow = true;o.receiveShadow = true; }
          });
          return model;
        } finally {
          decoder.dispose();
        }
      }, install);
    }
    return this.detailedModels.selectBorrowed(this.models.get(c.id), install);
  }
  setDrive(d: Drive) {
    this.drive = d;
    d.dynamics.setVehicle(this.selectedCar.id);
    this.wheels?.reset(d.travelled);
    d.wheelbase = this.selectedCar.wheelbase / 1000;
    const bounds=(this.selectedCar as Car & {collisionDimensions?:number[]}).collisionDimensions??this.selectedCar.dimensions;
    d.vehicleWidth=bounds[1]/1000;d.vehicleLength=bounds[0]/1000;d.collision=this.collision;
    this.trafficDistances=[];
    this.trafficTravel = 0;
    this.trafficWheelTravel=[];
    this.home = true;
    this.cameraReady = false;
    this.orbit = 0;
    this.pitch = 0.1;
    this.routeVisual.children.forEach((o) => {
      if (o instanceof THREE.Line) {
        o.geometry.dispose();
        (o.material as THREE.Material).dispose();
      }
    });
    this.routeVisual.clear();
    const route = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(
        d.route.points.map((p,i) => new THREE.Vector3(p[0], (d.route.elevations?.[i]??0)+0.19, p[1])),
      ),
      new THREE.LineBasicMaterial({
        color: "#8e9475",
        transparent: true,
        opacity: 0.45,
      }),
    );
    this.routeVisual.add(route);
    route.visible=false;
  }
  setCamera(mode: CameraMode) {
    this.mode = mode;
    this.orbit = 0;
    this.pitch = 0.1;
  }
  setQuality(q: string) {
    this.quality = q === "high" ? "high" : "balanced";
    const budget = renderBudget(this.quality);
    this.streets?.setRadii(budget.loadRadius, budget.unloadRadius);
    // GTAOPass reconstructs conventional perspective depth. Keep it out of
    // this large-map extended-depth pipeline; high mode adds shadows and
    // resolution without introducing incorrect screen-space occlusion.
    this.renderer.shadowMap.enabled = budget.shadows;
    this.sun.shadow.mapSize.set(budget.shadowSize, budget.shadowSize);
    this.sun.shadow.map?.dispose();
    this.sun.shadow.map = null;
    this.resize();
  }
  resize() {
    const w = this.host.clientWidth || innerWidth,
      h = this.host.clientHeight || innerHeight;
    this.renderer.setPixelRatio(
      renderPixelRatio(w, h, devicePixelRatio, this.quality),
    );
    this.renderer.setSize(w, h);
    this.composer?.setPixelRatio(this.renderer.getPixelRatio());
    this.composer?.setSize(w, h);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }
  focus(l: Landmark) {
    const p = project(l.lon, l.lat);
    this.home = false;
    this.mode = "panorama";
    this.orbit = 0;
    this.target.set(p[0], l.height * 0.4, p[1]);
    this.desired.set(
      p[0] - Math.max(130, l.height * 0.9),
      l.height * 0.55,
      p[1] + Math.max(120, l.height * 0.7),
    );
    this.focusUntil = performance.now() + 12000;
    this.streetFocus = p;
  }
  private focusUntil = 0;
  private streetFocus?: Point;
  update(dt: number, time: number) {
    const d = this.drive;
    if (!d) return;
    // Hidden tabs need no GPU work. Home and paused screens stay interactive at
    // 20 fps; driving and fixed-camera measurements use the normal frame loop.
    if (document.hidden) return;
    if (!this.continuousRendering && (this.home || d.phase !== "running")) {
      if (time - this.lastFrameTime < 50) return;
      dt = Math.min(.1, this.lastFrameTime ? (time - this.lastFrameTime) / 1000 : dt);
    }
    const p = d.pose;
    // Deep tunnel details cannot be seen from the skyline or distant streets.
    // Keep them available before either portal enters view; geometry is intact.
    const nearTunnel=!this.home && (d.route.tunnels??[]).some(t=>d.distance>t.start-140 && d.distance<t.end+140);
    for(const object of this.tunnelInteriors)object.visible=nearTunnel;
    const streetFocus = this.focusUntil > time && this.streetFocus ? this.streetFocus : [p.x, p.z];
    const lookAhead = d.phase === "running" && !this.home && this.focusUntil <= time
      ? { x: p.x + Math.sin(p.heading) * Math.sign(d.gear) * Math.min(400, Math.abs(d.speed) * d.rate * 8),
          z: p.z + Math.cos(p.heading) * Math.sign(d.gear) * Math.min(400, Math.abs(d.speed) * d.rate * 8) } : undefined;
    this.streets?.update(streetFocus[0], streetFocus[1], lookAhead);
    this.car.position.set(p.x, (p.y??0)+0.15, p.z);
    for(let i=0;i<this.headlights.length;i++){
      const lamp=this.headlights[i],side=(i-.5)*1.25;
      lamp.position.set(p.x+Math.sin(p.heading)*1.9+Math.cos(p.heading)*side,(p.y??0)+.8,p.z+Math.cos(p.heading)*1.9-Math.sin(p.heading)*side);
      lamp.target.position.set(p.x+Math.sin(p.heading)*27,(p.y??0)+.05,p.z+Math.cos(p.heading)*27);
      lamp.intensity=this.home?0:(p.y??0)<-1||this.lighting==='night'?75:this.lighting==='dusk'?30:0;
    }
    if(d.lastImpact && d.lastImpact.sequence!==this.impactSequence){this.impactSequence=d.lastImpact.sequence;this.impactShake=Math.min(.25,d.lastImpact.speed*.02);}
    this.impactShake*=Math.exp(-dt*8);
    this.journeyWorld?.update(this.journey?.time??0,this.journey?.save.collected??[]);
    this.car.rotation.set(vehiclePitch(d.path,d.distance,p.heading,p.y??0),p.heading+Math.PI,0,'YXZ');
    this.wheels?.update(d.travelled, d.steering, d.wheelbase);
    this.lightTarget.position.set(p.x, 0, p.z);
    this.sun.position.set(p.x + 450, 450, p.z + 300);
    const shadowExtent = this.home ? 1000 : 75;
    Object.assign(this.sun.shadow.camera, {
      left: -shadowExtent,
      right: shadowExtent,
      top: shadowExtent,
      bottom: -shadowExtent,
    });
    this.sun.shadow.camera.updateProjectionMatrix();
    const angle = p.heading + this.orbit,
      portrait = this.camera.aspect < 0.8;
    this.car.visible = this.mode !== "hood" || this.home;
    if (this.focusUntil > time) {
    } else if (this.home) {
      const pudong = d.route.id === "pudong";
      this.desired.set(
        pudong ? -520 : -1060,
        portrait ? 230 : 170,
        pudong ? 780 : 650,
      );
      this.target.set(pudong ? 550 : 380, portrait ? 230 : 200, -50);
    } else if (this.mode === "follow") {
      const dist = portrait ? 13 : 10;
      this.desired.set(
        p.x - Math.sin(angle) * dist,
        4.0 + this.pitch * 12,
        p.z - Math.cos(angle) * dist,
      );
      const ahead = portrait ? 3 : 6;
      this.target.set(
        p.x + Math.sin(p.heading) * ahead,
        1.0,
        p.z + Math.cos(p.heading) * ahead,
      );
    } else if (this.mode === "vehicle") {
      const dist = portrait ? 7.8 : 6.8;
      this.desired.set(
        p.x + Math.sin(angle + 0.75) * dist,
        1.65 + this.pitch * 5,
        p.z + Math.cos(angle + 0.75) * dist,
      );
      this.target.set(p.x, 0.85, p.z);
    } else if (this.mode === "hood") {
      this.desired.set(
        p.x + Math.sin(p.heading) * 0.5,
        1.5,
        p.z + Math.cos(p.heading) * 0.5,
      );
      this.target.set(
        p.x + Math.sin(angle) * 30,
        2 + this.pitch * 20,
        p.z + Math.cos(angle) * 30,
      );
    } else {
      this.desired.set(
        p.x - Math.sin(angle + 1.1) * 120,
        105 + this.pitch * 100,
        p.z - Math.cos(angle + 1.1) * 120,
      );
      this.target.set(p.x, 24, p.z);
    }
    if(!this.home && this.focusUntil<=time){
      this.desired.y+=p.y??0;this.target.y+=p.y??0;
      this.desired.x+=Math.sin(time*.13)*this.impactShake;this.desired.y+=Math.cos(time*.11)*this.impactShake;
      if((p.y??0)<-1 && this.mode!=='hood'){
        const behind=d.path.pose(d.distance-5,1.4);
        this.desired.x=behind.x;this.desired.z=behind.z;
        this.desired.y=Math.min(this.desired.y,(p.y??0)+3.7);
        const ahead=d.path.pose(d.distance+7,1.4);
        this.target.set(ahead.x,(ahead.y??0)+1.6,ahead.z);
      }
    }
    if (!this.cameraReady) {
      this.camera.position.copy(this.desired);
      this.cameraReady = true;
    } else this.camera.position.lerp(this.desired, 1 - Math.exp(-dt * 3));
    this.camera.lookAt(this.target);
    const mat = this.water?.material as THREE.MeshPhysicalMaterial | undefined;
    if (mat?.userData.shader)
      mat.userData.shader.uniforms.uTime.value = time * 0.001;
    // The sun, buildings and foliage are static. A paused tour's traffic is
    // static too, so orbiting the camera can reuse the identical shadow map.
    // Any movement, route/car/view/quality change invalidates it immediately.
    const shadowState = `${p.x},${p.z},${p.heading},${d.steering},${this.trafficTravel},${this.home},${this.mode},${this.selectedCar.id},${this.quality},${this.streets?.currentRevision}`;
    this.renderer.shadowMap.needsUpdate = shadowState !== this.shadowState;
    this.shadowState = shadowState;
    this.renderer.info.reset();
    this.composer.render(dt);
    this.frames++;
    this.elapsed += this.lastFrameTime ? (time - this.lastFrameTime) / 1000 : 0;
    this.lastFrameTime = time;
    if (this.elapsed > 1) {
      this.fps = Math.round(this.frames / this.elapsed);
      document.body.dataset.performance = JSON.stringify(this.stats);
      document.body.dataset.tour = JSON.stringify({
        route: d.route.id,
        phase: d.phase,
        distance: d.distance,
        total: d.path.total,
        car: this.selectedCar.id,
        camera: this.mode,
      });
      this.frames = 0;
      this.elapsed = 0;
    }
  }
  simulateTraffic(dt: number) {
    const d=this.drive;if(!d||!this.collision)return;
    const running=!this.home&&d.phase==='running', p=d.pose;
    const step=running?dt*(d.mode==='auto'?d.rate:1):0;
    const traffic=[];
    const frustum=new THREE.Frustum().setFromProjectionMatrix(new THREE.Matrix4().multiplyMatrices(this.camera.projectionMatrix,this.camera.matrixWorldInverse),THREE.WebGLCoordinateSystem,this.camera.reversedDepth);
    const visibleDistance=(distance:number)=>{
      if(this.home)return false;
      const position=d.path.pose(distance,1.4);
      return Math.hypot(position.x-p.x,position.z-p.z)<900 &&
        frustum.intersectsSphere(new THREE.Sphere(new THREE.Vector3(position.x,(position.y??0)+1,position.z),4));
    };
    d.autoStopDistance=this.journey?.redAhead(d);
    const player={id:'player',kind:'vehicle',points:rectangle(p.x,p.z,p.heading,d.vehicleWidth,d.vehicleLength),minY:p.y??0,maxY:(p.y??0)+1.8};
    for(let i=0;i<this.traffic.length;i++){
      let distance=this.trafficDistances[i]??(d.distance+100+i*105)%d.path.total;
      distance=trafficRespawnDistance(distance,d.distance,d.path.total,i,visibleDistance)??distance;
      let gap=(d.distance-distance+d.path.total)%d.path.total;
      if(Math.abs(d.lateral-1.4)>2.5)gap=Infinity;
      for(let j=0;j<this.trafficDistances.length;j++)if(j!==i)gap=Math.min(gap,(this.trafficDistances[j]-distance+d.path.total)%d.path.total);
      for(const signal of this.journey?.data.signals??[])if(this.journey && signalState(this.journey.time,signal)!=='green')gap=Math.min(gap,(signal.distance-distance+d.path.total)%d.path.total+4);
      const speed=Math.min(8,Math.sqrt(Math.max(0,gap-9)*3));
      const car=this.trafficFleet[i], before=d.path.pose(distance,1.4);
      const bounds=(car as Car & {collisionDimensions?:number[]}).collisionDimensions??car.dimensions;
      const desiredDistance=(distance+speed*step)%d.path.total,desired=d.path.pose(desiredDistance,1.4);
      const movement=step>0?this.collision.move(before,desired,bounds[1]/1000,bounds[0]/1000,{ignoreId:`traffic-${i}`,extra:[player]}):{pose:before,contacts:[]};
      // A traffic car brakes before contact. It never pushes the player or snaps
      // through an obstacle to reach its next route point.
      const q=movement.contacts.length?before:desired;
      if(!movement.contacts.length)distance=desiredDistance;
      this.trafficDistances[i]=distance;
      const travel=Math.hypot(q.x-before.x,q.z-before.z);
      this.trafficTravel+=travel;this.trafficWheelTravel[i]=(this.trafficWheelTravel[i]??0)+travel;
      const steer=travel>.0001?-Math.atan(angleDifference(q.heading,before.heading)/travel*car.wheelbase/1000):0;
      const g=this.traffic[i];g.position.set(q.x,(q.y??0)+.15,q.z);g.rotation.set(vehiclePitch(d.path,distance,q.heading,q.y??0),q.heading+Math.PI,0,'YXZ');
      g.visible=!this.home&&Math.hypot(q.x-p.x,q.z-p.z)<900;
      this.trafficRigs[i].update(this.trafficWheelTravel[i],steer,car.wheelbase/1000);
      traffic.push({id:`traffic-${i}`,pose:q,width:bounds[1]/1000,length:bounds[0]/1000});
      const ahead=(distance-d.distance+d.path.total)%d.path.total;
      if(ahead<150)d.autoStopDistance=Math.min(d.autoStopDistance??Infinity,Math.max(0,ahead-7));
    }
    this.collision.setTraffic(traffic);
  }
  private applyWindowLighting(object: THREE.Mesh) {
    const night=this.lighting==='night',dusk=this.lighting==='dusk';
    for(const material of Array.isArray(object.material)?object.material:[object.material]){
      if(material instanceof THREE.MeshStandardMaterial && /glass|glaz|window/i.test(material.name)){
        material.emissive.set(night?'#cba06c':dusk?'#675644':'#000000');
        material.emissiveIntensity=night?.25:dusk?.08:0;
      }
    }
  }
  setLighting(value: "day" | "dusk" | "night") {
    this.lighting=value;
    const night=value==='night',dusk=value==='dusk';
    this.scene.background=night?new THREE.Color('#101b31'):this.daylight??this.scene.background;
    this.scene.backgroundIntensity=dusk?.45:.9;
    this.scene.environmentIntensity=night?.16:dusk?.52:1;
    this.sun.color.set(dusk?'#ffd0a0':'#fff2db');this.sun.intensity=night?.12:dusk?1.4:3.1;
    if(this.scene.fog instanceof THREE.FogExp2)this.scene.fog.color.set(night?'#111d2d':dusk?'#bca79b':'#bbcbd2');
    this.scene.traverse(o=>{if(o instanceof THREE.HemisphereLight)o.intensity=night?.26:dusk?.5:1;});
    this.streetGroup.traverse(o=>{if(o instanceof THREE.Mesh)this.applyWindowLighting(o);});
    this.shadowState='';
  }
  async capturePhoto(): Promise<Blob> {
    this.composer.render(0);
    return new Promise((resolve,reject)=>this.renderer.domElement.toBlob(blob=>blob?resolve(blob):reject(new Error('照片生成失败')),'image/jpeg',.9));
  }
  nearest() {
    if (!this.drive) return LANDMARKS[0];
    const p = this.drive.pose;
    return [...LANDMARKS].sort((a, b) => {
      const x = project(a.lon, a.lat),
        y = project(b.lon, b.lat);
      return (
        Math.hypot(x[0] - p.x, x[1] - p.z) - Math.hypot(y[0] - p.x, y[1] - p.z)
      );
    })[0];
  }
  get stats() {
    return {
      sceneReady: this.isLoaded,
      fps: this.fps,
      drawCalls: this.renderer.info.render.calls,
      triangles: this.renderer.info.render.triangles,
      geometries: this.renderer.info.memory.geometries,
      textures: this.renderer.info.memory.textures,
      quality: this.quality,
      pixelRatio: this.renderer.getPixelRatio(),
      detailedCarsLoaded: this.detailedModels.size,
      trafficCars: this.traffic.length,
      retainedTunnelMeshes: this.tunnelInteriors.length,
      trafficModels: this.trafficFleet.map(car=>car.id),
      shadows: this.renderer.shadowMap.enabled,
      depthMode: this.renderer.capabilities.reversedDepthBuffer ? "reversed-float" : this.renderer.capabilities.logarithmicDepthBuffer ? "logarithmic" : "standard",
      streetStreaming: this.streets?.stats,
      colliders:this.collision?.count,
      lighting:this.lighting,
    };
  }
  get wheelState() {
    return this.wheels?.snapshot || [];
  }
}
