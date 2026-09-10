"""Prepare the CC-BY Car2022 SU7 mesh. Preserve its modeled panels and texture UVs."""
import bpy,bmesh,math,json,pathlib,shutil
from mathutils import Vector,Matrix
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'public/vehicles';OUT.mkdir(exist_ok=True)
SRC=ROOT/'assets/vehicles/source/su7/source/unpacked/source/SU7.glb'
bpy.context.preferences.filepaths.use_scripts_auto_execute=False
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);bpy.ops.import_scene.gltf(filepath=str(SRC))
objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
source_triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objects)
source_meshes=len(objects)
# Bake node transforms before measuring; imported node dimensions are in mixed axes.
for o in objects:
    matrix=o.matrix_world.copy();o.data=o.data.copy();o.data.transform(matrix);o.parent=None;o.matrix_world=Matrix.Identity(4)
for o in list(bpy.context.scene.objects):
    if o not in objects:bpy.data.objects.remove(o,do_unlink=True)
points=[v.co for o in objects for v in o.data.vertices];lo=[min(p[i] for p in points) for i in range(3)];hi=[max(p[i] for p in points) for i in range(3)]
wheel=next(o for o in objects if o.name.startswith('Wheel'))
axles=[]
for side in [-1,1]:
    ps=[v.co.y for v in wheel.data.vertices if v.co.y*side>0];axles.append((min(ps)+max(ps))/2)
print('SOURCE_BOUNDS',lo,hi,'AXLES',axles,flush=True)
# Match physical wheelbase and overhangs with three linear intervals, not a whole-car stretch.
center=sum(axles)/2;rear,front=axles
src_y=[lo[1],rear,front,hi[1]];half=4.997/2;tgt_y=[-half,-1.5,1.5,half]
def remap(y):
    for i in range(3):
        if y<=src_y[i+1]:return tgt_y[i]+(y-src_y[i])/(src_y[i+1]-src_y[i])*(tgt_y[i+1]-tgt_y[i])
    return tgt_y[-1]
for o in objects:
    for v in o.data.vertices:v.co.x*=1.963/1.966;v.co.y=remap(v.co.y);v.co.z=(v.co.z-lo[2])*1.46/(hi[2]-lo[2])
# Exterior-only runtime asset: remove seats, dashboard and door upholstery by
# their source material assignment, preserving trim, lamps and exterior panels.
removed=[]
for o in list(objects):
    interior={i for i,m in enumerate(o.data.materials) if m and m.name.startswith('interior')}
    if not interior:continue
    bm=bmesh.new();bm.from_mesh(o.data)
    faces=[f for f in bm.faces if f.material_index in interior]
    removed.append({'object':o.name,'triangles':sum(len(f.verts)-2 for f in faces)})
    bmesh.ops.delete(bm,geom=faces,context='FACES')
    bm.to_mesh(o.data);bm.free()
    if not o.data.polygons:
        objects.remove(o);bpy.data.objects.remove(o,do_unlink=True)
    else:
        bpy.context.view_layer.objects.active=o
        bpy.ops.object.material_slot_remove_unused()
# Small badges have disproportionate tessellation. Keep body/wheel geometry
# intact; simplify only the badge object and preserve its material boundaries.
logo=next((o for o in objects if o.name=='logo3'),None)
if logo:
    bpy.context.view_layer.objects.active=logo
    dec=logo.modifiers.new('Small badge optimization','DECIMATE');dec.ratio=.35;dec.delimit={'MATERIAL','SEAM'}
    bpy.ops.object.modifier_apply(modifier=dec.name)
# The source is a 2024 exterior. Calibration does not claim to create missing 2026 trim details.
body=bpy.data.materials.get('Car_body');p=body.node_tree.nodes.get('Principled BSDF')
for link in list(p.inputs['Base Color'].links):body.node_tree.links.remove(link)
color=[(int('72afb5'[i:i+2],16)/255)**2.2 for i in [0,2,4]]
p.inputs['Base Color'].default_value=(*color,1);p.inputs['Metallic'].default_value=.72;p.inputs['Roughness'].default_value=.24;p.inputs['Coat Weight'].default_value=1;p.inputs['Coat Roughness'].default_value=.12
for mat in bpy.data.materials:
    if mat.name in ['Car_window','Car_lightglass']:
        p=mat.node_tree.nodes.get('Principled BSDF')
        if p:
            p.inputs['Roughness'].default_value=.10;p.inputs['Metallic'].default_value=.05
            p.inputs['Transmission Weight'].default_value=0
            p.inputs['Coat Weight'].default_value=1
            p.inputs['Alpha'].default_value=1 if mat.name=='Car_window' else .12
            if mat.name=='Car_window':
                p.inputs['Base Color'].default_value=(.009,.015,.019,1)
                p.inputs['Metallic'].default_value=.3
            else:
                p.inputs['Base Color'].default_value=(.96,.96,.96,1)
                mat.surface_render_method='DITHERED'
            p.inputs['IOR'].default_value=1.46
