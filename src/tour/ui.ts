import type { Journey } from "./journey";
import type { Missions, MissionResult } from "./missions";
import vehicleAssets from "./vehicle-assets.json";
import { garageDynamics } from "./vehicle-garage";
const detailedAssets: Record<
  string,
  { preview: string; displayModel: string }
> = vehicleAssets;
const preview = (c: Car) =>
  detailedAssets[c.id]?.preview || "/cars/" + c.id + ".png";
const displayModel = (c: Car) =>
  detailedAssets[c.id]?.displayModel || c.model.replace(c.name, "").trim();
const carCategory = (c: Car) => (c as Car & { category?: string }).category || '城市座驾';
const distanceLabel = (distance: number) => distance < 1000 ? `${Math.ceil(distance)} 米` : `${(distance / 1000).toFixed(1)} km`;
const clockLabel = (seconds: number) => `${Math.floor(Math.max(0, Math.ceil(seconds)) / 60)}:${String(Math.max(0, Math.ceil(seconds)) % 60).padStart(2, '0')}`;
import {
  CARS,
  LANDMARKS,
  project,
  type Car,
  type City,
  type Point,
} from "./data";
import type { Drive } from "./drive";
import { pauseHint, pauseLabel, type PauseReason } from "../core/pause-policy";
export const icon = (name: string) => {
  const p: Record<string, string> = {
    play: "M8 5l11 7-11 7Z",
    pause: "M8 5v14M16 5v14",
    arrow: "M5 12h14m-6-6 6 6-6 6",
    close: "m6 6 12 12M6 18 18 6",
    camera: "M4 7h4l2-3h4l2 3h4v13H4ZM16 13a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
    wheel: "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM3 10h18M12 10v11",
    map: "m3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2Zm6-2v16m6-14v16",
    car: "m4 10 2-6h12l2 6M3 10h18v9H3Zm2 9v2m14-2v2M6 14h2m8 0h2",
    back: "m14 5-7 7 7 7",
    reset: "M4 10a8 8 0 1 1 2 8M4 4v6h6",
    sound: "M3 9h4l5-4v14l-5-4H3Zm13-1a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14",
    info: "M12 11v6m0-10v1M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
    eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7Zm13 0a3 3 0 1 1-6 0 3 3 0 0 1 6 0",
  };
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"> <path d="${p[name] || p.arrow}"/></svg>`;
};
export class UI {
  selected = 0;
  car: Car = CARS[0];
  private app = document.getElementById("app")!;
  private previousFocus?: HTMLElement;
  private pendingDialogClose = false;
  private lastNearest = "";
  private toastTimer?: ReturnType<typeof setTimeout>;
  private dialog = document.createElement("dialog");
  private mini: HTMLCanvasElement;
  constructor(
    readonly city: City,
    readonly act: (action: string, value?: string) => void,
  ) {
    this.app.innerHTML = `<div class="loading" role="status"><span class="brand-mark">沪</span><p>正在打开上海</p><span id="loading-text">准备江岸、街道与车辆</span><div class="loading-line"></div></div>
 <header class="topbar"><a class="wordmark" href="/" aria-label="上海漫游首页"><span class="brand-mark">沪</span><span>上海漫游<small>SHANGHAI, AT YOUR PACE</small></span></a><div class="top-actions"><button class="weather" data-action="lighting" aria-label="切换日景、暮色与夜景">日景 · 切换光线</button><button class="icon-button" data-action="sound" aria-label="切换驾驶声音">${icon("sound")}</button><button class="icon-button" data-action="sources" aria-label="地图与车型参考">${icon("info")}</button><button class="icon-button" data-action="photo" aria-label="隐藏界面欣赏风景">${icon("eye")}</button></div></header>
 <main class="home"><div class="intro"><h1>开一圈，<br>爱上上海。</h1><p>沿外滩驶过百年建筑，穿江走进陆家嘴。<br>在北外滩回望，接一份委托，留一张风景。</p></div><section class="departure" aria-label="上海环游路线"><div class="section-label">一江两岸，环游上海</div><div class="routes">${city.routes.map((r, i) => `<button class="route-card ${i === 0 ? "selected" : ""}" data-action="route" data-value="${i}" aria-pressed="${i === 0}"><span><strong>${r.name}</strong><small>${r.subtitle}</small></span><span class="route-length">${(r.length / 1000).toFixed(2)} km</span></button>`).join("")}</div><div class="departure-actions"><button class="primary" data-action="manual" disabled>出发，探索上海 ${icon("arrow")}</button><button class="text-button" data-action="auto" disabled>${icon("play")} 自动观光</button></div><button class="text-button mission-entry" data-action="missions" disabled>城市委托 · 接送与送达 ${icon("arrow")}</button><p class="departure-note">12 处风景等你收藏 · 环游约 <span id="duration">4</span> 分钟</p></section><button class="chosen-car" data-action="garage"><div class="car-portrait"><img id="chosen-image" src="${preview(this.car)}" alt="${this.car.name}三维模型"></div><span class="car-label">本次座驾 <span>更换 ${icon("arrow")}</span></span><strong id="chosen-name">${this.car.name}</strong><small id="chosen-trim">${displayModel(this.car)}</small></button></main>
 <div class="journey" hidden><div class="journey-top"><button class="glass-button" data-action="home">${icon("back")} 返回首页</button><button class="glass-button" data-action="missions">城市委托</button><span id="journey-name">浦西滨江线</span></div><aside class="tour-objective"><div><span id="collection-progress">上海相册 0 / 12</span><button data-action="album">查看相册 ${icon("arrow")}</button></div><strong id="next-stop">寻找沿途风景</strong><p id="stop-instruction">沿路线发现上海，驶入观景位后按 F 拍照。</p><div class="objective-footer"><span>安全分 <b id="driving-score">1000</b></span><button data-action="capture" id="capture-button" disabled>${icon("camera")} 拍照收藏</button></div></aside><aside class="mission-objective" aria-label="当前城市委托" hidden></aside><aside class="mini-wrap"><canvas id="minimap" width="420" height="340" aria-label="真实道路与当前观光路线"></canvas><div><span id="map-position">中山东一路</span><span>N ↑</span></div></aside><button class="landmark-note" data-action="landmark"><span>此刻，看看这里</span><strong id="landmark-name">外滩建筑群 ${icon("arrow")}</strong></button><div class="drive-dock"><div class="drive-progress"><span id="journey-state">自动观光</span><span id="remaining">1.75 km</span><div class="progress-track"><i id="progress-fill"></i></div></div><div class="drive-controls"><button data-action="pause" class="icon-button" aria-label="暂停观光" id="pause-button">${icon("pause")}</button><div class="speed"><strong id="speed">0</strong><span>km/h <b id="gear-label">D</b></span></div><span class="dock-divider"></span><button class="dock-button" data-action="mode" id="mode-button">${icon("wheel")}<span>接管驾驶</span></button><button class="dock-button" data-action="camera" id="camera-button">${icon("camera")}<span>跟车视角</span></button><button class="dock-button" data-action="rate" id="rate-button"><b>1×</b><span>巡游速度</span></button><button class="icon-button" data-action="garage" aria-label="更换座驾">${icon("car")}</button><button class="dock-button" data-action="gear" id="gear-button">D / R<span>换挡</span></button><button class="icon-button" data-action="recover" aria-label="回到附近车道">${icon("reset")}</button><button class="icon-button" data-action="restart" aria-label="重新开始路线">${icon("reset")}</button></div></div><p class="keyboard-hint" id="keyboard-hint">拖动画面环顾 · C 切换视角 · P 暂停</p><div class="touch-controls" hidden><div><button data-control="left" aria-label="向左转向">←</button><button data-control="right" aria-label="向右转向">→</button></div><div><button data-action="gear" aria-label="切换前进与倒挡">D / R</button><button data-control="brake" aria-label="刹车">刹车</button><button data-control="gas" aria-label="加速">加速</button></div></div></div>
 <footer class="credits"><span>© OpenStreetMap contributors</span><button data-action="sources">地图与车型参考</button></footer><button class="restore-ui glass-button" data-action="photo" hidden>${icon("eye")} 显示界面</button><div class="toast" role="status" hidden></div>`;
    this.dialog.className = "panel";
    document.body.append(this.dialog);
    this.mini = document.querySelector("#minimap")!;
    document.getElementById("journey-state")!.setAttribute("role", "status");
    document.addEventListener("click", (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>("[data-action]");
      if (b && !b.hasAttribute("disabled")) {
        if (b.dataset.action === "close") this.close();
        else this.act(b.dataset.action!, b.dataset.value);
      }
    });
    this.dialog.addEventListener("click", (e) => {
      if (e.target === this.dialog) {
        const r = this.dialog.getBoundingClientRect();
        if (
          e.clientX < r.left ||
          e.clientX > r.right ||
          e.clientY < r.top ||
          e.clientY > r.bottom
        )
          this.close();
      }
    });
    this.dialog.addEventListener("close", () => {
      if (this.dialog.open) return;
      for (const url of this.photoURLs) URL.revokeObjectURL(url);
      this.photoURLs = [];
      this.dialog.replaceChildren();
      if (!document.hidden && document.hasFocus())
        this.previousFocus?.focus({ preventScroll: true });
      this.act("dialog-closed");
    });
    const finishDeferredClose = () => {
      if (this.pendingDialogClose && !document.hidden && document.hasFocus())
        this.close();
    };
    document.addEventListener("visibilitychange", finishDeferredClose);
    window.addEventListener("focus", finishDeferredClose);
  }
  loading(text: string) {
    const el = document.getElementById("loading-text");
    if (el) el.textContent = text;
  }
  preparing(text: string) {
    if (!document.querySelector(".loading")) {
      const overlay = document.createElement("div");
      overlay.className = "loading";
      overlay.setAttribute("role", "status");
      overlay.innerHTML = '<span class="brand-mark">沪</span><p>即将出发</p><span id="loading-text"></span><div class="loading-line"></div>';
      this.app.append(overlay);
    }
    this.loading(text);
  }
  loadFailed() {
    const overlay = document.querySelector(".loading");
    if (overlay) overlay.innerHTML = '<p>沿途景色暂时未能加载</p><span>检查网络后可以继续，已下载的资源会尽量复用。</span><button class="primary" data-action="retry-load">重试加载</button><button class="text-button" data-action="home">返回首页</button>';
  }
  ready() {
    document.querySelector(".loading")?.remove();
    document
      .querySelectorAll("button[disabled][data-action='manual'], button[disabled][data-action='auto'], button[disabled][data-action='missions']")
      .forEach((b) => b.removeAttribute("disabled"));
    document.body.classList.add("ready");
  }
  error(e: string) {
    const loading = document.querySelector(".loading");
    if (loading)
      loading.innerHTML = `<p>上海暂时没有打开</p><span>${e.replace(/[<&]/g, "")}</span><button class="primary" data-action="reload">重新加载</button>`;
  }
  select(index: number) {
    this.selected = index;
    document.querySelectorAll<HTMLElement>(".route-card").forEach((e, i) => {
      e.classList.toggle("selected", index === i);
      e.setAttribute("aria-pressed", String(index === i));
    });
    document.getElementById("duration")!.textContent = String(
      Math.ceil(
        this.city.routes[index].length /
          (this.city.routes[index].speed / 3.6) /
          60,
      ),
    );
  }
  setCar(c: Car) {
    this.car = c;
    const img = document.getElementById("chosen-image") as HTMLImageElement;
    img.src = preview(c);
    img.alt = c.name + "三维模型";
    document.getElementById("chosen-name")!.textContent = c.name;
    document.getElementById("chosen-trim")!.textContent = displayModel(c);
  }
  home(show: boolean) {
    document.querySelector<HTMLElement>(".home")!.hidden = !show;
    document.querySelector<HTMLElement>(".journey")!.hidden = show;
    document.body.classList.toggle("driving", !show);
  }
  private open(title: string, body: string, wide = false) {
    this.pendingDialogClose = false;
    if (!this.dialog.open)
      this.previousFocus = document.activeElement as HTMLElement;
    this.dialog.innerHTML = `<div class="panel-heading"><div><span class="eyebrow" data-dialog-state>上海漫游</span><h2>${title}</h2></div><button class="icon-button" data-action="close" aria-label="关闭">${icon("close")}</button></div>${body}`;
    this.dialog.classList.toggle("wide", wide);
    if (!this.dialog.open) this.dialog.showModal();
    this.act("dialog-opened");
  }
  close() {
    // Native dialog.close() can restore its own saved focus before the close
    // listener runs. Do not let background asset loading activate this tab.
    if (this.dialog.open && (document.hidden || !document.hasFocus())) {
      this.pendingDialogClose = true;
      return;
    }
    this.pendingDialogClose = false;
    this.dialog.close();
  }
  garage() {
    this.open(
      "选一辆喜欢的车",
      `<p class="panel-intro">选一辆座驾，去街头接单或沿江慢慢逛。</p><div class="garage-grid">${CARS.map((c) => {
        const dynamics=garageDynamics(c.id);
        return `<button class="garage-car ${c.id === this.car.id ? "selected" : ""}" data-action="car" data-value="${c.id}" aria-pressed="${c.id === this.car.id}"><span class="car-category">${carCategory(c)}</span><img src="${preview(c)}" alt="${c.name}三维模型"><strong>${c.name}</strong><small>${displayModel(c)}</small><span class="car-dimensions">${c.dimensions.join(" × ")} mm</span><span class="car-dynamics"><span class="car-acceleration">${dynamics.acceleration}</span><span class="car-character">${dynamics.character}</span></span></button>`;
      }).join("")}</div><p class="panel-foot garage-measurement">游戏调校，计时至 79.5 km/h；前进限速 80 km/h。<br>车辆尺寸和驾驶反馈各有不同，选择适合自己的座驾。部分车型使用简化外观。</p>`,
      true,
    );
  }
  sources() {
    this.open(
      "地图与车型参考",
      `<div class="reading"><p>环游路线沿公开地图中的上海道路生成，建筑位置与轮廓来自 OpenStreetMap。地标按公开外观资料重建；普通建筑的立面、部分高度与街道设施经过简化。隧道采用连续的游戏坡度。观景车位和信号灯周期为游戏设计，不提供现实道路导航或停车指引。</p><p><a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap contributors · ODbL</a></p><h3>车型与外观参考</h3><p>座驾包含日常城市用车与个性车型，外观版本见车库。以下为车型资料来源。</p><div class="source-cars">${CARS.map((c) => `<a href="${c.source}" target="_blank" rel="noreferrer"><span>${c.name}</span><span>${carCategory(c)} ↗</span></a>`).join("")}</div><h3>车辆模型</h3><p>${Object.entries(
        vehicleAssets,
      )
        .filter(([id]) => CARS.some(c => c.id === id))
        .map(
          ([id, a]) =>
            `<a href="${a.source}" target="_blank" rel="noreferrer">${CARS.find((c) => c.id === id)?.name} · ${a.author} · ${a.license}</a>`,
        )
        .join(
          "；",
        )}。各模型来源及许可分别列于上方，已调整比例、外观材质与独立车轮。展示年份与版本见车库。部分车型使用简化外观。</p><h3>材质与景色</h3><p>道路表面与自然天空使用 Poly Haven 的 CC0 材质：<a href="https://polyhaven.com/a/asphalt_02" target="_blank" rel="noreferrer">Asphalt 02</a>、<a href="https://polyhaven.com/a/kloppenheim_05_puresky" target="_blank" rel="noreferrer">Kloppenheim 05 Pure Sky</a>。上海地标参考上海市政府与上海文旅公开资料。</p><label class="quality-label">画面精细度 <select id="quality" aria-label="画面精细度"><option value="balanced">流畅（推荐）</option><option value="high">精细（更耗性能）</option></select></label></div>`,
    );
    const select = this.dialog.querySelector("select")!;
    select.value = document.body.dataset.quality || "balanced";
    select.addEventListener("change", () => this.act("quality", select.value));
  }
  landmark(id: string) {
    const l = LANDMARKS.find((l) => l.id === id)!;
    this.open(
      l.name,
      `<div class="reading"><p>${l.about}</p><p class="place-meta">${l.lon.toFixed(5)}° E · ${l.lat.toFixed(5)}° N</p><button class="primary" data-action="focus" data-value="${l.id}">${icon("eye")} 看看这座建筑</button></div>`,
    );
  }
  completed() {
    this.open(
      "这段上海，慢慢看完了",
      `<div class="reading"><p>江岸还在，下一段景色也在等你。</p><div class="end-actions"><button class="primary" data-action="next">看看另一条路线 ${icon("arrow")}</button><button class="text-button" data-action="restart">再走一遍</button></div></div>`,
    );
  }
  photo() {
    const active = document.body.classList.toggle("photo-mode");
    document.querySelector<HTMLElement>(".restore-ui")!.hidden = !active;
  }
  toast(text: string) {
    const el = document.querySelector<HTMLElement>(".toast")!;
    el.textContent = text;
    el.hidden = false;
    clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => (el.hidden = true), 3500);
  }
  pauseFeedback(reason: PauseReason) {
    // A safety stop must remain understandable even with the scenery-only UI.
    if (
      (reason === "blur" || reason === "background") &&
      document.body.classList.contains("photo-mode")
    )
      this.photo();
  }
  update(
    d: Drive,
    nearest: string,
    camera: string,
    reason: PauseReason = null,
  ) {
    document.getElementById("journey-name")!.textContent = d.route.name;
    const journeyState =
      d.phase === "paused"
        ? pauseLabel(reason)
        : d.phase === "complete"
          ? "已抵达"
          : d.mode === "auto"
            ? "自动观光"
            : d.routeDeviation > 6
              ? "已偏离观光路线"
              : "手动驾驶";
    const stateLabel = document.getElementById("journey-state")!;
    if (stateLabel.textContent !== journeyState)
      stateLabel.textContent = journeyState;
    document.getElementById("speed")!.textContent = String(
      Math.round(Math.abs(d.speed) * 3.6),
    );
    document.getElementById("remaining")!.textContent =
      `第 ${d.laps+1} 圈 · ${((d.path.total - d.distance) / 1000).toFixed(2)} km`;
    document.getElementById("progress-fill")!.style.width =
      `${(d.distance / d.path.total) * 100}%`;
    const pb = document.getElementById("pause-button")!;
    pb.className = d.phase === "paused" ? "dock-button" : "icon-button";
    pb.innerHTML =
      d.phase === "paused" ? `${icon("play")}<span>继续</span>` : icon("pause");
    pb.setAttribute(
      "aria-label",
      d.phase === "paused" ? "继续行程" : "暂停行程",
    );
    pb.setAttribute(
      "title",
      d.phase === "paused" ? pauseHint(reason) : "暂停行程（P）",
    );
    const dialogState = this.dialog.querySelector<HTMLElement>(
      "[data-dialog-state]",
    );
    if (dialogState)
      dialogState.textContent =
        d.phase === "paused"
          ? reason === "dialog"
            ? "查看详情 · 关闭后继续行程"
            : `${pauseLabel(reason)} · 关闭后点击继续`
          : "上海漫游";
    document.querySelector("#mode-button span")!.textContent =
      d.mode === "auto" ? "接管驾驶" : "自动观光";
    document.querySelector("#camera-button span")!.textContent = (
      {
        follow: "跟车视角",
        vehicle: "赏车视角",
        hood: "前方视角",
        panorama: "俯瞰视角",
      } as Record<string, string>
    )[camera];
    document.querySelector("#rate-button b")!.textContent = d.rate + "×";
    document.querySelector<HTMLElement>("#rate-button")!.hidden =
      d.mode === "manual";
    document.querySelector<HTMLElement>(".touch-controls")!.hidden =
      d.mode !== "manual";
    document.getElementById("keyboard-hint")!.textContent =
      d.phase === "paused"
        ? pauseHint(reason)
        : d.mode === "manual"
          ? d.routeDeviation > 6
            ? "请主动转向返回车道 · S 刹车 · Q 倒挡 · R 脱困"
            : "W 油门 / S 刹车 · A / D 转向 · Q 换挡 · F 拍照 · R 救援"
          : "拖动画面环顾 · C 切换视角 · P 暂停";
    if (this.lastNearest !== nearest) {
      this.lastNearest = nearest;
      document.getElementById("landmark-name")!.innerHTML =
        LANDMARKS.find((l) => l.id === nearest)!.name + icon("arrow");
    }
    document.getElementById("gear-label")!.textContent=d.gear===1?"D":"R";
    document.getElementById("gear-button")!.hidden=d.mode!=="manual";
    this.map(d);
  }
  setLighting(mode: string) {
    document.querySelector('.weather')!.textContent=({day:'日景',dusk:'暮色',night:'夜景'} as Record<string,string>)[mode]+' · 切换光线';
  }
  private tour?: Journey;
  private missionState?: Missions;
  private missionMarkup = '';
  private resultMarkup(result: MissionResult) {
    return `<p class="mission-kicker">${result.success ? '委托完成' : '本次委托已结束'}</p><h3>${result.title}</h3><p>${result.message}</p>${result.success ? `<p class="mission-rating" aria-label="${result.stars} 星评价">${'★'.repeat(result.stars)}${'☆'.repeat(5-result.stars)} <strong>+${result.reward} 积分</strong></p><p class="mission-detail">本次用时 ${clockLabel(result.elapsed)} · 安全扣分事件 ${result.incidents} 次${result.eventBonus ? ` · 顺路停靠奖励 ${result.eventBonus} 积分` : ''}</p>` : '<p class="mission-detail">没有扣除已有积分，可以从接取地点重新开始。</p>'}`;
  }
  missionBoard(missions: Missions, drive: Drive) {
    const current = missions.current, active = missions.active, navigation = missions.navigation(drive), result = missions.save.lastResult;
    this.open('城市委托', `<div class="mission-career"><span>已完成 <strong>${missions.save.completed}</strong> 次</span><span>累计 <strong>${missions.save.credits}</strong> 积分</span></div><p class="panel-intro">接一位旅人，送一份心意。沿上海环线完成接送，在标记停车位停稳两秒即可上下客或交接物件。</p>${current && active && navigation ? `<section class="mission-current"><p class="mission-kicker">正在进行 · ${navigation.objective}</p><h3>${current.title}</h3><p>${current.person} · ${navigation.target.name}</p><p>${active.stage === 'pickup' ? current.timeLimit ? `接到${current.kind === 'tourist' ? '乘客' : '物件'}后开始 ${clockLabel(current.timeLimit)} 倒计时` : '轻松出行 · 不限时' : active.remaining === null ? '轻松出行 · 不限时' : `剩余 ${clockLabel(active.remaining)}`}</p>${navigation.eventOffered ? `<p>${current.event!.request}</p><div class="mission-actions"><button class="primary" data-action="mission-event-accept">答应停靠</button><button class="text-button" data-action="mission-event-skip">直接送达</button></div>` : ''}<div class="mission-actions"><button class="primary" data-action="mission-resume">继续委托 ${icon('arrow')}</button><button class="text-button" data-action="mission-abandon">结束本次委托</button></div></section>` : result ? `<section class="mission-current">${this.resultMarkup(result)}<button class="text-button" data-action="mission-retry">${result.success ? '再接一次' : '重新接取'} ${icon('arrow')}</button></section>` : ''}<div class="mission-list">${missions.catalog.map(mission => {
      const record = missions.save.records[mission.id], currentMission = active?.id === mission.id;
      return `<article class="mission-row"><div><p class="mission-kicker">${mission.kind === 'tourist' ? '游客接送' : '物件送达'} · ${mission.timeLimit ? `限时 ${clockLabel(mission.timeLimit)}` : '不限时'}${mission.event ? ' · 有沿途请求' : ''}</p><h3>${mission.title}</h3><p>${mission.description}</p><p class="mission-route">${mission.pickup.name} ${icon('arrow')} ${mission.destination.name}</p><small>基础奖励 ${mission.reward} 积分${record ? ` · 最佳 ${record.bestStars} 星 · 已完成 ${record.completed} 次` : ''}</small></div><button class="${currentMission ? 'text-button' : 'primary'}" data-action="${currentMission ? 'mission-resume' : 'mission-accept'}" data-value="${mission.id}" ${active && !currentMission ? 'disabled' : ''}>${currentMission ? '继续' : '接取'} ${icon('arrow')}</button></article>`;
    }).join('')}</div><p class="panel-foot">接到乘客或物件后才开始限时。打开面板、暂停或离开页面会停表；自动观光加速时，计时也同步加速。安全完成可获 5 星基础奖励，每次安全扣分或救援降低 1 星；完成沿途请求另有奖励。积分用于记录游玩成绩。委托和积分保存在当前浏览器。</p>${missions.storageAvailable ? '' : '<p class="mission-storage" role="status">浏览器暂时无法保存委托，本次游玩可以继续，刷新可能丢失进度。</p>'}`, true);
  }
  missions(missions: Missions, drive: Drive) {
    this.missionState = missions;
    const panel = document.querySelector<HTMLElement>('.mission-objective')!;
    const navigation = missions.navigation(drive), current = missions.current, result = missions.save.lastResult;
    panel.hidden = !navigation && !result;
    document.body.classList.toggle('mission-visible', !panel.hidden);
    const markup = navigation && current ? `<div class="mission-heading"><span id="mission-stage"></span><button data-action="missions" aria-label="查看当前委托详情">详情 ${icon('arrow')}</button></div><h2>${current.title}</h2><p class="mission-person">${current.person}</p><div class="mission-destination"><strong id="mission-target"></strong><span id="mission-distance"></span></div><p id="mission-instruction"></p><p class="mission-clock" id="mission-clock"></p>${navigation.eventOffered ? `<div class="mission-event"><strong>${current.event!.title}</strong><p>${current.event!.request}</p><div class="mission-actions"><button data-action="mission-event-accept">答应停靠</button><button data-action="mission-event-skip">直接送达</button></div></div>` : ''}<div class="mission-album"><button data-action="album">上海相册 <span id="mission-album-count"></span></button><button id="mission-capture" data-action="capture" disabled>${icon('camera')} 拍照</button></div>` : result ? `<div class="mission-heading"><span>城市委托</span><button data-action="mission-dismiss" aria-label="收起委托结果">${icon('close')}</button></div>${this.resultMarkup(result)}<div class="mission-actions"><button data-action="missions">挑选下一份委托 ${icon('arrow')}</button><button data-action="mission-retry">${result.success ? '再接一次' : '重新接取'}</button></div>` : '';
    if (this.missionMarkup !== markup) { panel.innerHTML = markup; this.missionMarkup = markup; }
    if (navigation && current) {
      document.getElementById('mission-stage')!.textContent = navigation.objective;
      document.getElementById('mission-target')!.textContent = navigation.target.name;
      document.getElementById('mission-distance')!.textContent = `${navigation.nearby ? '距停车点' : '沿环线'} ${distanceLabel(navigation.distance)}`;
      document.getElementById('mission-instruction')!.textContent = navigation.instruction;
      const clock = document.getElementById('mission-clock')!;
      clock.textContent = navigation.stage === 'pickup' ? current.timeLimit ? `接取后计时 · ${clockLabel(current.timeLimit)}` : '不限时 · 慢慢开' : navigation.remaining === null ? '不限时 · 慢慢开' : `${drive.phase !== 'running' ? '计时暂停' : '送达剩余'} ${clockLabel(navigation.remaining)}`;
      clock.classList.toggle('urgent', navigation.remaining !== null && navigation.remaining < 60);
    }
  }
  journey(j: Journey,d: Drive,captureName?: string) {
    this.tour=j;
    const guidance=j.photoGuidance(d);
    document.getElementById('collection-progress')!.textContent=`上海相册 ${j.save.collected.length} / ${j.data.stops.length}`;
    document.getElementById('driving-score')!.textContent=String(j.save.score);
    document.getElementById('next-stop')!.textContent=captureName??guidance.title;
    document.getElementById('stop-instruction')!.textContent=captureName?'正在保存这张风景，完成后会收入相册。':guidance.instruction;
    const capture=document.getElementById('capture-button') as HTMLButtonElement;
    capture.disabled=!!captureName || !guidance.canCapture;
    capture.setAttribute('aria-busy',String(!!captureName));
    const label=captureName?'正在保存…':guidance.stage==='complete'?'相册已集齐':guidance.stage==='collected'?'已收藏':'拍照收藏';
    if(capture.dataset.label!==label){capture.innerHTML=`${icon('camera')} ${label}`;capture.dataset.label=label;}
    const missionCapture = document.getElementById('mission-capture') as HTMLButtonElement | null;
    if(missionCapture) { missionCapture.disabled=capture.disabled;missionCapture.setAttribute('aria-busy',String(!!captureName));missionCapture.textContent=captureName?'保存中…':guidance.canCapture?'拍照收藏':'拍照'; }
    const missionAlbum = document.getElementById('mission-album-count');
    if(missionAlbum)missionAlbum.textContent=`${j.save.collected.length}/${j.data.stops.length}`;
  }
  private photoURLs: string[]=[];
  album(j: Journey,photos: {id:string;name:string;blob:Blob}[]) {
    for(const url of this.photoURLs)URL.revokeObjectURL(url);this.photoURLs=[];
    const images=new Map(photos.map(p=>{const url=URL.createObjectURL(p.blob);this.photoURLs.push(url);return [p.id,url];}));
    this.open('我的上海相册',`<p class="panel-intro">已收藏 ${j.save.collected.length} / ${j.data.stops.length} 处风景 · 安全分 ${j.save.score}</p><div class="album-grid">${j.data.stops.map(stop=>`<article>${images.has(stop.id)?`<img src="${images.get(stop.id)}" alt="${stop.name}的驾驶观景照片">`:`<div class="album-empty">${j.save.discovered.includes(stop.id)?'已发现，等你停下':'沿途寻找'}</div>`}<h3>${stop.name}</h3><p>${stop.about}</p></article>`).join('')}</div><p class="panel-foot">在观景位停稳两秒，再按 F 拍照。照片和进度保存在这台设备的浏览器中。</p>`,true);
  }
  private map(d: Drive) {
    const c = this.mini.getContext("2d")!,
      w = 420,
      h = 340;
    c.clearRect(0, 0, w, h);
    c.fillStyle = "#e4e4da";
    c.fillRect(0, 0, w, h);
    const p = d.pose,
      scale = 0.18;
    const xy = (q: Point) => [
      w / 2 + (q[0] - p.x) * scale,
      h / 2 + (q[1] - p.z) * scale,
    ];
    const draw = (points: Point[], closed = false) => {
      c.beginPath();
      points.forEach((q, i) => {
        const v = xy(q);
        if (i) c.lineTo(v[0], v[1]);
        else c.moveTo(v[0], v[1]);
      });
      if (closed) c.closePath();
    };
    c.fillStyle = "#9ebdc4";
    for (const r of this.city.water) {
      draw(r.points, true);
      c.fill();
    }
    c.strokeStyle = "#fffef6";
    c.lineWidth = 2;
    for (const r of this.city.roads) {
      if (r.foot || r.tunnel) continue;
      draw(r.points);
      c.stroke();
    }
    c.strokeStyle = "#315d51";
    c.lineWidth = 5;
    draw(d.route.points);
    c.stroke();
    for (const l of LANDMARKS) {
      const q = xy(project(l.lon, l.lat));
      if (q[0] > 5 && q[0] < w - 8 && q[1] > 15 && q[1] < h - 8) {
        c.fillStyle = "#566259";
        c.beginPath();
        c.arc(q[0], q[1], 3, 0, Math.PI * 2);
        c.fill();
        c.font = "18px sans-serif";
        c.fillText(l.name, q[0] + 7, q[1] - 7);
      }
    }
    const next=this.tour?.next(d);
    for(const stop of this.tour?.data.stops??[]){
      const q=xy([stop.x,stop.z]);
      if(q[0]<12||q[0]>w-12||q[1]<12||q[1]>h-12)continue;
      c.fillStyle=this.tour?.save.collected.includes(stop.id)?'#315d51':stop===next?'#aa4c29':'#7a6b50';
      c.fillRect(q[0]-10,q[1]-10,20,20);c.strokeStyle='#fff';c.lineWidth=2;c.strokeRect(q[0]-10,q[1]-10,20,20);
      c.fillStyle='#fff';c.font='bold 16px sans-serif';c.fillText('P',q[0]-5,q[1]+6);
    }
    const target = this.missionState?.navigation(d)?.target;
    if(target){
      const q=xy([target.x,target.z]);
      const factor=Math.min(1,(w/2-25)/Math.max(1,Math.abs(q[0]-w/2)),(h/2-25)/Math.max(1,Math.abs(q[1]-h/2)));
      const x=w/2+(q[0]-w/2)*factor,z=h/2+(q[1]-h/2)*factor;
      c.beginPath();c.moveTo(x,z-14);c.lineTo(x+14,z);c.lineTo(x,z+14);c.lineTo(x-14,z);c.closePath();
      c.fillStyle='#b94c2b';c.fill();c.strokeStyle='#fff8e5';c.lineWidth=3;c.stroke();
      c.fillStyle='#fff';
      if(factor<1){
        c.save();c.translate(x,z);c.rotate(Math.atan2(z-h/2,x-w/2)+Math.PI/2);
        c.beginPath();c.moveTo(0,-8);c.lineTo(-5,4);c.lineTo(0,1);c.lineTo(5,4);c.closePath();c.fill();c.restore();
      }else{c.font='bold 16px sans-serif';c.textAlign='center';c.fillText('停',x,z+5);c.textAlign='start';}
    }
    c.save();
    c.translate(w / 2, h / 2);
    c.rotate(-d.pose.heading);
    c.fillStyle = "#ba613b";
    c.strokeStyle = "#fff";
    c.lineWidth = 3;
    c.beginPath();
    c.moveTo(0, 12);
    c.lineTo(-8, -7);
    c.lineTo(0, -3);
    c.lineTo(8, -7);
    c.closePath();
    c.fill();
    c.stroke();
    c.restore();
    document.getElementById("map-position")!.textContent =
      (d.pose.y??0)<-1 ? "浦江隧道" : p.x<-250 ? "外滩 · 黄浦江" : p.z<-1000 ? "北外滩 · 黄浦江" : "陆家嘴 · 黄浦江";
  }
}
