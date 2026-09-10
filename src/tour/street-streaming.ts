import * as THREE from "three";
import { createStreetTreeLod, type StreetTreeLod, type StreetTreeLodOptions } from "./street-lod";

/** Coordinates are metres: X east, Z south, Y up. Chunk scenes already contain world placement. */
export type StreetChunk = {
  id: string;
  file: string;
  bounds: [number, number, number, number];
  bytes: number;
  sha256?: string;
  triangles: number;
  coveredWays: number[];
  always?: boolean;
};
export type StreetManifest = {
  version: number | string;
  master?: { file: string; bytes: number; triangles?: number; [key: string]: unknown };
  delivery?: boolean;
  chunks: StreetChunk[];
  coveredWays: number[];
};
/** GLTFLoader satisfies this interface. A custom loader transfers ownership of its scene resources. */
export type StreetChunkLoader = {
  loadAsync(file: string): Promise<{ scene: THREE.Group; animations?: readonly unknown[] }>;
};
export type StreetStreamingOptions = {
  loadRadius?: number;
  unloadRadius?: number;
  maxConcurrent?: number;
  anisotropy?: number;
  instanceStaticMeshes?: boolean;
  /** Near trees retain their original geometry; false disables distance LOD. */
  treeLod?: false | StreetTreeLodOptions;
  /** Include borrowed resources that may not be attached to the surrounding scene. */
  protectedResources?: ReadonlySet<object>;
  /** Assign shadows/materials before the static-instancing safety checks run. */
  prepareScene?: (scene: THREE.Group, chunk: StreetChunk) => void;
  onError?: (failure: StreetChunkFailure) => void;
  /** Drop application references before the chunk's GPU and CPU resources are released. */
  onUnload?: (scene: THREE.Group) => void;
};
export type StreetChunkFailure = { id: string; file: string; error: string };

export function distanceToStreetBounds(x: number, z: number, bounds: readonly number[]) {
  return Math.hypot(Math.max(bounds[0] - x, 0, x - bounds[2]), Math.max(bounds[1] - z, 0, z - bounds[3]));
}

/** Pure desired-load and hysteresis decisions; nearest first also defines queue priority. */
export function planStreetChunks(chunks: readonly StreetChunk[], x: number, z: number, loadRadius = 850, unloadRadius = 1400) {
  const sorted = chunks.map(chunk => ({ chunk, distance: distanceToStreetBounds(x, z, chunk.bounds) }))
    .sort((a, b) => Number(Boolean(b.chunk.always)) - Number(Boolean(a.chunk.always)) || a.distance - b.distance || a.chunk.id.localeCompare(b.chunk.id));
  return {
    required: sorted.filter(({ chunk, distance }) => chunk.always || distance <= loadRadius).map(({ chunk }) => chunk.id),
    retained: new Set(sorted.filter(({ chunk, distance }) => chunk.always || distance <= unloadRadius).map(({ chunk }) => chunk.id)),
  };
}

type Disposable = object & { dispose?: () => void; close?: () => void };
function materialResources(material: THREE.Material, into: Set<Disposable>) {
  into.add(material);
  const textures = new Set<THREE.Texture>();
  for (const value of Object.values(material)) {
    if (value instanceof THREE.Texture) textures.add(value);
    if (Array.isArray(value)) for (const entry of value) if (entry instanceof THREE.Texture) textures.add(entry);
  }
  if (material instanceof THREE.ShaderMaterial) {
    const visit = (value: unknown, depth: number) => {
      if (value instanceof THREE.Texture) textures.add(value);
      else if (depth < 4 && value && typeof value === "object") for (const child of Object.values(value)) visit(child, depth + 1);
    };
    visit(material.uniforms, 0);
  }
  for (const texture of textures) {
    into.add(texture);
    const images = Array.isArray(texture.source.data) ? texture.source.data : [texture.source.data];
    for (const image of images) if (image && typeof image.close === "function") into.add(image);
  }
}
function collectResources(root: THREE.Object3D, exclude?: THREE.Object3D, into = new Set<Disposable>()) {
  const visit = (object: THREE.Object3D) => {
    if (object === exclude) return;
    if (object instanceof THREE.Mesh || object instanceof THREE.Line || object instanceof THREE.Points || object instanceof THREE.Sprite) {
      into.add(object.geometry);
      for (const material of Array.isArray(object.material) ? object.material : [object.material]) materialResources(material, into);
      if (object instanceof THREE.InstancedMesh) into.add(object);
    }
    for (const child of object.children) visit(child);
  };
  visit(root);
  return into;
}

