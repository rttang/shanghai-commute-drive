import * as THREE from "three";

export type StreetTreeLodOptions = {
  /** Ground distance in metres, measured from the tree's placement root. */
  nearDistance?: number;
  /** A small transition band prevents flicker when driving around the boundary. */
  hysteresis?: number;
};
type Tree = { root: THREE.Object3D; meshes: THREE.Mesh[]; matrix: THREE.Matrix4; near: boolean; sourceTriangles: number };
type Instance = { matrix: THREE.Matrix4; tree: number; name: string; metadata: Record<string, unknown> };
type Batch = { mesh: THREE.InstancedMesh; instances: Instance[]; near: boolean; triangles: number };

function triangleCount(geometry: THREE.BufferGeometry) {
  return (geometry.index?.count ?? geometry.getAttribute("position")?.count ?? 0) / 3;
}
function materials(mesh: THREE.Mesh) { return Array.isArray(mesh.material) ? mesh.material : [mesh.material]; }
function renderKey(mesh: THREE.Mesh) {
  return [mesh.castShadow, mesh.receiveShadow, mesh.renderOrder, mesh.layers.mask, mesh.frustumCulled].join("|");
}
function copyRenderState(source: THREE.Mesh, target: THREE.InstancedMesh) {
  target.castShadow = source.castShadow; target.receiveShadow = source.receiveShadow;
  target.renderOrder = source.renderOrder; target.layers.mask = source.layers.mask;
  target.frustumCulled = source.frustumCulled;
}

/** Identity belongs to the placement ancestor, not to the unlabelled GLTF mesh. */
export function streetTreeAncestor(object: THREE.Object3D, scene: THREE.Object3D): THREE.Object3D | undefined {
  for (let parent: THREE.Object3D | null = object; parent; parent = parent.parent) {
    if (parent.userData.category === "furniture" && /^plane-tree-\d+(?:_\d+)?$/.test(parent.name)) return parent;
    if (parent === scene) break;
  }
  return undefined;
}
function safeMesh(mesh: THREE.Mesh, scene: THREE.Group) {
  if (mesh.constructor !== THREE.Mesh || mesh.children.length || mesh.morphTargetInfluences?.length || mesh.geometry.morphAttributes.position?.length) return false;
  if (mesh.onBeforeRender !== THREE.Object3D.prototype.onBeforeRender || mesh.onAfterRender !== THREE.Object3D.prototype.onAfterRender) return false;
  if (mesh.matrixWorld.determinant() <= 0) return false;
  for (let object: THREE.Object3D | null = mesh; object; object = object.parent) {
    if (!object.visible) return false;
    if (object === scene) break;
  }
  return materials(mesh).every(material => !material.transparent && !(material instanceof THREE.ShaderMaterial) &&
    !("transmission" in material && Number(material.transmission) > 0) && material.onBeforeCompile === THREE.Material.prototype.onBeforeCompile);
}

function localBounds(tree: Tree, leafOnly: boolean) {
  const box = new THREE.Box3();
  const inverse = tree.root.matrixWorld.clone().invert();
  const transform = new THREE.Matrix4();
  for (const mesh of tree.meshes) {
    if (leafOnly && !/leaf|foliage|canopy/i.test(mesh.name + materials(mesh).map(m => m.name).join(" "))) continue;
    const position = mesh.geometry.getAttribute("position");
    if (!position) continue;
    // Compute a private bound: source geometry, including its cached bounds, is untouched.
    const part = new THREE.Box3().setFromBufferAttribute(position as THREE.BufferAttribute);
    transform.multiplyMatrices(inverse, mesh.matrixWorld); box.union(part.applyMatrix4(transform));
  }
  return box;
}
function partColor(tree: Tree, expression: RegExp, fallback: number) {
  for (const mesh of tree.meshes) for (const material of materials(mesh)) {
    if (expression.test(mesh.name + " " + material.name) && material instanceof THREE.MeshStandardMaterial) return material.color.clone();
  }
  return new THREE.Color(fallback);
}

