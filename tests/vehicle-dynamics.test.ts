import test from 'node:test';
import assert from 'node:assert/strict';
import sources from '../references/vehicle-dynamics-sources.json';
import { VehicleDynamics, VEHICLE_DYNAMICS_PROFILES, VEHICLE_DYNAMICS_LIMITS, forwardTraction } from '../src/tour/vehicle-dynamics';
import { FRAME_PATTERNS, frameTrace, measureAcceleration, measureBraking } from '../scripts/verify_vehicle_dynamics';

const full = { throttle: true, brake: false } as const;
const expectedIds = ['su7', 'model-3', 'model-y', 'dolphin', 'yuan-up', 'g63', 'urus', 'porsche-911', 'ferrari-488', 'alphard'];
const close = (a: number, b: number, tolerance = 1e-9) => assert.ok(Math.abs(a - b) <= tolerance, `${a} vs ${b}; tolerance ${tolerance}`);

test('ten independently tuned profiles have explicit official reference versions', () => {
  assert.deepEqual(VEHICLE_DYNAMICS_PROFILES.map(p => p.id), expectedIds);
  assert.equal(new Set(VEHICLE_DYNAMICS_PROFILES.map(p => JSON.stringify(p.accelerationCurve))).size, 10);
  for (const p of VEHICLE_DYNAMICS_PROFILES) {
    const source = sources.sources.find(s => s.id === p.referenceId);
    assert.ok(source, p.id);
    assert.equal(p.officialZeroTo100Seconds, source.official.zeroTo100Seconds, p.id);
    assert.ok(p.responseSeconds >= .05 && p.responseSeconds <= .6);
    assert.equal(p.accelerationCurve[0][0], 0);
    assert.equal(p.accelerationCurve.at(-1)![0], 80);
    for (let i = 0; i < p.accelerationCurve.length; i++) {
      const [speed, acceleration] = p.accelerationCurve[i];
      assert.ok(Number.isFinite(acceleration) && acceleration > 0);
      if (i > 0) assert.ok(speed > p.accelerationCurve[i - 1][0]);
      close(forwardTraction(p, speed / 3.6), acceleration);
    }
  }
  assert.equal(new VehicleDynamics('alphard').profile.officialZeroTo100Seconds, null);
});

test('sports cars and performance SUVs accelerate distinctly; normal EVs stay responsive', () => {
  const times = new Map(VEHICLE_DYNAMICS_PROFILES.map(p => [p.id, measureAcceleration(p.id).reachedSeconds]));
  const order = ['porsche-911', 'ferrari-488', 'urus', 'g63', 'su7', 'model-y', 'model-3', 'yuan-up', 'alphard', 'dolphin'] as const;
  for (let i = 1; i < order.length; i++) assert.ok(times.get(order[i - 1])![79.5] + .1 < times.get(order[i])![79.5], `${order[i - 1]} vs ${order[i]}`);
  assert.ok(times.get('su7')![50] < 2.7);
  assert.ok(times.get('model-3')![50] < 3);
  assert.ok(times.get('model-y')![50] < 3);
  assert.ok(times.get('model-3')![50] < times.get('dolphin')![50] * .7);
  assert.ok(times.get('porsche-911')![50] < times.get('ferrari-488')![50]);
  assert.ok(times.get('porsche-911')![50] < times.get('urus')![50]);
});

test('every car reaches the same city and parking speed caps without overshoot', () => {
  for (const p of VEHICLE_DYNAMICS_PROFILES) {
    const forward = measureAcceleration(p.id), reverse = measureAcceleration(p.id, FRAME_PATTERNS.dropped, true);
    close(forward.finalSpeedKmh, 80);
    close(reverse.finalSpeedKmh, -15);
    assert.ok(forward.reachedSeconds[79.5] < 12, p.id);
    assert.ok(reverse.reachedSeconds[14.5] > 1.5 && reverse.reachedSeconds[14.5] < 4, p.id);
  }
});

test('10/20/60 Hz and dropped frames agree at equal elapsed times in forward and reverse', () => {
  for (const p of VEHICLE_DYNAMICS_PROFILES) for (const reverse of [false, true]) {
    const expected = frameTrace(p.id, FRAME_PATTERNS.hz120, reverse);
    for (const [name, pattern] of Object.entries(FRAME_PATTERNS)) {
      const actual = frameTrace(p.id, pattern, reverse);
      assert.equal(actual.length, expected.length);
      for (let i = 0; i < actual.length; i++) {
        close(actual[i].seconds, expected[i].seconds, 1e-8);
        assert.ok(Math.abs(actual[i].speedMps - expected[i].speedMps) < .0005, `${p.id} ${name} reverse=${reverse} t=${actual[i].seconds}: ${actual[i].speedMps} / ${expected[i].speedMps}`);
        close(actual[i].pedal, expected[i].pedal, 1e-10);
      }
    }
  }
});

