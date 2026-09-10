import type { Input } from "../tour/drive";
export class Controls {
  private keys = new Set<string>();
  private touch = new Map<number, string>();
  constructor(public onAction: (action: string) => void) {
    window.addEventListener("keydown", (e) => {
      if ((e.target as HTMLElement).closest?.("dialog[open]")) return;
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLSelectElement
      )
        return;
      if (
        ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space"].includes(
          e.code,
        )
      )
        e.preventDefault();
      this.keys.add(e.code);
      if (!e.repeat) {
        const action: Record<string, string> = {
          Escape: "pause",
          KeyP: "pause",
          KeyC: "camera",
          KeyR: "recover",
          KeyQ: "gear",
          KeyF: "capture",
          KeyJ: "album",
          KeyH: "horn",
        };
        if (action[e.code]) this.onAction(action[e.code]);
      }
    });
    window.addEventListener("keyup", (e) => this.keys.delete(e.code));
    window.addEventListener("blur", () => {
      this.clear();
      this.onAction("blur");
    });
    window.addEventListener("focus", () => this.onAction("window-focus"));
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        this.clear();
      }
      this.onAction(document.hidden ? "hidden" : "visible");
    });
    document.addEventListener("pointerdown", (e) => {
      const target = (e.target as HTMLElement).closest<HTMLElement>(
        "[data-control]",
      );
      if (!target) return;
      e.preventDefault();
      target.setPointerCapture(e.pointerId);
      this.touch.set(e.pointerId, target.dataset.control!);
    });
    const release = (e: PointerEvent) => {
      this.touch.delete(e.pointerId);
    };
    document.addEventListener("pointerup", release);
    document.addEventListener("pointercancel", release);
    document.addEventListener("lostpointercapture", release);
  }
  clear() {
    this.keys.clear();
    this.touch.clear();
  }
  get state(): Input {
    const pressed = new Set(this.touch.values());
    const has = (...keys: string[]) =>
      keys.some((k) => this.keys.has(k) || pressed.has(k));
    return {
      throttle: has("KeyW", "ArrowUp", "gas"),
      brake: has("KeyS", "ArrowDown", "brake"),
      steer:
        Number(has("KeyD", "ArrowRight", "right")) -
        Number(has("KeyA", "ArrowLeft", "left")),
      handbrake: has("Space"),
    };
  }
}
