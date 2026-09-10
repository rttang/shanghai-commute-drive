import { angleDifference } from './drive';
import type { TourStop } from './journey';

export const MISSION_STORAGE_KEY = 'shanghai-city-missions-v1';
export type MissionKind = 'tourist' | 'delivery';
export type MissionDefinition = {
  id: string; title: string; kind: MissionKind; person: string; description: string;
  pickup: TourStop; destination: TourStop; reward: number; timeLimit?: number;
  pickupLine: string; finishLine: string;
  event?: { stop: TourStop; title: string; request: string; thanks: string; bonus: number; extraSeconds: number };
};
export type MissionDrive = {
  phase: 'ready' | 'running' | 'paused' | 'complete'; mode: 'auto' | 'manual';
  rate: number; speed: number; distance: number;
  pose: { x: number; z: number; y?: number; heading: number };
};
export type MissionActive = {
  id: string; stage: 'pickup' | 'dropoff' | 'event';
  event: 'waiting' | 'offered' | 'accepted' | 'completed' | 'skipped';
  elapsed: number; remaining: number | null; incidents: number;
};
export type MissionResult = {
  id: string; success: boolean; title: string; message: string;
  stars: number; reward: number; eventBonus: number; incidents: number; elapsed: number;
};
export type MissionSave = {
  version: 1; credits: number; completed: number;
  records: Record<string, { completed: number; bestStars: number }>;
  active: MissionActive | null; lastResult: MissionResult | null;
};
export type MissionNavigation = {
  target: TourStop; stage: MissionActive['stage']; title: string; person: string;
  objective: string; instruction: string; distance: number; nearby: boolean;
  remaining: number | null; parkedSeconds: number; eventOffered: boolean;
};
const forward = (from: number, to: number, total: number) => ((to - from) % total + total) % total;
const finite = (value: unknown, fallback = 0, max = 1e9) => typeof value === 'number' && Number.isFinite(value) ? Math.max(0, Math.min(max, value)) : fallback;

/** Original, replayable trips using the same lightweight parking places as the album. */
export function createMissionCatalog(stops: TourStop[], routeLength: number): MissionDefinition[] {
  const stop = new Map(stops.map(s => [s.id, s]));
  const definitions: Array<{
    id: string; title: string; kind: MissionKind; person: string; description: string;
    from: string; to: string; reward: number; timed?: boolean; pickupLine: string; finishLine: string;
    event?: { at: string; title: string; request: string; thanks: string; bonus: number; extraSeconds: number };
  }> = [
    { id: 'first-shanghai', title: '第一次来上海', kind: 'tourist', person: '旅人 · 林阿姨', from: 'peace-hotel', to: 'shiliupu', reward: 180,
      description: '林阿姨想从老饭店出发，去十六铺看看江上的船。', pickupLine: '「慢慢开就好，我想看看这一路的老房子。」', finishLine: '「这段江岸真好看，谢谢你陪我慢慢走。」',
      event: { at: 'customs-house', title: '钟楼下的小停留', request: '「能在江海关停一下吗？我想听一会儿钟声。」', thanks: '「年轻时在明信片上见过这里，今天终于亲眼看到了。」', bonus: 60, extraSeconds: 0 } },
    { id: 'river-express', title: '跨江的设计稿', kind: 'delivery', person: '设计师 · 小顾', from: 'customs-house', to: 'financial-center', reward: 320, timed: true,
      description: '把装好的设计稿送到陆家嘴，收件人正在等这份提案。', pickupLine: '「设计稿放好了，辛苦你在约定时间内送到。」', finishLine: '「赶上了！谢谢你把稿件完整送到。」' },
    { id: 'family-by-river', title: '去看东方明珠', kind: 'tourist', person: '游客 · 周先生一家', from: 'financial-center', to: 'pearl', reward: 220,
      description: '一家人逛完陆家嘴，想坐车去看看东方明珠。', pickupLine: '「孩子一路都在找那颗大圆球，出发吧。」', finishLine: '「到了，我们一眼就认出来了！」' },
    { id: 'city-appointment', title: '江对岸的约定', kind: 'tourist', person: '摄影师 · 阿岚', from: 'pearl', to: 'north-bund', reward: 380, timed: true,
      description: '阿岚约了朋友在北外滩碰面，想在约定时间前抵达。', pickupLine: '「江对岸有人在等我，时间交给你了。」', finishLine: '「刚好赶上约定，也谢谢你一路平稳地开。」',
      event: { at: 'jinmao', title: '留一张街角照片', request: '「能在金茂大厦旁稍停一下吗？朋友说可以多等两分钟。」', thanks: '「拍好了，这张街角留给今天。」', bonus: 80, extraSeconds: 120 } },
    { id: 'bridge-return', title: '桥边见', kind: 'tourist', person: '市民 · 陈伯', from: 'north-bund', to: 'waibaidu', reward: 160,
      description: '陈伯结束江边散步，想去外白渡桥边和老朋友会合。', pickupLine: '「往桥边去吧，今天的风很舒服。」', finishLine: '「朋友就在桥头，谢谢你。」' },
    { id: 'night-postcard', title: '饭店的明信片', kind: 'delivery', person: '店员 · 小许', from: 'waibaidu', to: 'palace-hotel', reward: 140, timed: true,
      description: '将一盒上海明信片沿环线送到和平饭店南楼。', pickupLine: '「是客人要带走的明信片，请按时送到。」', finishLine: '「明信片收到了，客人一定会喜欢。」' },
  ];
  return definitions.flatMap(({ from, to, timed, event, ...definition }) => {
    const pickup = stop.get(from), destination = stop.get(to);
    if (!pickup || !destination) return [];
    const eventStop = event && stop.get(event.at);
    return [{ ...definition, pickup, destination,
      timeLimit: timed ? Math.ceil(forward(pickup.distance, destination.distance, routeLength) / 8 + 100) : undefined,
      event: event && eventStop ? { ...event, stop: eventStop } : undefined }];
  });
}

