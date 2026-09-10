import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { CARS, LANDMARKS } from "../src/tour/data";
import photoArchitecture from "../src/tour/photo-architecture.json";
const root = new URL("../", import.meta.url);
test("scenery builds preserve the original baseline except explicitly approved driving changes", () => {
  const frozen = JSON.parse(
    readFileSync(
      new URL("docs/evidence/tourism/street-freeze.json", root),
      "utf8",
    ),
  );
  const scope = JSON.parse(
    readFileSync(
      new URL("docs/evidence/tourism/driving-scope.json", root),
      "utf8",
    ),
  );
  assert.deepEqual([...scope.releasedFromStreetFreeze].sort(), [
    "src/main.ts",
    "src/tour/drive.ts",
    "src/tour/ui.ts",
    "src/tour/vehicle-assets.json",
  ]);
  const loopScope=JSON.parse(readFileSync(new URL("docs/evidence/tourism/loop-scope.json",root),"utf8"));
  const fleetScope=JSON.parse(readFileSync(new URL('docs/evidence/tourism/luxury-fleet-scope.json',root),'utf8'));
  assert.deepEqual(fleetScope.releasedFromStreetFreeze,['src/tour/cars.json']);
  const retired=['starwish','leap-a10','qiyuan-q05','li-i6','bingo-pro'];
  assert.deepEqual(Object.keys(fleetScope.archivedFrozenFiles).sort(),retired.flatMap(id=>[`public/cars/${id}.png`,`public/tour-models/${id}.glb`]).sort());
  const released = new Set([...scope.releasedFromStreetFreeze,...loopScope.releasedFromStreetFreeze,...fleetScope.releasedFromStreetFreeze]);
  for (const [path, hash] of Object.entries(frozen)) {
    const archive=fleetScope.archivedFrozenFiles[path]??fleetScope.baselineArchives[path];
    if(archive)assert.equal(createHash('sha256').update(readFileSync(new URL(archive,root))).digest('hex'),hash,`Archived original baseline retained: ${path}`);
    if(fleetScope.archivedFrozenFiles[path])continue;
    if (released.has(path)) {
      assert.equal(
        scope.preChangeHashes[path]??loopScope.originalFrozenHashes[path]??fleetScope.originalFrozenHashes[path],
        hash,
        `Original baseline retained: ${path}`,
      );
      continue;
    }
    assert.equal(
      createHash("sha256")
        .update(readFileSync(new URL(path, root)))
        .digest("hex"),
      hash,
      path,
    );
  }
});
test("scenery manifest is complete, compressed, finite and separate from vehicle assets", () => {
  const manifest = JSON.parse(
    readFileSync(new URL("public/streets/models/manifest.json", root), "utf8"),
  );
  assert.equal(manifest.protectedFilesUnchanged, true);
  const required = [
    ...LANDMARKS.map((x) => x.id),
    "waibaidu-bridge",
    "plane-tree",
    "streetlamp",
    "river-railing",
  ];
  for (const id of required)
    assert.ok(
      manifest.models.some((m: { id: string }) => m.id === id),
      id,
    );
  let total = 0;
  for (const model of manifest.models) {
    assert.ok(!CARS.some((c) => c.id === model.id));
    const bytes = readFileSync(
      new URL(`public/streets/models/${model.id}.glb`, root),
    );
    total += bytes.length;
    assert.equal(bytes.length, model.bytes);
    assert.equal(bytes.readUInt32LE(8), bytes.length);
    const gltf = JSON.parse(
      bytes.subarray(20, 20 + bytes.readUInt32LE(12)).toString(),
    );
    assert.ok(gltf.extensionsRequired.includes("KHR_draco_mesh_compression"));
    assert.ok(
      !gltf.images?.length,
      "Textures are shared, not copied into every landmark",
    );
    for (const a of gltf.accessors)
      for (const key of ["min", "max"])
        if (a[key]) assert.ok(a[key].every(Number.isFinite));
    const triangles = gltf.meshes.reduce(
      (n: number, m: { primitives: { indices: number }[] }) =>
        n +
        m.primitives.reduce(
          (n, p) => n + gltf.accessors[p.indices].count / 3,
          0,
        ),
      0,
    );
    assert.equal(triangles, model.triangles, model.id);
    if (model.id === "plane-tree") assert.ok(triangles < 4000);
  }
  assert.ok(total < 4_000_000);
});

