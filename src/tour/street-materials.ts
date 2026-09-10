import * as THREE from "three";

/** Shared maps: landmark GLBs contain geometry/UVs, avoiding repeated texture payloads. */
export async function loadStreetMaterials() {
  const loader = new THREE.TextureLoader();
  const names = [
    "stone-diff.jpg",
    "stone-nor_gl.jpg",
    "stone-rough.jpg",
    "paving-diff.jpg",
    "paving-nor_gl.jpg",
    "paving-rough.jpg",
    "plane-bark.png",
    "plane-leaf.png",
    "heritage-facade.png",
    "ground-grass-diff.jpg",
    "ground-grass-nor_gl.jpg",
  ];
  const images = await Promise.all(
    names.map((n) => loader.loadAsync("/streets/textures/" + n)),
  );
  const maps = Object.fromEntries(names.map((n, i) => [n, images[i]]));
  for (const [name, t] of Object.entries(maps)) {
    if (name.includes("diff") || name.endsWith(".png"))
      t.colorSpace = THREE.SRGBColorSpace;
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.anisotropy = 8;
  }
  const stone = new THREE.MeshStandardMaterial({
    name: "street-stone",
    map: maps["stone-diff.jpg"],
    normalMap: maps["stone-nor_gl.jpg"],
    roughnessMap: maps["stone-rough.jpg"],
    normalScale: new THREE.Vector2(0.2, 0.2),
    color: "#d8d0be",
    roughness: 0.93,
  });
  const trim = stone.clone();
  trim.name = "street-trim";
  trim.color.set("#ebe4d5");
  trim.normalScale.set(0.11, 0.11);
  const paving = new THREE.MeshStandardMaterial({
    map: maps["paving-diff.jpg"],
    normalMap: maps["paving-nor_gl.jpg"],
    roughnessMap: maps["paving-rough.jpg"],
    normalScale: new THREE.Vector2(0.32, 0.32),
    color: "#c5c3b6",
    roughness: 0.94,
  });
  const bark = new THREE.MeshStandardMaterial({
    name: "street-bark",
    map: maps["plane-bark.png"],
    bumpMap: maps["plane-bark.png"],
    bumpScale: 0.018,
    color: "#c1bcab",
    roughness: 0.93,
  });
  for (const name of ["ground-grass-diff.jpg", "ground-grass-nor_gl.jpg"])
    maps[name].repeat.set(1 / 15, 1 / 15);
  const grass = new THREE.MeshStandardMaterial({
    map: maps["ground-grass-diff.jpg"],
    normalMap: maps["ground-grass-nor_gl.jpg"],
    normalScale: new THREE.Vector2(0.2, 0.2),
    color: "#7fa363",
    roughness: 1,
  });
  const ground = paving.clone();
  ground.color.set("#929587");
  for (const key of ["map", "normalMap", "roughnessMap"] as const) {
    const t = ground[key]!.clone();
    t.repeat.set(10000, 10000);
    ground[key] = t;
  }
  const leaf = new THREE.MeshStandardMaterial({
    name: "street-leaf",
    map: maps["plane-leaf.png"],
    alphaTest: 0.42,
    side: THREE.DoubleSide,
    color: "#bbc495",
    roughness: 0.88,
    emissive: "#394a19",
    emissiveMap: maps["plane-leaf.png"],
    emissiveIntensity: 0.16,
  });
  leaf.alphaToCoverage = true;
  const glass = new THREE.MeshPhysicalMaterial({
    name: "street-glass",
    color: "#536464",
    metalness: 0.16,
    roughness: 0.19,
    clearcoat: 1,
    clearcoatRoughness: 0.08,
    envMapIntensity: 1.3,
  });
  const heritage = maps["heritage-facade.png"].clone();
  heritage.repeat.set(1 / 13.6, 1 / 13.6);
  const named: Record<string, THREE.Material> = {
    "street-stone": stone,
    "street-trim": trim,
    "street-bark": bark,
    "street-leaf": leaf,
    "street-glass": glass,
  };
  return {
    stone,
    trim,
    paving,
    grass,
    ground,
    heritage,
    decorate(root: THREE.Group) {
      root.traverse((o) => {
        if (!(o instanceof THREE.Mesh)) return;
        const adapt = (m: THREE.Material) => {
          const key = m.name.replace(/\.\d+$/, "");
          if (named[key]) return named[key];
          if (
            m instanceof THREE.MeshStandardMaterial &&
            /towerglass|blueglass/.test(key)
          ) {
            m.color.set(key.includes("blue") ? "#719099" : "#7d9b9e");
            m.metalness = 0.2;
            m.roughness = 0.25;
            m.envMapIntensity = 1.1;
          }
          return m;
        };
        o.material = Array.isArray(o.material)
          ? o.material.map(adapt)
          : adapt(o.material);
      });
    },
  };
}
