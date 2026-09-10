import { angleDifference, type Drive } from './drive';
export type TourStop={id:string;name:string;about:string;x:number;z:number;y:number;heading:number;distance:number;landmark:[number,number];};
export type Signal={id:string;distance:number;x:number;z:number;heading:number;offset:number;};
export type JourneyData={stops:TourStop[];signals:Signal[];roadRules?:{start:number;end:number;oneway:boolean;width:number}[]};
export type JourneySave={version:1;collected:string[];discovered:string[];score:number;lap:number;distance:number;progress?:number;penalties:number};
export type PhotoGuidance = {
  stage: 'explore' | 'takeover' | 'position' | 'align' | 'brake' | 'settling' | 'ready' | 'collected' | 'complete' | 'paused';
  title: string;
  instruction: string;
  canCapture: boolean;
};
const KEY='shanghai-loop-journey-v1';
export const signalState=(time:number,s:Signal):'red'|'amber'|'green'=>{
  const phase=((time+s.offset)%70+70)%70;
  return phase<34?'green':phase<38?'amber':'red';
};
export class Journey {
  readonly save:JourneySave={version:1,collected:[],discovered:[],score:1000,lap:0,distance:0,penalties:0};
  time=0;parkedSeconds=0;active?:TourStop;notice='';
  private lastCollision=0;private lastDistance=0;private speeding=0;private wrongWay=0;
  private dirty=false;private saveElapsed=0;
  private parkingDrive?: Drive;
  constructor(readonly data:JourneyData,private storage?:Pick<Storage,'getItem'|'setItem'>){
    try{
      const value=JSON.parse(storage?.getItem(KEY)||'null');
      if(value?.version===1){
        const valid=new Set(data.stops.map(s=>s.id));
        this.save.collected=Array.isArray(value.collected)?[...new Set<string>(value.collected.filter((id:string)=>valid.has(id)))]:[];
        this.save.discovered=Array.isArray(value.discovered)?[...new Set<string>(value.discovered.filter((id:string)=>valid.has(id)))]:[];
        for(const key of ['score','lap','distance','penalties'] as const)if(Number.isFinite(value[key])&&value[key]>=0)this.save[key]=value[key];
        if(Number.isFinite(value.progress))this.save.progress=value.progress;
      }
    }catch{}
  }
  restore(d:Drive){
    this.resetParking();
    d.restoreProgress(this.save.progress??Math.floor(this.save.lap)*d.path.total+Math.max(0,Math.min(d.path.total-.001,this.save.distance)));
    this.lastDistance=d.distance;
  }
  get complete(){return this.data.stops.length>0 && this.save.collected.length===this.data.stops.length;}
  private alignedWith(stop: TourStop, d: Drive) {
    const p = d.pose;
    return Math.hypot(stop.x-p.x, stop.z-p.z)<2.2 && Math.abs(angleDifference(p.heading,stop.heading))<.3 && Math.abs((p.y??0)-stop.y)<1;
  }
  get canCapture(){
    const d=this.parkingDrive;
    return !!d && d.phase==='running' && d.mode==='manual' && Math.abs(d.speed)<.2 && !!this.active && this.alignedWith(this.active,d) && this.parkedSeconds>=2 && !this.save.collected.includes(this.active.id);
  }
  resetParking(){this.active=undefined;this.parkedSeconds=0;this.parkingDrive=undefined;}
  photoGuidance(d: Drive): PhotoGuidance {
    const next=this.next(d), p=d.pose;
    const result=(stage: PhotoGuidance['stage'], title: string, instruction: string): PhotoGuidance=>({stage,title,instruction,canCapture:stage==='ready' && this.canCapture});
    if(this.complete)return result('complete','上海相册已集齐',`已收藏全部 ${this.data.stops.length} 处风景。打开相册回看，或继续环游上海。`);
    const parkedStop=this.data.stops.find(stop=>this.alignedWith(stop,d));
    if(parkedStop && this.save.collected.includes(parkedStop.id))return result('collected',`${parkedStop.name} · 已收藏`,next?`这一处已经收藏。下一处：${next.name}，继续沿路线前行。`:'打开相册，回看收藏的上海。');
    const nearby=this.data.stops.filter(stop=>!this.save.collected.includes(stop.id) && Math.abs((p.y??0)-stop.y)<1 && Math.hypot(stop.x-p.x,stop.z-p.z)<14)
      .sort((a,b)=>Math.hypot(a.x-p.x,a.z-p.z)-Math.hypot(b.x-p.x,b.z-p.z))[0];
    const target=nearby??next;
    if(!target)return result('explore','沿路线慢慢看上海','继续欣赏沿途风景。');
    if(d.phase!=='running')return result('paused',target.name,'行程已暂停。继续行程后再停车拍照。');
    if(nearby){
      if(d.mode!=='manual')return result('takeover',target.name,'点击「接管驾驶」，驶入观景停车位后拍照。');
      const gap=Math.hypot(target.x-p.x,target.z-p.z);
      if(gap>=2.2)return result('position',target.name,`距车位 ${Math.ceil(gap)} 米，慢慢驶入停车线内。`);
      if(!this.alignedWith(target,d))return result('align',target.name,'沿停车线摆正车身，轻打方向调整后刹停。');
      if(Math.abs(d.speed)>=.2)return result('brake',target.name,'已进入车位。按 S 或踩刹车，让车辆完全停稳。');
      if(this.canCapture)return result('ready',target.name,'停车完成 · 按 F 或点击「拍照收藏」，留下眼前的上海。');
      return result('settling',target.name,`保持停稳，再等 ${Math.max(0,2-this.parkedSeconds).toFixed(1)} 秒即可拍照。`);
    }
    const ahead=(target.distance-d.distance+d.path.total)%d.path.total;
    return result('explore',target.name,`前方 ${Math.round(ahead)} 米 · ${d.mode==='auto'?'到达后接管驾驶，停车拍照。':'寻找路旁观景停车位。'}`);
  }
  private penalize(points:number,text:string){this.save.score=Math.max(0,this.save.score-points);this.save.penalties++;this.notice=text;this.dirty=true;}
  update(dt:number,d:Drive){
    if(this.parkingDrive!==d)this.resetParking();
    this.parkingDrive=d;
    if(d.phase!=='running'){this.active=undefined;this.parkedSeconds=0;return;}
    const time=dt*(d.mode==='auto'?d.rate:1);this.time+=time;
    const p=d.pose;
    for(const stop of this.data.stops)if(Math.hypot(p.x-stop.landmark[0],p.z-stop.landmark[1])<300 && (p.y??0)>-1 && !this.save.discovered.includes(stop.id)){
      this.save.discovered.push(stop.id);this.notice=`发现 ${stop.name}`;this.dirty=true;
    }
    const previousStop=this.active;
    this.active=this.data.stops.find(s=>this.alignedWith(s,d));
    this.parkedSeconds=this.active && Math.abs(d.speed)<.2 && d.mode==='manual'?(previousStop===this.active?this.parkedSeconds:0)+dt:0;
    if(d.collisions!==this.lastCollision){this.lastCollision=d.collisions;this.penalize(60,'发生碰撞 · 安全分 −60');}
    const speed=Math.abs(d.speed)*3.6;
    this.speeding=speed>50?this.speeding+dt:0;
    if(this.speeding>3){this.penalize(15,'请减速至 50 km/h 以下 · 安全分 −15');this.speeding=0;}
    const road=this.data.roadRules?.find(r=>d.distance>=r.start&&d.distance<r.end);
    this.wrongWay=d.mode==='manual' && speed>10 && (Math.abs(angleDifference(p.heading,d.path.pose(d.distance).heading))>Math.PI/2 || (!road?.oneway && d.lateral<-.5))?this.wrongWay+dt:0;
    if(this.wrongWay>3){this.penalize(20,'请顺向靠右行驶 · 安全分 −20');this.wrongWay=0;}
    let advance=d.distance-this.lastDistance;if(d.route.closed && advance<-d.path.total/2)advance+=d.path.total;
    if(advance>0 && advance<100)for(const s of this.data.signals){
      const gap=(s.distance-this.lastDistance+d.path.total)%d.path.total;
      if(gap>0 && gap<=advance && signalState(this.time-time,s)==='red' && d.routeDeviation<8 && d.mode==='manual')this.penalize(80,'红灯越线 · 安全分 −80');
    }
    this.lastDistance=d.distance;this.save.distance=d.distance;this.save.lap=d.laps;this.save.progress=d.progress;
    this.saveElapsed+=dt;
    if(this.saveElapsed>5 || this.dirty){this.persist();this.saveElapsed=0;}
  }
  prepareCapture(){
    if(!this.canCapture)return;
    const stop=this.active!;
    let used=false;
    return {stop,commit:()=>{
      if(used || this.save.collected.includes(stop.id))return false;
      used=true;this.save.collected.push(stop.id);this.save.score+=100;
      this.notice=this.complete?`全部 ${this.data.stops.length} 处风景已收藏 · 打开相册回看上海`:`${stop.name} 已收入相册 · +100`;this.persist();return true;
    }};
  }
  capture(){return this.prepareCapture()?.commit()??false;}
  next(d:Drive){
    const remaining=this.data.stops.filter(s=>!this.save.collected.includes(s.id));
    return remaining.sort((a,b)=>((a.distance-d.distance+d.path.total)%d.path.total)-((b.distance-d.distance+d.path.total)%d.path.total))[0];
  }
  redAhead(d:Drive){
    return Math.min(Infinity,...this.data.signals.filter(s=>signalState(this.time,s)!=='green').map(s=>(s.distance-d.distance+d.path.total)%d.path.total));
  }
  consumeNotice(){const n=this.notice;this.notice='';return n;}
  persist(){
    try{this.storage?.setItem(KEY,JSON.stringify(this.save));this.dirty=false;return true;}
    catch{this.notice='进度暂时无法保存，请检查浏览器存储空间';return false;}
  }
}
