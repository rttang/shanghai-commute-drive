import type { Matrix4 } from 'three';
import type { ModelObstacle } from './model_collision_geometry.mjs';
export function transformLowHull(obstacle: ModelObstacle, matrix: Matrix4, id: string, kind: string): ModelObstacle;
export function tunnelBarriersFromGeometry(positions: Float32Array | Float64Array, indices: Uint32Array | Float64Array, matrix?: Matrix4): ModelObstacle[];
export const ROOT: string;
export const CANDIDATE: string;
export const VERIFICATION: string;
export const RECEIPT: string;
