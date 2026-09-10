type Position = { x: number; z: number; y?: number };

/** Join a ramp continuously; a nearby underground route is not ground support. */
export function drivingSurfaceHeight(previous: Position, next: Position, routeY: number, separation: number, tunnel: boolean) {
  const oldY = previous.y ?? 0;
  if (!Number.isFinite(routeY)) return oldY;
  const movement = Math.hypot(next.x - previous.x, next.z - previous.z);
  // The authored ramps are at most 6%; tolerate projection rounding without
  // allowing a surface road above the bore to pull the car underground.
  const maxRise = movement * .1 + .025;
  if (Math.abs(routeY - oldY) > maxRise) return oldY;
  if (tunnel && separation > 3.45 && oldY > -.15) return 0;
  return routeY;
}
