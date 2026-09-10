"""Restore semantic exterior PBR materials to licensed grey Model Y geometry.
The original source files and source renders are retained. Run with --inspect
for a read-only mesh inventory; default builds reviewed exterior assets.
"""
import bpy, bmesh, pathlib, json, sys, math, hashlib, shutil
from mathutils import Vector, Matrix
ROOT=pathlib.Path(__file__).resolve().parents[1]
BLEND=ROOT/'assets/blender/tourism/model-y-wheels.blend'
REVIEW=ROOT/'assets/vehicles/source/model-y/review'
OUT=ROOT/'public/vehicles/rigged'
REFS=ROOT/'references/tourism'
bpy.context.preferences.filepaths.use_scripts_auto_execute=False
bpy.ops.wm.open_mainfile(filepath=str(BLEND))
objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
def bounds(points):return [[min(p[i] for p in points) for i in range(3)],[max(p[i] for p in points) for i in range(3)]]
if '--inspect' in sys.argv:
    summary=[]
    for o in objects:
        bb=bounds([o.matrix_world@v.co for v in o.data.vertices])
        summary.append(dict(name=o.name,materials=[m.name for m in o.data.materials if m],triangles=sum(len(p.vertices)-2 for p in o.data.polygons),bounds=bb))
    (REVIEW/'model-y-mesh-inventory.json').write_text(json.dumps(summary,indent=2))
    for o in summary:
        print(o['name'],o['triangles'],[','.join(f'{v:.3f}' for v in p) for p in o['bounds']],','.join(o['materials']))
    print('MODEL_Y_INVENTORY',len(summary),flush=True)
    sys.exit(0)

# Restore only source lamp optical pieces that the all-opaque input made the
# previous exterior visibility filter discard. Hidden cabin parts stay excluded.
LAMP_OBJECT_IDS={5,42,50,63,64,65,68,89,90,92,93,94,95,96}
existing_ids={int(o.name.split('_')[1]) for o in objects if o.name.startswith('desirefx.me_')}
missing_ids=LAMP_OBJECT_IDS-existing_ids
if missing_ids:
    before_import=set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(ROOT/'assets/vehicles/source/model-y/source/scene.gltf'))
    imported=[o for o in bpy.context.scene.objects if o not in before_import]
    meshes=[o for o in imported if o.type=='MESH']
    rotation=Matrix.Rotation(math.pi/2,4,'Z')
    transformed={o:[rotation@o.matrix_world@v.co for v in o.data.vertices] for o in meshes}
    allpoints=[p for ps in transformed.values() for p in ps]
    bb=bounds(allpoints);scale=4.750/(bb[1][1]-bb[0][1])
    centre=Vector(((bb[0][0]+bb[1][0])/2,(bb[0][1]+bb[1][1])/2,bb[0][2]))
    retained=[]
    for obj in meshes:
        oid=int(obj.name.split('_')[1])
        if oid not in missing_ids:continue
        obj.data=obj.data.copy()
        for vertex,point in zip(obj.data.vertices,transformed[obj]):vertex.co=(point-centre)*scale
        obj.parent=None;obj.matrix_world=Matrix.Identity(4)
        obj['modelYRestoredOptics']=True;obj['sourceCar']='model-y';obj['usage']='Exterior lamp optics restored from licensed source'
        obj.data.update();retained.append(obj)
    for obj in imported:
        if obj not in retained:bpy.data.objects.remove(obj,do_unlink=True)
    objects.extend(retained)
restored_triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objects if o.get('modelYRestoredOptics'))

