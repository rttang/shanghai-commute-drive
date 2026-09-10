import * as THREE from 'three';
import { signalState,type JourneyData } from './journey';
import { Path } from './drive';
export class JourneyWorld {
  readonly group=new THREE.Group();
  private lamps:{signal:JourneyData['signals'][number];lights:THREE.MeshStandardMaterial[]}[]=[];
  private markers=new Map<string,THREE.MeshStandardMaterial>();
  constructor(readonly data:JourneyData,readonly path:Path){
    const pole=new THREE.MeshStandardMaterial({color:'#566365',roughness:.7,metalness:.6});
    const white=new THREE.MeshStandardMaterial({color:'#ebe7cd',roughness:.85});
    const box=(parent:THREE.Object3D,w:number,h:number,l:number,x:number,y:number,z:number,m:THREE.Material)=>{const mesh=new THREE.Mesh(new THREE.BoxGeometry(w,h,l),m);mesh.position.set(x,y,z);parent.add(mesh);return mesh;};
    for(const stop of data.stops){
      const group=new THREE.Group();group.position.set(stop.x,stop.y+.14,stop.z);group.rotation.y=stop.heading;
      const line=new THREE.MeshStandardMaterial({color:'#dcb97b',roughness:.8});this.markers.set(stop.id,line);
      box(group,.08,.018,6,-1.5,.005,0,line);box(group,.08,.018,6,1.5,.005,0,line);
      box(group,3,.018,.08,0,.005,-3,line);box(group,3,.018,.08,0,.005,3,line);
      box(group,.065,2.1,.065,-1.85,1.05,-2.7,pole);
      const canvas=document.createElement('canvas');canvas.width=512;canvas.height=320;
      const c=canvas.getContext('2d')!;c.fillStyle='#234e45';c.fillRect(0,0,512,320);c.fillStyle='#fff9e7';c.font='bold 94px sans-serif';c.textAlign='center';c.fillText('P',256,114);c.font='36px "PingFang SC", sans-serif';c.fillText(stop.name,256,198);c.font='26px sans-serif';c.fillText('上海漫游 · 观景点',256,259);
      const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
      const sign=new THREE.Mesh(new THREE.PlaneGeometry(.95,.6),new THREE.MeshStandardMaterial({map:texture,side:THREE.DoubleSide}));sign.position.set(-1.85,1.9,-2.7);sign.rotation.y=Math.PI;group.add(sign);
      this.group.add(group);
    }
    for(const signal of data.signals){
      const group=new THREE.Group();group.position.set(signal.x,path.at(signal.distance).y+.15,signal.z);group.rotation.y=signal.heading;
      box(group,.16,5.2,.16,-5,2.6,0,pole);box(group,5.6,.14,.14,-2.3,5.1,0,pole);box(group,.58,1.8,.4,0,4.5,0,pole);
      const lights=['#f44038','#ffb73c','#4ddba0'].map((color,i)=>{const mat=new THREE.MeshStandardMaterial({color,emissive:color,emissiveIntensity:0});const mesh=new THREE.Mesh(new THREE.CircleGeometry(.17,16),mat);mesh.rotation.y=Math.PI;mesh.position.set(0,5.08-i*.56,-.21);group.add(mesh);return mat;});
      box(group,3.3,.015,.35,-1.65,.015,-3,white);this.group.add(group);this.lamps.push({signal,lights});
    }
  }
  update(time:number,collected:readonly string[]){
    for(const {signal,lights} of this.lamps){const state=signalState(time,signal),active=state==='red'?0:state==='amber'?1:2;lights.forEach((m,i)=>{m.emissiveIntensity=i===active?2:0;m.color.setScalar(i===active?1:.12);});}
    for(const [id,m] of this.markers)m.color.set(collected.includes(id)?'#86b7a7':'#dcb97b');
  }
}