/** One vertex-coloured mesh: tapered trunk/branches plus an irregular lobed crown.
 * Crown dimensions come from the source leaf meshes; no billboard or texture is
 * introduced. This geometry is only drawn beyond the near-detail distance.
 */
function treeProxy(tree: Tree) {
  const full = localBounds(tree, false), crown = localBounds(tree, true);
  if (crown.isEmpty()) {
    crown.copy(full); crown.min.y = THREE.MathUtils.lerp(full.min.y, full.max.y, .55);
  }
  const size = crown.getSize(new THREE.Vector3()), center = crown.getCenter(new THREE.Vector3());
  const leaf = partColor(tree, /leaf|foliage|canopy/i, 0x617d43), bark = partColor(tree, /bark/i, 0x898573);
  const positions: number[] = [], colors: number[] = [];
  const face = (a: THREE.Vector3, b: THREE.Vector3, c: THREE.Vector3, color: THREE.Color, shade = 1) => {
    for (const p of [a, b, c]) { positions.push(p.x, p.y, p.z); colors.push(color.r * shade, color.g * shade, color.b * shade); }
  };
  const branch = (a: THREE.Vector3, b: THREE.Vector3, lower: number, upper: number) => {
    const quaternion = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize());
    const rings = [a, b].map((p, level) => Array.from({ length: 7 }, (_, i) =>
      new THREE.Vector3(Math.cos(i * Math.PI * 2 / 7) * (level ? upper : lower), 0,
        Math.sin(i * Math.PI * 2 / 7) * (level ? upper : lower)).applyQuaternion(quaternion).add(p)));
    for (let i = 0; i < 7; i++) {
      const next = (i + 1) % 7;
      face(rings[0][i], rings[1][i], rings[0][next], bark);
      face(rings[0][next], rings[1][i], rings[1][next], bark);
    }
  };
  const trunkTop = Math.max(full.min.y + .5, crown.min.y + size.y * .25);
  const trunkRadius = THREE.MathUtils.clamp(Math.min(size.x, size.z) * .035, .06, .32);
  branch(new THREE.Vector3(0, full.min.y, 0), new THREE.Vector3(.04, trunkTop, 0), trunkRadius, trunkRadius * .45);
  for (let i = 0; i < 4; i++) {
    const angle = i * Math.PI / 2 + .3;
    branch(new THREE.Vector3(.04, trunkTop * .70, 0),
      new THREE.Vector3(center.x + Math.cos(angle) * size.x * .24, center.y, center.z + Math.sin(angle) * size.z * .24),
      trunkRadius * .42, trunkRadius * .07);
  }
  const lobes = [[0, .13, 0, .35, .46, .35], [-.22, -.04, -.12, .28, .43, .31],
    [.22, -.03, .12, .28, .43, .31], [-.12, -.09, .22, .32, .36, .28],
    [.12, -.10, -.22, .32, .36, .28], [0, -.20, 0, .36, .29, .34]];
  lobes.forEach(([x, y, z, rx, ry, rz], index) => {
    const origin = new THREE.Vector3(center.x + x * size.x, center.y + y * size.y, center.z + z * size.z);
    const rings = [-.68, 0, .68].map((height, ring) => Array.from({ length: 7 }, (_, i) => {
      const angle = i * Math.PI * 2 / 7 + index * .37;
      const radius = (ring === 1 ? 1 : .70) * (.92 + .08 * Math.sin(index * 5 + i * 3.7));
      return new THREE.Vector3(origin.x + Math.cos(angle) * size.x * rx * radius,
        origin.y + height * size.y * ry, origin.z + Math.sin(angle) * size.z * rz * radius);
    }));
    const top = origin.clone().add(new THREE.Vector3(0, size.y * ry, 0));
    const bottom = origin.clone().add(new THREE.Vector3(0, -size.y * ry, 0));
    const shade = .84 + index * .045;
    for (let i = 0; i < 7; i++) {
      const next = (i + 1) % 7;
      face(top, rings[2][next], rings[2][i], leaf, shade);
      face(bottom, rings[0][i], rings[0][next], leaf, shade);
      for (let ring = 0; ring < 2; ring++) {
        face(rings[ring][i], rings[ring + 1][i], rings[ring][next], leaf, shade);
        face(rings[ring][next], rings[ring + 1][i], rings[ring + 1][next], leaf, shade);
      }
    }
  });
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  geometry.computeVertexNormals(); geometry.computeBoundingBox(); geometry.computeBoundingSphere();
  const material = new THREE.MeshStandardMaterial({ color: 0xffffff, vertexColors: true, roughness: .95, side: THREE.DoubleSide });
  material.name = "street-tree-distant-foliage";
  return { geometry, material };
}

