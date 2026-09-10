export type PauseReason = "user" | "background" | "blur" | "dialog" | null;
export type PauseEvent =
  | "pause"
  | "blur"
  | "focus"
  | "hidden"
  | "visible"
  | "dialog-opened"
  | "dialog-closed";
type Journey = {
  phase: "ready" | "running" | "paused" | "complete";
  mode: "auto" | "manual";
};

export const pauseLabel = (reason: PauseReason) =>
  ({
    user: "已主动暂停",
    background: "切到后台 · 已暂停",
    blur: "窗口失焦 · 已暂停",
    dialog: "查看详情 · 已暂停",
  })[reason || "user"];

export const pauseHint = (reason: PauseReason) =>
  ({
    user: "点击继续或按 P 继续行程",
    background: "离开页面时已暂停，点击继续后再出发",
    blur: "驾驶窗口失去焦点，按键已松开；点击继续后再驾驶",
    dialog: "关闭详情后继续行程",
  })[reason || "user"];

/** Tracks who owns a pause. Only a dialog-owned pause resumes on close. */
export class PausePolicy {
  reason: PauseReason = null;
  private hidden = false;
  private focused = true;
  private dialog = false;

  reset(hidden = false, focused = true) {
    this.reason = null;
    this.hidden = hidden;
    this.focused = focused;
    this.dialog = false;
  }

  handle(event: PauseEvent, journey: Journey): "pause" | "resume" | null {
    if (event === "focus") this.focused = true;
    if (event === "visible") this.hidden = false;
    if (event === "blur") this.focused = false;
    if (event === "hidden") this.hidden = true;
    if (event === "dialog-opened") this.dialog = true;
    if (event === "dialog-closed") this.dialog = false;

    if (journey.phase !== "running" && journey.phase !== "paused") {
      this.reason = null;
      return null;
    }

    if (event === "pause") {
      if (journey.phase === "running") {
        this.reason = "user";
        return "pause";
      }
      if (
        this.hidden ||
        this.dialog ||
        (journey.mode === "manual" && !this.focused)
      )
        return null;
      this.reason = null;
      return "resume";
    }

    // Backgrounding supersedes a temporary dialog pause, never a user's pause.
    if (event === "hidden" || (event === "blur" && journey.mode === "manual")) {
      if (this.reason !== "user" && this.reason !== "background")
        this.reason = event === "hidden" ? "background" : "blur";
      return journey.phase === "running" ? "pause" : null;
    }
    if (event === "dialog-opened" && journey.phase === "running") {
      this.reason = "dialog";
      return "pause";
    }
    if (
      event === "dialog-closed" &&
      journey.phase === "paused" &&
      this.reason === "dialog"
    ) {
      if (this.hidden || (journey.mode === "manual" && !this.focused)) {
        this.reason = this.hidden ? "background" : "blur";
        return null;
      }
      this.reason = null;
      return "resume";
    }
    return null;
  }
}
