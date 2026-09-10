import test from 'node:test';
import assert from 'node:assert/strict';
import {vehiclePitch} from '../src/tour/vehicle-pitch';
import {readFileSync} from 'node:fs';
import {Path} from '../src/tour/drive';

const slope={at:(distance:number)=>({y:-18+distance*.06,dx:Math.sin(.7),dz:Math.cos(.7)})};
test('vehicle axle heights match a six-percent tunnel ramp in either facing direction',()=>{
  const forward=vehiclePitch(slope,100,.7,-12);
  assert.ok(Math.abs(Math.tan(forward)-.06)<1e-10);
  assert.ok(Math.abs(Math.tan(forward)*3-.18)<1e-10,'Three metre wheelbase follows the 18 cm road rise');
  const reversed=vehiclePitch(slope,100,.7+Math.PI,-12);
  assert.ok(Math.abs(forward+reversed)<1e-10);
  assert.ok(Math.abs(vehiclePitch(slope,100,.7+Math.PI/2,-12))<1e-10);
});
test('ground above a tunnel remains level and invalid sharp grades stay bounded',()=>{
  assert.equal(vehiclePitch(slope,100,.7,0),0);
  assert.equal(vehiclePitch({at:()=>({y:0,dx:0,dz:1})},10,0,0),0);
  const sharp={at:(distance:number)=>({y:distance*2,dx:0,dz:1})};
  assert.ok(vehiclePitch(sharp,0,0,0)<=Math.atan(.1));
});
test('actual Shanghai exit road raises front axles and lowers rear axles relative to the body',()=>{
  const route=JSON.parse(readFileSync(new URL('../public/tour-city.json',import.meta.url),'utf8')).routes[0];
  const path=new Path(route.points,true,route.elevations),d=5375,p=path.pose(d,0);
  const pitch=vehiclePitch(path,d,p.heading,p.y??0);
  assert.ok(pitch>0 && pitch<.08);
  const rise=Math.tan(pitch)*3;
  assert.ok(Math.abs(rise-((path.at(d+1.5).y??0)-(path.at(d-1.5).y??0)))<.001);
});
