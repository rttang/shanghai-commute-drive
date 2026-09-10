/** Bounded CPU measurements; no browser, asset loading or service lifecycle.
 * node --import tsx scripts/verify_vehicle_dynamics.ts [--no-write]
 */
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { VehicleDynamics, VEHICLE_DYNAMICS_PROFILES, type DynamicsInput } from '../src/tour/vehicle-dynamics.ts';

export const FRAME_PATTERNS = {
  hz120: [1 / 120], hz60: [1 / 60], hz20: [1 / 20], hz10: [1 / 10],
  dropped: [1 / 60, 1 / 60, .1, 1 / 60, .2, .05, .25, 1 / 60],
} as const;
const full = { throttle: true, brake: false } as const;
const round = (n: number) => Math.round(n * 1e6) / 1e6;

export function measureAcceleration(id: string, pattern: readonly number[] = FRAME_PATTERNS.hz120, reverse = false) {
  const dynamics = new VehicleDynamics(id), thresholds = reverse ? [14.5, 15] : [50, 79.5, 80];
  const reached: Record<string, number> = {};
  let speed = 0, elapsed = 0, distance = 0, frames = 0;
  while (elapsed < 20 - 1e-9) {
    const dt = Math.min(pattern[frames % pattern.length], 20 - elapsed), before = speed;
    speed = dynamics.step(speed, reverse ? -1 : 1, full, dt);
    for (const kmh of thresholds) if (reached[kmh] === undefined && Math.abs(speed) * 3.6 >= kmh - 1e-10) {
      reached[kmh] = elapsed + dt * Math.min(1, (kmh / 3.6 - Math.abs(before)) / Math.max(1e-12, Math.abs(speed) - Math.abs(before)));
    }
    distance += (before + speed) * dt / 2;
    elapsed += dt; frames++;
  }
  return { reachedSeconds: reached, finalSpeedKmh: speed * 3.6, distanceMetres: distance, frames };
}

export function measureBraking(id: string, reverse = false, handbrake = false) {
  const dynamics = new VehicleDynamics(id), dt = 1 / 120;
  let speed = (reverse ? -15 : 80) / 3.6, seconds = 0, distance = 0;
  // Throttle stays pressed to verify that the brake has priority.
  while (speed !== 0 && seconds < 10) {
    const before = speed;
    speed = dynamics.step(speed, reverse ? -1 : 1, { ...full, brake: true, handbrake }, dt);
    distance += (Math.abs(before) + Math.abs(speed)) * dt / 2;
    seconds += dt;
  }
  return { seconds, distanceMetres: distance, finalSpeedMps: speed };
}

/** Compare identical input-change times and checkpoint times, not frame counts. */
export function frameTrace(id: string, pattern: readonly number[], reverse = false) {
  const dynamics = new VehicleDynamics(id), checkpoints: { seconds: number; speedMps: number; pedal: number }[] = [];
  let speed = 0, total = 0, frames = 0;
  const segments: { seconds: number; input: DynamicsInput }[] = [
    { seconds: 4, input: full },
    { seconds: 1, input: { throttle: false, brake: false } },
    { seconds: 2, input: { throttle: .45, brake: false } },
    { seconds: 4, input: { throttle: true, brake: true } },
  ];
  for (const segment of segments) {
    const end = total + segment.seconds;
    while (total < end - 1e-9) {
      const checkpointAt = Math.floor((total + 1e-9) * 2) / 2 + .5;
      const dt = Math.min(pattern[frames % pattern.length], end - total, checkpointAt - total);
      speed = dynamics.step(speed, reverse ? -1 : 1, segment.input, dt);
      total += dt; frames++;
      if (Math.abs(total - checkpointAt) < 1e-8) checkpoints.push({ seconds: total, speedMps: speed, pedal: dynamics.pedal });
    }
  }
  return checkpoints;
}

