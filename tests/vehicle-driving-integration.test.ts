import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import type {City} from '../src/tour/data';
import {CollisionWorld,type Obstacle} from '../src/tour/collision';
import {fleetControlIntegration,integratedFrameComparison,tunnelSupportIntegration} from '../scripts/verify_vehicle_driving_integration';

const route=(JSON.parse(readFileSync(new URL('../public/tour-city.json',import.meta.url),'utf8')) as City).routes[0];
test('all ten profiles flow through Drive manual while auto and reset behavior stay stable',()=>{
  assert.equal(fleetControlIntegration(route).length,10);
});
test('actual Drive pose agrees at 10/20/60 Hz and dropped frames with full-width forward and reverse steering',()=>{
  assert.equal(integratedFrameComparison(route).length,80);
});
test('Turbo S at 80 km/h and reverse keep the actual tunnel support layer with a wide vehicle',()=>{
  const obstacles=JSON.parse(readFileSync(new URL('../public/streets/collisions.json',import.meta.url),'utf8')).obstacles as Obstacle[];
  assert.equal(tunnelSupportIntegration(route,new CollisionWorld(obstacles)).length,114);
});
