"""Give the ten existing procedural prototypes independent wheel pivots.

The original tour-models GLBs are immutable input. This is a rig-only conversion,
not a claim that these procedural bodies match photographed production vehicles.
"""
import bpy, json, pathlib, sys, hashlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from rig_vehicle_wheels import rig_wheels, write_rig_manifest

OUT = ROOT / 'public/vehicles/rigged/prototypes'
OUT.mkdir(parents=True, exist_ok=True)
bpy.context.preferences.filepaths.use_scripts_auto_execute = False
bpy.context.preferences.filepaths.temporary_directory = str(ROOT / '.tooling/blender/tmp') + '/'
cars = json.loads((ROOT / 'src/tour/cars.json').read_text())
records = []
for car in cars:
    name = car['id']
    source = ROOT / 'public/tour-models' / (name + '.glb')
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(source))
    objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    before = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objects)
    objects, wheels = rig_wheels(objects)
    after = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objects if o.type == 'MESH')
    assert before == after
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    dest = OUT / (name + '.glb')
    bpy.ops.export_scene.gltf(filepath=str(dest), export_format='GLB', use_selection=True,
        export_apply=True, export_extras=True, export_draco_mesh_compression_enable=True,
        export_draco_mesh_compression_level=6, export_draco_position_quantization=18,
        export_draco_normal_quantization=14, export_draco_texcoord_quantization=16)
    bpy.ops.file.pack_all()
    editable = ROOT / 'assets/blender/tourism' / (name + '-prototype-wheels.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(editable))
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    record = dict(car=name, type='procedural-prototype', fidelity='Not a verified production-car reconstruction',
        sourceFile=str(source.relative_to(ROOT)), sourceSha256=source_hash,
        file='/' + str(dest.relative_to(ROOT / 'public')), editable=str(editable.relative_to(ROOT)),
        runtimeBytes=dest.stat().st_size, sourceTriangles=before, runtimeTriangles=after,
        rigFacesBefore=before, rigFacesAfter=after, wheelRig=wheels)
    records.append(record)
    print('PROTOTYPE_READY', json.dumps(record), flush=True)
(OUT / 'manifest.json').write_text(json.dumps(records, indent=2))
write_rig_manifest(ROOT)
