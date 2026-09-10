import verification from '../../docs/evidence/tourism/vehicle-dynamics-verification.json';
import { VEHICLE_DYNAMICS_PROFILES } from './vehicle-dynamics';

const profiles = new Map(VEHICLE_DYNAMICS_PROFILES.map(profile => [String(profile.id), profile]));
const measured = new Map(verification.vehicles.map(vehicle => [vehicle.id, vehicle.zeroTo79Point5Seconds]));

/** Garage figures come from the 120 Hz game measurement, never official 0–100 data. */
export function garageDynamics(id: string) {
  const profile = profiles.get(id), seconds = measured.get(id);
  const verified = verification.passed && verification.measurement.zeroTo80ReportedThresholdKmh === 79.5 && typeof seconds === 'number' && Number.isFinite(seconds) && seconds > 0;
  return {
    character: profile?.character.split('；')[0] ?? '选择座驾，体验城市驾驶',
    acceleration: profile && verified ? `城市加速 0–80 · ${seconds.toFixed(1)} 秒` : '城市加速 · 暂无测量',
  };
}
