import { test } from "node:test";
import assert from "node:assert/strict";
import { usePerformanceStreets } from "../src/tour/performance-streets";
import type { StreetManifest } from "../src/tour/street-streaming";

test("performance variants retain placement and cannot silently replace a new source revision", () => {
  const chunk = { id: "skyline", file: "/streets/master/chunks/skyline.glb", bytes: 1000, triangles: 1000,
    sha256: "a".repeat(64), bounds: [1, 2, 3, 4] as [number, number, number, number], coveredWays: [42], always: true };
  const manifest: StreetManifest = { version: 1, master: { file: "/master.glb", bytes: 1000 }, chunks: [chunk], coveredWays: [42] };
  const variant = { id: "skyline", sourceFile: chunk.file, sourceSha256: chunk.sha256,
    file: "/streets/performance/skyline.glb", bytes: 700, triangles: 800 };
  const result = usePerformanceStreets(manifest, [variant]);
  assert.equal(result.chunks[0].file, variant.file);
  assert.deepEqual(result.chunks[0].bounds, chunk.bounds);
  assert.deepEqual(result.chunks[0].coveredWays, [42]);
  assert.equal(result.chunks[0].always, true);
  assert.equal(manifest.chunks[0].file, chunk.file);
  for (const change of [{ sourceSha256: "b".repeat(64) }, { sourceFile: "/wrong.glb" }, { file: "https://example.com/scene.glb" }, { bytes: -1 }, { triangles: 2000 }])
    assert.equal(usePerformanceStreets(manifest, [{ ...variant, ...change }]).chunks[0], chunk);
  assert.equal(usePerformanceStreets(manifest, null), manifest);
});
