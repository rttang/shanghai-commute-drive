import { test } from "node:test";
import assert from "node:assert/strict";
import { renderBudget, renderPixelRatio } from "../src/tour/render-budget";

test("Retina and large displays cannot silently exceed the render pixel budget", () => {
  for (const quality of ["balanced", "high", "invalid"]) {
    for (const [width, height, density] of [[592, 814, 2], [1280, 720, 2], [2560, 1440, 2], [3840, 2160, 3]]) {
      const ratio = renderPixelRatio(width, height, density, quality);
      assert.ok(width * height * ratio ** 2 <= renderBudget(quality).pixels + 1);
      assert.ok(ratio <= density && ratio <= renderBudget(quality).pixelRatio);
    }
  }
  assert.equal(renderPixelRatio(1280, 720, 2, "balanced"), 1);
  assert.equal(renderPixelRatio(592, 814, 1, "high"), 1);
});