# Only wheel textures remain in the exterior material set. 1K keeps lettering
# and spoke shading at driving/inspection distance without 4K interior atlases.
for mat in {m for o in objects for m in o.data.materials if m}:
    if not mat.use_nodes:continue
    for node in mat.node_tree.nodes:
        if node.type=='TEX_IMAGE' and node.image and max(node.image.size)>1024:
            im=node.image;ratio=1024/max(im.size);im.scale(round(im.size[0]*ratio),round(im.size[1]*ratio))
root=bpy.data.objects.new('su7-car2022-calibrated',None);bpy.context.collection.objects.link(root)
for o in objects:o.parent=root
bpy.ops.object.select_all(action='DESELECT');root.select_set(True)
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=root
bpy.ops.export_scene.gltf(filepath=str(OUT/'su7.glb'),export_format='GLB',use_selection=True,export_apply=True,export_extras=True,export_image_format='JPEG',export_jpeg_quality=86,export_draco_mesh_compression_enable=True,export_draco_mesh_compression_level=6,export_draco_position_quantization=16,export_draco_normal_quantization=12,export_draco_texcoord_quantization=14)
# Ship a local decoder so selecting the vehicle never contacts a CDN.
decoder=ROOT/'public/decoders/draco';decoder.mkdir(parents=True,exist_ok=True)
for file in ['draco_wasm_wrapper.js','draco_decoder.wasm','draco_decoder.js']:
    shutil.copy2(ROOT/'node_modules/three/examples/jsm/libs/draco/gltf'/file,decoder/file)
editable=ROOT/'assets/blender/tourism/su7-detailed.blend';bpy.ops.wm.save_as_mainfile(filepath=str(editable))
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True
scene.render.resolution_x=1200;scene.render.resolution_y=780;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.film_transparent=True
scene.world.use_nodes=True;nt=scene.world.node_tree;nt.nodes.clear();env=nt.nodes.new('ShaderNodeTexEnvironment');env.image=bpy.data.images.load(str(ROOT/'public/environment/sky.hdr'));bg=nt.nodes.new('ShaderNodeBackground');bg.inputs['Strength'].default_value=.5;output=nt.nodes.new('ShaderNodeOutputWorld');nt.links.new(env.outputs['Color'],bg.inputs['Color']);nt.links.new(bg.outputs['Background'],output.inputs['Surface'])
for location,power,size in [((2,4,6),950,5),((-5,0,4),1100,4),((2,-4,5),950,4)]:
    data=bpy.data.lights.new('Studio softbox','AREA');data.energy=power;data.shape='DISK';data.size=size;o=bpy.data.objects.new('Studio softbox',data);bpy.context.collection.objects.link(o);o.location=location;o.rotation_euler=(-o.location).to_track_quat('-Z','Y').to_euler()
camdata=bpy.data.cameras.new('Vehicle reference');cam=bpy.data.objects.new('Vehicle reference',camdata);bpy.context.collection.objects.link(cam);scene.camera=cam;camdata.lens=56
for name,location in [('front',(6.4,8.5,3.4)),('rear',(-6.4,-8.5,3.4)),('side',(9.5,0,2.0))]:
    cam.location=location;cam.rotation_euler=(Vector((0,0,.75))-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(OUT/f'su7-{name}.png');bpy.ops.render.render(write_still=True)
(OUT/'su7-quality.json').write_text(json.dumps({'car':'su7','sourceTriangles':source_triangles,'sourceMeshes':source_meshes,'runtimeTriangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objects),'runtimeMeshes':len(objects),'runtimeBytes':(OUT/'su7.glb').stat().st_size,'budgetBytes':3000000,'textureMaxSize':1024,'removedInterior':removed,'sourceAxles':axles,'bodyCalibrationMM':[4997,1963,1460],'wheelbaseMM':3000,'sourceYear':2024,'scope':'Exterior only; alternate model years accepted by user','source':'https://sketchfab.com/3d-models/xiaomi-su7-ca2cda599f5341068c992c9f44551bf9','license':'CC-BY-4.0','author':'Mona x Supercars (Car2022)','changes':['Metre scale and wheelbase calibration','Bay blue PBR paint','Removed interior upholstery, seats and dashboard','Reflective opaque glazing; transparent lamp covers without refraction pass','1K exterior textures and Draco geometry compression','Small badge simplification; body panels and wheels preserved']},indent=2))
print('DETAILED_SU7_READY',flush=True)