test('brake and handbrake override held throttle with the original shared deceleration', () => {
  for (const p of VEHICLE_DYNAMICS_PROFILES) for (const reverse of [false, true]) for (const handbrake of [false, true]) {
    const d = new VehicleDynamics(p.id), initial = (reverse ? -15 : 80) / 3.6;
    d.step(0, 1, full, .25);
    const actual = d.step(initial, reverse ? -1 : 1, { ...full, brake: true, handbrake }, .1);
    close(actual, Math.sign(initial) * (Math.abs(initial) - (handbrake ? 9 : 7.5) * .1));
    assert.equal(d.pedal, 0);
    const stop = measureBraking(p.id, reverse, handbrake), deceleration = handbrake ? 9 : 7.5;
    assert.equal(stop.finalSpeedMps, 0);
    close(stop.seconds, Math.abs(initial) / deceleration, 1 / 120 + 1e-9);
    close(stop.distanceMetres, initial ** 2 / (2 * deceleration), .001);
  }
});

test('release removes propulsion immediately and coast/brake cannot cross zero', () => {
  for (const p of VEHICLE_DYNAMICS_PROFILES) {
    const d = new VehicleDynamics(p.id);
    d.step(0, 1, full, .25);
    const coast = d.step(10, 1, { throttle: false, brake: false }, 1 / 120);
    close(coast, 10 - (.23 + .0035 * 100) / 120);
    assert.equal(d.pedal, 0);
    for (const speed of [-.0001, 0, .0001]) for (const brake of [false, true]) {
      assert.equal(d.step(speed, speed < 0 ? -1 : 1, { throttle: false, brake }, .25), 0);
    }
  }
});

test('progressive pedal remains bounded and the MPV builds torque more smoothly', () => {
  const ferrari = new VehicleDynamics('ferrari-488'), alphard = new VehicleDynamics('alphard');
  ferrari.step(0, 1, full, .1); alphard.step(0, 1, full, .1);
  assert.ok(ferrari.pedal > .65);
  assert.ok(alphard.pedal < .25);
  for (const p of VEHICLE_DYNAMICS_PROFILES) {
    const partial = new VehicleDynamics(p.id), maximum = new VehicleDynamics(p.id);
    let partialSpeed = 0, maximumSpeed = 0;
    for (let i = 0; i < 120; i++) {
      partialSpeed = partial.step(partialSpeed, 1, { throttle: .4, brake: false }, 1 / 60);
      maximumSpeed = maximum.step(maximumSpeed, 1, full, 1 / 60);
      assert.ok(partial.pedal >= 0 && partial.pedal <= .4);
    }
    assert.ok(partialSpeed > 0 && partialSpeed < maximumSpeed * .6, p.id);
  }
});

test('reset and vehicle changes do not carry another car throttle response', () => {
  const d = new VehicleDynamics('ferrari-488');
  d.step(0, 1, full, .25); assert.ok(d.pedal > .9);
  d.setVehicle('alphard'); assert.equal(d.pedal, 0); assert.equal(d.profile.id, 'alphard');
  close(d.step(0, 1, full, .1), new VehicleDynamics('alphard').step(0, 1, full, .1));
  d.reset(); assert.equal(d.pedal, 0);
  d.setVehicle('unknown-legacy-id'); assert.equal(d.profile.id, 'su7');
});

test('invalid inputs stay finite and long stalls preserve the existing 250 ms cap', () => {
  for (const p of VEHICLE_DYNAMICS_PROFILES) {
    const a = new VehicleDynamics(p.id), b = new VehicleDynamics(p.id);
    close(a.step(0, 1, full, 2), b.step(0, 1, full, .25));
    close(a.pedal, b.pedal);
    for (const dt of [NaN, Infinity, -1, 0]) close(a.step(5, 1, full, dt), 5);
    for (const speed of [NaN, Infinity, -Infinity]) assert.ok(Number.isFinite(a.step(speed, 1, full, .1)));
    for (const pedal of [NaN, Infinity, -1, 2]) assert.ok(Number.isFinite(a.step(0, 1, { throttle: pedal, brake: false }, .1)));
  }
  assert.equal(VEHICLE_DYNAMICS_LIMITS.maximumIntegrationSeconds, 1 / 120);
});
