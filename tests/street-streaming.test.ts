import { test } from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import { StreetStreaming, distanceToStreetBounds, planStreetChunks, instanceStreetMeshes, type StreetManifest, type StreetChunk } from "../src/tour/street-streaming";

function chunk(id: string, x: number, extra: Partial<StreetChunk> = {}): StreetChunk {
  return { id, file: `/chunks/${id}.glb`, bounds: [x, 0, x + 100, 100], bytes: 100, triangles: 12, coveredWays: [x], ...extra };
}
function manifest(chunks: StreetChunk[]): StreetManifest {
  return { version: 1, master: { file: "/streets/master/shanghai-streets.glb", bytes: 200_000_000 }, chunks, coveredWays: chunks.flatMap(chunk => chunk.coveredWays) };
}
function scene(geometry = new THREE.BoxGeometry(), material = new THREE.MeshStandardMaterial()) {
  const group = new THREE.Group(); group.add(new THREE.Mesh(geometry, material)); return group;
}
function deferredLoader() {
  const calls: string[] = [];
  const pending = new Map<string, { resolve: (value: { scene: THREE.Group; animations?: unknown[] }) => void; reject: (error: Error) => void }>();
  return {
    calls, pending,
    loadAsync(file: string) {
      calls.push(file);
      return new Promise<{ scene: THREE.Group; animations?: unknown[] }>((resolve, reject) => pending.set(file, { resolve, reject }));
    },
  };
}
const tick = () => new Promise<void>(resolve => setImmediate(resolve));

test("moving lookahead queues future chunks after current requirements without blocking current readiness", async () => {
  const loader = deferredLoader();
  const stream = new StreetStreaming(new THREE.Group(), loader, manifest([chunk("near",0),chunk("ahead",700),chunk("behind",-900)]),{loadRadius:420,unloadRadius:650,maxConcurrent:1});
  stream.update(0,0,{x:400,z:0});
  assert.deepEqual(loader.calls,["/chunks/near.glb"]);
  assert.deepEqual(stream.stats.prefetchChunkIds,["ahead"]);
  loader.pending.get("/chunks/near.glb")!.resolve({scene:scene()});await tick();
  assert.equal(stream.stats.ready,true);
  assert.deepEqual(loader.calls,["/chunks/near.glb","/chunks/ahead.glb"]);
  loader.pending.get("/chunks/ahead.glb")!.resolve({scene:scene()});await tick();
  stream.update(0,0,{x:-400,z:0});
  assert.ok(!stream.stats.prefetchChunkIds.includes("ahead"));
  assert.ok(!stream.stats.loadedChunkIds.includes("ahead"));
  stream.dispose();
});

test("chunk eviction drops application references before disposing its geometry", async () => {
  const retained = new Set<THREE.Group>();
  let released = 0;
  const stream = new StreetStreaming(new THREE.Group(), {loadAsync:async()=>{
    const group=scene();retained.add(group);
    (group.children[0] as THREE.Mesh).geometry.addEventListener('dispose',()=>{assert.ok(!retained.has(group));released++;});
    return {scene:group};
  }},manifest([chunk('a',0),chunk('b',3000)]),{onUnload:group=>{retained.delete(group);}});
  await stream.readyAt(0,0);assert.equal(retained.size,1);
  await stream.readyAt(3000,0);assert.equal(retained.size,1);assert.equal(released,1);
  stream.dispose();assert.equal(retained.size,0);assert.equal(released,2);
});

test("chunk selection uses distance to bounds with a separate unloading radius", () => {
  assert.equal(distanceToStreetBounds(500, 500, [0, 0, 1000, 1000]), 0);
  assert.equal(distanceToStreetBounds(1300, 1400, [0, 0, 1000, 1000]), 500);
  const chunks = [chunk("near", 800), chunk("retained", 1100), chunk("far", 1600), chunk("always", 9000, { always: true })];
  const result = planStreetChunks(chunks, 0, 0);
  assert.deepEqual(result.required, ["always", "near"]);
  assert.deepEqual([...result.retained], ["always", "near", "retained"]);
});

