"""Read geometry components; keep source meshes untouched. Blender entrypoint."""
import bpy, pathlib, json
from mathutils import Vector
ROOT=pathlib.Path(__file__).resolve().parents[1]
report={}
for car in ['su7','model-3','dolphin','starwish']:
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 source=ROOT/('public/tour-models' if car=='starwish' else 'public/vehicles')/(car+'.glb')
 bpy.ops.import_scene.gltf(filepath=str(source))
 vertices=[];parent=[];faces=[];weld={}
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 for o in bpy.context.scene.objects:
  if o.type!='MESH':continue
  ids=[]
  for v in o.data.vertices:
   p=o.matrix_world@v.co;k=tuple(round(t,5) for t in p)
   if k not in weld:weld[k]=len(vertices);vertices.append(tuple(p));parent.append(len(parent))
   ids.append(weld[k])
  for p in o.data.polygons:
   a=find(ids[p.vertices[0]])
   for j in p.vertices[1:]:parent[find(ids[j])]=a
 comps={}
 for i,p in enumerate(vertices):comps.setdefault(find(i),[]).append(p)
 items=[]
 for pts in comps.values():
  if len(pts)<16:continue
  lo=[min(p[i] for p in pts) for i in range(3)];hi=[max(p[i] for p in pts) for i in range(3)]
  items.append(dict(vertices=len(pts),lo=lo,hi=hi,center=[(a+b)/2 for a,b in zip(lo,hi)],size=[b-a for a,b in zip(lo,hi)]))
 items.sort(key=lambda x:-x['vertices']);report[car]=items
 print('PARTS',car,json.dumps([x for x in items if x['hi'][2]<.95 and abs(x['center'][0])>.4]),flush=True)
(ROOT/'docs/evidence/tourism/wheel-components.json').write_text(json.dumps(report,indent=2))
