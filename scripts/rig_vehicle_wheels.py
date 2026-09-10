"""Partition connected exterior components without cutting body panels.

All source faces, UVs, corner colors and materials survive. Only hierarchy and
origins change. Blender +Y is forward; GLB +Y is up and -Z is forward.
"""
import bpy, bmesh, math
from mathutils import Matrix, Vector

def rig_wheels(objects):
 vertices=[];parent=[];weld={};indices={}
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 for o in objects:
  # Exterior preparation has normalized geometry into world metres already.
  transform=o.matrix_world.copy();o.parent=None;o.matrix_world=Matrix.Identity(4)
  o.data.transform(transform);o.data.update()
  ids=[]
  for v in o.data.vertices:
   p=v.co;k=tuple(round(t,5) for t in p)
   if k not in weld:weld[k]=len(vertices);vertices.append(tuple(p));parent.append(len(parent))
   ids.append(weld[k])
  indices[o]=ids
  for p in o.data.polygons:
   a=find(ids[p.vertices[0]])
   for j in p.vertices[1:]:parent[find(ids[j])]=a
 comps={}
 for i,p in enumerate(vertices):comps.setdefault(find(i),[]).append(p)
 boxes={}
 for key,pts in comps.items():
  lo=[min(p[i] for p in pts) for i in range(3)];hi=[max(p[i] for p in pts) for i in range(3)]
  boxes[key]=dict(lo=lo,hi=hi,center=[(a+b)/2 for a,b in zip(lo,hi)],size=[b-a for a,b in zip(lo,hi)])
 candidates={}
 for key,b in boxes.items():
  x,y,z=b['center'];sx,sy,sz=b['size']
  if abs(x)>.5 and abs(y)>.9 and .55<sy<.9 and .55<sz<.9 and abs(sy-sz)<.04 and .1<sx<.42 and b['hi'][2]<.9:
   name=('F' if y>0 else 'R')+('L' if x<0 else 'R')
   if name not in candidates or sz>candidates[name]['size'][2]:candidates[name]=b
 assert len(candidates)==4,('Four complete tires required',candidates)
 assignments={};pivots={};rolls={};stats={};new=[]
 for name,b in candidates.items():
  center=Vector(b['center']);radius=max(b['size'][1:])/2
  pivot=bpy.data.objects.new('Wheel_'+name,None);bpy.context.collection.objects.link(pivot);pivot.location=center
  pivot['wheelPosition']=name;pivot['wheelRadius']=radius;pivot['frontWheel']=name.startswith('F')
  roll=bpy.data.objects.new('WheelRoll_'+name,None);bpy.context.collection.objects.link(roll);roll.parent=pivot
  pivots[name]=pivot;rolls[name]=roll;new.extend([pivot,roll]);stats[name]={'centerBlender':list(center),'radius':radius,'triangles':0,'components':0}
  for key,points in comps.items():
   box=boxes[key]
   # Whole connected pieces must fit the tire cylinder. Wheel arches, bumpers
   # and sills extend outside this cylinder and remain attached to the body.
   if all(abs(p[0]-center.x)<max(.24,b['size'][0]/2+.05) and math.hypot(p[1]-center.y,p[2]-center.z)<radius+.018 for p in points):
    assignments[key]=name;stats[name]['components']+=1
 before=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objects)
 for o in objects:
  ids=indices[o];groups={}
  for p in o.data.polygons:
   name=assignments.get(find(ids[p.vertices[0]]),'body');groups.setdefault(name,set()).add(p.index)
  for name,keep in groups.items():
   mesh=o.data.copy();bm=bmesh.new();bm.from_mesh(mesh);bm.faces.ensure_lookup_table()
   bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.index not in keep],context='FACES')
   bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
   bm.to_mesh(mesh);bm.free();mesh.update()
   part=bpy.data.objects.new(o.name+'_'+name,mesh);bpy.context.collection.objects.link(part)
   if name!='body':
    center=pivots[name].location;mesh.transform(Matrix.Translation(-center))
    # Explicit caliper materials steer with the upright but do not roll.
    mats=' '.join(m.name.lower() for m in mesh.materials if m)
    part.parent=pivots[name] if 'caliper' in mats and len(groups)==1 else rolls[name]
    stats[name]['triangles']+=sum(len(p.vertices)-2 for p in mesh.polygons)
   new.append(part)
  bpy.data.objects.remove(o,do_unlink=True)
 after=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in new if o.type=='MESH')
 assert before==after,('Rig changed geometry',before,after)
 assert all(w['triangles']>1000 for w in stats.values()),stats
 return new,stats