test("switching to a smaller quality radius releases distant GPU resources immediately", async () => {
  let disposed = 0;
  const stream = new StreetStreaming(new THREE.Group(), { loadAsync: async () => {
    const result = scene();
    (result.children[0] as THREE.Mesh).geometry.addEventListener("dispose", () => disposed++);
    return { scene: result };
  } }, manifest([chunk("near", 0), chunk("far", 800)]));
  await stream.readyAt(0, 0);
  assert.equal(stream.stats.loadedBytes, 200);
  stream.setRadii(420, 650);
  assert.deepEqual(stream.stats.loadedChunkIds, ["near"]);
  assert.equal(stream.stats.loadedBytes, 100);
  assert.equal(disposed, 1);
  assert.equal(stream.stats.ready, true);
  assert.throws(() => stream.setRadii(500, 400), /Invalid/);
  stream.dispose();
});

test("initial ready waits for all nearby chunks, queues at most two and never requests the master", async () => {
  const loader = deferredLoader(), group = new THREE.Group();
  const stream = new StreetStreaming(group, loader, manifest([chunk("a", 0), chunk("b", 200), chunk("c", 400), chunk("far", 4000)]), { maxConcurrent: 20 });
  const ready = stream.readyAt(0, 0);
  assert.deepEqual(loader.calls, ["/chunks/a.glb", "/chunks/b.glb"]);
  assert.equal(stream.stats.activeLoads, 2);
  assert.equal(stream.stats.ready, false);
  loader.pending.get("/chunks/a.glb")!.resolve({ scene: scene() }); await tick();
  assert.deepEqual(loader.calls, ["/chunks/a.glb", "/chunks/b.glb", "/chunks/c.glb"]);
  assert.equal(stream.stats.activeLoads, 2);
  loader.pending.get("/chunks/b.glb")!.resolve({ scene: scene() });
  loader.pending.get("/chunks/c.glb")!.resolve({ scene: scene() }); await ready;
  assert.equal(stream.stats.ready, true);
  assert.equal(stream.stats.loadedBytes, 300);
  assert.equal(stream.stats.totalBytes, 400);
  assert.equal(stream.stats.loadedTriangles, 36);
  assert.deepEqual(stream.stats.failedChunks, []);
  assert.equal(group.children.length, 3);
  assert.ok(loader.calls.every(file => !file.includes("master")));
  stream.dispose();
});

test("outdated queued chunks are not fetched and late far-away results are disposed", async () => {
  const loader = deferredLoader(), group = new THREE.Group();
  const stream = new StreetStreaming(group, loader, manifest([chunk("a", 0), chunk("b", 200), chunk("queued", 400), chunk("new", 4000)]));
  const initial = assert.rejects(stream.readyAt(0, 0), /superseded/);
  stream.update(4000, 0);
  const old = scene(); let disposed = 0;
  (old.children[0] as THREE.Mesh).geometry.addEventListener("dispose", () => disposed++);
  loader.pending.get("/chunks/a.glb")!.resolve({ scene: old }); await tick();
  assert.equal(disposed, 1);
  assert.ok(!loader.calls.includes("/chunks/queued.glb"));
  assert.ok(loader.calls.includes("/chunks/new.glb"));
  loader.pending.get("/chunks/b.glb")!.resolve({ scene: scene() });
  loader.pending.get("/chunks/new.glb")!.resolve({ scene: scene() }); await tick();
  await initial;
  assert.deepEqual(stream.stats.loadedChunkIds, ["new"]);
  stream.dispose();
});

test("failures stay visible, reject initial readiness and only retry when requested", async () => {
  const loader = deferredLoader(); const failures: string[] = [];
  const stream = new StreetStreaming(new THREE.Group(), loader, manifest([chunk("a", 0)]), { onError: failure => { failures.push(failure.error); throw new Error("UI callback error"); } });
  const failed = assert.rejects(stream.readyAt(0, 0), /a failed: HTTP 503/);
  loader.pending.get("/chunks/a.glb")!.reject(new Error("HTTP 503")); await failed;
  assert.deepEqual(stream.stats.loadedChunkIds, []);
  assert.equal(stream.stats.failedChunks[0].error, "HTTP 503");
  assert.deepEqual(failures, ["HTTP 503"]);
  stream.update(0, 0); stream.update(5, 0);
  assert.equal(loader.calls.length, 1);
  stream.retryFailed("a");
  const ready = stream.readyAt(0, 0);
  loader.pending.get("/chunks/a.glb")!.resolve({ scene: scene() }); await ready;
  assert.equal(loader.calls.length, 2);
  assert.deepEqual(stream.stats.failedChunks, []);
  stream.dispose();
});

