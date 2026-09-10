import bpy,pathlib,json
ROOT=pathlib.Path(__file__).resolve().parents[1];results=[]
for item in json.loads((ROOT/'public/models/manifest.json').read_text()):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(ROOT/'public/models'/item['file']))
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    assert meshes and sum(len(o.data.vertices) for o in meshes)>0,item['id']
    coords=[o.matrix_world@__import__('mathutils').Vector(p) for o in meshes for p in o.bound_box]
    bounds=[round(max(p[i] for p in coords)-min(p[i] for p in coords),3) for i in range(3)]
    assert all(v>0 for v in bounds),(item['id'],bounds)
    results.append({'id':item['id'],'meshes':len(meshes),'dimensions':bounds,'reimport':'passed'})
(ROOT/'docs/evidence/models.json').write_text(json.dumps(results,indent=2));print('REIMPORT_PASS',len(results),flush=True)
