import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { GLTFLoader, type GLTF } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { VehicleModelCache } from '../src/tour/vehicle-model-cache';
import { World } from '../src/tour/world';
import { CARS } from '../src/tour/data';
import assets from '../src/tour/vehicle-assets.json';

function deferred<T>() {
  let resolve!: (value:T)=>void, reject!: (reason:unknown)=>void;
  const promise=new Promise<T>((a,b)=>{resolve=a;reject=b;});
  return {promise,resolve,reject};
}
const settle = () => new Promise<void>(resolve=>setImmediate(resolve));
function model(name:string, rig=false) {
  const disposed={geometry:0,material:0,texture:0,image:0};
  const texture=new THREE.Texture({close(){disposed.image++;}} as unknown as HTMLImageElement);
  const material=new THREE.MeshStandardMaterial({map:texture});
  const geometry=new THREE.BoxGeometry(1,1,1);
  geometry.addEventListener('dispose',()=>disposed.geometry++);
  material.addEventListener('dispose',()=>disposed.material++);
  texture.addEventListener('dispose',()=>disposed.texture++);
  const group=new THREE.Group();group.name=name;group.add(new THREE.Mesh(geometry,material));
  if(rig)for(const name of ['FL','FR','RL','RR']){
    const pivot=new THREE.Group(),roll=new THREE.Group();
    pivot.userData={wheelPosition:name,wheelRadius:.3,frontWheel:name[0]==='F'};roll.name=`WheelRoll_${name}`;pivot.add(roll);group.add(pivot);
  }
  return {group,geometry,material,texture,disposed};
}
function display() {
  const root=new THREE.Group();
  return {root,install:(group:THREE.Group)=>{root.clear();root.add(group.clone(true));}};
}

test('browsing ten vehicles keeps only current and spare, releasing every unused resource exactly once',async()=>{
  const shown=display(),cache=new VehicleModelCache({protectedRoots:()=>[shown.root]});
  const models=Array.from({length:10},(_,i)=>model(String(i)));
  for(const [i,entry] of models.entries()){
    assert.equal(await cache.select(String(i),async()=>entry.group,shown.install),true);
    assert.ok(cache.size<=2);assert.equal(cache.activeId,String(i));
    assert.deepEqual(entry.disposed,{geometry:0,material:0,texture:0,image:0});
    for(let previous=0;previous<i-1;previous++)assert.deepEqual(models[previous].disposed,{geometry:1,material:1,texture:1,image:1});
  }
  assert.deepEqual(cache.ids,['8','9']);
  shown.root.clear();cache.dispose();cache.dispose();
  models.forEach(entry=>assert.deepEqual(entry.disposed,{geometry:1,material:1,texture:1,image:1}));
});

test('a cached selection becomes the pinned recent car and its spare is evicted before another decode starts',async()=>{
  const shown=display(),cache=new VehicleModelCache({protectedRoots:()=>[shown.root]});
  const a=model('a'),b=model('b'),c=model('c');let reloads=0;
  await cache.select('a',async()=>a.group,shown.install);await cache.select('b',async()=>b.group,shown.install);
  await cache.select('a',async()=>{throw new Error('cached car was reloaded');},shown.install);
  await cache.select('c',async()=>{assert.equal(cache.size,1);assert.equal(a.disposed.texture,0);assert.equal(b.disposed.texture,1);return c.group;},shown.install);
  await cache.select('b',async()=>{reloads++;return model('fresh-b').group;},shown.install);
  assert.equal(reloads,1);assert.deepEqual(cache.ids,['c','b']);
  shown.root.clear();cache.dispose();
});

test('rapid changes load serially, skip obsolete queued cars, and release late data before starting the final car',async()=>{
  const shown=display(),cache=new VehicleModelCache({protectedRoots:()=>[shown.root]});
  const current=model('current');await cache.select('current',async()=>current.group,shown.install);await settle();
  const a=model('a'),c=model('c'),pending=deferred<THREE.Group>(),started:string[]=[];
  const first=cache.select('a',()=>{started.push('a');return pending.promise;},shown.install);await settle();
  const skipped=cache.select('b',async()=>{started.push('b');return model('b').group;},shown.install);
  const last=cache.select('c',async()=>{started.push('c');assert.equal(a.disposed.image,1);return c.group;},shown.install);
  assert.equal(await first,false);assert.equal(await skipped,false);assert.deepEqual(started,['a']);
  assert.equal(current.disposed.geometry,0);assert.equal(shown.root.children[0].name,'current');
  pending.resolve(a.group);assert.equal(await last,true);assert.deepEqual(started,['a','c']);
  assert.equal(shown.root.children[0].name,'c');assert.equal(cache.size,2);
  shown.root.clear();cache.dispose();
});

