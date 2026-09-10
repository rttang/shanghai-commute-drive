/** Recycle traffic only when neither its old nor its new pose can be seen. */
export function trafficRespawnDistance(current: number, player: number, total: number, index: number, visible: (distance: number) => boolean): number | undefined {
  const gap = ((current - player) % total + total) % total;
  if (Math.min(gap, total - gap) <= 1700 || visible(current)) return;
  for (const offset of [1100 + index * 60, -1100 - index * 60, 1450 + index * 30]) {
    const candidate = ((player + offset) % total + total) % total;
    if (!visible(candidate)) return candidate;
  }
}
