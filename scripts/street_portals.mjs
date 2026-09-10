import * as THREE from 'three';

// Portal identities are tied to the actual driven branches, not just a tunnel
// name. See loop-tunnel-reference-review.json / portalLocalizationAudit.
export function buildStreetPortals(tunnelPaths,roads,add,colors){
  Object.assign(colors,{'context-portal-steel':'#747e7d','context-portal-dark':'#313d3c','context-portal-yellow':'#d7bb40','context-portal-glass':'#aebdb7','context-portal-white':'#f4f2df','context-portal-red':'#a3362e','context-portal-renmin-sign':'#ffffff','context-portal-xinjian-sign':'#ffffff','context-portal-hailun-sign':'#ffffff','context-portal-limit43-sign':'#ffffff'});
  const supports=[],portals=[];
  function point(p,x,y,z=0){return new THREE.Vector3(p.x+Math.cos(p.heading)*x+Math.sin(p.heading)*z,p.y+y+.12,p.z-Math.sin(p.heading)*x+Math.cos(p.heading)*z);}
  function place(g,p,x,y,z,material){g.translate(x,y,z);g.rotateY(p.heading);g.translate(p.x,p.y+.12,p.z);add(g,material);}
  function box(p,w,h,l,x,y,z,m){place(new THREE.BoxGeometry(w,h,l),p,x,y,z,m);}
  function rod(p,a,b,r,m){
    const av=new THREE.Vector3(...a),bv=new THREE.Vector3(...b),g=new THREE.CylinderGeometry(r,r,av.distanceTo(bv),10);
    g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0,1,0),bv.clone().sub(av).normalize()));
    place(g,p,...av.add(bv).multiplyScalar(.5).toArray(),m);
  }
  function post(p,x,height,id){
    box(p,.19,height,.19,x,height/2,0,'context-portal-steel');
    const v=point(p,x,0);supports.push({id,x:v.x,z:v.z,heading:p.heading,width:.19,length:.19,minY:v.y,maxY:v.y+height});
  }
  function sign(p,key,width,height,x,y,z,facesOut=false){
    if(key!=='hailun'&&key!=='limit43')box(p,width+.08,height+.08,.085,x,y,z,'context-portal-steel');
    const g=new THREE.PlaneGeometry(width,height);if(!facesOut)g.rotateY(Math.PI);
    place(g,p,x,y,z+(facesOut?.052:-.052),`context-portal-${key}-sign`);
  }
  function gate(path,d,key){
    const p=path.pose(d,0),width=8.8;
    for(const side of [-1,1])post(p,side*4.4,5.95,`${key}-gantry-${side}`);
    box(p,width,.21,.2,0,5.82,0,'context-portal-steel');
    box(p,width,.18,.18,0,4.5,0,'context-portal-yellow');
    for(let x=-4.25;x<4.25;x+=.48){box(p,.24,.184,.184,x,4.5,0,'context-portal-dark');}
    sign(p,key,3.25,.81,0,5.30,0);
    // 4.3 m is visible in the photographed approach; this recreates that sign,
    // rather than providing a current real-world navigation instruction.
    sign(p,'limit43',.60,.60,-3.30,5.2,-.15);
    for(const x of [-1.6,1.6]){
      box(p,.09,.40,.02,x,4.02,-.14,'context-portal-white');
      for(const side of [-1,1]){const g=new THREE.BoxGeometry(.09,.27,.02);g.rotateZ(side*Math.PI/4);place(g,p,x+side*.085,3.81,-.14,'context-portal-white');}
    }
    portals.push({id:key,distance:d,kind:'open-approach-gantry',dimensions:'authored to the mapped road width; not surveyed'});
  }
  for(const {path,tunnel} of tunnelPaths){
    if(tunnel.name==='人民路隧道')gate(path,tunnel.start+40,'renmin');
    if(tunnel.name!=='新建路隧道')continue;
    gate(path,tunnel.start+80,'xinjian');
    // Hailun's main portal covers both mapped surface ramps. Derive its span
    // from the opposing approach, rather than centring a generic narrow arch.
    const reference=path.pose(tunnel.end-25,0),opposite=roads.find(r=>r.id===145007020);
    let closest;
    for(let i=1;opposite&&i<opposite.points.length;i++){
      const a=opposite.points[i-1],b=opposite.points[i],dx=b[0]-a[0],dz=b[1]-a[1],t=Math.max(0,Math.min(1,((reference.x-a[0])*dx+(reference.z-a[1])*dz)/(dx*dx+dz*dz)));
      const q=[a[0]+t*dx,a[1]+t*dz],distance=Math.hypot(q[0]-reference.x,q[1]-reference.z);
      if(!closest||distance<closest.distance)closest={q,distance};
    }
    if(!closest)throw new Error('Hailun opposing approach geometry is missing');
    const offset=Math.cos(reference.heading)*(closest.q[0]-reference.x)-Math.sin(reference.heading)*(closest.q[1]-reference.z),center=offset/2,half=Math.abs(offset)/2+4.55;
    const arch=Array.from({length:41},(_,i)=>{const a=Math.PI*i/40;return [center+half*Math.cos(a),3.8+4.25*Math.sin(a)];});
    for(let row=0;row<=8;row++){
      const d=tunnel.end-54+row*6,p=path.pose(d,0);
      const curve=new THREE.CatmullRomCurve3(arch.map(([x,y])=>new THREE.Vector3(x,y,0)));
      place(new THREE.TubeGeometry(curve,80,.095,10,false),p,0,0,0,'context-portal-steel');
      for(const side of [-1,1])post(p,center+side*half,3.8,`hailun-${row}-${side}`);
      if(!row)continue;
      const before=path.pose(d-6,0);
      for(let j=1;j<arch.length;j++){
        const [x0,y0]=arch[j-1],[x1,y1]=arch[j],v=[point(before,x0,y0),point(before,x1,y1),point(p,x1,y1),point(p,x0,y0)];
        const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute([v[0],v[1],v[2],v[0],v[2],v[3]].flatMap(q=>q.toArray()),3));g.computeVertexNormals();add(g,'context-portal-glass');
        if(j%4===0){const a=point(before,x1,y1),b=point(p,x1,y1),curve=new THREE.LineCurve3(a,b);add(new THREE.TubeGeometry(curve,1,.033,6,false),'context-portal-steel');}
      }
    }
    const face=path.pose(tunnel.end-6,0);
    // The real red/gold name faces the street. An exiting player sees its rear.
    sign(face,'hailun',8.5,2.12,center,8.7,0,true);
    portals.push({id:'hailun',distance:tunnel.end-6,kind:'paired-ramp-arched-shelter',spanM:half*2,opposingWay:145007020,facesOutward:true,dimensions:'plan-view span derived from mapped ramps; height/depth inferred from photographs'});
  }
  return {portals,supports,source:'references/tourism/loop-tunnel-reference-review.json',unmodeled:['Unverified roof form of the northbound Pucheng Road exit branch']};
}
