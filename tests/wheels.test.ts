import { test } from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import { WheelRig } from "../src/tour/wheels";
function fixture() {
  const model = new THREE.Group();
  const body = new THREE.Mesh(new THREE.BoxGeometry(1.8, 1.2, 4));
  model.add(body);
  for (const name of ["FL", "FR", "RL", "RR"]) {
    const pivot = new THREE.Group();
    pivot.name = `Wheel_${name}`;
    pivot.position.set(
      name.endsWith("L") ? -0.8 : 0.8,
      0.35,
      name.startsWith("F") ? -1.5 : 1.5,
    );
    pivot.userData = {
      wheelPosition: name,
      wheelRadius: 0.35,
      frontWheel: name.startsWith("F"),
    };
    const roll = new THREE.Group();
    roll.name = `WheelRoll_${name}`;
    pivot.add(roll);
    model.add(pivot);
  }
  return { model, body, rig: new WheelRig(model) };
}
test("one tire circumference rolls one revolution without moving the body or hubs", () => {
  const { rig, model, body } = fixture();
  model.position.set(45, 0.15, -90);
  model.rotation.y = 0.7;
  rig.update(0, 0, 3);
  const hubs = rig.snapshot.map((w) => w.position);
  rig.update(2 * Math.PI * 0.35, 0, 3);
  for (const wheel of rig.snapshot)
    assert.ok(Math.abs(wheel.roll + 2 * Math.PI) < 1e-10);
  assert.deepEqual(
    rig.snapshot.map((w) => w.position),
    hubs,
  );
  assert.equal(body.rotation.x, 0);
  assert.equal(body.rotation.y, 0);
});
test("stationary steering changes front angles only; inner wheel turns farther", () => {
  const { rig } = fixture();
  rig.update(0, 0, 3);
  rig.update(0, 0.4, 3);
  const wheels = Object.fromEntries(rig.snapshot.map((w) => [w.name, w]));
  assert.ok(wheels.FR.steer < wheels.FL.steer && wheels.FL.steer < 0);
  assert.equal(wheels.RL.steer, 0);
  assert.equal(wheels.RR.steer, 0);
  assert.ok(rig.snapshot.every((w) => w.roll === 0));
  rig.update(2, 0.4, 3);
  const turning = Object.fromEntries(rig.snapshot.map((w) => [w.name, w]));
  assert.ok(Math.abs(turning.FL.roll) > Math.abs(turning.FR.roll));
  const stopped = rig.snapshot;
  rig.update(2, 0.4, 3);
  assert.deepEqual(rig.snapshot, stopped);
});
test("new car and route reset do not spin through a stale odometer jump", () => {
  const { rig } = fixture();
  rig.update(2000, 0, 3);
  assert.ok(rig.snapshot.every((w) => w.roll === 0));
  rig.update(2001, 0, 3);
  assert.ok(rig.snapshot.every((w) => w.roll < -2));
  rig.reset(0);
  rig.update(0, 0, 3);
  assert.ok(rig.snapshot.every((w) => w.roll === 0));
  assert.throws(() => new WheelRig(new THREE.Group()), /四轮/);
});
test("reverse movement turns the physical tire in the opposite direction through a zero odometer",()=>{
  const {rig,model}=fixture();
  const marker=new THREE.Mesh(new THREE.BoxGeometry(.03,.03,.03));
  marker.position.set(0,.35,0);model.getObjectByName('WheelRoll_FL')!.add(marker);
  rig.update(.3,0,3);model.updateMatrixWorld(true);
  const before=marker.getWorldPosition(new THREE.Vector3());
  rig.update(-.2,0,3);model.updateMatrixWorld(true);
  const reverse=marker.getWorldPosition(new THREE.Vector3());
  assert.ok(reverse.distanceTo(before)>.3,'The tire mesh must actually move while reversing');
  for(const wheel of rig.snapshot)assert.ok(Math.abs(wheel.roll-.5/.35)<1e-10);
  rig.update(.3,0,3);model.updateMatrixWorld(true);
  assert.ok(marker.getWorldPosition(new THREE.Vector3()).distanceTo(before)<1e-10);
  assert.ok(rig.snapshot.every(w=>Math.abs(w.roll)<1e-10));
});
