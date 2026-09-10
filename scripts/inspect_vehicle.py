import bpy,pathlib,json,sys
from mathutils import Vector
ROOT=pathlib.Path(__file__).resolve().parents[1]
args=sys.argv[sys.argv.index('--')+1:];path=pathlib.Path(args[0]);bpy.context.preferences.filepaths.use_scripts_auto_execute=False
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
if path.suffix.lower()=='.glb' or path.suffix.lower()=='.gltf':bpy.ops.import_scene.gltf(filepath=str(path))
elif path.suffix.lower()=='.fbx':bpy.ops.import_scene.fbx(filepath=str(path))
elif path.suffix.lower()=='.obj':bpy.ops.wm.obj_import(filepath=str(path))
else:raise ValueError('Use a static GLB, glTF, FBX or OBJ file')
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];points=[o.matrix_world@Vector(v) for o in meshes for v in o.bound_box]
result={'file':str(path),'min':[min(v[i] for v in points) for i in range(3)],'max':[max(v[i] for v in points) for i in range(3)],'objects':[{'name':o.name,'dimensions':list(o.dimensions),'location':list(o.location),'triangles':sum(len(p.vertices)-2 for p in o.data.polygons),'materials':[m.name for m in o.data.materials if m]} for o in meshes],'materials':[{'name':m.name,'base':list(m.diffuse_color),'nodes':[{'type':n.type,'image':n.image.filepath if n.type=='TEX_IMAGE' and n.image else None} for n in m.node_tree.nodes] if m.use_nodes else []} for m in bpy.data.materials]}
output=pathlib.Path(args[1]) if len(args)>1 else ROOT/'assets/vehicles/source/su7/inspection.json'
output.write_text(json.dumps(result,indent=2));print(json.dumps({k:result[k] for k in ['min','max']},indent=2));print('OBJECTS',len(meshes),'TRIANGLES',sum(x['triangles'] for x in result['objects']))