function instanceable(mesh: THREE.Mesh, scene: THREE.Group) {
  if (mesh.constructor !== THREE.Mesh || mesh.children.length || mesh.morphTargetInfluences?.length || mesh.geometry.morphAttributes.position?.length) return false;
  if (mesh.onBeforeRender !== THREE.Object3D.prototype.onBeforeRender || mesh.onAfterRender !== THREE.Object3D.prototype.onAfterRender) return false;
  for (let parent: THREE.Object3D | null = mesh; parent; parent = parent.parent) {
    if (!parent.visible) return false;
    if (parent === scene) break;
  }
  if (mesh.matrixWorld.determinant() <= 0) return false;
  return (Array.isArray(mesh.material) ? mesh.material : [mesh.material]).every(material =>
    !material.transparent && !(material instanceof THREE.ShaderMaterial) &&
    !("transmission" in material && Number(material.transmission) > 0) &&
    material.onBeforeCompile === THREE.Material.prototype.onBeforeCompile);
}

/** Preserve nested transforms and render state; never combine merely similar material values. */
export function instanceStreetMeshes(scene: THREE.Group, treeOptions: false | StreetTreeLodOptions = {}) {
  scene.updateMatrixWorld(true);
  const treeLod = treeOptions === false ? undefined : createStreetTreeLod(scene, treeOptions, mesh => instanceable(mesh, scene));
  const inverseRoot = scene.matrixWorld.clone().invert();
  const groups = new Map<string, THREE.Mesh[]>();
  scene.traverse(object => {
    if (!(object instanceof THREE.Mesh) || !instanceable(object, scene)) return;
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    const key = [object.geometry.uuid, materials.map(material => material.uuid).join(","), object.castShadow, object.receiveShadow, object.renderOrder, object.layers.mask, object.frustumCulled].join("|");
    const group = groups.get(key) ?? [];
    group.push(object); groups.set(key, group);
  });
  let batches = treeLod?.stats.batches ?? 0, meshesSaved = 0;
  if (treeLod) {
    scene.traverse(object => {
      if (object instanceof THREE.InstancedMesh && object.userData.streetTreeLod === "near") meshesSaved += object.count - 1;
    });
  }
  for (const meshes of groups.values()) {
    if (meshes.length < 2) continue;
    const first = meshes[0];
    const batch = new THREE.InstancedMesh(first.geometry, first.material, meshes.length);
    batch.name = `street-instances-${batches}`;
    batch.castShadow = first.castShadow; batch.receiveShadow = first.receiveShadow;
    batch.renderOrder = first.renderOrder; batch.layers.mask = first.layers.mask; batch.frustumCulled = first.frustumCulled;
    batch.userData.instanceNames = meshes.map(mesh => mesh.name);
    batch.userData.instanceMetadata = meshes.map(mesh => mesh.userData);
    meshes.forEach((mesh, index) => batch.setMatrixAt(index, new THREE.Matrix4().multiplyMatrices(inverseRoot, mesh.matrixWorld)));
    batch.instanceMatrix.needsUpdate = true;
    batch.computeBoundingBox(); batch.computeBoundingSphere();
    for (const mesh of meshes) mesh.removeFromParent();
    scene.add(batch); batches++; meshesSaved += meshes.length - 1;
  }
  return treeLod ? { batches, meshesSaved, treeLod } : { batches, meshesSaved };
}

type LoadedChunk = { chunk: StreetChunk; scene: THREE.Group; resources: Set<Disposable>; batches: number; meshesSaved: number; treeLod?: StreetTreeLod };
type Waiter = { ids: Set<string>; resolve: () => void; reject: (error: Error) => void };

export class StreetStreaming {
  private readonly chunks: Map<string, StreetChunk>;
  private readonly loaded = new Map<string, LoadedChunk>();
  private readonly loading = new Set<string>();
  private readonly failures = new Map<string, StreetChunkFailure>();
  private readonly refs = new Map<Disposable, number>();
  private readonly waiters = new Set<Waiter>();
  private required: string[] = [];
  private retained = new Set<string>();
  private disposed = false;
  private revision = 0;
  private focus?: [number, number];
  private loadRadius: number;
  private unloadRadius: number;
  private readonly concurrency: number;
  private prefetch: string[] = [];
  private readonly anisotropy: number;

