"""Open the delivered GLB itself and save an editable, packed Blender master."""
import bpy
import pathlib
import json
import hashlib
from mathutils import Vector
ROOT=pathlib.Path(__file__).resolve().parents[1]
source=ROOT/'public/streets/master/shanghai-streets.glb'
output=ROOT/'assets/blender/streets/shanghai-streets-master.blend'
before=hashlib.sha256(source.read_bytes()).hexdigest()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(source),import_pack_images=True)
scene=bpy.context.scene
scene.unit_settings.system='METRIC'
scene.unit_settings.scale_length=1
scene['source_glb']=str(source.relative_to(ROOT))
scene['source_sha256']=before
scene['coordinate_note']='GLB X east Y up Z south; Blender X east Y north Z up; metres'
scene['reconstruction_boundary']='Photo-informed external geometry, OSM footprints; unobserved elevations are explicitly inferred in district manifests.'
bpy.ops.object.camera_add(location=(-1500,1800,750))
camera=bpy.context.object
camera.name='Street master overview'
camera.rotation_euler=(Vector((150,0,150))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.lens=42
camera.data.clip_end=20000
scene.camera=camera
bpy.ops.object.light_add(type='SUN',location=(450,-300,450))
bpy.context.object.name='Shanghai afternoon sun'
bpy.context.object.data.energy=2.8
bpy.context.object.rotation_euler=(.6,-.4,-.7)
scene.render.engine='BLENDER_EEVEE'
scene.world.color=(.3,.4,.5)
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(output),compress=True)
assert hashlib.sha256(source.read_bytes()).hexdigest()==before
meshes={o.data for o in scene.objects if o.type=='MESH'}
result={'source':str(source.relative_to(ROOT)),'sourceSha256':before,'editable':str(output.relative_to(ROOT)),'bytes':output.stat().st_size,'objects':len(scene.objects),'uniqueMeshDatablocks':len(meshes),'packedImages':sum(bool(i.packed_file) for i in bpy.data.images),'sourceUnchanged':True}
(ROOT/'docs/evidence/tourism/street-master-blender.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('MASTER_BLEND',json.dumps(result,ensure_ascii=False),flush=True)