# Source wire identifiers are semantic part boundaries, though their exported
# diffuse values were all grey. Assignment is explicit and reviewable, never
# random or based on arbitrary polygon colouring.
PARTS={
 'pearl-white-paint':['137179227','226164137'],
 'privacy-glass':['131210127'],
 'panoramic-glass':['126170208'],
 'black-window-trim':['126166208','238144228'],
 'underbody-polymer':['184209127','185142234','238144217','209142127','219133211'],
 'camera-housing':['228138153','172204124','145219133','141141232'],
 'rear-wiper':['122201175','128211137'],
 'chrome-emblem':['122193202','238144208'],
 'mirror-reflector':['204124189','156232141'],
 'mirror-mount':['136225145','238144164'],
 'flush-handle':['212224136','124180204','127209186','238151144'],
 'tire-rubber':['181229139','139177229','231144237','133220182'],
 'graphite-alloy':['208231140','203123149','123160203','122201198','136225142','237183144','209127165','134222196'],
 'brake-cast-metal':['121191200','221169134','224136177','203233141','125133207','189131217'],
 'wheel-fasteners':['213204129','122183201'],
 'headlamp-cover':['238144223'],
 'headlamp-black-bezel':['158136224'],
 'headlamp-reflector':['222134208','129124204','214149130'],
 'headlamp-led':['211234142','176215130','132218134','139214230'],
 'fog-lamp-bezel':['142235153'],
 'tail-lamp-lens':['127177209','136225221'],
 'tail-lamp-led':['135223195','190139230','139229227','138212128','195221134','222134190'],
 'rear-reflector':['234170142','227137192'],
 'tail-lamp-bezel':['163140231','140231157','153129213'],
 'reverse-lamp':['216131131','228170138','130168215'],
 'tail-lamp-reflector':['216131171','224136181','159144237'],
}
ID_TO_PART={key:part for part,keys in PARTS.items() for key in keys}
# Values are linear RGB for Blender/glTF PBR, not sRGB byte values.
FINISHES={
 'pearl-white-paint':((.74,.76,.77),.22,.23,.90,1,0),
 'privacy-glass':((.012,.018,.025),.20,.105,1,1,0),
 'panoramic-glass':((.009,.014,.021),.24,.10,1,1,0),
 'black-window-trim':((.012,.015,.018),.12,.30,.4,1,0),
 'underbody-polymer':((.013,.015,.018),0,.78,0,1,0),
 'camera-housing':((.009,.011,.013),.1,.29,.3,1,0),
 'rear-wiper':((.011,.012,.014),.15,.53,0,1,0),
 'chrome-emblem':((.64,.68,.70),.9,.18,.7,1,0),
 'mirror-reflector':((.28,.34,.38),.96,.07,.8,1,0),
 'mirror-mount':((.014,.017,.019),.08,.34,.3,1,0),
 'flush-handle':((.015,.018,.021),.45,.25,.4,1,0),
 'tire-rubber':((.012,.014,.017),0,.87,0,1,0),
 'graphite-alloy':((.045,.049,.056),.8,.27,.5,1,0),
 'brake-cast-metal':((.20,.22,.24),.70,.45,0,1,0),
 'wheel-fasteners':((.48,.51,.55),.86,.23,.1,1,0),
 'headlamp-cover':((.50,.59,.66),.10,.065,.8,.12,0),
 'headlamp-black-bezel':((.009,.012,.016),.25,.22,.6,1,0),
 'headlamp-reflector':((.55,.60,.67),.92,.14,.7,1,0),
 'headlamp-led':((.73,.84,.92),.12,.17,.4,1,.45),
 'fog-lamp-bezel':((.018,.022,.026),.20,.24,.6,1,0),
 'tail-lamp-lens':((.028,.014,.020),.12,.11,.85,.22,0),
 'tail-lamp-led':((.55,.004,.009),.10,.22,.5,1,.22),
 'rear-reflector':((.38,.006,.009),.20,.28,.6,1,0),
 'tail-lamp-bezel':((.010,.011,.014),.25,.23,.6,1,0),
 'reverse-lamp':((.65,.69,.70),.45,.18,.5,1,0),
 'tail-lamp-reflector':((.20,.22,.26),.70,.22,.3,1,0),
}
materials={}
for name,(rgb,metal,rough,coat,alpha,emission) in FINISHES.items():
    mat=bpy.data.materials.new('Model Y · '+name)
    mat.use_nodes=True
    p=mat.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*rgb,1)
    p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough
    p.inputs['Coat Weight'].default_value=coat;p.inputs['Coat Roughness'].default_value=.11
    p.inputs['IOR'].default_value=1.48;p.inputs['Alpha'].default_value=alpha
    p.inputs['Emission Color'].default_value=(*rgb,1);p.inputs['Emission Strength'].default_value=emission
    mat.diffuse_color=(*rgb,alpha)
    if alpha<1:
        mat.surface_render_method='DITHERED'
        mat.use_transparency_overlap=False
    mat['semanticPart']=name
    materials[name]=mat