export function verifyVehicleDynamics() {
  const root = fileURLToPath(new URL('../', import.meta.url));
  const inputs = ['src/tour/vehicle-dynamics.ts', 'src/tour/vehicle-dynamics.json', 'references/vehicle-dynamics-sources.json', 'scripts/verify_vehicle_dynamics.ts'];
  const hashes = Object.fromEntries(inputs.map(file => [file, createHash('sha256').update(fs.readFileSync(path.join(root, file))).digest('hex')]));
  const vehicles = VEHICLE_DYNAMICS_PROFILES.map(profile => {
    const reference = measureAcceleration(profile.id), reverse = measureAcceleration(profile.id, FRAME_PATTERNS.hz120, true);
    const traces = [false, true].map(backwards => {
      const expected = frameTrace(profile.id, FRAME_PATTERNS.hz120, backwards);
      return { direction: backwards ? 'reverse' : 'forward', comparisons: Object.entries(FRAME_PATTERNS).filter(([id]) => id !== 'hz120').map(([id, pattern]) => {
        const actual = frameTrace(profile.id, pattern, backwards);
        return { pattern: id, maximumSpeedDifferenceMps: Math.max(...actual.map((p, i) => Math.abs(p.speedMps - expected[i].speedMps))), maximumPedalDifference: Math.max(...actual.map((p, i) => Math.abs(p.pedal - expected[i].pedal))) };
      }) };
    });
    const frames = Object.fromEntries(Object.entries(FRAME_PATTERNS).map(([id, pattern]) => {
      const measured = measureAcceleration(profile.id, pattern);
      return [id, { zeroTo50Seconds: measured.reachedSeconds[50], zeroTo79Point5Seconds: measured.reachedSeconds[79.5], maximumSpeedKmh: measured.finalSpeedKmh }];
    }));
    return {
      id: profile.id, name: profile.name, referenceId: profile.referenceId,
      pedalResponseSeconds: profile.responseSeconds,
      zeroTo50Seconds: reference.reachedSeconds[50], zeroTo79Point5Seconds: reference.reachedSeconds[79.5],
      fiftyTo79Point5Seconds: reference.reachedSeconds[79.5] - reference.reachedSeconds[50],
      maximumForwardSpeedKmh: reference.finalSpeedKmh,
      reverseZeroTo14Point5Seconds: reverse.reachedSeconds[14.5], maximumReverseSpeedKmh: Math.abs(reverse.finalSpeedKmh),
      brake80ToZero: measureBraking(profile.id), handbrake80ToZero: measureBraking(profile.id, false, true), reverseBrake15ToZero: measureBraking(profile.id, true),
      frames, traces,
    };
  });
  const maximumFrameDifference = Math.max(...vehicles.flatMap(car => car.traces.flatMap(trace => trace.comparisons.map(c => c.maximumSpeedDifferenceMps))));
  return {
    generatedAt: new Date().toISOString(), passed: maximumFrameDifference < .0005 && vehicles.every(car => car.maximumForwardSpeedKmh === 80 && Math.abs(car.maximumReverseSpeedKmh - 15) < 1e-9),
    inputs: hashes,
    boundary: 'Pure manual longitudinal dynamics. Flat road, full pedal from rest; no tyre/gearbox/battery simulation. This is game calibration, not official acceleration. Drive pose/collision and browser integration belong to separate acceptance.',
    measurement: {
      primaryHz: 120, zeroTo80ReportedThresholdKmh: 79.5,
      thresholdTiming: 'Linear interpolation of sampled speed; lower render frequency can change threshold observation timing. Equal-time traces are the frame-invariance check.',
      brakeTiming: 'First zero-speed sample at 120 Hz; time resolution 1/120 second.',
      framePatternsSeconds: FRAME_PATTERNS,
      frameComparison: 'Same control transitions and half-second checkpoints; includes full throttle, release, partial throttle, braking, forward and reverse.',
      acceptedFrameLimitSeconds: .25, longerStalls: 'Excess over 0.25 seconds is discarded, preserving existing Drive stall behavior.',
      maximumFrameDifferenceMps: maximumFrameDifference,
    }, vehicles,
  };
}

const isMain = process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href;
if (isMain) {
  const report = verifyVehicleDynamics();
  const serializable = JSON.parse(JSON.stringify(report, (_key, value) => typeof value === 'number' ? round(value) : value));
  if (!process.argv.includes('--no-write')) {
    const output = fileURLToPath(new URL('../docs/evidence/tourism/vehicle-dynamics-verification.json', import.meta.url));
    fs.mkdirSync(path.dirname(output), { recursive: true });
    fs.writeFileSync(output, JSON.stringify(serializable, null, 2) + '\n');
  }
  console.log(JSON.stringify(serializable, null, 2));
  if (!report.passed) process.exitCode = 1;
}
