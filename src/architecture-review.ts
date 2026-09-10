import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
async function run() {
  const id = new URLSearchParams(location.search).get("id") || "bund-18";
  const decoder = new DRACOLoader()
    .setDecoderPath("/decoders/draco/")
    .setWorkerLimit(1);
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(innerWidth, innerHeight);
  renderer.setPixelRatio(1);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1;
  document.body.append(renderer.domElement);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color("#b7c5ce");
  scene.add(new THREE.HemisphereLight("#e4f3ff", "#726f60", 2));
  const sun = new THREE.DirectionalLight("#fff3dd", 2.5);
  sun.position.set(30, 60, 50);
  scene.add(sun);
  const camera = new THREE.PerspectiveCamera(
    45,
    innerWidth / innerHeight,
    0.1,
    2000,
  );
  const g = (
    await new GLTFLoader()
      .setDRACOLoader(decoder)
      .loadAsync("/streets/photo-models/" + id + ".glb")
  ).scene;
  scene.add(g);
  decoder.dispose();
  const box = new THREE.Box3().setFromObject(g),
    size = box.getSize(new THREE.Vector3());
  camera.position.set(size.x * 0.65, size.y * 0.6, -size.y * 1.7);
  camera.lookAt(0, size.y * 0.43, 0);
  document.querySelector("#status")!.textContent = id;
  document.body.dataset.review = JSON.stringify({ id });
  let count = 0;
  function frame() {
    renderer.render(scene, camera);
    document.body.dataset.sample = JSON.stringify({
      frames: ++count,
      diagnostic: true,
    });
    requestAnimationFrame(frame);
  }
  frame();
}
void run().catch((e) => {
  document.querySelector("#status")!.textContent = String(e);
  console.error(e);
});
