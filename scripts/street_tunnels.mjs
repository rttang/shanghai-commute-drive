import * as THREE from 'three';

// Shapes and colours follow the individually reviewed tunnel photographs in
// references/tourism/loop-tunnel-reference-review.json. Width, component spacing
// and equipment placement remain authored for this game's carriageway.
export function buildStreetTunnels(tunnelPaths, add, colors) {
  Object.assign(colors, {
    'context-tunnel-shell':'#414745', 'context-tunnel-rib':'#303734',
    'context-tunnel-floor':'#414644', 'context-tunnel-panel':'#dfded4',
    'context-tunnel-cream':'#cbc9b0', 'context-tunnel-base':'#555a56',
    'context-tunnel-joint':'#5b6058', 'context-tunnel-light':'#f7f4dc',
    'context-tunnel-fixture':'#454e4c', 'context-tunnel-fire':'#842f27',
    'context-tunnel-green':'#37d590',
  });
  const counts={tunnels:0,panels:0,lights:0,ribs:0,fireCabinets:0,laneSignals:0};
  function place(g,p,x,y,z,name) {
    g.translate(x,y,z);g.rotateY(p.heading);g.translate(p.x,p.y+.12,p.z);add(g,name);
  }
  const box=(p,w,h,l,x,y,z,name)=>place(new THREE.BoxGeometry(w,h,l),p,x,y,z,name);
  // Make longitudinal surfaces follow both horizontal curves and ramp grade.
  function strip(path,d0,d1,section,name) {
    const poses=[path.pose(d0,0),path.pose(d1,0)],v=[],uv=[],indices=[];
    for(const [i,p] of poses.entries())for(const [x,y] of section){
      v.push(p.x+Math.cos(p.heading)*x,p.y+y+.12,p.z-Math.sin(p.heading)*x);
      uv.push(x/3,(i?d1:d0)/3);
    }
    for(let j=1;j<section.length;j++){const n=section.length;indices.push(j-1,j,n+j,j-1,n+j,n+j-1);}
    const indexed=new THREE.BufferGeometry();indexed.setAttribute('position',new THREE.Float32BufferAttribute(v,3));indexed.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2));indexed.setIndex(indices);
    // Keep the sloping barrier face separate from its horizontal top. Averaging
    // those normals produced dark triangular patches on the otherwise flat face.
    const g=indexed.toNonIndexed();indexed.dispose();g.computeVertexNormals();add(g,name);
  }
  function arch(path,d,thickness,name) {
    const p=path.pose(d,0),v=[];
    for(let i=0;i<=28;i++){
      const angle=Math.PI*i/28;
      v.push(new THREE.Vector3(4.18*Math.cos(angle),3.4+2.42*Math.sin(angle),0));
    }
    place(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(v),56,thickness,5,false),p,0,0,0,name);
  }
  for(const {path,tunnel,samples} of tunnelPaths){
    counts.tunnels++;
    const roofSection=Array.from({length:29},(_,i)=>{
      const a=Math.PI*i/28;return [4.2*Math.cos(a),3.4+2.45*Math.sin(a)];
    });
    for(let i=1;i<samples.length;i++){
      const d0=samples[i-1],d1=samples[i],d=(d0+d1)/2,p=path.pose(d,0);
      strip(path,d0,d1,[[-3.35,0],[3.35,0]],'context-tunnel-floor');
      if(d0<tunnel.start+35||d1>tunnel.end-35)continue;
      const underground=p.y<-5.9;
      const wallHeight=underground?3.4:Math.min(3.4,-p.y+.6);
      for(const side of [-1,1]){
        // The front of the sloping barrier is exactly the existing collision
        // face (3.35 m minus its 0.10 m half-thickness). No new road obstruction.
        strip(path,d0,d1,[[side*3.25,0],[side*3.47,.68],[side*4.2,.68]],'context-tunnel-base');
        strip(path,d0,d1,[[side*4.2,.68],[side*4.2,wallHeight]],'context-tunnel-joint');
        strip(path,d0,d1,[[side*3.12,.012],[side*3.23,.012]],'context-markings');
        if(!underground)continue;
        for(let row=0;row<4;row++){
          const y0=.7+row*.67,y1=y0+.65;
          strip(path,d0+.013,d1-.013,[[side*4.175,y0],[side*4.175,y1]],row%2?'context-tunnel-cream':'context-tunnel-panel');
          counts.panels++;
          const joint=path.pose(d0+.015,0);
          box(joint,.022,.65,.022,side*4.154,(y0+y1)/2,0,'context-tunnel-joint');
        }
        // Four slim surface cable conduits along each shoulder.
        for(let cable=0;cable<3;cable++)strip(path,d0,d1,[[side*(4.12-cable*.042),3.4],[side*(4.10-cable*.042),3.43]],'context-tunnel-fixture');
        if(i%2===0){
          box(p,.31,.13,1.15,side*3.5,4.49,0,'context-tunnel-fixture');
          box(p,.27,.035,.95,side*3.5,4.413,0,'context-tunnel-light');counts.lights++;
        }
        if(i%4===0){
          box(p,.04,.1,.22,side*3.47,.75,0,'context-tunnel-light');
        }
        if(i%30===0 && tunnel.name==='人民路隧道'){
          // Normal closed cabinet inferred from photographed recessed hardware;
          // the accident damage and open doors are intentionally not reproduced.
          box(p,.035,1.13,.9,side*4.13,1.43,0,'context-tunnel-fixture');
          box(p,.045,1.04,.81,side*4.10,1.43,0,'context-tunnel-panel');
          box(p,.049,.09,.7,side*4.065,1.9,0,'context-tunnel-fire');
          box(p,.055,.16,.24,side*4.06,2.22,0,'context-tunnel-fire');
          box(p,.07,.16,.025,side*4.035,1.4,.28,'context-tunnel-fixture');
          counts.fireCabinets++;
        }
      }
      if(i%2===0)strip(path,d0+.8,Math.min(d0+3.8,d1),[[-.06,.015],[.06,.015]],'context-markings');
      if(!underground)continue;
      strip(path,d0,d1,roofSection,'context-tunnel-shell');
      arch(path,d0,.038,'context-tunnel-rib');counts.ribs++;
      if(i%40===0 && tunnel.name==='新建路隧道'){
        for(const x of [-1.65,1.65]){
          box(p,.7,.55,.13,x,4.8,0,'context-tunnel-fixture');
          box(p,.065,.29,.02,x,4.84,-.077,'context-tunnel-green');
          for(const side of [-1,1]){
            const g=new THREE.BoxGeometry(.065,.23,.02);g.rotateZ(side*Math.PI/4);
            place(g,p,x+side*.07,4.64,-.079,'context-tunnel-green');
          }
          counts.laneSignals++;
        }
      }
    }
  }
  return {counts,referenceCatalog:'references/tourism/loop-tunnel-reference-review.json',
    measured:false,carriagewayWidth:6.7,collisionFaceHalfWidth:3.25,
    inferred:['component dimensions and spacing','closed fire cabinet door treatment'],
    excluded:['unconfirmed ventilation fans','accident damage','unlocated portal canopies']};
}
