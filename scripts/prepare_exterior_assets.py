"""Prepare licensed static car meshes for an exterior-only real-time scene.

Source archives stay untouched. Run through blender-local.sh, followed by -- car-id.
"""
import bpy, bmesh, json, math, pathlib, sys, shutil, hashlib
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / 'public/vehicles/rigged'
CAR = sys.argv[sys.argv.index('--') + 1]
CONFIG = {
    'starwish': {'file':'starwish/original.glb','length':4.135,'yaw':0,'year':2025,
                 'paint':[],'glass':[],'remove':[],'protect':[],'color':'e3d9c5','target':100000},
    'su7': {'file':'su7/sketchfab-official.glb','length':4.997,'yaw':0,'year':2024,
            'paint':['Paint1Mtl'],'glass':['Mesh26Mtl','Mesh72Mtl'],
            'remove':['Mesh13Mtl','Mesh30Mtl'],
            'protect':['Mesh61Mtl','Mesh65Mtl','Mesh68Mtl','Mesh17Mtl','Mesh19Mtl','Mesh62Mtl','Mesh71Mtl'],
            'color':'72afb5','target':90000},
    'dolphin': {'file':'dolphin/source/source/2024 BYD Dolphin.glb','length':4.290,'yaw':math.pi,'year':2024,
                'paint':[],'glass':[],'remove':[],'protect':[],'color':'bdd8df','target':110000},
    'model-3': {'file':'model-3/source/source/2024_tesla_model_3.glb','length':4.720,'yaw':math.pi/2,'year':2024,
                'paint':['Geohoodsub00021Mtl'],'glass':['Geoextwindow0021Mtl','Geodoorl2sub31Mtl','Geodoorr2sub31Mtl'],
                'remove':['Geocockpithrsub000332Mtl','Geocockpithrsub000921Mtl','Geocockpithrsub1031Mtl','Geodoorl2intsub651Mtl','Geodoorlintsub400251Mtl'],
                'protect':['Ln12Mtl','Ln1Mtl','Ln7Mtl'], 'color':'b62933','target':110000},
    'model-y': {'file':'model-y/source/scene.gltf','length':4.750,'yaw':math.pi/2,'year':2021,
                'paint':[],'glass':[],'remove':[],'protect':[], 'color':'e4e6e6','target':120000},
}
cfg=CONFIG[CAR]; source=ROOT/'assets/vehicles/source'/cfg['file']
if CAR in ['starwish','model-y']:
    OUT=ROOT/'assets/vehicles/source'/CAR/'review'
    OUT.mkdir(exist_ok=True)
bpy.context.preferences.filepaths.use_scripts_auto_execute=False
bpy.context.preferences.filepaths.temporary_directory=str(ROOT/'.tooling/blender/tmp')+'/'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(source))
objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
source_triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objects)
rotation=Matrix.Rotation(cfg['yaw'],4,'Z')
for o in objects:
    transform=rotation@o.matrix_world.copy();o.data=o.data.copy();o.data.transform(transform)
    o.parent=None;o.matrix_world=Matrix.Identity(4)
for o in list(bpy.context.scene.objects):
    if o not in objects:bpy.data.objects.remove(o,do_unlink=True)
points=[v.co for o in objects for v in o.data.vertices]
lo=[min(p[i] for p in points) for i in range(3)];hi=[max(p[i] for p in points) for i in range(3)]
scale=cfg['length']/(hi[1]-lo[1]);center=Vector(((lo[0]+hi[0])/2,(lo[1]+hi[1])/2,lo[2]))
for o in objects:
    for v in o.data.vertices:v.co=(v.co-center)*scale
    o.data.update()
    if CAR=='dolphin':
        attr=o.data.color_attributes.active_color
        if attr and attr.domain=='POINT':
            name=attr.name
            colours=[tuple(attr.data[loop.vertex_index].color) for loop in o.data.loops]
            o.data.color_attributes.remove(attr)
            attr=o.data.color_attributes.new(name=name,type='FLOAT_COLOR',domain='CORNER')
            for i,colour in enumerate(colours):attr.data[i].color=colour
            o.data.color_attributes.active_color=attr
        bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001);bm.to_mesh(o.data);bm.free()
        for face in o.data.polygons:face.use_smooth=True
        o.data.set_sharp_from_angle(angle=math.radians(38))
print('SOURCE',CAR,source_triangles,'NORMALIZED',[round((hi[i]-lo[i])*scale,4) for i in range(3)],flush=True)

removed_explicit=0
for o in list(objects):
    slots={i for i,m in enumerate(o.data.materials) if m and (m.name in cfg['remove'] or any(x in m.name.lower() for x in ['interior','cockpit','seat','steering']))}
    if not slots:continue
    bm=bmesh.new();bm.from_mesh(o.data)
    faces=[f for f in bm.faces if f.material_index in slots]
    removed_explicit+=sum(len(f.verts)-2 for f in faces)
    bmesh.ops.delete(bm,geom=faces,context='FACES');bm.to_mesh(o.data);bm.free()
    if not o.data.polygons:objects.remove(o);bpy.data.objects.remove(o,do_unlink=True)

