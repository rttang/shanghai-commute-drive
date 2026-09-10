import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import {prepareVehicleMaterials} from '../src/tour/vehicle-materials';
test('exterior glass avoids scene refraction while retaining tint, texture and alpha',()=>{
  const map=new THREE.Texture(),glass=new THREE.MeshPhysicalMaterial({transmission:.5,transparent:true,opacity:.3,color:'#172922',map});
  const originalColor=glass.color.clone();
  prepareVehicleMaterials(new THREE.Mesh(new THREE.BoxGeometry(),glass));
  assert.equal(glass.transmission,0);assert.equal(glass.opacity,.3);assert.equal(glass.map,map);assert.ok(glass.color.equals(originalColor));
});
test('opaque transmitting lamp covers remain see-through and paint is unchanged',()=>{
  const lamp=new THREE.MeshPhysicalMaterial({transmission:.94}),paint=new THREE.MeshPhysicalMaterial({color:'#d3a20f',metalness:.8});
  const group=new THREE.Group();group.add(new THREE.Mesh(new THREE.BoxGeometry(),[lamp,paint]));
  prepareVehicleMaterials(group);assert.ok(lamp.transparent && !lamp.depthWrite && lamp.opacity<.25);assert.equal(lamp.transmission,0);
  assert.equal(paint.opacity,1);assert.equal(paint.transparent,false);assert.equal(paint.metalness,.8);
  const opacity=lamp.opacity;prepareVehicleMaterials(group);assert.equal(lamp.opacity,opacity);
});
test('Alphard exterior correction targets rubber and cabin glass without darkening its lamps',()=>{
  const tire=new THREE.MeshPhysicalMaterial({color:'#999999'});tire.name='tire.139';
  const window=new THREE.MeshPhysicalMaterial({transmission:.3,transparent:true,opacity:.3});window.name='windowglass.139';
  const lamp=new THREE.MeshPhysicalMaterial({transmission:.3,transparent:true,opacity:.3,color:'#dd2200'});lamp.name='redglass.136';
  const group=new THREE.Group();group.add(new THREE.Mesh(new THREE.BoxGeometry(),[tire,window,lamp]));
  prepareVehicleMaterials(group,'alphard');assert.ok(tire.color.r<.02);assert.equal(window.opacity,1);assert.equal(window.transmission,0);
  assert.equal(lamp.opacity,.3);assert.ok(lamp.color.r>.5 && lamp.color.g<.03);
});