test("photo architecture has unique mapped sites, traced sources and self-contained bounded GLBs", () => {
  const json = (file: string) =>
    JSON.parse(readFileSync(new URL(file, root), "utf8"));
  const manifest = json("public/streets/photo-models/manifest.json");
  const budget = json("public/streets/model-budget.json");
  // The retained photo-model snapshot predates the complete master-scene
  // policy. Its independent-model limits must remain compatible and intact.
  assert.equal(manifest.budget.ordinaryAverageBytes, budget.ordinaryAverageBytes);
  assert.equal(manifest.budget.aggregateLimitBytes, budget.aggregateLimitBytes);
  assert.deepEqual(manifest.budget.landmarkExceptions, budget.landmarkExceptions);
  assert.equal(budget.streetMaster.minBytesExclusive, 0);
  assert.equal(budget.streetMaster.maxBytesExclusive, 4_294_967_296);
  assert.equal(budget.streetMaster.runtimePackageMaxBytesInclusive, 5_000_000_000);
  assert.equal(budget.ordinaryAverageBytes, 10_000_000);
  assert.equal(budget.aggregateLimitBytes, null);
  assert.deepEqual(Object.keys(budget.landmarkExceptions).sort(), [
    "bank-china",
    "customs-house",
    "hsbc-bund",
    "peace-hotel",
    "pearl",
  ]);
  assert.equal(manifest.quality.jpegQuality, 96);
  assert.equal(manifest.quality.textureResize, false);
  assert.equal(manifest.quality.meshDecimation, false);
  assert.deepEqual(
    [
      manifest.quality.dracoPositionBits,
      manifest.quality.dracoNormalBits,
      manifest.quality.dracoTexcoordBits,
    ],
    [18, 14, 16],
  );
  assert.equal(manifest.protectedFilesUnchanged, true);
  assert.equal(manifest.protectedFileCount, 38);
  assert.deepEqual(
    Object.keys(manifest.approvedDrivingFilesUnchangedDuringBuild).sort(),
    [
      "src/main.ts",
      "src/tour/drive.ts",
      "src/tour/ui.ts",
      "src/tour/vehicle-assets.json",
    ],
  );
  for (const [path, sha] of Object.entries(
    manifest.generatedSourceImagesUnchanged,
  ))
    assert.equal(
      createHash("sha256")
        .update(readFileSync(new URL(path, root)))
        .digest("hex"),
      sha,
    );
  const photos = json("references/tourism/architecture-photos.json");
  const city = json("public/tour-city.json");
  const expected = [...photoArchitecture.map((b) => b.id), "pearl"].sort();
  assert.deepEqual(
    manifest.models.map((m: { id: string }) => m.id).sort(),
    expected,
  );
  const usedWays = new Set<number>();
  for (const b of photoArchitecture) {
    for (const id of b.ways) {
      assert.ok(!usedWays.has(id), `Overlapping photo replacements: ${id}`);
      usedWays.add(id);
      assert.ok(
        city.buildings.some((way: { id: number }) => way.id === id),
        `${b.id}: missing mapped footprint`,
      );
    }
    assert.ok(b.front.flat().every(Number.isFinite));
    assert.ok(
      Math.hypot(b.front[0][0] - b.front[1][0], b.front[0][1] - b.front[1][1]) >
        10,
    );
  }
  let total = 0;
  let ordinaryTotal = 0;
  let ordinaryCount = 0;
  for (const model of manifest.models) {
    const source = photos.find((p: { id: string }) => p.id === model.reference);
    assert.ok(
      source && source.usage === "exterior-reference",
      `${model.id}: rejected/missing exterior source`,
    );
    assert.ok(
      source.author &&
        source.licenseUrl &&
        source.source.startsWith("https://commons.wikimedia.org/wiki/File:"),
    );
    assert.equal(
      createHash("sha256")
        .update(readFileSync(new URL(source.file, root)))
        .digest("hex"),
      source.sha256,
    );
    const bytes = readFileSync(
      new URL(`public/streets/photo-models/${model.id}.glb`, root),
    );
    total += bytes.length;
    const landmark = model.id in budget.landmarkExceptions;
    assert.equal(
      model.budgetClass,
      landmark ? "landmark-exception" : "ordinary",
    );
    assert.deepEqual(model.quality, manifest.quality);
    if (!landmark) {
      ordinaryTotal += bytes.length;
      ordinaryCount += 1;
    }
    assert.equal(bytes.length, model.bytes);
    assert.equal(
      createHash("sha256").update(bytes).digest("hex"),
      model.sha256,
    );
    assert.equal(bytes.readUInt32LE(8), bytes.length);
    const gltf = JSON.parse(
      bytes.subarray(20, 20 + bytes.readUInt32LE(12)).toString(),
    );
    assert.ok(gltf.extensionsRequired.includes("KHR_draco_mesh_compression"));
    if (model.id !== "pearl")
      assert.ok(gltf.images?.length >= 1 && gltf.images.length <= 2);
    for (const image of gltf.images || []) {
      assert.equal(image.mimeType, "image/jpeg");
      assert.equal(typeof image.bufferView, "number");
      assert.equal(image.uri, undefined);
      // Check the actual embedded JPEG dimensions against the preserved PNG;
      // manifest claims alone would not catch accidental texture downsizing.
      const view = gltf.bufferViews[image.bufferView];
      const binaryStart = 28 + bytes.readUInt32LE(12);
      const jpeg = bytes.subarray(
        binaryStart + (view.byteOffset || 0),
        binaryStart + (view.byteOffset || 0) + view.byteLength,
      );
      const png = readFileSync(
        new URL(`assets/streets/photofacades/${image.name}.png`, root),
      );
      assert.deepEqual(
        jpegDimensions(jpeg),
        [png.readUInt32BE(16), png.readUInt32BE(20)],
        image.name,
      );
    }
    for (const a of gltf.accessors)
      for (const k of ["min", "max"])
        if (a[k]) assert.ok(a[k].every(Number.isFinite));
    const triangles = gltf.meshes.reduce(
      (n: number, m: { primitives: { indices: number }[] }) =>
        n +
        m.primitives.reduce(
          (n, p) => n + gltf.accessors[p.indices].count / 3,
          0,
        ),
      0,
    );
    assert.equal(triangles, model.triangles);
    assert.ok(triangles < 200_000);
    assert.ok(!CARS.some((c) => c.id === model.id));
  }
  assert.ok(ordinaryCount > 0);
  assert.equal(total, manifest.totalBytes);
  assert.equal(total / manifest.models.length, manifest.averageBytes);
  assert.equal(ordinaryTotal / ordinaryCount, manifest.ordinaryAverageBytes);
  assert.ok(
    ordinaryTotal / ordinaryCount < budget.ordinaryAverageBytes,
    "Ordinary models average below 10 MB each; named landmarks may be larger",
  );
});

function jpegDimensions(bytes: Buffer): [number, number] {
  assert.equal(bytes.readUInt16BE(0), 0xffd8, "Valid JPEG header");
  for (let offset = 2; offset < bytes.length;) {
    assert.equal(bytes[offset++], 0xff);
    while (bytes[offset] === 0xff) offset++;
    const marker = bytes[offset++];
    const length = bytes.readUInt16BE(offset);
    if ([0xc0, 0xc1, 0xc2].includes(marker))
      return [bytes.readUInt16BE(offset + 5), bytes.readUInt16BE(offset + 3)];
    offset += length;
  }
  throw new Error("Missing JPEG dimensions");
}