  constructor(readonly rootGroup: THREE.Group, readonly loader: StreetChunkLoader, readonly manifest: StreetManifest, private readonly options: StreetStreamingOptions = {}) {
    this.loadRadius = options.loadRadius ?? 850;
    this.unloadRadius = options.unloadRadius ?? 1400;
    if (!Number.isFinite(options.maxConcurrent ?? 2) || !Number.isFinite(options.anisotropy ?? 8)) throw new Error("Invalid street streaming limits");
    this.concurrency = Math.max(1, Math.min(2, Math.floor(options.maxConcurrent ?? 2)));
    this.anisotropy = Math.max(1, Math.min(8, options.anisotropy ?? 8));
    if (!Number.isFinite(this.loadRadius) || !Number.isFinite(this.unloadRadius) || this.loadRadius < 0 || this.unloadRadius <= this.loadRadius) throw new Error("Invalid street streaming radii");
    this.chunks = new Map();
    for (const chunk of manifest.chunks) {
      if (this.chunks.has(chunk.id) || chunk.bounds.length !== 4 || !chunk.bounds.every(Number.isFinite) || chunk.bounds[0] > chunk.bounds[2] || chunk.bounds[1] > chunk.bounds[3] || !chunk.file || !Number.isFinite(chunk.bytes) || chunk.bytes < 0 || !Number.isFinite(chunk.triangles) || chunk.triangles < 0) throw new Error(`Invalid street chunk: ${chunk.id}`);
      this.chunks.set(chunk.id, chunk);
    }
  }

  /** Non-blocking frame update. The master GLB is never requested. */
  update(x: number, z: number, ahead?: { x: number; z: number }) {
    if (this.disposed) return;
    if (!Number.isFinite(x) || !Number.isFinite(z)) throw new Error("Street focus must be finite");
    this.focus = [x, z];
    const plan = planStreetChunks(this.manifest.chunks, x, z, this.loadRadius, this.unloadRadius);
    this.required = plan.required; this.retained = plan.retained;
    const forecast = ahead && Number.isFinite(ahead.x) && Number.isFinite(ahead.z)
      ? planStreetChunks(this.manifest.chunks, ahead.x, ahead.z, this.loadRadius, this.unloadRadius) : undefined;
    this.prefetch = forecast?.required.filter(id => !this.required.includes(id)) ?? [];
    for (const id of this.prefetch) this.retained.add(id);
    for (const [id, loaded] of this.loaded) if (!this.retained.has(id)) {
      this.loaded.delete(id); this.release(loaded);
    }
    let lodChanged = false;
    for (const loaded of this.loaded.values()) if (loaded.treeLod?.update(x, z)) lodChanged = true;
    if (lodChanged) this.revision++;
    this.settleWaiters(); this.pump();
  }

  /** Rejects on required-load failure, disposal, or a focus change that supersedes this request. */
  readyAt(x: number, z: number): Promise<void> {
    if (this.disposed) return Promise.reject(new Error("Street streaming disposed"));
    this.update(x, z);
    return new Promise((resolve, reject) => {
      this.waiters.add({ ids: new Set(this.required), resolve, reject });
      this.settleWaiters();
    });
  }

  setFocus(x: number, z: number) { return this.readyAt(x, z); }

  setRadii(loadRadius: number, unloadRadius: number) {
    if (!Number.isFinite(loadRadius) || !Number.isFinite(unloadRadius) || loadRadius < 0 || unloadRadius <= loadRadius)
      throw new Error("Invalid street streaming radii");
    this.loadRadius = loadRadius; this.unloadRadius = unloadRadius;
    if (this.focus) this.update(...this.focus);
  }

  get currentRevision() { return this.revision; }

  retryFailed(id?: string) {
    if (id) this.failures.delete(id); else this.failures.clear();
    this.pump();
  }

  get loadedChunks(): StreetChunk[] { return [...this.loaded.values()].map(({ chunk }) => ({ ...chunk, bounds: [...chunk.bounds], coveredWays: [...chunk.coveredWays] })); }

  get stats() {
    return {
      loadedChunkIds: [...this.loaded.keys()],
      pendingChunkIds: [...new Set([...this.loading, ...this.required.filter(id => !this.loaded.has(id) && !this.failures.has(id))])],
      failedChunks: [...this.failures.values()].map(failure => ({ ...failure })),
      prefetchChunkIds: [...this.prefetch],
      activeLoads: this.loading.size,
      loadedBytes: [...this.loaded.values()].reduce((sum, item) => sum + item.chunk.bytes, 0),
      loadRadius: this.loadRadius,
      unloadRadius: this.unloadRadius,
      totalBytes: this.manifest.chunks.reduce((sum, chunk) => sum + chunk.bytes, 0),
      loadedTriangles: [...this.loaded.values()].reduce((sum, item) => sum + item.chunk.triangles, 0),
      instancedBatches: [...this.loaded.values()].reduce((sum, item) => sum + item.batches, 0),
      instancedMeshesSaved: [...this.loaded.values()].reduce((sum, item) => sum + item.meshesSaved, 0),
      treeLod: [...this.loaded.values()].reduce((sum, item) => {
        const lod = item.treeLod?.stats;
        if (lod) { sum.trees += lod.trees; sum.nearTrees += lod.nearTrees; sum.farTrees += lod.farTrees; sum.trianglesSaved += lod.trianglesSaved; sum.drawnTriangles += lod.drawnTriangles; }
        return sum;
      }, { trees: 0, nearTrees: 0, farTrees: 0, trianglesSaved: 0, drawnTriangles: 0 }),
      ready: this.required.every(id => this.loaded.has(id)) && !this.disposed,
      revision: this.revision,
    };
  }

