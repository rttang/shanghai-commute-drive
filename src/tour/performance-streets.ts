import type { StreetManifest } from "./street-streaming";

/** A derived asset is valid only for the exact source revision it was built from. */
export function usePerformanceStreets(manifest: StreetManifest, variants: unknown): StreetManifest {
  if (!Array.isArray(variants)) return manifest;
  return { ...manifest, chunks: manifest.chunks.map(chunk => {
    const variant = variants.find(candidate => candidate?.id === chunk.id &&
      typeof chunk.sha256 === "string" && /^[a-f0-9]{64}$/.test(chunk.sha256) &&
      candidate.sourceSha256 === chunk.sha256 &&
      candidate.sourceFile === chunk.file &&
      typeof candidate.file === "string" && /^\/streets\/performance\/[a-z0-9-]+\.glb$/.test(candidate.file) &&
      Number.isSafeInteger(candidate.bytes) && candidate.bytes > 0 && candidate.bytes <= chunk.bytes &&
      Number.isSafeInteger(candidate.triangles) && candidate.triangles > 0 &&
      candidate.triangles <= Math.ceil(chunk.triangles * (candidate.purpose === "portal-surface-repair" ? 1.03 : 1)));
    return variant ? { ...chunk, file: variant.file, bytes: variant.bytes, triangles: variant.triangles, sha256: variant.sha256 } : chunk;
  }) };
}