mapping=[]
for obj in objects:
    originals=[m.name for m in obj.data.materials if m]
    newslots=[]
    for source_name in originals:
        # A subsequent run reads previously assigned slots; original identifiers
        # are retained on each mesh as provenance for reproducibility.
        key=source_name.removeprefix('wire_').split('.')[0]
        if key not in ID_TO_PART:
            stored=json.loads(obj.get('modelYSourceMaterials','[]'))
            if not stored:raise AssertionError('Unmapped original material '+source_name)
            key=stored[len(newslots)].removeprefix('wire_').split('.')[0]
        assert key in ID_TO_PART,(obj.name,key)
        newslots.append(materials[ID_TO_PART[key]])
    source_names=json.loads(obj.get('modelYSourceMaterials','null')) or originals
    obj['modelYSourceMaterials']=json.dumps(source_names)
    obj['modelYMaterialRestoration']='Named source part + inspected global bounds + 2020–2024 photographic comparison'
    assignments=[ID_TO_PART[n.removeprefix('wire_').split('.')[0]] for n in source_names]
    indices=[p.material_index for p in obj.data.polygons]
    obj.data.materials.clear()
    for mat in newslots:obj.data.materials.append(mat)
    for p,i in zip(obj.data.polygons,indices):p.material_index=i
    # Smooth original exterior panels while preserving actual sharp boundaries.
    if any(n in assignments for n in ['pearl-white-paint','privacy-glass','panoramic-glass']):
        original_faces=sum(len(p.vertices)-2 for p in obj.data.polygons)
        bm=bmesh.new();bm.from_mesh(obj.data)
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000001)
        bm.to_mesh(obj.data);bm.free()
        assert sum(len(p.vertices)-2 for p in obj.data.polygons)==original_faces
        for p in obj.data.polygons:p.use_smooth=True
        obj.data.set_sharp_from_angle(angle=math.radians(38))
        if obj.data.has_custom_normals:
            bpy.context.view_layer.objects.active=obj
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
    mapping.append(dict(mesh=obj.name,sourceMaterials=source_names,semanticMaterials=assignments,
        triangles=sum(len(p.vertices)-2 for p in obj.data.polygons),boundsBlender=bounds([obj.matrix_world@v.co for v in obj.data.vertices])))

# Rig data is preserved exactly, without remapping the cylindrical wheel pieces.
base_quality=json.loads((REVIEW/'model-y-quality.json').read_text())
triangles=sum(sum(len(p.vertices)-2 for p in obj.data.polygons) for obj in objects)
assert triangles==base_quality['runtimeTriangles']+restored_triangles
for name in ['FL','FR','RL','RR']:
    pivot=bpy.data.objects['Wheel_'+name];roll=bpy.data.objects['WheelRoll_'+name]
    assert roll.parent==pivot and pivot['wheelPosition']==name
    assert abs(pivot['wheelRadius']-base_quality['wheelRig'][name]['radius'])<1e-6
    count=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in pivot.children_recursive if o.type=='MESH')
    assert count==base_quality['wheelRig'][name]['triangles']

for obj in bpy.context.selected_objects:obj.select_set(False)
for obj in bpy.context.scene.objects:
    if obj.type in ('MESH','EMPTY'):obj.select_set(True)
