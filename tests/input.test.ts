import test from "node:test";
import assert from "node:assert/strict";
import { Controls } from "../src/core/input";

test("touch release is tracked by pointer identity, including cancellation outside a button", () => {
  const targetWindow = new EventTarget();
  const targetDocument = new EventTarget();
  const saved = Object.getOwnPropertyDescriptors(globalThis);
  Object.defineProperty(globalThis, "window", {
    value: targetWindow,
    configurable: true,
  });
  Object.defineProperty(globalThis, "document", {
    value: targetDocument,
    configurable: true,
  });
  try {
    const actions: string[] = [];
    const controls = new Controls((action) => actions.push(action));
    const pointer = (type: string, id: number, control?: string) => {
      const event = new Event(type, { cancelable: true });
      Object.defineProperties(event, {
        pointerId: { value: id },
        target: {
          value: {
            closest: () =>
              control ? { dataset: { control }, setPointerCapture() {} } : null,
          },
        },
      });
      targetDocument.dispatchEvent(event);
    };
    pointer("pointerdown", 1, "right");
    assert.equal(controls.state.steer, 1);
    pointer("pointerup", 1);
    assert.equal(controls.state.steer, 0);
    pointer("pointerdown", 2, "gas");
    pointer("pointerdown", 3, "gas");
    pointer("pointercancel", 2);
    assert.equal(controls.state.throttle, true);
    pointer("lostpointercapture", 3);
    assert.equal(controls.state.throttle, false);
    pointer("pointerdown", 4, "brake");
    targetWindow.dispatchEvent(new Event("blur"));
    assert.equal(controls.state.brake, false);
    assert.deepEqual(actions, ["blur"]);
  } finally {
    for (const key of ["window", "document"] as const) {
      if (saved[key]) Object.defineProperty(globalThis, key, saved[key]);
      else Reflect.deleteProperty(globalThis, key);
    }
  }
});