# Probe surface normals and oblique directions against the complete shell.
# This removes buried upholstery/duplicate internal surfaces, while explicit
# lamp and trim materials remain protected even behind a transparent cover.
vertices=[];polygons=[]
for o in objects:
    offset=len(vertices);vertices.extend(v.co.copy() for v in o.data.vertices)
    polygons.extend(tuple(offset+i for i in p.vertices) for p in o.data.polygons)
bvh=BVHTree.FromPolygons(vertices,polygons)
removed_hidden=0
directions=[Vector(v).normalized() for v in [(1,0,.45),(-1,0,.45),(0,1,.45),(0,-1,.45),(0,0,1),(0,0,-1)]]
for o in list(objects):
    protected={i for i,m in enumerate(o.data.materials) if m and m.name in cfg['protect']}
    keep=set()
    for face in o.data.polygons:
        # Steering/rolling exposes tire backs that were hidden in the static
        # pose. Retain complete wheel-area geometry before occlusion pruning.
        wheel_area=abs(face.center.x)>.55 and 1.0<abs(face.center.y)<1.95 and face.center.z<.85
        if face.material_index in protected or wheel_area:keep.add(face.index);continue
        c=face.center;n=face.normal
        for direction in [n,-n,*directions]:
            if bvh.ray_cast(c+direction*.0002,direction,15)[0] is None:
                keep.add(face.index);break
    # Preserve neighbouring edge faces so sampled occlusion cannot crack seams.
    incident={}
    for face in o.data.polygons:
        for vertex in face.vertices:incident.setdefault(vertex,[]).append(face.index)
    boundary_vertices={v for i in keep for v in o.data.polygons[i].vertices}
    keep.update(i for v in boundary_vertices for i in incident[v])
    bm=bmesh.new();bm.from_mesh(o.data);bm.faces.ensure_lookup_table()
    hidden=[f for f in bm.faces if f.index not in keep]
    removed_hidden+=sum(len(f.verts)-2 for f in hidden)
    bmesh.ops.delete(bm,geom=hidden,context='FACES');bm.to_mesh(o.data);bm.free()
    if not o.data.polygons:objects.remove(o);bpy.data.objects.remove(o,do_unlink=True)
del bvh,vertices,polygons
print('REMOVED',removed_explicit,removed_hidden,flush=True)

# Keep per-face colours on the SketchUp-derived Dolphin, with separate optical
# responses for glass, rubber and paint; source colours remain in the vertices.
if CAR=='dolphin':
    o=objects[0];attr=o.data.color_attributes.active_color
    if attr:
        materials=[]
        for name,metal,rough,coat in [('Body paint',.55,.27,1),('Rubber and trim',.03,.7,0),('Exterior glass',.3,.12,1),('Alloy',.7,.25,.6)]:
            m=bpy.data.materials.new(name);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF')
            vertex=m.node_tree.nodes.new('ShaderNodeVertexColor');vertex.layer_name=attr.name
            m.node_tree.links.new(vertex.outputs['Color'],p.inputs['Base Color'])
            p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough;p.inputs['Coat Weight'].default_value=coat
            materials.append(m)
        o.data.materials.clear()
        for m in materials:o.data.materials.append(m)
        for p in o.data.polygons:
            idx=p.vertices[0] if attr.domain=='POINT' else p.loop_start
            rgb=attr.data[idx].color[:3];brightness=sum(rgb)/3
            wheel=abs(p.center.y)>1.05 and p.center.z<.72
            p.material_index=2 if brightness<.14 and p.center.z>.9 else 1 if brightness<.045 else 3 if wheel else 0

for mat in {m for o in objects for m in o.data.materials if m}:
    if not mat.use_nodes:continue
    p=mat.node_tree.nodes.get('Principled BSDF')
    if not p:continue
    lower=mat.name.lower()
    if mat.name in cfg['paint'] or (CAR=='model-y' and ('paint' in lower or 'body' in lower)):
        for link in list(p.inputs['Base Color'].links):mat.node_tree.links.remove(link)
        rgb=[(int(cfg['color'][i:i+2],16)/255)**2.2 for i in [0,2,4]]
        p.inputs['Base Color'].default_value=(*rgb,1);p.inputs['Metallic'].default_value=.65;p.inputs['Roughness'].default_value=.25
        p.inputs['Coat Weight'].default_value=1;p.inputs['Coat Roughness'].default_value=.15
    if mat.name in cfg['glass'] or any(x in lower for x in ['window','windscreen','windshield','glass']):
        for key in ['Base Color','Alpha','Transmission Weight']:
            for link in list(p.inputs[key].links):mat.node_tree.links.remove(link)
        p.inputs['Base Color'].default_value=(.008,.014,.018,1);p.inputs['Alpha'].default_value=1
        p.inputs['Transmission Weight'].default_value=0;p.inputs['Metallic'].default_value=.28;p.inputs['Roughness'].default_value=.12;p.inputs['Coat Weight'].default_value=1
    p.inputs['Emission Strength'].default_value=min(p.inputs['Emission Strength'].default_value,1.2)
    for node in mat.node_tree.nodes:
        if node.type=='TEX_IMAGE' and node.image and max(node.image.size)>4096:
            im=node.image;s=4096/max(im.size);im.scale(round(im.size[0]*s),round(im.size[1]*s))

