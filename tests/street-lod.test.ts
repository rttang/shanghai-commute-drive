import { test } from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import { createStreetTreeLod, streetTreeAncestor } from "../src/tour/street-lod";
import { StreetStreaming, instanceStreetMeshes, type StreetManifest } from "../src/tour/street-streaming";

function treeAssets() {
  const leaves = new THREE.SphereGeometry(4, 64, 48).translate(.1, 9, -.2);
  const trunk = new THREE.CylinderGeometry(.15, .3, 6, 10).translate(0, 3, 0);
  const leafMaterial = new THREE.MeshStandardMaterial({ color: 0x658148 }); leafMaterial.name = "furniture-leaf";
  const barkMaterial = new THREE.MeshStandardMaterial({ color: 0x898573 }); barkMaterial.name = "furniture-bark";
  return { leaves, trunk, leafMaterial, barkMaterial };
}
function tree(id: number, x: number, z: number, assets: ReturnType<typeof treeAssets>) {
  const root = new THREE.Group(); root.name = `plane-tree-${id}`; root.userData.category = "furniture"; root.position.set(x, .14, z);
  const nested = new THREE.Group(); nested.name = "plane-tree"; root.add(nested);
  const leaf = new THREE.Mesh(assets.leaves, assets.leafMaterial); leaf.name = "plane-tree-leaf";
  const bark = new THREE.Mesh(assets.trunk, assets.barkMaterial); bark.name = "plane-tree-bark";
  leaf.castShadow = bark.castShadow = true; leaf.receiveShadow = bark.receiveShadow = true;
  nested.add(leaf, bark); return { root, leaf, bark };
}
function batches(scene: THREE.Group, level: string) {
  return scene.children.filter((object): object is THREE.InstancedMesh => object instanceof THREE.InstancedMesh && object.userData.streetTreeLod === level);
}
function equalMatrix(actual: THREE.Matrix4, expected: THREE.Matrix4) {
  actual.elements.forEach((number, i) => assert.ok(Math.abs(number - expected.elements[i]) < .0002, `${i}: ${number} vs ${expected.elements[i]}`));
}
function visibleMatrix(batch: THREE.InstancedMesh, index = 0) {
  batch.updateWorldMatrix(true, false); const matrix = new THREE.Matrix4(); batch.getMatrixAt(index, matrix); return matrix.premultiply(batch.matrixWorld);
}
function manifest(ids: string[]): StreetManifest {
  return { version: 1, master: { file: "/master.glb", bytes: 200_000_000 }, coveredWays: [],
    chunks: ids.map((id, index) => ({ id, file: `/${id}.glb`, bounds: [index * 500, 0, index * 500 + 10, 10], bytes: 100, triangles: 6000, coveredWays: [] })) };
}

test("tree identity is inherited from its furniture placement ancestor only", () => {
  const scene = new THREE.Group(), item = tree(713, 0, 0, treeAssets()); scene.add(item.root);
  assert.equal(item.leaf.userData.category, undefined); assert.equal(streetTreeAncestor(item.leaf, scene), item.root);
  item.root.userData.category = "building"; assert.equal(streetTreeAncestor(item.leaf, scene), undefined);
  item.root.userData.category = "furniture"; item.root.name = "plane-tree-leaf";
  assert.equal(streetTreeAncestor(item.leaf, scene), undefined);
});