export class StreetTreeLod {
  private initialized = false;
  private disposed = false;
  private readonly worldPoint = new THREE.Vector3();
  readonly nearDistance: number;
  readonly hysteresis: number;
  constructor(private readonly scene: THREE.Group, private readonly trees: Tree[], private readonly batches: Batch[], options: StreetTreeLodOptions) {
    this.nearDistance = options.nearDistance ?? 120; this.hysteresis = options.hysteresis ?? 12;
  }
  /** Repack only when a tree crosses its distance band; source matrices never change. */
  update(x: number, z: number) {
    if (this.disposed) return false;
    if (!Number.isFinite(x) || !Number.isFinite(z)) throw new Error("Tree LOD focus must be finite");
    this.scene.updateWorldMatrix(true, false);
    let changed = !this.initialized;
    for (const tree of this.trees) {
      this.worldPoint.setFromMatrixPosition(tree.matrix).applyMatrix4(this.scene.matrixWorld);
      const limit = this.nearDistance + (this.initialized ? (tree.near ? this.hysteresis : -this.hysteresis) : 0);
      const near = (this.worldPoint.x - x) ** 2 + (this.worldPoint.z - z) ** 2 <= limit ** 2;
      if (near !== tree.near) { tree.near = near; changed = true; }
    }
    if (!changed) return false;
    this.initialized = true;
    for (const batch of this.batches) {
      let count = 0;
      const names: string[] = [], metadata: Record<string, unknown>[] = [];
      for (const instance of batch.instances) if (this.trees[instance.tree].near === batch.near) {
        batch.mesh.setMatrixAt(count++, instance.matrix);
        names.push(instance.name); metadata.push(instance.metadata);
      }
      batch.mesh.count = count; batch.mesh.visible = count > 0;
      batch.mesh.userData.instanceNames = names; batch.mesh.userData.instanceMetadata = metadata;
      batch.mesh.instanceMatrix.needsUpdate = true;
      if (count) { batch.mesh.computeBoundingBox(); batch.mesh.computeBoundingSphere(); }
    }
    return true;
  }
  get stats() {
    const nearTrees = this.trees.filter(tree => tree.near).length;
    const sourceTriangles = this.trees.reduce((sum, tree) => sum + tree.sourceTriangles, 0);
    const drawnTriangles = this.batches.reduce((sum, batch) => sum + batch.mesh.count * batch.triangles, 0);
    return { trees: this.trees.length, nearTrees, farTrees: this.trees.length - nearTrees,
      sourceTriangles, drawnTriangles, trianglesSaved: Math.max(0, sourceTriangles - drawnTriangles),
      batches: this.batches.length, nearDistance: this.nearDistance, hysteresis: this.hysteresis };
  }
  /** GPU resources belong to StreetStreaming's reference-counted resource set. */
  dispose() { this.disposed = true; this.trees.length = 0; this.batches.length = 0; }
}

/** Install before generic static instancing. Unsafe/hidden/animated parts keep
 * their original nodes; a whole tree is eligible only if all its meshes are safe.
 */
