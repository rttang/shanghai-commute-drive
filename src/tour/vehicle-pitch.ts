type RoadSample={y?:number;dx:number;dz:number};
type RoadPath={at(distance:number):RoadSample};

/** Pitch the -Z-forward vehicle mesh along its supporting road, including reverse travel.
 * A ground-level vehicle above a buried road must not inherit the tunnel slope.
 */
export function vehiclePitch(path:RoadPath,distance:number,heading:number,bodyY:number) {
  const center=path.at(distance);
  if(Math.abs((center.y??0)-bodyY)>.3)return 0;
  const a=path.at(distance-1),b=path.at(distance+1);
  const grade=((b.y??0)-(a.y??0))/2;
  const alongHeading=grade*Math.cos(heading-Math.atan2(center.dx,center.dz));
  return Math.atan(Math.max(-.1,Math.min(.1,alongHeading)));
}