test("near and far batches preserve nested world transforms and untouched original geometry", () => {
  const scene = new THREE.Group(); scene.position.set(1000, 7, -500); scene.rotation.y = .4;
  const parent = new THREE.Group(); parent.position.set(5, 1, -8); parent.rotation.y = .2; scene.add(parent);
  const assets = treeAssets(); const a = tree(1, -20, 5, assets), b = tree(2, 320, 0, assets);
  a.root.rotation.y = .37; b.root.rotation.y = -.6; b.root.scale.set(1.2, .9, 1.1);
  parent.add(a.root, b.root); scene.updateMatrixWorld(true);
  const expectedA = a.leaf.matrixWorld.clone(), expectedB = b.leaf.matrixWorld.clone(), expectedProxyB = b.root.matrixWorld.clone();
  const pointA = a.root.getWorldPosition(new THREE.Vector3()), pointB = b.root.getWorldPosition(new THREE.Vector3());
  const positions = Array.from(assets.leaves.getAttribute("position").array), indices = Array.from(assets.leaves.index!.array);
  const result = instanceStreetMeshes(scene), lod = result.treeLod!;
  assert.ok(lod); assert.equal(lod.stats.nearTrees, 2); assert.equal(lod.stats.farTrees, 0);
  assert.equal(batches(scene, "near").length, 2); assert.equal(batches(scene, "far").length, 1);
  assert.equal(a.leaf.parent, null); assert.equal(b.leaf.parent, null);
  lod.update(pointA.x, pointA.z); scene.updateMatrixWorld(true);
  const highLeaf = batches(scene, "near").find(mesh => mesh.geometry === assets.leaves)!;
  const proxy = batches(scene, "far")[0];
  assert.equal(highLeaf.count, 1); assert.equal(proxy.count, 1); assert.equal(highLeaf.material, assets.leafMaterial);
  assert.equal(highLeaf.castShadow, true); equalMatrix(visibleMatrix(highLeaf), expectedA); equalMatrix(visibleMatrix(proxy), expectedProxyB);
  assert.equal(highLeaf.userData.instanceMetadata[0].streetTreeName, "plane-tree-1");
  for (let i = 0; i < 20; i++) {
    lod.update(pointB.x, pointB.z); equalMatrix(visibleMatrix(highLeaf), expectedB);
    lod.update(pointA.x, pointA.z); equalMatrix(visibleMatrix(highLeaf), expectedA);
  }
  assert.deepEqual(Array.from(assets.leaves.getAttribute("position").array), positions);
  assert.deepEqual(Array.from(assets.leaves.index!.array), indices);
});

test("far trees use one compact instanced proxy batch rather than one draw per tree", () => {
  const scene = new THREE.Group(), assets = treeAssets();
  for (let i = 0; i < 100; i++) scene.add(tree(i, i * 2, 0, assets).root);
  const lod = createStreetTreeLod(scene)!;
  assert.equal(batches(scene, "near").length, 2); assert.equal(batches(scene, "far").length, 1);
  lod.update(5000, 5000);
  assert.equal(lod.stats.nearTrees, 0); assert.equal(lod.stats.farTrees, 100);
  assert.ok(lod.stats.drawnTriangles < lod.stats.sourceTriangles * .1);
  for (const batch of batches(scene, "near")) { assert.equal(batch.count, 0); assert.equal(batch.visible, false); }
  const proxy = batches(scene, "far")[0]; assert.equal(proxy.count, 100); assert.equal(proxy.visible, true);
  assert.ok(proxy.geometry.getAttribute("position").count / 3 < 500);
  assert.ok(proxy.boundingSphere && Number.isFinite(proxy.boundingSphere.radius) && proxy.boundingSphere.radius > 100);
  assert.ok(proxy.geometry.getAttribute("color"));
});

test("distance hysteresis prevents threshold flicker and near matrices recover after zero count", () => {
  const scene = new THREE.Group(); scene.add(tree(1, 0, 0, treeAssets()).root); const lod = createStreetTreeLod(scene)!;
  lod.update(119, 0); assert.equal(lod.stats.nearTrees, 1);
  assert.equal(lod.update(125, 0), false); assert.equal(lod.stats.nearTrees, 1);
  assert.equal(lod.update(133, 0), true); assert.equal(lod.stats.nearTrees, 0);
  assert.equal(lod.update(115, 0), false); assert.equal(lod.stats.nearTrees, 0);
  assert.equal(lod.update(107, 0), true); assert.equal(lod.stats.nearTrees, 1);
  for (const batch of batches(scene, "near")) assert.ok(batch.visible && batch.count === 1 && batch.boundingSphere!.radius > 0);
  assert.throws(() => lod.update(NaN, 0), /finite/);
  assert.throws(() => createStreetTreeLod(new THREE.Group(), { nearDistance: 0 }), /distances/);
  assert.throws(() => createStreetTreeLod(new THREE.Group(), { nearDistance: 10, hysteresis: 10 }), /distances/);
});

test("unsafe trees, unrelated furniture, and explicit LOD opt-out retain their detail", () => {
  const scene = new THREE.Group(), assets = treeAssets(), a = tree(1, 0, 0, assets);
  a.leaf.onBeforeRender = () => {}; scene.add(a.root);
  assert.equal(createStreetTreeLod(scene), undefined); assert.ok(a.leaf.parent);
  const other = new THREE.Group(), b = tree(2, 0, 0, treeAssets()); b.root.name = "bench-2"; other.add(b.root);
  assert.equal(createStreetTreeLod(other), undefined);
  const optOut = new THREE.Group(), c = tree(3, 0, 0, treeAssets()); optOut.add(c.root);
  assert.equal(instanceStreetMeshes(optOut, false).treeLod, undefined); assert.equal(batches(optOut, "far").length, 0);
});