test("hysteresis retains loaded chunks, then disposes shared owned resources exactly once", async () => {
  const geometry = new THREE.BoxGeometry(), material = new THREE.MeshStandardMaterial();
  const texture = new THREE.Texture(); let closed = 0; texture.source.data = { close: () => closed++ }; material.map = texture;
  const counts = { geometry: 0, material: 0, texture: 0 };
  geometry.addEventListener("dispose", () => counts.geometry++); material.addEventListener("dispose", () => counts.material++); texture.addEventListener("dispose", () => counts.texture++);
  const stream = new StreetStreaming(new THREE.Group(), { loadAsync: async () => ({ scene: scene(geometry, material) }) }, manifest([chunk("a", 0), chunk("b", 800)]));
  await stream.readyAt(0, 0);
  assert.equal(texture.anisotropy, 8);
  stream.update(1200, 0);
  assert.deepEqual(stream.stats.loadedChunkIds, ["a", "b"]);
  stream.update(1600, 0);
  assert.deepEqual(stream.stats.loadedChunkIds, ["b"]);
  assert.deepEqual(counts, { geometry: 0, material: 0, texture: 0 });
  stream.update(3000, 0);
  assert.deepEqual(counts, { geometry: 1, material: 1, texture: 1 });
  assert.equal(closed, 1);
  stream.dispose();
  assert.deepEqual(counts, { geometry: 1, material: 1, texture: 1 });
});

test("external scene materials and detached explicitly borrowed resources are protected", async () => {
  const parent = new THREE.Scene(), group = new THREE.Group(); parent.add(group);
  const geometry = new THREE.BoxGeometry(), material = new THREE.MeshStandardMaterial(), texture = new THREE.Texture(); material.map = texture;
  parent.add(new THREE.Mesh(geometry, material));
  const detached = new THREE.MeshStandardMaterial();
  let disposed = 0;
  for (const resource of [geometry, material, texture, detached]) resource.addEventListener("dispose", () => disposed++);
  const stream = new StreetStreaming(group, { loadAsync: async () => {
    const result = scene(geometry, material); result.add(new THREE.Mesh(new THREE.BoxGeometry(), detached)); return { scene: result };
  } }, manifest([chunk("a", 0)]), { protectedResources: new Set([detached]) });
  await stream.readyAt(0, 0); stream.dispose();
  assert.equal(disposed, 0);
  assert.equal(parent.children.length, 2);
  assert.equal(group.children.length, 0);
});

test("disposing while loading rejects readiness and releases results that arrive afterwards", async () => {
  const loader = deferredLoader(), group = new THREE.Group();
  const stream = new StreetStreaming(group, loader, manifest([chunk("a", 0)]));
  const rejection = assert.rejects(stream.readyAt(0, 0), /disposed/);
  stream.dispose(); await rejection;
  const result = scene(); let releases = 0;
  (result.children[0] as THREE.Mesh).geometry.addEventListener("dispose", () => releases++);
  loader.pending.get("/chunks/a.glb")!.resolve({ scene: result }); await tick();
  assert.equal(releases, 1); assert.equal(group.children.length, 0); assert.equal(stream.stats.activeLoads, 0);
  assert.equal(stream.stats.ready, false);
  await assert.rejects(stream.readyAt(0, 0), /disposed/);
});

test("instancing preserves each nested world transform, geometry and opaque material", () => {
  const root = new THREE.Group(); root.position.set(1000, 7, -500); root.rotation.y = 0.4;
  const nested = new THREE.Group(); nested.position.set(5, 3, -8); nested.rotation.y = 0.2; root.add(nested);
  const geometry = new THREE.BoxGeometry(), material = new THREE.MeshStandardMaterial();
  const a = new THREE.Mesh(geometry, material), b = new THREE.Mesh(geometry, material); a.name = "tree-1"; b.name = "tree-2";
  a.position.set(-15, 0, 30); b.position.set(20, 0, 0); b.scale.set(2, 3, 4); a.castShadow = b.castShadow = true;
  nested.add(a); root.add(b); root.updateMatrixWorld(true);
  const expected = [a.matrixWorld.clone(), b.matrixWorld.clone()];
  assert.deepEqual(instanceStreetMeshes(root), { batches: 1, meshesSaved: 1 });
  const batch = root.children.find(child => child instanceof THREE.InstancedMesh) as THREE.InstancedMesh;
  root.updateMatrixWorld(true);
  assert.equal(batch.count, 2); assert.equal(batch.geometry, geometry); assert.equal(batch.material, material); assert.equal(batch.castShadow, true);
  expected.forEach((matrix, index) => {
    const actual = new THREE.Matrix4(); batch.getMatrixAt(index, actual); actual.premultiply(batch.matrixWorld);
    actual.elements.forEach((element, i) => assert.ok(Math.abs(element - matrix.elements[i]) < 1e-4));
  });
  assert.deepEqual(batch.userData.instanceNames, ["tree-1", "tree-2"]);
  assert.equal(a.parent, null); assert.equal(b.parent, null);
});

