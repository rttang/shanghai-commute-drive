import {test} from 'node:test';
import assert from 'node:assert/strict';
import {drivingSurfaceHeight} from '../src/tour/driving-height';
import {trafficRespawnDistance} from '../src/tour/traffic-visibility';

test('a ground-level car crossing above a tunnel never inherits the bore elevation',()=>{
  assert.equal(drivingSurfaceHeight({x:0,z:0,y:0},{x:.1,z:0},-18,0,true),0);
  assert.equal(drivingSurfaceHeight({x:0,z:0,y:0},{x:.1,z:0},-.01,7,true),0);
});
test('forward and reverse ramp travel keep the authored grade without a vertical jump',()=>{
  for(const direction of [-1,1]){
    let p={x:0,z:0,y:-6};
    for(let i=0;i<300;i++){
      const next={x:0,z:p.z+direction*.2};
      const expected=p.y+direction*.012;
      const y=drivingSurfaceHeight(p,next,expected,1.4,true);
      assert.ok(Math.abs(y-expected)<1e-9);p={...next,y};
    }
  }
  assert.equal(drivingSurfaceHeight({x:0,z:0,y:-18},{x:0,z:.1},0,0,false),-18);
  assert.equal(drivingSurfaceHeight({x:0,z:0,y:-.012},{x:0,z:.2},0,1.4,true),0);
});
test('visible traffic cannot teleport across a folded route or spawn in front of the camera',()=>{
  assert.equal(trafficRespawnDistance(3000,0,14000,0,()=>true),undefined);
  assert.equal(trafficRespawnDistance(3000,0,14000,0,d=>d===3000),undefined);
  assert.equal(trafficRespawnDistance(3000,0,14000,0,d=>d===1100),12900);
  assert.equal(trafficRespawnDistance(800,0,14000,0,()=>false),undefined);
  const placed=trafficRespawnDistance(3000,0,14000,0,()=>false)!;
  assert.equal(placed,1100);
  assert.equal(trafficRespawnDistance(placed,0,14000,0,()=>false),undefined);
});
