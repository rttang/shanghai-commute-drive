import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as THREE from "three";
import { createStreetTreeLod } from "../src/tour/street-lod";

/** Read only the nine meshes of an existing tree template, without a browser,
 * texture decoding, a Draco worker, or regenerating the frozen asset. */
function streetTreeSample() {
  const bytes = readFileSync(new URL("../public/streets/master/chunks/-1_-4.glb", import.meta.url));
  const jsonLength = bytes.readUInt32LE(12);
  const gltf = JSON.parse(bytes.subarray(20, 20 + jsonLength).toString());
  const binStart = 28 + jsonLength;
  const geometries = new Map<number, THREE.BufferGeometry>();
  const materials = new Map<number, THREE.MeshStandardMaterial>();
  const accessor = (index: number) => {
    const a = gltf.accessors[index], view = gltf.bufferViews[a.bufferView];
    assert.equal(view.extensions, undefined, "The read-only tree fixture must use ordinary GLB accessors");
    assert.equal(a.sparse, undefined);
    const size = ({ SCALAR: 1, VEC2: 2, VEC3: 3 } as Record<string, number>)[a.type];
    const C = ({ 5126: Float32Array, 5123: Uint16Array, 5125: Uint32Array } as const)[a.componentType as 5126 | 5123 | 5125];
    assert.ok(C && size);
    assert.ok(!view.byteStride || view.byteStride === size * C.BYTES_PER_ELEMENT);
    const offset = bytes.byteOffset + binStart + (view.byteOffset ?? 0) + (a.byteOffset ?? 0);
    return new THREE.BufferAttribute(new C(bytes.buffer, offset, a.count * size), size);
  };
  const node = (index: number): THREE.Object3D => {
    const n = gltf.nodes[index];
    let object: THREE.Object3D;
    if (n.mesh !== undefined) {
      const primitives = gltf.meshes[n.mesh].primitives;
      assert.equal(primitives.length, 1);
      const p = primitives[0];
      let geometry = geometries.get(n.mesh);
      if (!geometry) {
        geometry = new THREE.BufferGeometry();
        geometry.setAttribute("position", accessor(p.attributes.POSITION));
        geometry.setAttribute("normal", accessor(p.attributes.NORMAL));
        geometry.setIndex(accessor(p.indices)); geometries.set(n.mesh, geometry);
      }
      let material = materials.get(p.material);
      if (!material) {
        const m = gltf.materials[p.material], rgba = m.pbrMetallicRoughness.baseColorFactor;
        material = new THREE.MeshStandardMaterial({ color: new THREE.Color(rgba[0], rgba[1], rgba[2]),
          side: m.doubleSided ? THREE.DoubleSide : THREE.FrontSide });
        material.name = m.name; materials.set(p.material, material);
      }
      object = new THREE.Mesh(geometry, material);
    } else object = new THREE.Group();
    object.name = n.name ?? ""; object.userData = structuredClone(n.extras ?? {});
    if (n.translation) object.position.fromArray(n.translation);
    if (n.rotation) object.quaternion.fromArray(n.rotation);
    if (n.scale) object.scale.fromArray(n.scale);
    for (const child of n.children ?? []) object.add(node(child));
    return object;
  };
  const scene = new THREE.Group();
  gltf.nodes.forEach((n: { name?: string }, i: number) => {
    if (["plane-tree-697", "plane-tree-698", "plane-tree-699"].includes(n.name ?? "")) scene.add(node(i));
  });
  assert.equal(scene.children.length, 3);
  return scene;
}

test("frozen GLB trees keep exactly one representation and enclosing frustum bounds while LOD batches repack", () => {
  const scene = streetTreeSample(); scene.updateMatrixWorld(true);
  const trees = scene.children.map(root => {
    let parts = 0; root.traverse(o => { if (o instanceof THREE.Mesh) parts++; });
    return { name: root.name, parts, position: root.getWorldPosition(new THREE.Vector3()) };
  });
  const lod = createStreetTreeLod(scene)!; assert.ok(lod);
  const batches = scene.children.filter((o): o is THREE.InstancedMesh => o instanceof THREE.InstancedMesh);
  const at = trees[0].position;
  const camera = new THREE.PerspectiveCamera(52, 1, .3, 2000);
  const frustum = new THREE.Frustum(), projection = new THREE.Matrix4(), instanceMatrix = new THREE.Matrix4();
  for (const offset of [0, 119, 125, 131, 133, 400, 125, 115, 107, 0, 400, 0]) {
    const x = at.x + offset, z = at.z;
    lod.update(x, z); scene.updateMatrixWorld(true);
    const visible = new Map(trees.map(t => [t.name, { near: 0, far: 0 }]));
    for (const batch of batches) {
      assert.equal(batch.visible, batch.count > 0);
      assert.equal(batch.userData.instanceNames.length, batch.count);
      assert.equal(batch.userData.instanceMetadata.length, batch.count);
      if (!batch.count) continue;
      assert.ok(batch.boundingSphere && Number.isFinite(batch.boundingSphere.radius));
      batch.geometry.computeBoundingSphere();
      const outer = batch.boundingSphere.clone().applyMatrix4(batch.matrixWorld);
      for (let i = 0; i < batch.count; i++) {
        const level = batch.userData.streetTreeLod as "near" | "far";
        const name = level === "near" ? batch.userData.instanceMetadata[i].streetTreeName : batch.userData.instanceNames[i];
        visible.get(name)![level]++;
        batch.getMatrixAt(i, instanceMatrix); instanceMatrix.premultiply(batch.matrixWorld);
        const inner = batch.geometry.boundingSphere!.clone().applyMatrix4(instanceMatrix);
        assert.ok(outer.center.distanceTo(inner.center) + inner.radius <= outer.radius + .001);
        camera.position.set(x, 3, z + 15); camera.lookAt(inner.center); camera.updateMatrixWorld(true);
        projection.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse); frustum.setFromProjectionMatrix(projection);
        assert.ok(frustum.intersectsSphere(inner));
        assert.ok(frustum.intersectsObject(batch), "An individually visible tree must not vanish through batch culling");
      }
    }
    for (const tree of trees) {
      const counts = visible.get(tree.name)!;
      assert.ok((counts.near === tree.parts && counts.far === 0) || (counts.near === 0 && counts.far === 1), `${tree.name}: ${JSON.stringify(counts)}`);
    }
    assert.equal(lod.update(x, z), false, "An unchanged focus must not switch LOD again");
  }
  lod.dispose();
});
