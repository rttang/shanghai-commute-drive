import configuration from './vehicle-dynamics.json';

export type VehicleDynamicsId = 'su7' | 'model-3' | 'model-y' | 'dolphin' | 'yuan-up' | 'g63' | 'urus' | 'porsche-911' | 'ferrari-488' | 'alphard';
export type DynamicsInput = { throttle: boolean | number; brake: boolean; handbrake?: boolean };
export type DynamicsProfile = Readonly<{
  id: VehicleDynamicsId;
  name: string;
  referenceId: string;
  referenceVariant: string;
  officialZeroTo100Seconds: number | null;
  responseSeconds: number;
  reverseAccelerationMps2: number;
  accelerationCurve: readonly (readonly [number, number])[];
  character: string;
  referenceBoundary?: string;
}>;

export const VEHICLE_DYNAMICS_LIMITS = Object.freeze({ ...configuration.limits });
export const VEHICLE_DYNAMICS_PROFILES: readonly DynamicsProfile[] = Object.freeze(configuration.profiles.map(profile => Object.freeze({
  ...profile, id: profile.id as VehicleDynamicsId,
  accelerationCurve: Object.freeze(profile.accelerationCurve.map(point => Object.freeze([point[0], point[1]] as [number, number]))),
})));
const profiles = new Map<string, DynamicsProfile>(VEHICLE_DYNAMICS_PROFILES.map(profile => [profile.id, profile]));
const clamp = (value: number, low: number, high: number) => Math.max(low, Math.min(high, value));
const forwardLimit = VEHICLE_DYNAMICS_LIMITS.forwardKmh / 3.6;
const reverseLimit = VEHICLE_DYNAMICS_LIMITS.reverseKmh / 3.6;

export function getVehicleDynamicsProfile(id: string): DynamicsProfile {
  return profiles.get(id) ?? profiles.get('su7')!;
}

/** Full-pedal wheel acceleration before the shared driving resistance.
 * The curve is game calibration. Published 0–100 data is kept separately. */
export function forwardTraction(profile: DynamicsProfile, speedMps: number): number {
  const speed = Math.max(0, Math.abs(speedMps) * 3.6), curve = profile.accelerationCurve;
  for (let i = 1; i < curve.length; i++) {
    if (speed > curve[i][0]) continue;
    const [v0, a0] = curve[i - 1], [v1, a1] = curve[i];
    return a0 + (a1 - a0) * clamp((speed - v0) / (v1 - v0), 0, 1);
  }
  return curve[curve.length - 1][1];
}

/** Stateful pedal response, independent of Drive pose/collision integration.
 * Only call this in manual mode. Auto cruise keeps its existing controller.
 * Own integration is <=1/120 s; calls already split by Drive remain one step. */
export class VehicleDynamics {
  private selected: DynamicsProfile;
  private deliveredPedal = 0;

  constructor(carId = 'su7') { this.selected = getVehicleDynamicsProfile(carId); }
  get profile(): DynamicsProfile { return this.selected; }
  get pedal(): number { return this.deliveredPedal; }
  setVehicle(carId: string): void { this.selected = getVehicleDynamicsProfile(carId); this.reset(); }
  reset(): void { this.deliveredPedal = 0; }

  step(speedMps: number, gear: 1 | -1, input: DynamicsInput, dtSeconds: number): number {
    let speed = clamp(Number.isFinite(speedMps) ? speedMps : 0, -reverseLimit, forwardLimit);
    if (!Number.isFinite(dtSeconds) || dtSeconds <= 0) return speed;
    const dt = Math.min(dtSeconds, VEHICLE_DYNAMICS_LIMITS.maximumFrameSeconds);
    const count = Math.max(1, Math.ceil(dt / VEHICLE_DYNAMICS_LIMITS.maximumIntegrationSeconds));
    const h = dt / count;
    const request = typeof input.throttle === 'boolean' ? Number(input.throttle) : (Number.isFinite(input.throttle) ? clamp(input.throttle, 0, 1) : 0);
    const braking = input.brake || input.handbrake;
    const direction = gear === -1 ? -1 : 1;
    for (let i = 0; i < count; i++) {
      if (braking || request === 0) {
        // Release and brake override torque immediately, matching existing input
        // behavior; response lag only softens the subsequent throttle opening.
        this.deliveredPedal = 0;
        const deceleration = braking ? (input.handbrake ? VEHICLE_DYNAMICS_LIMITS.handbrakeMps2 : VEHICLE_DYNAMICS_LIMITS.brakeMps2)
          : VEHICLE_DYNAMICS_LIMITS.coastBaseMps2 + VEHICLE_DYNAMICS_LIMITS.coastDragPerSpeedSquared * speed * speed;
        const remainingSpeed = Math.max(0, Math.abs(speed) - deceleration * h);
        speed = remainingSpeed === 0 ? 0 : Math.sign(speed) * remainingSpeed;
        continue;
      }
      const tau = direction < 0 ? Math.max(.22, this.selected.responseSeconds) : this.selected.responseSeconds;
      const decay = Math.exp(-h / tau);
      // Exact average of the first-order pedal response during this step.
      const averagePedal = request + (this.deliveredPedal - request) * (-Math.expm1(-h / tau)) / (h / tau);
      this.deliveredPedal = request + (this.deliveredPedal - request) * decay;
      const acceleration = (value: number) => {
        const traction = direction > 0 ? forwardTraction(this.selected, value)
          : this.selected.reverseAccelerationMps2 * (1 - .2 * Math.min(1, Math.abs(value) / reverseLimit));
        return direction * (averagePedal * traction - VEHICLE_DYNAMICS_LIMITS.driveDragPerSpeedSquared * value * value);
      };
      const first = acceleration(speed), predicted = speed + first * h;
      // Heun integration avoids frame-pattern dependent throttle/curve drift.
      speed = clamp(speed + (first + acceleration(predicted)) * h / 2, -reverseLimit, forwardLimit);
    }
    return speed;
  }
}