test('same-ID in-flight requests share one load and only the latest selection installs',async()=>{
  const cache=new VehicleModelCache(),pending=deferred<THREE.Group>(),a=model('a');let loads=0,obsoleteInstalls=0,currentInstalls=0;
  const first=cache.select('a',()=>{loads++;return pending.promise;},()=>obsoleteInstalls++);
  const second=cache.select('a',async()=>{loads++;throw new Error('duplicate load');},()=>currentInstalls++);
  pending.resolve(a.group);assert.equal(await first,false);assert.equal(await second,true);
  assert.equal(loads,1);assert.equal(obsoleteInstalls,0);assert.equal(currentInstalls,1);assert.equal(a.disposed.texture,0);
  await cache.select('a',async()=>{loads++;return model('unexpected').group;},()=>currentInstalls++);
  assert.equal(loads,1);assert.equal(cache.size,1);cache.dispose();assert.equal(a.disposed.image,1);
});

test('selecting the current cached car cancels a different pending selection without damaging its clone',async()=>{
  const shown=display(),cache=new VehicleModelCache({protectedRoots:()=>[shown.root]}),a=model('a'),late=model('late'),pending=deferred<THREE.Group>();
  await cache.select('a',async()=>a.group,shown.install);await settle();
  const loading=cache.select('late',()=>pending.promise,shown.install);await settle();
  assert.equal(await cache.select('a',async()=>a.group,shown.install),true);
  assert.equal(await loading,false);pending.resolve(late.group);await settle();
  assert.deepEqual(cache.ids,['a']);assert.equal(a.disposed.texture,0);assert.equal(late.disposed.texture,1);
  assert.equal((shown.root.children[0].children[0] as THREE.Mesh).material,a.material);
  shown.root.clear();cache.dispose();
});

test('stale load failures cannot reject the latest car, while a current failure preserves the displayed model',async()=>{
  const shown=display(),cache=new VehicleModelCache({protectedRoots:()=>[shown.root]}),a=model('a');
  await cache.select('a',async()=>a.group,shown.install);await settle();
  const pending=deferred<THREE.Group>(),stale=cache.select('stale',()=>pending.promise,shown.install);await settle();
  const next=cache.select('next',async()=>model('next').group,shown.install);
  pending.reject(new Error('obsolete download'));assert.equal(await stale,false);assert.equal(await next,true);
  await assert.rejects(cache.select('bad',async()=>{throw new Error('current download');},shown.install),/current download/);
  assert.equal(shown.root.children[0].name,'next');assert.equal(cache.activeId,'next');
  shown.root.clear();cache.dispose();
});

test('a failed installation releases the new asset and keeps the current template and live clone',async()=>{
  const shown=display(),cache=new VehicleModelCache({protectedRoots:()=>[shown.root]}),a=model('a'),bad=model('bad');
  await cache.select('a',async()=>a.group,shown.install);
  await assert.rejects(cache.select('bad',async()=>bad.group,()=>{throw new Error('missing wheels');}),/missing wheels/);
  assert.deepEqual(cache.ids,['a']);assert.equal(shown.root.children[0].name,'a');assert.equal(a.disposed.geometry,0);
  assert.deepEqual(bad.disposed,{geometry:1,material:1,texture:1,image:1});
  shown.root.clear();cache.dispose();
});

test('different cached clones sharing all resources do not release them until the last owner is evicted',async()=>{
  const shared=model('a'),b=shared.group.clone(true),shown=display(),cache=new VehicleModelCache({protectedRoots:()=>[shown.root]});b.name='b';
  await cache.select('a',async()=>shared.group,shown.install);await cache.select('b',async()=>b,shown.install);
  await cache.select('c',async()=>model('c').group,shown.install);assert.equal(shared.disposed.material,0);
  assert.equal(shared.disposed.image,0);
  await cache.select('d',async()=>model('d').group,shown.install);
  assert.deepEqual(shared.disposed,{geometry:1,material:1,texture:1,image:1});
  shown.root.clear();cache.dispose();
});

test('separate textures sharing one image close that image only after both textures are unused',async()=>{
  const a=model('a'),b=model('b');b.texture.source=a.texture.source;
  const cache=new VehicleModelCache();
  await cache.select('a',async()=>a.group,()=>{});await cache.select('b',async()=>b.group,()=>{});
  await cache.select('c',async()=>model('c').group,()=>{});
  assert.equal(a.disposed.texture,1);assert.equal(a.disposed.image,0);assert.equal(b.disposed.texture,0);
  await cache.select('d',async()=>model('d').group,()=>{});
  assert.equal(b.disposed.texture,1);assert.equal(a.disposed.image,1);cache.dispose();
});