test("streaming applies the latest focus when an async tree chunk arrives after preparation", async () => {
  let resolve!: (value: { scene: THREE.Group }) => void;
  const asset = treeAssets(), scene = new THREE.Group(); scene.add(tree(1, 0, 0, asset).root);
  const data = manifest(["a"]); data.chunks[0].always = true;
  let prepared = false;
  const stream = new StreetStreaming(new THREE.Group(), { loadAsync: () => new Promise(done => { resolve = done; }) }, data, {
    prepareScene(group) { prepared = true; assert.equal(batches(group, "near").length, 0); assert.ok(group.getObjectByName("plane-tree-leaf")); },
  });
  const ready = stream.readyAt(0, 0); stream.update(500, 0); resolve({ scene }); await ready;
  assert.equal(prepared, true); assert.equal(stream.stats.treeLod.nearTrees, 0); assert.equal(stream.stats.treeLod.farTrees, 1);
  const revision = stream.stats.revision; stream.update(0, 0);
  assert.equal(stream.stats.treeLod.nearTrees, 1); assert.equal(stream.stats.revision, revision + 1);
  stream.update(0, 0); assert.equal(stream.stats.revision, revision + 1); stream.dispose();
});

test("chunk eviction disposes proxy resources and instances once while shared source resources survive", async () => {
  const assets = treeAssets(), a = new THREE.Group(), b = new THREE.Group(); a.add(tree(1, 0, 0, assets).root); b.add(tree(2, 500, 0, assets).root);
  const counts = { leaves: 0, trunk: 0, leafMaterial: 0, barkMaterial: 0, texture: 0, image: 0 };
  for (const key of ["leaves", "trunk", "leafMaterial", "barkMaterial"] as const) assets[key].addEventListener("dispose", () => counts[key]++);
  const texture = new THREE.Texture({ close() { counts.image++; } }); texture.addEventListener("dispose", () => counts.texture++); assets.leafMaterial.map = texture;
  const stream = new StreetStreaming(new THREE.Group(), { loadAsync: async file => ({ scene: file === "/a.glb" ? a : b }) }, manifest(["a", "b"]), { loadRadius: 600, unloadRadius: 900 });
  await stream.readyAt(0, 0);
  const proxyA = batches(a, "far")[0], proxyB = batches(b, "far")[0];
  let proxyAGeometry = 0, proxyAMaterial = 0, proxyBGeometry = 0, instanceDisposals = 0;
  proxyA.geometry.addEventListener("dispose", () => proxyAGeometry++); (proxyA.material as THREE.Material).addEventListener("dispose", () => proxyAMaterial++);
  proxyB.geometry.addEventListener("dispose", () => proxyBGeometry++);
  for (const group of [a, b]) for (const level of ["near", "far"]) for (const mesh of batches(group, level)) mesh.addEventListener("dispose", () => instanceDisposals++);
  stream.update(1100, 0);
  assert.equal(proxyAGeometry, 1); assert.equal(proxyAMaterial, 1); assert.equal(proxyBGeometry, 0);
  assert.deepEqual(counts, { leaves: 0, trunk: 0, leafMaterial: 0, barkMaterial: 0, texture: 0, image: 0 });
  stream.dispose(); stream.dispose();
  assert.equal(proxyAGeometry, 1); assert.equal(proxyAMaterial, 1); assert.equal(proxyBGeometry, 1); assert.equal(instanceDisposals, 6);
  assert.deepEqual(counts, { leaves: 1, trunk: 1, leafMaterial: 1, barkMaterial: 1, texture: 1, image: 1 });
});

test("external and explicitly protected source resources are not disposed with new tree proxies", async () => {
  const assets = treeAssets(), scene = new THREE.Group(), world = new THREE.Group(), streamingRoot = new THREE.Group();
  world.add(streamingRoot, new THREE.Mesh(assets.leaves, assets.leafMaterial)); scene.add(tree(1, 0, 0, assets).root);
  let leaves = 0, leafMaterial = 0, trunk = 0, proxy = 0;
  assets.leaves.addEventListener("dispose", () => leaves++); assets.leafMaterial.addEventListener("dispose", () => leafMaterial++); assets.trunk.addEventListener("dispose", () => trunk++);
  const stream = new StreetStreaming(streamingRoot, { loadAsync: async () => ({ scene }) }, manifest(["a"]), { protectedResources: new Set([assets.trunk]) });
  await stream.readyAt(0, 0); batches(scene, "far")[0].geometry.addEventListener("dispose", () => proxy++); stream.dispose();
  assert.equal(proxy, 1); assert.equal(leaves, 0); assert.equal(leafMaterial, 0); assert.equal(trunk, 0);
});
