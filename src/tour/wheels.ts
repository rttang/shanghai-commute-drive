import * as THREE from "three";

type Wheel = {
  name: string;
  front: boolean;
  radius: number;
  pivot: THREE.Object3D;
  roll: THREE.Object3D;
  angle: number;
};

/** Animate the preserved tire/rim geometry around its measured axle. */
export class WheelRig {
  readonly wheels: Wheel[] = [];
  private previousTravel?: number;
  constructor(readonly model: THREE.Object3D) {
    model.traverse((pivot) => {
      const name = pivot.userData.wheelPosition;
      if (typeof name !== "string" || !/^[FR][LR]$/.test(name)) return;
      const roll = pivot.getObjectByName(`WheelRoll_${name}`);
      const radius = Number(pivot.userData.wheelRadius);
      if (!roll || !Number.isFinite(radius) || radius <= 0) return;
      this.wheels.push({
        name,
        front: Boolean(pivot.userData.frontWheel),
        radius,
        pivot,
        roll,
        angle: 0,
      });
    });
    if (this.wheels.length !== 4)
      throw new Error(`车辆缺少独立的四轮结构：${model.name || "未命名模型"}`);
    this.wheels.sort((a, b) => a.name.localeCompare(b.name));
  }

  reset(travelled=0) {
    this.previousTravel=travelled;
    for(const wheel of this.wheels){wheel.angle=0;wheel.roll.rotation.x=0;}
  }

  update(travelled: number, steering: number, wheelbase: number) {
    const delta =
      this.previousTravel === undefined
        ? 0
        : travelled - this.previousTravel;
    this.previousTravel = travelled;
    const turning = Math.abs(steering) > 0.00001;
    const turnRadius = turning
      ? wheelbase / Math.tan(Math.abs(steering))
      : Infinity;
    const centerRadius = Math.hypot(turnRadius, wheelbase / 2);
    for (const wheel of this.wheels) {
      // Ackermann steering: the wheel on the inside of a turn has a tighter angle.
      const radius = turnRadius - Math.sign(steering) * wheel.pivot.position.x;
      wheel.pivot.rotation.y =
        wheel.front && turning
          ? -Math.sign(steering) * Math.atan2(wheelbase, radius)
          : 0;
      const ratio = turning
        ? Math.hypot(radius, wheel.front ? wheelbase : 0) / centerRadius
        : 1;
      wheel.angle -= (delta * ratio) / wheel.radius;
      wheel.roll.rotation.x = wheel.angle;
    }
  }

  get snapshot() {
    this.model.updateWorldMatrix(true, true);
    return this.wheels.map((w) => {
      const position = w.pivot.getWorldPosition(new THREE.Vector3());
      return {
        name: w.name,
        front: w.front,
        radius: w.radius,
        roll: w.angle,
        steer: w.pivot.rotation.y,
        position: { x: position.x, y: position.y, z: position.z },
      };
    });
  }
}