def write_rig_manifest(root):
 """Rebuild the derived 13-asset inventory after either conversion entrypoint."""
 import json, hashlib, struct
 folder=root/'public/vehicles/rigged';records=[]
 for car in ['su7','model-3','dolphin']:
  file=folder/(car+'-quality.json')
  if file.exists():
   record=json.loads(file.read_text());record.update(file='/vehicles/rigged/'+car+'.glb',type='licensed-exterior');records.append(record)
 prototype_manifest=folder/'prototypes/manifest.json'
 if prototype_manifest.exists():records+=json.loads(prototype_manifest.read_text())
 for record in records:
  raw=(root/'public'/record['file'].lstrip('/')).read_bytes()
  gltf=json.loads(raw[20:20+struct.unpack_from('<I',raw,12)[0]])
  nodes=gltf['nodes'];wheels=[n for n in nodes if n.get('name') in ['Wheel_FL','Wheel_FR','Wheel_RL','Wheel_RR']]
  assert len(wheels)==4
  for wheel in wheels:
   position=wheel['extras']['wheelPosition']
   assert wheel['extras']['frontWheel']==position.startswith('F')
   assert wheel['extras']['wheelRadius']>.2
   assert any(nodes[i].get('name')=='WheelRoll_'+position for i in wheel.get('children',[]))
  assert record['rigFacesBefore']==record['rigFacesAfter']
  record['rigValidation']={'fourWheelPivots':True,'faceCountPreserved':True,'minimumWheelTriangles':min(w['triangles'] for w in record['wheelRig'].values()),'runtimeSha256':hashlib.sha256(raw).hexdigest()}
 manifest={'schemaVersion':1,'coordinateConvention':'glTF Y up, -Z forward. Wheel pivots steer around +Y; WheelRoll children roll around +X.','qualityPolicy':'Individual average below 10 MB; geometry preserved when rigging; licensed exteriors and procedural prototypes labelled separately.','models':records}
 (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')

def review_exported_wheels():
 """Render the actual exported assets at front and steered-wheel angles.

 This leaves source files and editable projects untouched. Render evidence is
 kept beside the new rigged GLBs, never in the user's temporary-image folder.
 """
 import pathlib, json
 root=pathlib.Path(__file__).resolve().parents[1]
 out=root/'public/vehicles/rigged/review';out.mkdir(exist_ok=True)
 report=[]
 for car in ['su7','model-3','dolphin']:
  bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
  bpy.ops.import_scene.gltf(filepath=str(root/'public/vehicles/rigged'/(car+'.glb')))
  wheels=[o for o in bpy.context.scene.objects if o.name.startswith('Wheel_')]
  rolls=[o for o in bpy.context.scene.objects if o.name.startswith('WheelRoll_')]
  assert len(wheels)==len(rolls)==4
  body=[o for o in bpy.context.scene.objects if o.type=='MESH' and not any(p in wheels+rolls for p in [o.parent,o.parent.parent if o.parent else None])]
  original_body={o.name:[tuple(o.matrix_world@v.co) for v in o.data.vertices] for o in body}
  # Imported glTF axes are converted back to Blender +Y forward / Z up.
  for w in wheels:
   if w.get('frontWheel'):w.rotation_euler.z=math.radians(25)
  for r in rolls:r.rotation_euler.x=math.radians(60)
  bpy.context.view_layer.update()
  assert all(original_body[o.name]==[tuple(o.matrix_world@v.co) for v in o.data.vertices] for o in body)
  for w in wheels:w.rotation_euler.z=0
  for r in rolls:r.rotation_euler.x=0
  scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.use_denoising=True
  scene.render.resolution_x=1000;scene.render.resolution_y=700;scene.render.resolution_percentage=100
  scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
  scene.world.use_nodes=True;nt=scene.world.node_tree;nt.nodes.clear()
  bg=nt.nodes.new('ShaderNodeBackground');bg.inputs['Color'].default_value=(.48,.52,.57,1);bg.inputs['Strength'].default_value=.5
  output=nt.nodes.new('ShaderNodeOutputWorld');nt.links.new(bg.outputs['Background'],output.inputs['Surface'])
  for location,power,size in [((2,4,6),900,5),((-5,0,4),1000,4),((2,-4,5),900,4)]:
   data=bpy.data.lights.new('Review softbox','AREA');data.energy=power;data.shape='DISK';data.size=size
   obj=bpy.data.objects.new('Review softbox',data);bpy.context.collection.objects.link(obj);obj.location=location;obj.rotation_euler=(-obj.location).to_track_quat('-Z','Y').to_euler()
  bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.015));floor=bpy.context.object
  mat=bpy.data.materials.new('Review ground');mat.use_nodes=True;p=mat.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(.1,.12,.14,1);p.inputs['Roughness'].default_value=.8;floor.data.materials.append(mat)
  data=bpy.data.cameras.new('Wheel rig review');cam=bpy.data.objects.new('Wheel rig review',data);bpy.context.collection.objects.link(cam);scene.camera=cam;data.lens=56
  for view,location in [('front',(6.4,8.5,3.4)),('steered',(8.0,4.0,1.8)),('rear',(-6.4,-8.5,3.4))]:
   for w in wheels:w.rotation_euler.z=math.radians(25) if w.get('frontWheel') and view=='steered' else 0
   for r in rolls:r.rotation_euler.x=math.radians(60) if view=='steered' else 0
   cam.location=location;cam.rotation_euler=(Vector((0,0,.75))-cam.location).to_track_quat('-Z','Y').to_euler()
   scene.render.filepath=str(out/(car+'-'+view+'.png'));bpy.ops.render.render(write_still=True)
  report.append({'car':car,'fourWheels':True,'bodyStationaryWhenWheelsMove':True,'frontSteeringDegrees':25,'rollingDegrees':60,'views':['front','steered','rear']})
 (out/'geometry-review.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':
 import sys
 if '--review' in sys.argv:review_exported_wheels()
