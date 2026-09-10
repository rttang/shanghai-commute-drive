import type { Point } from './data';

export type VehiclePose = { x: number; z: number; heading: number; y?: number };
export type Obstacle = { id: string; kind: string; points: Point[]; minY: number; maxY: number };
export type Contact = { id: string; kind: string; normal: Point; strength: number };
const dot = (a: Point, b: Point) => a[0]*b[0]+a[1]*b[1];
export function rectangle(x: number, z: number, heading: number, width: number, length: number): Point[] {
  const s=Math.sin(heading), c=Math.cos(heading);
  return [[-1,-1],[1,-1],[1,1],[-1,1]].map(([a,b]) => [x+a*c*width/2+b*s*length/2,z-a*s*width/2+b*c*length/2]);
}
export function wall(id: string, a: Point, b: Point, minY=0, maxY=4, thickness=.12, kind='barrier'): Obstacle {
  return {id,kind,minY,maxY,points:rectangle((a[0]+b[0])/2,(a[1]+b[1])/2,Math.atan2(b[0]-a[0],b[1]-a[1]),thickness,Math.hypot(b[0]-a[0],b[1]-a[1])+thickness)};
}

/** Continuous separating-axis sweep. Even a zero-width wall between frames
 * is detected; projection padding conservatively covers rotation during a step. */
export function sweepPolygon(moving: Point[], fixed: Point[], delta: Point, padding=0) {
  let enter=-Infinity, exit=Infinity, normal: Point=[0,0];
  let overlap=Infinity, overlapNormal: Point=[0,0];
  for (const poly of [moving,fixed]) for(let i=0;i<poly.length;i++) {
    const a=poly[i], b=poly[(i+1)%poly.length], length=Math.hypot(b[0]-a[0],b[1]-a[1]);
    if(length<1e-8) continue;
    const axis: Point=[-(b[1]-a[1])/length,(b[0]-a[0])/length];
    const m=moving.map(p=>dot(p,axis)), f=fixed.map(p=>dot(p,axis));
    const lo=Math.min(...m)-padding, hi=Math.max(...m)+padding, flo=Math.min(...f), fhi=Math.max(...f);
    const velocity=dot(delta,axis), depth=Math.min(hi-flo,fhi-lo);
    const outward: Point=lo+hi < flo+fhi ? [-axis[0],-axis[1]] : axis;
    if(depth<overlap){overlap=depth;overlapNormal=outward;}
    if(Math.abs(velocity)<1e-10){if(hi<flo || lo>fhi)return;continue;}
    let t0=(flo-hi)/velocity,t1=(fhi-lo)/velocity;
    if(t0>t1)[t0,t1]=[t1,t0];
    if(t0>enter){enter=t0;normal=velocity>0 ? [-axis[0],-axis[1]] : axis;}
    exit=Math.min(exit,t1);
    if(enter>exit)return;
  }
  if(exit<0 || enter>1)return;
  if(enter<0){
    // Allow movement away from or parallel to an existing contact.
    if(dot(delta,overlapNormal)>=-1e-8)return;
    return {t:0,normal:overlapNormal};
  }
  return {t:Math.max(0,enter),normal};
}