before=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objects)
ratio=min(1,350000/before)
for o in objects:
    if len(o.data.polygons)>3500 and ratio<.98:
        bpy.context.view_layer.objects.active=o
        dec=o.modifiers.new('Exterior runtime budget','DECIMATE');dec.ratio=ratio;dec.delimit={'MATERIAL','SEAM'}
        bpy.ops.object.modifier_apply(modifier=dec.name)
    bpy.context.view_layer.objects.active=o;bpy.ops.object.material_slot_remove_unused()
    # Flat and sharp source boundaries stay unchanged; imported smooth normals
    # are retained by Blender rather than smoothing across panel gaps.
    o['sourceCar']=CAR;o['usage']='Exterior only'
runtime_triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objects)
sys.path.insert(0,str(ROOT/'scripts'))
from rig_vehicle_wheels import rig_wheels, write_rig_manifest
objects,wheel_rig=rig_wheels(objects)
rigged_triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objects if o.type=='MESH')
assert runtime_triangles==rigged_triangles
bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
OUT.mkdir(exist_ok=True,parents=True)
dest=OUT/(CAR+'.glb')
bpy.ops.export_scene.gltf(filepath=str(dest),export_format='GLB',use_selection=True,export_apply=True,export_extras=True,export_image_format='JPEG',export_jpeg_quality=95,export_draco_mesh_compression_enable=True,export_draco_mesh_compression_level=6,export_draco_position_quantization=18,export_draco_normal_quantization=14,export_draco_texcoord_quantization=16)
editable=ROOT/'assets/blender/tourism'/(CAR+'-wheels.blend')
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(editable))
decoder=ROOT/'public/decoders/draco';decoder.mkdir(parents=True,exist_ok=True)
for name in ['draco_decoder.wasm','draco_wasm_wrapper.js','draco_decoder.js']:
    shutil.copy2(ROOT/'node_modules/three/examples/jsm/libs/draco/gltf'/name,decoder/name)
record={'car':CAR,'sourceFile':str(source.relative_to(ROOT)),'sourceTriangles':source_triangles,'runtimeTriangles':runtime_triangles,'runtimeBytes':dest.stat().st_size,'budgetBytes':10000000,'textureMaxSize':4096,'jpegQuality':95,'removedInteriorTriangles':removed_explicit,'removedHiddenTriangles':removed_hidden,'sourceYear':cfg['year'],'dimensionsM':[(hi[i]-lo[i])*scale for i in [1,0,2]],'scope':'Exterior with independent steering and rolling wheels','wheelRig':wheel_rig,'geometryCompression':'Draco 18-bit position, 14-bit normal, 16-bit UV','review':'Pending browser multi-angle review'}
record.update(sourceSha256=hashlib.sha256(source.read_bytes()).hexdigest(),runtimeSha256=hashlib.sha256(dest.read_bytes()).hexdigest(),rigFacesBefore=runtime_triangles,rigFacesAfter=rigged_triangles,editable=str(editable.relative_to(ROOT)))
(OUT/(CAR+'-quality.json')).write_text(json.dumps(record,indent=2));print(json.dumps(record),flush=True)
if CAR in ['su7','model-3','dolphin']:write_rig_manifest(ROOT)
if '--no-render' in sys.argv:sys.exit(0)

scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
scene.render.resolution_x=1100;scene.render.resolution_y=720;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=True
scene.world.use_nodes=True;nt=scene.world.node_tree;nt.nodes.clear();env=nt.nodes.new('ShaderNodeTexEnvironment');env.image=bpy.data.images.load(str(ROOT/'public/environment/sky.hdr'))
bg=nt.nodes.new('ShaderNodeBackground');bg.inputs['Strength'].default_value=.45;output=nt.nodes.new('ShaderNodeOutputWorld');nt.links.new(env.outputs['Color'],bg.inputs['Color']);nt.links.new(bg.outputs['Background'],output.inputs['Surface'])
for location,power,size in [((2,4,6),850,5),((-5,0,4),1000,4),((2,-4,5),900,4)]:
    data=bpy.data.lights.new('Studio softbox','AREA');data.energy=power;data.shape='DISK';data.size=size
    o=bpy.data.objects.new('Studio softbox',data);bpy.context.collection.objects.link(o);o.location=location;o.rotation_euler=(-o.location).to_track_quat('-Z','Y').to_euler()
camdata=bpy.data.cameras.new('Exterior review');cam=bpy.data.objects.new('Exterior review',camdata);bpy.context.collection.objects.link(cam);scene.camera=cam;camdata.lens=56
for name,location in [('front',(6.4,8.5,3.4)),('rear',(-6.4,-8.5,3.4)),('side',(9.5,0,2.0))]:
    cam.location=location;cam.rotation_euler=(Vector((0,0,.75))-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(OUT/(CAR+'-'+name+'.png'));bpy.ops.render.render(write_still=True)
print('EXTERIOR_READY',CAR,flush=True)
