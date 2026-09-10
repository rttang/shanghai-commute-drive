"""Installation smoke check: save, export, re-import and render on external disk."""
import json
import os
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'assets/blender/validation'
TMP = ROOT / '.tooling/blender/tmp'
assert os.path.ismount(ROOT.parent), 'External volume is not mounted'
OUT.mkdir(parents=True, exist_ok=True)
TMP.mkdir(parents=True, exist_ok=True)
bpy.context.preferences.filepaths.temporary_directory = str(TMP) + '/'
bpy.context.preferences.filepaths.render_output_directory = str(OUT) + '/'
bpy.ops.wm.save_userpref()

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
material = bpy.data.materials.new('Validation enamel')
material.diffuse_color = (0.035, 0.24, 0.32, 1)
material.use_nodes = True
shader = material.node_tree.nodes.get('Principled BSDF')
shader.inputs['Base Color'].default_value = material.diffuse_color
shader.inputs['Roughness'].default_value = 0.3
shader.inputs['Metallic'].default_value = 0.25
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0.7))
model = bpy.context.object
model.name = 'Blender installation validation'
model.scale = (1.5, 0.7, 0.7)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
bevel = model.modifiers.new('Rounded edges', 'BEVEL')
bevel.width = 0.14
bevel.segments = 4
model.data.materials.append(material)

model.select_set(True)
bpy.context.view_layer.objects.active = model
glb = OUT / 'installation-check.glb'
bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB',
                          use_selection=True, export_apply=True)
assert glb.stat().st_size > 1000, 'Empty GLB export'
with glb.open('rb') as stream:
    assert stream.read(4) == b'glTF', 'Invalid GLB header'
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(glb))
imported = set(bpy.data.objects) - before
imported_mesh_count = sum(obj.type == 'MESH' and len(obj.data.vertices) > 0 for obj in imported)
assert imported_mesh_count > 0
for obj in imported:
    bpy.data.objects.remove(obj, do_unlink=True)

bpy.ops.mesh.primitive_plane_add(size=200)
floor = bpy.data.materials.new('Warm ground')
floor.diffuse_color = (0.68, 0.66, 0.60, 1)
bpy.context.object.data.materials.append(floor)
bpy.ops.object.light_add(type='AREA', location=(3, -4, 6))
bpy.context.object.data.energy = 1000
bpy.context.object.data.shape = 'DISK'
bpy.context.object.data.size = 5
bpy.ops.object.camera_add(location=(4.5, -6, 4))
camera = bpy.context.object
camera.rotation_euler = (Vector((0, 0, 0.5)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
scene = bpy.context.scene
scene.camera = camera
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 16
scene.render.resolution_x = 640
scene.render.resolution_y = 480
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(OUT / 'installation-check.png')
scene.world.color = (0.25, 0.25, 0.25)
blend = OUT / 'installation-check.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
bpy.ops.render.render(write_still=True)
result = {
    'version': bpy.app.version_string,
    'binary': bpy.app.binary_path,
    'blend': str(blend), 'glb': str(glb),
    'render': scene.render.filepath,
    'glb_reimport_meshes': imported_mesh_count,
    'temporary_directory': bpy.context.preferences.filepaths.temporary_directory,
    'config_directory': bpy.utils.user_resource('CONFIG'),
    'status': 'PASS',
}
(OUT / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print('BLENDER_INSTALLATION_CHECK=' + json.dumps(result, ensure_ascii=False))