  dispose() {
    if (this.disposed) return;
    this.disposed = true; this.required = []; this.retained.clear();
    for (const loaded of this.loaded.values()) this.release(loaded);
    this.loaded.clear(); this.settleWaiters();
    // GLTFLoader has no general cancellation API. Late results are disposed on arrival.
    // The caller's shared loader and Draco decoder remain alive.
  }

  private pump() {
    if (this.disposed) return;
    for (const id of [...this.required, ...this.prefetch]) {
      if (this.loading.size >= this.concurrency) break;
      if (this.loaded.has(id) || this.loading.has(id) || this.failures.has(id)) continue;
      this.loading.add(id);
      void this.load(this.chunks.get(id)!);
    }
  }

  private async load(chunk: StreetChunk) {
    let owned: LoadedChunk | undefined;
    try {
      const gltf = await this.loader.loadAsync(chunk.file);
      if (!(gltf.scene instanceof THREE.Group)) throw new Error("Chunk loader returned no scene group");
      gltf.scene.userData.streetChunkId = chunk.id;
      owned = { chunk, scene: gltf.scene, resources: new Set(), batches: 0, meshesSaved: 0 };
      this.adoptResources(owned);
      try {
        this.options.prepareScene?.(gltf.scene, chunk);
        if (this.options.instanceStaticMeshes !== false && !gltf.animations?.length) Object.assign(owned, instanceStreetMeshes(gltf.scene, this.options.treeLod));
      } finally {
        // Includes newly instanced GPU state and materials supplied by prepareScene,
        // even if that callback fails partway through preparation.
        this.adoptResources(owned);
      }
      if (this.disposed || !this.retained.has(chunk.id)) this.release(owned);
      else {
        this.rootGroup.add(gltf.scene);
        if (this.focus) owned.treeLod?.update(...this.focus);
        this.loaded.set(chunk.id, owned);
        this.revision++;
        this.failures.delete(chunk.id);
      }
    } catch (error) {
      if (owned && !this.loaded.has(chunk.id)) this.release(owned);
      if (!this.disposed) {
        const failure = { id: chunk.id, file: chunk.file, error: error instanceof Error ? error.message : String(error) };
        this.failures.set(chunk.id, failure);
        try { this.options.onError?.({ ...failure }); } catch { /* Diagnostics callbacks cannot break the scheduler. */ }
      }
    } finally {
      this.loading.delete(chunk.id); this.settleWaiters(); this.pump();
    }
  }

  private settleWaiters() {
    for (const waiter of this.waiters) {
      const failed = [...waiter.ids].map(id => this.failures.get(id)).find(Boolean);
      const superseded = [...waiter.ids].some(id => !this.required.includes(id) && !this.loaded.has(id));
      if (this.disposed || failed || superseded) {
        this.waiters.delete(waiter);
        waiter.reject(new Error(this.disposed ? "Street streaming disposed" : failed ? `Street chunk ${failed.id} failed: ${failed.error}` : "Street focus superseded"));
      } else if ([...waiter.ids].every(id => this.loaded.has(id))) {
        this.waiters.delete(waiter); waiter.resolve();
      }
    }
  }

  private release(owned: LoadedChunk) {
    this.options.onUnload?.(owned.scene);
    if (owned.scene.parent === this.rootGroup) this.revision++;
    owned.scene.removeFromParent();
    let surrounding: THREE.Object3D = this.rootGroup;
    while (surrounding.parent) surrounding = surrounding.parent;
    const external = collectResources(surrounding, this.rootGroup);
    for (const resource of owned.resources) {
      const count = (this.refs.get(resource) ?? 1) - 1;
      if (count > 0) this.refs.set(resource, count);
      else {
        this.refs.delete(resource);
        if (!external.has(resource) && !this.options.protectedResources?.has(resource)) {
          if (resource.dispose) resource.dispose(); else resource.close?.();
        }
      }
    }
    owned.resources.clear();
    owned.treeLod?.dispose();
  }

  private adoptResources(owned: LoadedChunk) {
    for (const resource of collectResources(owned.scene)) {
      if (owned.resources.has(resource)) continue;
      owned.resources.add(resource);
      this.refs.set(resource, (this.refs.get(resource) ?? 0) + 1);
      if (resource instanceof THREE.Texture && !this.options.protectedResources?.has(resource)) resource.anisotropy = this.anisotropy;
    }
  }
}