export class Missions {
  readonly catalog: MissionDefinition[];
  readonly save: MissionSave = { version: 1, credits: 0, completed: 0, records: {}, active: null, lastResult: null };
  parkedSeconds = 0;
  private penaltyBaseline?: number;
  private saveElapsed = 0;
  private notice = '';
  private storageFailed = false;
  constructor(stops: TourStop[], readonly routeLength: number,
    private storage?: Pick<Storage, 'getItem' | 'setItem'>, catalog?: MissionDefinition[]) {
    this.catalog = catalog ?? createMissionCatalog(stops, routeLength);
    this.restore();
  }
  get current() { return this.catalog.find(m => m.id === this.save.active?.id); }
  get active() { return this.save.active; }
  get storageAvailable() { return !this.storageFailed; }
  private restore() {
    try {
      const value = JSON.parse(this.storage?.getItem(MISSION_STORAGE_KEY) || 'null');
      if (value?.version !== 1) return;
      this.save.credits = Math.floor(finite(value.credits));
      this.save.completed = Math.floor(finite(value.completed));
      for (const mission of this.catalog) {
        const record = value.records?.[mission.id];
        if (record) this.save.records[mission.id] = { completed: Math.floor(finite(record.completed)), bestStars: Math.floor(finite(record.bestStars, 0, 5)) };
      }
      const active = value.active, definition = this.catalog.find(m => m.id === active?.id);
      if (definition && ['pickup', 'dropoff', 'event'].includes(active.stage)) {
        let event: MissionActive['event'] = definition.event && ['waiting', 'offered', 'accepted', 'completed', 'skipped'].includes(active.event) ? active.event : 'skipped';
        const stage: MissionActive['stage'] = active.stage === 'event' && (!definition.event || event !== 'accepted') ? 'dropoff' : active.stage;
        if (event === 'accepted' && stage !== 'event') event = 'skipped';
        if (stage === 'pickup') event = definition.event ? 'waiting' : 'skipped';
        this.save.active = { id: definition.id, stage, event, elapsed: finite(active.elapsed), incidents: Math.floor(finite(active.incidents, 0, 999)),
          remaining: definition.timeLimit ? stage === 'pickup' ? definition.timeLimit : finite(active.remaining, definition.timeLimit, definition.timeLimit + (definition.event?.extraSeconds ?? 0)) : null };
      }
      const result = value.lastResult, completed = this.catalog.find(m => m.id === result?.id);
      if (completed && typeof result.success === 'boolean') {
        this.save.lastResult = { id: completed.id, success: result.success, title: completed.title,
          message: result.success ? completed.finishLine : result.message === '已结束本次委托' ? result.message : '未能在约定时间内送达',
          stars: result.success ? Math.max(1, Math.floor(finite(result.stars, 1, 5))) : 0,
          reward: Math.floor(finite(result.reward)), eventBonus: Math.floor(finite(result.eventBonus)),
          incidents: Math.floor(finite(result.incidents, 0, 999)), elapsed: finite(result.elapsed) };
      }
    } catch { /* An unreadable mission save must not affect driving or the album. */ }
  }
  accept(id: string, _drive: MissionDrive, penalties: number): boolean {
    const mission = this.catalog.find(m => m.id === id);
    if (!mission || this.active) return false;
    this.save.active = { id, stage: 'pickup', event: mission.event ? 'waiting' : 'skipped', elapsed: 0, remaining: mission.timeLimit ?? null, incidents: 0 };
    this.save.lastResult = null;
    this.penaltyBaseline = finite(penalties);
    this.parkedSeconds = 0;
    this.notice = `已接取「${mission.title}」· 前往${mission.pickup.name}`;
    this.persist();
    return true;
  }
  retry(drive: MissionDrive, penalties: number): boolean {
    const result = this.save.lastResult;
    return !!result && this.accept(result.id, drive, penalties);
  }
  abandon() {
    if (!this.active) return false;
    this.finish(false, '已结束本次委托');
    return true;
  }
  dismissResult() { this.save.lastResult = null; this.persist(); }
  suspend() { this.parkedSeconds = 0; this.persist(); }
  noteRecovery() {
    if (this.active) { this.active.incidents++; this.parkedSeconds = 0; this.persist(); }
  }
  chooseEvent(accept: boolean): boolean {
    const active = this.active, event = this.current?.event;
    if (!active || !event || active.event !== 'offered' || active.stage !== 'dropoff') return false;
    active.event = accept ? 'accepted' : 'skipped';
    if (accept) {
      active.stage = 'event';
      if (active.remaining !== null) active.remaining += event.extraSeconds;
      this.notice = `顺路停靠 · ${event.stop.name}${event.extraSeconds ? ` · 增加 ${event.extraSeconds} 秒` : ''}`;
    } else this.notice = '继续前往目的地';
    this.parkedSeconds = 0;
    this.persist();
    return true;
  }
  private target() {
    const mission = this.current;
    return mission && (this.active?.stage === 'pickup' ? mission.pickup : this.active?.stage === 'event' ? mission.event!.stop : mission.destination);
  }
  navigation(drive: MissionDrive): MissionNavigation | null {
    const active = this.active, mission = this.current, target = this.target();
    if (!active || !mission || !target) return null;
    const p = drive.pose, gap = Math.hypot(p.x - target.x, p.z - target.z);
    const nearby = gap < 55 && Math.abs((p.y ?? 0) - target.y) < 2;
    const objective = active.stage === 'pickup' ? mission.kind === 'tourist' ? '前往接客' : '前往取件' : active.stage === 'event' ? '顺路停靠' : mission.kind === 'tourist' ? '送乘客到达' : '送达物件';
    let instruction = `沿环线前往${target.name}，在目的地停车位停稳两秒。`;
    if (drive.phase !== 'running') instruction = '行程已暂停，委托计时也已暂停。继续行程后出发。';
    else if (nearby) {
      if (drive.mode === 'auto') instruction = '即将到达，点击「接管驾驶」，驶入标记停车位。';
      else if (gap >= 4) instruction = `距停车点 ${Math.ceil(gap)} 米，慢慢驶入标记停车位。`;
      else if (Math.abs(angleDifference(p.heading, target.heading)) >= .65) instruction = '沿停车线摆正车身，再刹停。';
      else if (Math.abs(drive.speed) >= .3) instruction = '已到停车点，按 S 或踩刹车停稳。';
      else instruction = `保持停稳 ${Math.max(0, 2 - this.parkedSeconds).toFixed(1)} 秒，${active.stage === 'pickup' ? mission.kind === 'tourist' ? '乘客即将上车' : '即将装好物件' : active.stage === 'event' ? '等乘客回到车上' : '即可完成委托'}。`;
    }
    return { target, stage: active.stage, title: mission.title, person: mission.person, objective, instruction,
      distance: nearby ? gap : forward(drive.distance, target.distance, this.routeLength), nearby,
      remaining: active.stage === 'pickup' ? null : active.remaining, parkedSeconds: this.parkedSeconds, eventOffered: active.event === 'offered' };
  }
  update(dt: number, drive: MissionDrive, penalties: number) {
    const active = this.active, mission = this.current;
    if (!active || !mission) return;
    const currentPenalties = finite(penalties);
    if (this.penaltyBaseline !== undefined) active.incidents += Math.max(0, currentPenalties - this.penaltyBaseline);
    this.penaltyBaseline = currentPenalties;
    if (drive.phase !== 'running') { this.parkedSeconds = 0; return; }
    const step = finite(dt, 0, 5), elapsed = step * (drive.mode === 'auto' ? Math.max(1, Math.min(3, finite(drive.rate, 1))) : 1);
    active.elapsed += elapsed;
    if (active.stage !== 'pickup' && active.remaining !== null) {
      active.remaining = Math.max(0, active.remaining - elapsed);
      if (active.remaining <= 0) { this.finish(false, '未能在约定时间内送达'); return; }
    }
    const p = drive.pose, event = mission.event;
    if (active.stage === 'dropoff' && event && active.event === 'waiting' && Math.hypot(p.x - event.stop.x, p.z - event.stop.z) < 240 && Math.abs((p.y ?? 0) - event.stop.y) < 2) {
      active.event = 'offered';
      this.notice = `${mission.person}有一个顺路请求 · ${event.title}`;
      this.persist();
    }
    const target = this.target()!;
    const stopped = drive.mode === 'manual' && Math.abs(drive.speed) < .3 && Math.hypot(p.x - target.x, p.z - target.z) < 4 && Math.abs((p.y ?? 0) - target.y) < 1 && Math.abs(angleDifference(p.heading, target.heading)) < .65;
    this.parkedSeconds = stopped ? this.parkedSeconds + step : 0;
    if (this.parkedSeconds >= 2) {
      this.parkedSeconds = 0;
      if (active.stage === 'pickup') {
        active.stage = 'dropoff'; this.notice = `${mission.pickupLine} → ${mission.destination.name}`;
      } else if (active.stage === 'event') {
        active.stage = 'dropoff'; active.event = 'completed'; this.notice = event!.thanks;
      } else { this.finish(true, mission.finishLine); return; }
      this.persist();
    }
    this.saveElapsed += step;
    if (this.saveElapsed >= 5) this.persist();
  }
  private finish(success: boolean, message: string) {
    const active = this.active, mission = this.current;
    if (!active || !mission) return;
    const stars = success ? Math.max(1, 5 - Math.floor(active.incidents)) : 0;
    const eventBonus = success && active.event === 'completed' ? mission.event?.bonus ?? 0 : 0;
    const reward = success ? Math.round(mission.reward * (.5 + stars / 10)) + eventBonus : 0;
    this.save.lastResult = { id: mission.id, title: mission.title, success, message, stars, reward, eventBonus, incidents: active.incidents, elapsed: active.elapsed };
    if (success) {
      this.save.credits += reward; this.save.completed++;
      const previous = this.save.records[mission.id];
      this.save.records[mission.id] = { completed: (previous?.completed ?? 0) + 1, bestStars: Math.max(previous?.bestStars ?? 0, stars) };
    }
    this.save.active = null;
    this.parkedSeconds = 0;
    this.notice = success ? `委托完成 · ${stars} 星评价 · +${reward} 积分` : `${message} · 可以重新接取`;
    this.persist();
  }
  consumeNotice() { const notice = this.notice; this.notice = ''; return notice; }
  persist() {
    this.saveElapsed = 0;
    try { this.storage?.setItem(MISSION_STORAGE_KEY, JSON.stringify(this.save)); this.storageFailed = false; return true; }
    catch { this.storageFailed = true; return false; }
  }
}
