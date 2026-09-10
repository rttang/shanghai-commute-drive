import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import type { MissionDrive, MissionNavigation } from './missions';

/** One reusable street marker and one waiting figure; no assets, lights or colliders. */
export class MissionsWorld {
  readonly group = new THREE.Group();
  private readonly markerMaterial = new THREE.MeshBasicMaterial({ color:'#efb961', fog:true });
  private readonly personMaterial = new THREE.MeshBasicMaterial({ vertexColors:true, fog:true });
  private readonly marker: THREE.Mesh;
  private readonly person: THREE.Mesh;
  constructor() {
    this.group.name = 'city-mission-place';
    const bars = [
      new THREE.BoxGeometry(.09,.035,6.2).translate(-1.65,.03,0),
      new THREE.BoxGeometry(.09,.035,6.2).translate(1.65,.03,0),
      new THREE.BoxGeometry(3.3,.035,.09).translate(0,.03,-3.1),
      new THREE.BoxGeometry(3.3,.035,.09).translate(0,.03,3.1),
      new THREE.OctahedronGeometry(.42).translate(0,3.7,0),
    ].map(geometry=>{
      if(!geometry.index)return geometry;
      const result=geometry.toNonIndexed();geometry.dispose();return result;
    });
    this.marker = new THREE.Mesh(mergeGeometries(bars)!,this.markerMaterial);
    bars.forEach(geometry=>geometry.dispose());
    this.marker.name = 'mission-parking-marker';
    const parts: THREE.BufferGeometry[] = [];
    const part = (source:THREE.BufferGeometry, x:number,y:number,z:number,color:string) => {
      const geometry=source.index?source.toNonIndexed():source;
      if(geometry!==source)source.dispose();
      geometry.translate(x,y,z);
      const tint=new THREE.Color(color),colors=new Float32Array(geometry.getAttribute('position').count*3);
      for(let i=0;i<colors.length;i+=3){colors[i]=tint.r;colors[i+1]=tint.g;colors[i+2]=tint.b;}
      geometry.setAttribute('color',new THREE.BufferAttribute(colors,3));parts.push(geometry);
    };
    part(new THREE.BoxGeometry(.4,.65,.24),0,1.04,0,'#557267');
    part(new THREE.SphereGeometry(.15,8,6),0,1.56,0,'#c69a75');
    for(const side of [-1,1]) {
      part(new THREE.BoxGeometry(.13,.58,.14),side*.28,1.02,0,'#557267');
      part(new THREE.BoxGeometry(.16,.65,.17),side*.11,.38,0,'#36444a');
      part(new THREE.BoxGeometry(.17,.1,.26),side*.11,.06,.04,'#303934');
    }
    part(new THREE.BoxGeometry(.32,.4,.13),0,1.05,-.18,'#987e5a');
    this.person = new THREE.Mesh(mergeGeometries(parts)!,this.personMaterial);
    parts.forEach(geometry=>geometry.dispose());
    this.person.name = 'mission-waiting-person';this.person.position.set(2.25,0,-.5);this.person.rotation.y=-Math.PI/2;
    this.group.add(this.marker,this.person);
    this.group.visible=false;
  }
  update(navigation:MissionNavigation|null,drive:MissionDrive,visible=true) {
    const target=navigation?.target,p=drive.pose;
    this.group.visible=!!target && visible && Math.hypot(p.x-target.x,p.z-target.z)<220 && Math.abs((p.y??0)-target.y)<5;
    if(!this.group.visible || !target)return;
    this.group.position.set(target.x,target.y+.16,target.z);this.group.rotation.y=target.heading;
    this.person.visible=navigation!.stage==='pickup' || navigation!.stage==='event';
  }
  dispose() {
    this.group.removeFromParent();
    this.marker.geometry.dispose();this.person.geometry.dispose();
    this.markerMaterial.dispose();this.personMaterial.dispose();
  }
}