test("transparent, transmitting, custom-shader and negative-scale meshes retain individual nodes", () => {
  const root = new THREE.Group(), geometry = new THREE.BoxGeometry();
  const materials: THREE.Material[] = [new THREE.MeshStandardMaterial({ transparent: true }), new THREE.MeshPhysicalMaterial({ transmission: 1 }), new THREE.ShaderMaterial(), new THREE.MeshStandardMaterial()];
  materials[3].onBeforeCompile = () => {};
  for (const material of materials) for (let i = 0; i < 2; i++) root.add(new THREE.Mesh(geometry, material));
  const mirrored = new THREE.MeshStandardMaterial();
  for (let i = 0; i < 2; i++) { const mesh = new THREE.Mesh(geometry, mirrored); mesh.scale.x = -1; root.add(mesh); }
  const result = instanceStreetMeshes(root);
  assert.deepEqual(result, { batches: 0, meshesSaved: 0 }); assert.equal(root.children.length, 10);
});

test("animated scenes are not instanced and malformed scheduling input fails early", async () => {
  const geometry = new THREE.BoxGeometry(), material = new THREE.MeshStandardMaterial(), group = scene(geometry, material);
  group.add(new THREE.Mesh(geometry, material));
  const stream = new StreetStreaming(new THREE.Group(), { loadAsync: async () => ({ scene: group, animations: [{}] }) }, manifest([chunk("a", 0)]));
  await stream.readyAt(0, 0); assert.equal(stream.stats.instancedBatches, 0); assert.equal(group.children.length, 2); stream.dispose();
  const loader = deferredLoader();
  assert.throws(() => new StreetStreaming(new THREE.Group(), loader, manifest([chunk("a", 0), chunk("a", 0)])), /Invalid street chunk/);
  assert.throws(() => new StreetStreaming(new THREE.Group(), loader, manifest([]), { loadRadius: 1500, unloadRadius: 1400 }), /radii/);
  assert.throws(() => new StreetStreaming(new THREE.Group(), loader, manifest([]), { maxConcurrent: NaN }), /limits/);
});

test("scene preparation runs before instancing and revision changes on attachment and eviction", async () => {
  const geometry = new THREE.BoxGeometry(), material = new THREE.MeshStandardMaterial(), group = scene(geometry, material);
  group.add(new THREE.Mesh(geometry, material));
  const stream = new StreetStreaming(new THREE.Group(), { loadAsync: async () => ({ scene: group }) }, manifest([chunk("a", 0)]), {
    prepareScene(scene, chunk) { assert.equal(chunk.id, "a"); scene.traverse(object => { if (object instanceof THREE.Mesh) object.castShadow = true; }); },
  });
  assert.equal(stream.stats.revision, 0); await stream.readyAt(0, 0);
  assert.equal(stream.stats.instancedBatches, 1); assert.equal(stream.stats.revision, 1);
  assert.ok(group.children.find(child => child instanceof THREE.InstancedMesh)?.castShadow);
  stream.update(0, 0); assert.equal(stream.stats.revision, 1);
  stream.update(3000, 0); assert.equal(stream.stats.revision, 2); stream.dispose();
});

test("failed scene preparation releases source and newly added resources without false readiness", async () => {
  const original = scene(), added = new THREE.BoxGeometry(); let releases = 0;
  (original.children[0] as THREE.Mesh).geometry.addEventListener("dispose", () => releases++);
  added.addEventListener("dispose", () => releases++);
  const stream = new StreetStreaming(new THREE.Group(), { loadAsync: async () => ({ scene: original }) }, manifest([chunk("a", 0)]), {
    prepareScene(scene) { scene.add(new THREE.Mesh(added)); throw new Error("Material preparation failed"); },
  });
  await assert.rejects(stream.readyAt(0, 0), /Material preparation failed/);
  assert.equal(releases, 2); assert.equal(stream.stats.ready, false); assert.deepEqual(stream.stats.loadedChunkIds, []); stream.dispose();
});