export function createStreetTreeLod(scene: THREE.Group, options: StreetTreeLodOptions = {},
  canInstance: (mesh: THREE.Mesh) => boolean = mesh => safeMesh(mesh, scene)): StreetTreeLod | undefined {
  const near = options.nearDistance ?? 120, band = options.hysteresis ?? 12;
  if (!Number.isFinite(near) || !Number.isFinite(band) || near <= 0 || band < 0 || band >= near) throw new Error("Invalid tree LOD distances");
  scene.updateMatrixWorld(true);
  const candidates = new Map<THREE.Object3D, THREE.Mesh[]>();
  scene.traverse(object => {
    if (!(object instanceof THREE.Mesh)) return;
    const root = streetTreeAncestor(object, scene);
    if (root) { const meshes = candidates.get(root) ?? []; meshes.push(object); candidates.set(root, meshes); }
  });
  const inverse = scene.matrixWorld.clone().invert();
  const trees: Tree[] = [];
  for (const [root, meshes] of candidates) if (meshes.length && meshes.every(canInstance)) {
    trees.push({ root, meshes, matrix: new THREE.Matrix4().multiplyMatrices(inverse, root.matrixWorld), near: true,
      sourceTriangles: meshes.reduce((sum, mesh) => sum + triangleCount(mesh.geometry), 0) });
  }
  if (!trees.length) return undefined;
  const high = new Map<string, { first: THREE.Mesh; instances: Instance[] }>();
  const low = new Map<string, { tree: Tree; instances: Instance[] }>();
  trees.forEach((tree, treeIndex) => {
    const treeInverse = tree.root.matrixWorld.clone().invert();
    const template: string[] = [];
    for (const mesh of tree.meshes) {
      const key = [mesh.geometry.uuid, materials(mesh).map(m => m.uuid).join(","), renderKey(mesh)].join("|");
      const group = high.get(key) ?? { first: mesh, instances: [] };
      group.instances.push({ matrix: new THREE.Matrix4().multiplyMatrices(inverse, mesh.matrixWorld), tree: treeIndex, name: mesh.name,
        metadata: { ...mesh.userData, streetTreeName: tree.root.name, streetTreeCategory: "furniture" } });
      high.set(key, group);
      template.push(key + new THREE.Matrix4().multiplyMatrices(treeInverse, mesh.matrixWorld).elements.map(n => Math.abs(n) < .0000005 ? "0.000000" : n.toFixed(6)).join(","));
    }
    const key = template.sort().join(";");
    const group = low.get(key) ?? { tree, instances: [] };
    group.instances.push({ matrix: tree.matrix.clone(), tree: treeIndex, name: tree.root.name, metadata: { ...tree.root.userData } });
    low.set(key, group);
  });
  const batches: Batch[] = [];
  const addBatch = (geometry: THREE.BufferGeometry, material: THREE.Material | THREE.Material[], instances: Instance[], near: boolean, first: THREE.Mesh) => {
    const mesh = new THREE.InstancedMesh(geometry, material, instances.length);
    mesh.name = `street-tree-${near ? "near" : "far"}-${batches.length}`;
    mesh.userData.streetTreeLod = near ? "near" : "far";
    copyRenderState(first, mesh); mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    instances.forEach((instance, index) => mesh.setMatrixAt(index, instance.matrix));
    mesh.instanceMatrix.needsUpdate = true;
    mesh.userData.instanceNames = instances.map(instance => instance.name);
    mesh.userData.instanceMetadata = instances.map(instance => instance.metadata);
    mesh.count = near ? instances.length : 0; mesh.visible = near;
    if (near) { mesh.computeBoundingBox(); mesh.computeBoundingSphere(); }
    scene.add(mesh); batches.push({ mesh, instances, near, triangles: triangleCount(geometry) });
  };
  for (const group of high.values()) addBatch(group.first.geometry, group.first.material, group.instances, true, group.first);
  for (const group of low.values()) {
    const proxy = treeProxy(group.tree);
    addBatch(proxy.geometry, proxy.material, group.instances, false, group.tree.meshes[0]);
  }
  for (const tree of trees) for (const mesh of tree.meshes) mesh.removeFromParent();
  return new StreetTreeLod(scene, trees, batches, options);
}