OUT.mkdir(parents=True,exist_ok=True)
dest=OUT/'model-y.glb'
bpy.ops.export_scene.gltf(filepath=str(dest),export_format='GLB',use_selection=True,export_apply=True,
    export_extras=True,export_draco_mesh_compression_enable=True,export_draco_mesh_compression_level=6,
    export_draco_position_quantization=18,export_draco_normal_quantization=14,export_draco_texcoord_quantization=16)
assert dest.stat().st_size<10_000_000
# Keep the semantic editable scene free of temporary studio lights/cameras.
bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
provenance=json.loads((ROOT/'assets/vehicles/source/model-y/provenance.json').read_text())
material_record=dict(car='model-y',sourceYear=2021,appearanceFamily='2020–2024 original exterior; retained source wheel variant',
    method='Explicit source-material mapping reviewed against real exterior photographs; no random recolouring',
    source=provenance,parts=mapping,finishes={k:dict(linearRgb=v[0],metallic=v[1],roughness=v[2],clearcoat=v[3],alpha=v[4]) for k,v in FINISHES.items()},
    officialReferences=[
      'https://www.tesla.com/ownersmanual/2020_2024_modely/en_qa/Owners_Manual.pdf',
      'https://service.tesla.com/docs/ModelY/ServiceManual/en-au/air/GUID-769C9625-76EE-467B-B756-C9032AC2B99A.html'],
    photographicReferences='references/tourism/model-y-photos.json',
    geometryChanged='Only original lamp optical objects restored; retained body and wheel faces unchanged',restoredLampTriangles=restored_triangles,normalRepair='Coincident vertices welded within 1 micrometre for paint/glass; face counts preserved, smooth split normals restored',interiorAdded=False,textureUpscaled=False)
(REFS/'model-y-materials.json').write_text(json.dumps(material_record,ensure_ascii=False,indent=2))
quality={**base_quality,'runtimeTriangles':triangles,'rigFacesBefore':triangles,'rigFacesAfter':triangles,'restoredLampTriangles':restored_triangles,'runtimeBytes':dest.stat().st_size,'runtimeSha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
    'semanticMaterials':len({m.name for o in objects for m in o.data.materials if m}),'appearanceFamily':'2020–2024 original Model Y',
    'sourceAuthor':'Nieve5677','sourceLicense':'CC-BY-4.0','sourceUrl':provenance['source'],
    'removedHiddenTrianglesBeforeLampRecovery':base_quality['removedHiddenTriangles'],
    'removedHiddenTriangles':base_quality['removedHiddenTriangles']-restored_triangles,
    'appearanceLimit':'Source wheel design retained; 2021 source exterior belongs to the 2020–2024 family, not the 2025 redesign.',
    'materialRecord':'references/tourism/model-y-materials.json','review':'Material pass exported; multi-angle render and reimport verification pending'}
(OUT/'model-y-quality.json').write_text(json.dumps(quality,ensure_ascii=False,indent=2))
print('MODEL_Y_FINISHED',triangles,dest.stat().st_size,flush=True)

# Re-import exported GLB with the actual Draco decoder, then measure all wheels.
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(dest))
objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
actual=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objects)
assert actual==triangles,(actual,triangles)
points=[o.matrix_world@v.co for o in objects for v in o.data.vertices]
box=bounds(points);dims=[box[1][i]-box[0][i] for i in range(3)]
assert abs(dims[1]-4.75)<.005 and 2<dims[0]<2.2 and 1.55<dims[2]<1.7
wheels=[]
for name in ['FL','FR','RL','RR']:
    pivot=bpy.data.objects['Wheel_'+name];roll=bpy.data.objects['WheelRoll_'+name]
    center=pivot.matrix_world.translation;radius=pivot['wheelRadius']
    assert roll.parent==pivot and pivot['frontWheel']==name.startswith('F')
    assert abs(center.z-radius)<.005
    assert center.y>0 if name.startswith('F') else center.y<0
    assert center.x<0 if name.endswith('L') else center.x>0
    pieces=[o for o in pivot.children_recursive if o.type=='MESH']
    wp=[o.matrix_world@v.co-center for o in pieces for v in o.data.vertices]
    wb=bounds(wp);wd=[wb[1][i]-wb[0][i] for i in range(3)]
    assert .1<wd[0]<.5 and .6<wd[1]<.8 and .6<wd[2]<.8
    assert abs(wd[1]-wd[2])<.03
    assert max(math.hypot(v.y,v.z) for v in wp)<radius+.025
    wheels.append(dict(id=name,centerBlender=list(center),radius=radius,dimensions=wd,
        triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in pieces),independentRoll=True,frontSteer=name.startswith('F')))
