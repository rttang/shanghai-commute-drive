/** Limit rendering work independently of the display's Retina pixel density. */
export function renderBudget(quality: string) {
  return quality === "high"
    ? { loadRadius: 650, unloadRadius: 950, pixelRatio: 1.5, pixels: 2_000_000, anisotropy: 4, shadows: true, shadowSize: 1536 }
    : { loadRadius: 420, unloadRadius: 650, pixelRatio: 1, pixels: 1_100_000, anisotropy: 2, shadows: false, shadowSize: 512 };
}

export function renderPixelRatio(width: number, height: number, density: number, quality: string) {
  const budget = renderBudget(quality);
  const area = Math.max(1, width) * Math.max(1, height);
  return Math.min(Math.max(.1, density), budget.pixelRatio, Math.sqrt(budget.pixels / area));
}
