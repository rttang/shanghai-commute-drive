import bpy,pathlib
from mathutils import Vector,Matrix
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'assets/vehicles/source/su7'
bpy.context.preferences.filepaths.use_scripts_auto_execute=False
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(OUT/'sketchfab-official.glb'))
objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
for o in objects:
 matrix=o.matrix_world.copy();o.data=o.data.copy();o.data.transform(matrix);o.parent=None;o.matrix_world=Matrix.Identity(4)
points=[v.co for o in objects for v in o.data.vertices]
lo=[min(p[i] for p in points) for i in range(3)];hi=[max(p[i] for p in points) for i in range(3)];scale=4.997/(hi[1]-lo[1])
for o in objects:
 for v in o.data.vertices:
  v.co.x*=scale;v.co.y=(v.co.y-(lo[1]+hi[1])/2)*scale;v.co.z=(v.co.z-lo[2])*scale
import json
r=[]
for o in objects:
 ps=[v.co for v in o.data.vertices];mn=[round(min(v[i] for v in ps),2) for i in range(3)];mx=[round(max(v[i] for v in ps),2) for i in range(3)]
 r.append({'name':o.name,'min':mn,'max':mx,'triangles':len(o.data.polygons),'material':o.data.materials[0].name})
(OUT/'normalized-parts.json').write_text(json.dumps(r,indent=2))