test('traffic prototype resources and external environment images remain borrowed, including shader texture uniforms',async()=>{
  const traffic=model('traffic'),environment=model('environment'),owned=model('owned');
  const shader=new THREE.ShaderMaterial({uniforms:{reflections:{value:{layers:[environment.texture]}}}});let shaderDisposed=0;shader.addEventListener('dispose',()=>shaderDisposed++);
  owned.material.envMap=environment.texture;
  owned.group.add(traffic.group.clone(true));owned.group.add(new THREE.Mesh(owned.geometry,[owned.material,shader]));
  const cache=new VehicleModelCache({protectedRoots:()=>[traffic.group],protectedResources:()=>[environment.texture]});
  await cache.select('owned',async()=>owned.group,()=>{});
  await cache.select('b',async()=>model('b').group,()=>{});await cache.select('c',async()=>model('c').group,()=>{});
  assert.deepEqual(owned.disposed,{geometry:1,material:1,texture:1,image:1});assert.equal(shaderDisposed,1);
  assert.deepEqual(traffic.disposed,{geometry:0,material:0,texture:0,image:0});assert.equal(environment.disposed.texture,0);assert.equal(environment.disposed.image,0);
  cache.dispose();
});

test('borrowed vehicle selection supersedes pending detail and never adopts or disposes traffic geometry',async()=>{
  const proxy=model('proxy'),shown=display(),cache=new VehicleModelCache({protectedRoots:()=>[proxy.group,shown.root]}),late=model('late'),pending=deferred<THREE.Group>();
  const loading=cache.select('late',()=>pending.promise,shown.install);await settle();
  assert.equal(cache.selectBorrowed(proxy.group,shown.install),true);assert.equal(await loading,false);
  pending.resolve(late.group);await settle();assert.equal(late.disposed.geometry,1);assert.equal(cache.size,0);
  cache.dispose();assert.equal(proxy.disposed.geometry,0);assert.equal(shown.root.children[0].name,'proxy');
});

test('disposing while loading resolves waiters and releases late resources exactly once',async()=>{
  const cache=new VehicleModelCache(),pending=deferred<THREE.Group>(),late=model('late');let installed=false;
  const request=cache.select('late',()=>pending.promise,()=>{installed=true;});await settle();
  cache.dispose();cache.dispose();assert.equal(await request,false);
  pending.resolve(late.group);await settle();assert.equal(installed,false);assert.deepEqual(late.disposed,{geometry:1,material:1,texture:1,image:1});
  assert.equal(cache.size,0);await assert.rejects(cache.select('new',async()=>model('new').group,()=>{}),/disposed/);
});

test('World.setCar validates the rig before replacing the car and keeps duplicate current requests on the same instance',async()=>{
  const originalLoad=GLTFLoader.prototype.loadAsync,originalDispose=DRACOLoader.prototype.dispose;
  const first=CARS.find(c=>c.id in assets)!,second=CARS.find(c=>c.id!==first.id && c.id in assets)!;
  const good=model(first.id,true),bad=model(second.id,false);let loads=0,decodersDisposed=0;
  GLTFLoader.prototype.loadAsync=async function(url){loads++;return {scene:url===(assets as Record<string,{file:string}>)[first.id].file?good.group:bad.group} as GLTF;};
  DRACOLoader.prototype.dispose=function(){decodersDisposed++;return this;};
  const world=Object.create(World.prototype) as World;
  Object.assign(world,{car:new THREE.Group(),scene:new THREE.Scene(),models:new Map(),selectedCar:first});
  const cache=new VehicleModelCache({protectedRoots:()=>[world.car]});Object.assign(world,{detailedModels:cache});
  try{
    assert.equal(await world.setCar(first),true);const instance=world.car.children[0];
    assert.equal(await world.setCar(first),true);assert.equal(world.car.children[0],instance);assert.equal(loads,1);
    await assert.rejects(world.setCar(second),/四轮结构/);
    assert.equal(world.selectedCar.id,first.id);assert.equal(world.car.children[0],instance);
    assert.equal(good.disposed.texture,0);assert.equal(bad.disposed.texture,1);assert.equal(decodersDisposed,2);
  }finally{GLTFLoader.prototype.loadAsync=originalLoad;DRACOLoader.prototype.dispose=originalDispose;world.car.clear();cache.dispose();}
});