verification=dict(decodedRuntime=True,triangles=actual,dimensionBlenderXYZ=dims,wheels=wheels,
    file='public/vehicles/rigged/model-y.glb',bytes=dest.stat().st_size,sha256=quality['runtimeSha256'],
    retainedFaceCountPreserved=True,restoredLampTriangles=restored_triangles)
(REVIEW/'model-y-finished-verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2))

# Studio renders of the *decoded runtime GLB*, including visibly steered wheels.
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True
scene.render.resolution_x=1440;scene.render.resolution_y=940;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=True
scene.view_settings.view_transform='AgX'
scene.world.use_nodes=True;nt=scene.world.node_tree;nt.nodes.clear()
env=nt.nodes.new('ShaderNodeTexEnvironment');env.image=bpy.data.images.load(str(ROOT/'public/environment/sky.hdr'))
bg=nt.nodes.new('ShaderNodeBackground');bg.inputs['Strength'].default_value=.50
output=nt.nodes.new('ShaderNodeOutputWorld');nt.links.new(env.outputs['Color'],bg.inputs['Color']);nt.links.new(bg.outputs['Background'],output.inputs['Surface'])
for location,power,size in [((2,4,6),800,5),((-5,0,4),850,4),((2,-4,5),700,4)]:
    data=bpy.data.lights.new('Model Y review softbox','AREA');data.energy=power;data.shape='DISK';data.size=size
    obj=bpy.data.objects.new('Model Y review softbox',data);bpy.context.collection.objects.link(obj);obj.location=location
    obj.rotation_euler=(-obj.location).to_track_quat('-Z','Y').to_euler()
camdata=bpy.data.cameras.new('Model Y exterior review');cam=bpy.data.objects.new('Model Y exterior review',camdata)
bpy.context.collection.objects.link(cam);scene.camera=cam;camdata.lens=58
views=[('front',(6.4,8.5,3.4)),('rear',(-6.4,-8.5,3.4)),('side',(9.5,0,2.0)),('front-steered',(5.8,7.1,2.8))]
for name,location in views:
    if name=='front-steered':
        for wheel in ['FL','FR']:
            bpy.data.objects['Wheel_'+wheel].rotation_euler.z=-.32
        for wheel in ['FL','FR','RL','RR']:
            bpy.data.objects['WheelRoll_'+wheel].rotation_euler.x=.46
    cam.location=location;cam.rotation_euler=(Vector((0,0,.78))-cam.location).to_track_quat('-Z','Y').to_euler()
    target=REVIEW/('model-y-finished-'+name+'.png')
    if target.exists():
        version=1
        keep=REVIEW/(f'model-y-material-pass{version}-'+name+'.png')
        while keep.exists():
            version+=1;keep=REVIEW/(f'model-y-material-pass{version}-'+name+'.png')
        shutil.copy2(target,keep)
    scene.render.filepath=str(target);bpy.ops.render.render(write_still=True)
quality['review']='Decoded runtime GLB rendered front/rear/side and steered wheel views; four-wheel geometry checks passed'
quality['reviewEvidence']='assets/vehicles/source/model-y/review/model-y-finished-verification.json'
(OUT/'model-y-quality.json').write_text(json.dumps(quality,ensure_ascii=False,indent=2))
print('MODEL_Y_REVIEW_COMPLETE',flush=True)