export class CollisionWorld {
  private grid=new Map<string,Obstacle[]>();
  private dynamic: Obstacle[]=[];
  count=0;
  constructor(obstacles: Obstacle[]=[]) { for(const o of obstacles)this.add(o); }
  add(o: Obstacle) {
    if(o.points.length<3)return;
    const xs=o.points.map(p=>p[0]),zs=o.points.map(p=>p[1]);
    for(let x=Math.floor(Math.min(...xs)/60);x<=Math.floor(Math.max(...xs)/60);x++)
      for(let z=Math.floor(Math.min(...zs)/60);z<=Math.floor(Math.max(...zs)/60);z++){
        const key=`${x},${z}`, list=this.grid.get(key)??[];list.push(o);this.grid.set(key,list);
      }
    this.count++;
  }
  setTraffic(cars: {id: string; pose: VehiclePose; width: number; length: number}[]) {
    this.dynamic=cars.map(c=>({id:c.id,kind:'vehicle',points:rectangle(c.pose.x,c.pose.z,c.pose.heading,c.width,c.length),minY:c.pose.y??0,maxY:(c.pose.y??0)+1.8}));
  }
  occupied(pose: VehiclePose,width=1.9,length=4.8) {
    const p=rectangle(pose.x,pose.z,pose.heading,width,length);
    return this.candidates(pose,pose,Math.hypot(width,length)).some(o=>{
      for(const poly of [p,o.points]) for(let i=0;i<poly.length;i++){
        const a=poly[i],b=poly[(i+1)%poly.length],axis:Point=[a[1]-b[1],b[0]-a[0]];
        const m=p.map(x=>dot(x,axis)),f=o.points.map(x=>dot(x,axis));
        if(Math.max(...m)<Math.min(...f) || Math.max(...f)<Math.min(...m))return false;
      }
      return true;
    });
  }
  private candidates(a: VehiclePose,b: VehiclePose,radius: number) {
    const found=new Set<Obstacle>(this.dynamic);
    for(let x=Math.floor((Math.min(a.x,b.x)-radius)/60);x<=Math.floor((Math.max(a.x,b.x)+radius)/60);x++)
      for(let z=Math.floor((Math.min(a.z,b.z)-radius)/60);z<=Math.floor((Math.max(a.z,b.z)+radius)/60);z++)
        for(const o of this.grid.get(`${x},${z}`)??[])found.add(o);
    return [...found].filter(o=>o.minY<Math.max(a.y??0,b.y??0)+1.65 && o.maxY>Math.min(a.y??0,b.y??0)+.25);
  }
  move(from: VehiclePose, desired: VehiclePose, width=1.9, length=4.8, options: {ignoreId?:string;extra?:Obstacle[]}={}) {
    let pose={...from}, target={...desired};
    const contacts: Contact[]=[];
    const radius=Math.hypot(width,length)/2;
    const angle=Math.atan2(Math.sin(desired.heading-from.heading),Math.cos(desired.heading-from.heading));
    const slices=Math.max(1,Math.ceil(Math.abs(angle)*radius/.015));
    for(let part=1;part<=slices;part++) {
      target={...desired,x:from.x+(desired.x-from.x)*part/slices,z:from.z+(desired.z-from.z)*part/slices,heading:from.heading+angle*part/slices};
      for(let iteration=0;iteration<3;iteration++){
        const delta: Point=[target.x-pose.x,target.z-pose.z];
        const polygon=rectangle(pose.x,pose.z,pose.heading,width,length);
        const padding=radius*Math.abs(target.heading-pose.heading);
        let first: {t:number;normal:Point;obstacle:Obstacle}|undefined;
        for(const obstacle of [...this.candidates(pose,target,radius+.1),...(options.extra??[])]){
          if(obstacle.id===options.ignoreId || obstacle.minY>=Math.max(pose.y??0,target.y??0)+1.65 || obstacle.maxY<=Math.min(pose.y??0,target.y??0)+.25)continue;
          const hit=sweepPolygon(polygon,obstacle.points,delta,padding);
          if(hit && (!first || hit.t<first.t))first={...hit,obstacle};
        }
        if(!first){pose={...target};break;}
        const travel=Math.hypot(...delta), t=Math.max(0,first.t-.005/Math.max(.001,travel));
        pose.x+=delta[0]*t;pose.z+=delta[1]*t;
        const left: Point=[delta[0]*(1-t),delta[1]*(1-t)], inward=Math.min(0,dot(left,first.normal));
        contacts.push({id:first.obstacle.id,kind:first.obstacle.kind,normal:first.normal,strength:travel ? Math.abs(dot(delta,first.normal))/travel : 0});
        target={...pose,x:pose.x+left[0]-first.normal[0]*inward,z:pose.z+left[1]-first.normal[1]*inward};
        if(Math.hypot(target.x-pose.x,target.z-pose.z)<1e-6)break;
      }
      if(contacts.length)break;
    }
    return {pose,contacts};
  }
}
