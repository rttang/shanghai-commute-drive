import test from "node:test";
import assert from "node:assert/strict";
import {
  PausePolicy,
  type PauseEvent,
  pauseHint,
  pauseLabel,
} from "../src/core/pause-policy";
import { Controls } from "../src/core/input";

const journey = (mode: "auto" | "manual" = "auto") => {
  const policy = new PausePolicy();
  const state: {
    phase: "running" | "paused" | "complete";
    mode: "auto" | "manual";
  } = { phase: "running", mode };
  return {
    policy,
    state,
    event(event: PauseEvent) {
      const change = policy.handle(event, state);
      if (change === "pause") state.phase = "paused";
      if (change === "resume") state.phase = "running";
      return change;
    },
  };
};

test("visible automatic sightseeing survives repeated window blur without an accidental pause", () => {
  const j = journey();
  j.event("blur");
  j.event("blur");
  assert.equal(j.state.phase, "running");
  assert.equal(j.policy.reason, null);
  j.event("focus");
  assert.equal(j.state.phase, "running");
});

test("manual loss of focus requires an explicit continue even after returning to the window", () => {
  const j = journey("manual");
  j.event("blur");
  assert.equal(j.state.phase, "paused");
  assert.equal(j.policy.reason, "blur");
  j.event("pause");
  assert.equal(
    j.state.phase,
    "paused",
    "cannot resume while the driving window remains unfocused",
  );
  j.event("focus");
  assert.equal(j.state.phase, "paused");
  j.event("pause");
  assert.equal(j.state.phase, "running");
  assert.equal(j.policy.reason, null);
});

test("both modes pause when backgrounded and visibility alone never resumes them", () => {
  for (const mode of ["auto", "manual"] as const) {
    const j = journey(mode);
    j.event("blur");
    j.event("hidden");
    assert.equal(j.state.phase, "paused");
    assert.equal(j.policy.reason, "background");
    j.event("pause");
    assert.equal(j.state.phase, "paused");
    j.event("visible");
    j.event("focus");
    assert.equal(j.state.phase, "paused");
    j.event("pause");
    assert.equal(j.state.phase, "running");
  }
});

test("a user-owned pause survives dialogs, repeated blur, backgrounding and return", () => {
  const j = journey("manual");
  j.event("pause");
  for (const event of [
    "dialog-opened",
    "dialog-opened",
    "blur",
    "hidden",
    "dialog-closed",
    "visible",
    "focus",
  ] as const) {
    j.event(event);
    assert.equal(j.state.phase, "paused", event);
    assert.equal(j.policy.reason, "user", event);
  }
  j.event("pause");
  assert.equal(j.state.phase, "running");
});

test("replacing dialog content retains temporary pause ownership and closes back to running", () => {
  const j = journey();
  j.event("dialog-opened");
  j.event("dialog-opened");
  assert.equal(j.policy.reason, "dialog");
  j.event("blur");
  j.event("dialog-closed");
  assert.equal(j.state.phase, "running");
  assert.equal(j.policy.reason, null);
  j.event("dialog-closed");
  assert.equal(
    j.state.phase,
    "running",
    "a duplicate close must not toggle pause",
  );
});

test("backgrounding a dialog cancels its automatic resume, in either event order", () => {
  for (const events of [
    ["dialog-opened", "hidden", "blur", "dialog-closed"],
    ["dialog-opened", "blur", "hidden", "visible", "focus", "dialog-closed"],
    ["hidden", "dialog-opened", "dialog-closed"],
  ] as PauseEvent[][]) {
    const j = journey();
    events.forEach((event) => j.event(event));
    assert.equal(j.state.phase, "paused");
    assert.equal(j.policy.reason, "background");
  }
});

test("manual focus loss during a dialog still requires explicit continue after closing", () => {
  const j = journey("manual");
  j.event("dialog-opened");
  j.event("blur");
  j.event("focus");
  j.event("dialog-closed");
  assert.equal(j.policy.reason, "blur");
  assert.equal(j.state.phase, "paused");
  j.event("pause");
  assert.equal(j.state.phase, "running");
});

test("reset and completed journeys do not retain or resume an earlier pause", () => {
  const j = journey();
  j.event("dialog-opened");
  j.policy.reset();
  j.state.phase = "running";
  j.event("dialog-closed");
  assert.equal(j.state.phase, "running");
  assert.equal(j.policy.reason, null);
  j.state.phase = "complete";
  j.event("hidden");
  j.event("dialog-opened");
  j.event("dialog-closed");
  j.event("pause");
  assert.equal(j.state.phase, "complete");
  assert.equal(j.policy.reason, null);
});

test("pause feedback distinguishes all causes and gives a clear continuation instruction", () => {
  const reasons = ["user", "background", "blur", "dialog"] as const;
  assert.equal(new Set(reasons.map(pauseLabel)).size, 4);
  for (const reason of reasons) assert.match(pauseHint(reason), /继续/);
});

test("controls distinguish focus from visibility changes and release held touch input on both stops", () => {
  const targetWindow = new EventTarget();
  const targetDocument = Object.assign(new EventTarget(), { hidden: false });
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
    const press = () => {
      const event = new Event("pointerdown", { cancelable: true });
      Object.defineProperties(event, {
        pointerId: { value: 1 },
        target: {
          value: {
            closest: () => ({
              dataset: { control: "gas" },
              setPointerCapture() {},
            }),
          },
        },
      });
      targetDocument.dispatchEvent(event);
      assert.equal(controls.state.throttle, true);
    };
    press();
    targetWindow.dispatchEvent(new Event("blur"));
    assert.equal(controls.state.throttle, false);
    targetWindow.dispatchEvent(new Event("focus"));
    press();
    targetDocument.hidden = true;
    targetDocument.dispatchEvent(new Event("visibilitychange"));
    assert.equal(controls.state.throttle, false);
    targetDocument.hidden = false;
    targetDocument.dispatchEvent(new Event("visibilitychange"));
    assert.deepEqual(actions, ["blur", "window-focus", "hidden", "visible"]);
  } finally {
    for (const key of ["window", "document"] as const) {
      if (saved[key]) Object.defineProperty(globalThis, key, saved[key]);
      else Reflect.deleteProperty(globalThis, key);
    }
  }
});
