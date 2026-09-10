/** Current-runtime core collider regeneration. Detailed architecture additions
 * remain opt-in via model_collision_runtime.mjs --candidate --include-architecture. */
import { createRuntimeCollisionCandidate, verifyRuntimeCollisionCandidate, publishRuntimeCollisionCandidate } from './model_collision_runtime.mjs';
await createRuntimeCollisionCandidate();
verifyRuntimeCollisionCandidate();
console.log(JSON.stringify(publishRuntimeCollisionCandidate()));
