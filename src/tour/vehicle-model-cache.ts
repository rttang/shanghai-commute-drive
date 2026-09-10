import * as THREE from 'three';

type Resource = object & { dispose?: () => void; close?: () => void };
type Entry = { model: THREE.Group; resources: Set<Resource> };
type Selection = { id: string; load: () => Promise<THREE.Group>; install: (model: THREE.Group) => void; resolve: (selected: boolean) => void; reject: (error: unknown) => void };
export type VehicleModelCacheOptions = {
  /** Borrowed traffic prototypes and the displayed clone can share owned resources. */
  protectedRoots?: () => Iterable<THREE.Object3D>;
  /** Scene environment/reflection textures stay owned by the scene. */
  protectedResources?: () => Iterable<object | null | undefined>;
};

function textureResources(texture: THREE.Texture, into: Set<Resource>) {
  into.add(texture);
  const images = Array.isArray(texture.source.data) ? texture.source.data : [texture.source.data];
  for (const image of images) if (image && typeof image.close === 'function') into.add(image);
}
function resources(root: THREE.Object3D, into = new Set<Resource>()) {
  root.traverse(object => {
    if (!(object instanceof THREE.Mesh || object instanceof THREE.Line || object instanceof THREE.Points || object instanceof THREE.Sprite)) return;
    into.add(object.geometry);
    for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
      into.add(material);
      for (const value of Object.values(material)) {
        if (value instanceof THREE.Texture) textureResources(value, into);
        else if (Array.isArray(value)) for (const item of value) if (item instanceof THREE.Texture) textureResources(item, into);
      }
      if (material instanceof THREE.ShaderMaterial) {
        const seen = new Set<object>();
        const visit = (value: unknown, depth: number) => {
          if (value instanceof THREE.Texture) textureResources(value, into);
          else if (depth < 8 && value && typeof value === 'object' && !seen.has(value)) {
            seen.add(value);for (const child of Object.values(value)) visit(child, depth + 1);
          }
        };
        visit(material.uniforms, 0);
      }
    }
    if (object instanceof THREE.SkinnedMesh && object.skeleton.boneTexture) textureResources(object.skeleton.boneTexture, into);
    if (object instanceof THREE.InstancedMesh) into.add(object);
  });
  return into;
}

/** Two detailed vehicles at most: the displayed model and its most recent spare.
 * Loads are serial. Obsolete queued requests never start; an in-flight result is
 * either installed for the latest selection or released immediately on arrival.
 * install must synchronously prepare the clone before replacing the displayed car.
 */
export class VehicleModelCache {
  private readonly entries = new Map<string, Entry>();
  private readonly released = new WeakSet<object>();
  private currentId?: string;
  private latest?: Selection;
  private loading?: { id: string };
  private disposed = false;
  constructor(private readonly options: VehicleModelCacheOptions = {}) {}
  get size() { return this.entries.size; }
  get ids() { return [...this.entries.keys()]; }
  get activeId() { return this.currentId; }

  select(id: string, load: () => Promise<THREE.Group>, install: (model: THREE.Group) => void): Promise<boolean> {
    if (this.disposed) return Promise.reject(new Error('Vehicle model cache disposed'));
    this.latest?.resolve(false);
    return new Promise((resolve, reject) => {
      const selection = { id, load, install, resolve, reject };
      this.latest = selection;
      const cached = this.entries.get(id);
      if (cached) this.install(selection, cached);
      else this.pump();
    });
  }

  /** A low-detail vehicle remains borrowed from World.models. */
  selectBorrowed(model: THREE.Group | undefined, install: (model: THREE.Group) => void): boolean {
    if (this.disposed) return false;
    this.latest?.resolve(false);this.latest = undefined;
    if (!model) return false;
    install(model);
    this.currentId = undefined;
    return true;
  }

  private install(selection: Selection, entry: Entry) {
    try {
      selection.install(entry.model);
      this.currentId = selection.id;
      this.entries.delete(selection.id);this.entries.set(selection.id, entry);
      this.latest = undefined;
      this.trim(2);
      selection.resolve(true);
    } catch (error) {
      // A malformed newly loaded rig cannot replace or evict the current car.
      if (selection.id !== this.currentId) {
        this.entries.delete(selection.id);this.release(entry);
      }
      this.latest = undefined;
      selection.reject(error);
    }
  }

  private pump() {
    if (this.loading || !this.latest || this.disposed) return;
    const { id, load } = this.latest;
    // Reserve the second slot before decoding, keeping the displayed model pinned.
    this.trim(1);
    this.loading = { id };
    void Promise.resolve().then(load).then(model => {
      const entry = { model, resources: resources(model) };
      if (!this.disposed && this.latest?.id === id) {
        this.entries.set(id, entry);
        this.install(this.latest, entry);
      } else this.release(entry);
    }).catch(error => {
      if (this.latest?.id === id) {
        this.latest.reject(error);this.latest = undefined;
      }
    }).finally(() => {
      this.loading = undefined;
      this.pump();
    });
  }

  private trim(limit: number) {
    for (const [id, entry] of this.entries) {
      if (this.entries.size <= limit) break;
      if (id === this.currentId) continue;
      this.entries.delete(id);this.release(entry);
    }
  }

  private release(entry: Entry) {
    const retained = new Set<Resource>();
    for (const other of this.entries.values()) {
      for (const resource of other.resources) retained.add(resource);
      resources(other.model, retained);
    }
    for (const root of this.options.protectedRoots?.() ?? []) resources(root, retained);
    for (const resource of this.options.protectedResources?.() ?? []) {
      if (resource instanceof THREE.Texture) textureResources(resource, retained);
      else if (resource) retained.add(resource);
    }
    resources(entry.model, entry.resources);
    for (const resource of entry.resources) {
      if (retained.has(resource) || this.released.has(resource)) continue;
      this.released.add(resource);
      if (resource.dispose) resource.dispose(); else resource.close?.();
    }
    entry.resources.clear();
  }

  dispose() {
    if (this.disposed) return;
    this.disposed = true;
    this.latest?.resolve(false);this.latest = undefined;
    this.currentId = undefined;
    for (const [id, entry] of this.entries) { this.entries.delete(id);this.release(entry); }
    // GLTFLoader offers no general load cancellation; its late result is released above.
  }
}
