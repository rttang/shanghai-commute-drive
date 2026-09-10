"""Inspect and prepare one licensed luxury source, independently of the old fleet.

Run only with scripts/blender-local.sh --background --disable-autoexec --threads 2
--python-exit-code 1 --python /absolute/path/to/this.py -- --recipe PATH --mode inspect.
An inspected recipe must mark normalization.axesVerified and scaleVerified before
--mode prepare. Detailed geometry is never reduced to inflate or meet a triangle
count. A separate copied scene supplies the lower-detail traffic asset.
"""
from pathlib import Path
import argparse, datetime, fcntl, hashlib, json, math, os, re, shutil, struct, sys, uuid

ROOT = Path(__file__).resolve().parents[1]
IDS = {'g63','urus','porsche-911','ferrari-488','alphard'}


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    os.replace(tmp,path)


def resolve(path):
    value=Path(path)
    value=value if value.is_absolute() else ROOT/value
    value=value.resolve()
    assert value==ROOT or ROOT in value.parents, ('All source/work/output paths must stay on this external workspace',value)
    return value


def glb_summary(path):
    raw=path.read_bytes()
    assert raw[:4]==b'glTF' and struct.unpack_from('<I',raw,8)[0]==len(raw)
    gltf=json.loads(raw[20:20+struct.unpack_from('<I',raw,12)[0]])
    tris=sum(gltf['accessors'][p['indices']]['count']//3 for m in gltf.get('meshes',[]) for p in m['primitives'])
    identity=[[float(i==j) for j in range(4)] for i in range(4)];points=[]
    def multiply(a,b):return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]
    def visit(index,parent):
        node=gltf['nodes'][index]
        if 'matrix' in node:
            m=[[node['matrix'][j*4+i] for j in range(4)] for i in range(4)]
        else:
            x,y,z,w=node.get('rotation',[0,0,0,1]);sx,sy,sz=node.get('scale',[1,1,1]);tx,ty,tz=node.get('translation',[0,0,0])
            m=[[(1-2*y*y-2*z*z)*sx,(2*x*y-2*z*w)*sy,(2*x*z+2*y*w)*sz,tx],
               [(2*x*y+2*z*w)*sx,(1-2*x*x-2*z*z)*sy,(2*y*z-2*x*w)*sz,ty],
               [(2*x*z-2*y*w)*sx,(2*y*z+2*x*w)*sy,(1-2*x*x-2*y*y)*sz,tz],[0,0,0,1]]
        m=multiply(parent,m)
        if 'mesh' in node:
            for p in gltf['meshes'][node['mesh']]['primitives']:
                a=gltf['accessors'][p['attributes']['POSITION']]
                for x in [a['min'][0],a['max'][0]]:
                    for y in [a['min'][1],a['max'][1]]:
                        for z in [a['min'][2],a['max'][2]]:
                            points.append([sum(m[i][j]*[x,y,z,1][j] for j in range(4)) for i in range(3)])
        for child in node.get('children',[]):visit(child,m)
    for index in gltf['scenes'][gltf.get('scene',0)]['nodes']:visit(index,identity)
    size=[max(p[i] for p in points)-min(p[i] for p in points) for i in range(3)]
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'triangles':tris,'dimensionsM':[size[2],size[0],size[1]],
            'meshes':len(gltf.get('meshes',[])),'primitives':sum(len(m['primitives']) for m in gltf.get('meshes',[])),'materials':len(gltf.get('materials',[])),
            'embeddedImages':len(gltf.get('images',[]))},gltf


def material_inventory(objects):
    mats={m for o in objects for m in o.data.materials if m}
    return [{'name':m.name,'baseColor':list(m.diffuse_color),'images':[
        {'name':n.image.name,'size':list(n.image.size),'source':n.image.source}
        for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image] if m.use_nodes else []} for m in mats]


def resize_images(objects, max_size, copy_materials=False):
    mats={m for o in objects for m in o.data.materials if m}; replacements={}; images={}; changes=[]
    for old in mats:
        mat=old.copy() if copy_materials else old;replacements[old]=mat
        if not mat.use_nodes:continue
        for node in mat.node_tree.nodes:
            if node.type!='TEX_IMAGE' or not node.image:continue
            original=node.image
            if original not in images:images[original]=original.copy() if copy_materials else original
            node.image=images[original];image=node.image
            if max(image.size)>max_size:
                before=list(image.size);factor=max_size/max(image.size)
                image.scale(max(1,round(image.size[0]*factor)),max(1,round(image.size[1]*factor)))
                changes.append({'image':original.name,'before':before,'after':list(image.size)})
    if copy_materials:
        for o in objects:
            for i,mat in enumerate(o.data.materials):
                if mat:o.data.materials[i]=replacements[mat]
    return changes


def material_overrides(objects, recipe):
    changes=[]
    for mat in {m for o in objects for m in o.data.materials if m}:
        override=recipe.get('materialOverrides',{}).get(mat.name)
        if not override:continue
        assert mat.use_nodes
        node=mat.node_tree.nodes.get('Principled BSDF');assert node
        for key,value in override.items():
            assert key in {'Base Color','Alpha','Transmission Weight','Roughness','Metallic','Coat Weight','Emission Strength'}
            socket=node.inputs[key]
            changes.append({'material':mat.name,'input':key,'oldValue':list(socket.default_value) if key=='Base Color' else socket.default_value,'oldLinked':bool(socket.links),'newValue':value})
            for link in list(socket.links):mat.node_tree.links.remove(link)
            socket.default_value=value
    return changes


def export_glb(objects, path, draco=True):
    import bpy
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=next(o for o in objects if o.type=='MESH')
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,
        export_apply=True,export_extras=True,export_animations=False,export_morph=False,
        export_image_format='AUTO',export_draco_mesh_compression_enable=draco,
        export_draco_mesh_compression_level=6,export_draco_position_quantization=18,
        export_draco_normal_quantization=14,export_draco_texcoord_quantization=16)


def merge_meshes_by_parent(objects):
    """Combine identical-rig-parent meshes; Blender retains material slots and UVs."""
    import bpy
    from luxury_vehicle_helpers import triangles
    before=triangles(objects);groups={};kept=[o for o in objects if o.type!='MESH']
    for o in objects:
        if o.type=='MESH':groups.setdefault(o.parent,[]).append(o)
    for parent,group in groups.items():
        bpy.ops.object.select_all(action='DESELECT')
        for o in group:o.select_set(True)
        active=group[0];bpy.context.view_layer.objects.active=active
        if len(group)>1:bpy.ops.object.join()
        active.name='Exterior_'+(parent.name if parent else 'Body');kept.append(active)
    bpy.context.view_layer.update()
    assert triangles(kept)==before, 'Joining by rig parent changed triangles'
    return kept


def copied_traffic_scene(objects, target):
    import bpy
    from luxury_vehicle_helpers import triangles, ancestors
    clones={o:o.copy() for o in objects}
    for original,clone in clones.items():
        if original.type=='MESH':clone.data=original.data.copy()
        bpy.context.collection.objects.link(clone)
    for original,clone in clones.items():
        clone.parent=clones.get(original.parent)
        clone.matrix_parent_inverse=original.matrix_parent_inverse.copy()
    for original in objects:bpy.data.objects.remove(original,do_unlink=True)
    for original,clone in clones.items():
        # Original names are restored after originals are unlinked.
        clone.name=clone.name.rsplit('.',1)[0] if re.search(r'\.\d{3}$',clone.name) else clone.name
    result=list(clones.values());groups={'body':[]}
    for o in result:
        if o.type!='MESH':continue
        wheel=next((a.name.removeprefix('Wheel_') for a in ancestors(o) if a.name.startswith('Wheel_')),None)
        groups.setdefault(wheel or 'body',[]).append(o)
    wheel_budget=min(1800,max(300,int(target*.075)))
    used=sum(min(triangles(group),wheel_budget) for name,group in groups.items() if name!='body')
    budgets={name:(max(1000,target-used) if name=='body' else wheel_budget) for name in groups}
    changes=[]
    for name,group in groups.items():
        before=triangles(group);ratio=min(1,budgets[name]/max(1,before))
        for o in group:
            count=triangles([o])
            if ratio<.995 and count>24:
                bpy.context.view_layer.objects.active=o
                modifier=o.modifiers.new('Traffic copy reduction','DECIMATE');modifier.ratio=ratio
                modifier.delimit={'MATERIAL','SEAM'}
                bpy.ops.object.modifier_apply(modifier=modifier.name)
        changes.append({'group':name,'beforeTriangles':before,'afterTriangles':triangles(group),'requestedBudget':budgets[name]})
    return result,changes


def clean_traffic_geometry(objects):
    """Limit QEM wheel overshoot, then remove geometry below encoder precision."""
    import bpy,bmesh
    from luxury_vehicle_helpers import triangles,ancestors
    bpy.context.view_layer.update();before=triangles(objects);moved=0;maximum_overflow=0
    for o in objects:
        if o.type!='MESH':continue
        pivot=next((a for a in ancestors(o) if a.name.startswith('Wheel_')),None)
        if pivot:
            radius=float(pivot['wheelRadius']);to_pivot=pivot.matrix_world.inverted() @ o.matrix_world;to_mesh=to_pivot.inverted()
            for v in o.data.vertices:
                point=to_pivot @ v.co;r=math.hypot(point.y,point.z)
                if r>radius+1e-7:
                    maximum_overflow=max(maximum_overflow,r-radius);moved+=1
                    point.y*=radius/r;point.z*=radius/r;v.co=to_mesh @ point
        # 50 micrometres: below visual detail, above 18-bit positional quantization.
        bm=bmesh.new();bm.from_mesh(o.data)
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00005)
        bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=.00005)
        bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if len(f.verts)>3])
        zero=[f for f in bm.faces if f.calc_area()<2.5e-9]
        if zero:bmesh.ops.delete(bm,geom=zero,context='FACES')
        bm.normal_update();bm.to_mesh(o.data);bm.free();o.data.update()
    bpy.context.view_layer.update()
    return {'beforeTriangles':before,'afterTriangles':triangles(objects),'weldDistanceM':.00005,
            'wheelVerticesConstrained':moved,'maximumWheelRadialOvershootBeforeM':maximum_overflow,
            'scope':'Traffic copy only; clamp decimation overshoot to original tyre radius and clean below-encoding-precision edges/faces'}


def render_three_views(folder, car_bounds, prefix=''):
    import bpy
    from mathutils import Vector
    scene=bpy.context.scene
    try:scene.render.engine='BLENDER_EEVEE_NEXT'
    except TypeError:scene.render.engine='BLENDER_EEVEE'
    assert scene.render.engine.startswith('BLENDER_EEVEE')
    scene.eevee.use_raytracing=True
    scene.render.resolution_x=960;scene.render.resolution_y=640;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
    scene.view_settings.view_transform='AgX'
    scene.world.use_nodes=True;nodes=scene.world.node_tree.nodes;nodes.clear()
    bg=nodes.new('ShaderNodeBackground');bg.inputs['Color'].default_value=(.32,.37,.44,1);bg.inputs['Strength'].default_value=.65
    environment=ROOT/'public/environment/sky.hdr'
    if environment.exists():
        env=nodes.new('ShaderNodeTexEnvironment');env.image=bpy.data.images.load(str(environment),check_existing=True)
        scene.world.node_tree.links.new(env.outputs['Color'],bg.inputs['Color'])
    world_out=nodes.new('ShaderNodeOutputWorld');scene.world.node_tree.links.new(bg.outputs['Background'],world_out.inputs['Surface'])
    width,length,height=car_bounds['size'];span=max(width,length,height);target=Vector((0,0,height*.48))
    for loc,energy in [((span*.6,span*.6,span),1200),((-span*.6,span*.1,span*.7),1000),((0,-span*.8,span*.8),1400)]:
        data=bpy.data.lights.new('Luxury review softbox','AREA');data.energy=energy;data.shape='DISK';data.size=span*.85
        o=bpy.data.objects.new('Luxury review softbox',data);scene.collection.objects.link(o);o.location=loc;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.mesh.primitive_plane_add(size=span*30,location=(0,0,-.005));floor=bpy.context.object
    mat=bpy.data.materials.new('Luxury review floor');mat.use_nodes=True
    mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.10,.12,.14,1)
    mat.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.85;floor.data.materials.append(mat)
    data=bpy.data.cameras.new('Luxury review camera');camera=bpy.data.objects.new('Luxury review camera',data);scene.collection.objects.link(camera);scene.camera=camera
    data.lens=58;data.clip_start=.01;data.clip_end=max(100,span*40)
    views=[('front',(span*1.12,span*1.40,height*1.45)),('rear',(-span*1.12,-span*1.40,height*1.45)),('side',(span*1.8,0,height*.50))]
    for name,loc in views:
        data.type='ORTHO' if name=='side' else 'PERSP';data.ortho_scale=span*1.25
        camera.location=loc;camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(folder/(prefix+name+'.png'));bpy.ops.render.render(write_still=True)
    return {'engine':scene.render.engine,'views':[prefix+n+'.png' for n,_ in views],'resolution':[960,640]}


def promote(source, destination, backup_folder):
    destination.parent.mkdir(parents=True,exist_ok=True);backup_folder.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        previous=backup_folder/(destination.stem+'-previous-'+sha(destination)[:12]+destination.suffix)
        if not previous.exists():shutil.copy2(destination,previous)
    staging=destination.with_name('.'+destination.name+'.'+uuid.uuid4().hex+'.tmp')
    shutil.copy2(source,staging);assert sha(staging)==sha(source);os.replace(staging,destination)


def promote_run(work):
    """Promote an already validated staged run after its three views were read."""
    work=resolve(work);record=json.loads((work/'quality.json').read_text());car=record['id'];assert car in IDS
    detail=work/'detail.glb';traffic=work/'traffic.glb';editable=work/(car+'.blend')
    assert sha(detail)==record['runtimeSha256'] and sha(traffic)==record['traffic']['sha256']
    assert sha(resolve(record['sourceFile']))==record['sourceSha256']
    assert record['rigValidation']['bodyStationary'] and record['traffic']['rigValidation']['bodyStationary']
    record['conversionVisualReviewed']=True
    record['conversionVisualReviewScope']='Local three-view imported-GLB inspection; gameplay acceptance remains separate'
    write_json(work/'quality.json',record)
    promote(detail,ROOT/'public/vehicles/rigged'/(car+'.glb'),work/'backups')
    promote(traffic,ROOT/'public/vehicles/rigged/luxury-traffic'/(car+'.glb'),work/'backups')
    promote(editable,ROOT/record['editable'],work/'backups')
    promote(work/'front.png',ROOT/'public/vehicles'/(car+'-front.png'),work/'backups')
    promote(work/'quality.json',ROOT/'public/vehicles/rigged'/(car+'-quality.json'),work/'backups')
    fragment=ROOT/'references/luxury-fleet-ready.json'
    # Separate vehicle workers may promote together; merge by id under an OS lock.
    with fragment.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        fleet=json.loads(fragment.read_text()) if fragment.exists() else {'schemaVersion':1,'models':[]}
        fleet['models']=[r for r in fleet['models'] if r.get('id',r.get('car'))!=car]+[record]
        fleet['readyIds']=[r['id'] for r in fleet['models']]
        fleet['averageRuntimeBytes']=sum(r['runtimeBytes'] for r in fleet['models'])/len(fleet['models'])
        fleet['updatedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat();write_json(fragment,fleet)
    print('LUXURY_VEHICLE_READY',json.dumps({'id':car,'detailBytes':record['runtimeBytes'],'trafficBytes':record['traffic']['bytes'],'work':str(work)},ensure_ascii=False),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipe');parser.add_argument('--mode',choices=['inspect','prepare','promote'],default='inspect');parser.add_argument('--run')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:])
    if args.mode=='promote':
        assert args.run, 'Provide the completed staged run path'
        promote_run(args.run);return
    assert args.recipe, 'Provide a source recipe'
    recipe_path=resolve(args.recipe);recipe=json.loads(recipe_path.read_text());car=recipe['id'];assert car in IDS
    source=resolve(recipe['sourceFile']);assert source.is_file()
    run_id=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+args.mode+'-'+uuid.uuid4().hex[:6]
    work=ROOT/'assets/vehicles/luxury-prepared'/car/run_id;work.mkdir(parents=True)
    write_json(work/'recipe-used.json',recipe)
    for name in ['prepare_luxury_vehicles.py','luxury_vehicle_helpers.py']:shutil.copy2(ROOT/'scripts'/name,work/name)
    import bpy
    sys.path.insert(0,str(ROOT/'scripts'))
    from luxury_vehicle_helpers import import_source,normalize,bounds,triangles,remove_explicit_interior,components,public_component,detect_wheels,rig_wheels,clear_scene,validate_motion
    bpy.context.preferences.filepaths.use_scripts_auto_execute=False
    bpy.context.preferences.filepaths.temporary_directory=str(ROOT/'.tooling/blender/tmp')+'/'
    objects=import_source(source);source_triangles=triangles(objects);raw_bounds=bounds(objects)
    original_materials=material_inventory(objects)
    settings=dict(recipe.get('normalization',{}))
    if args.mode=='inspect' and not settings:
        settings={'unitScale':5/max(raw_bounds['size']),'rotationEulerDegrees':[0,0,0]}
    if args.mode=='prepare':
        assert settings.get('axesVerified') and settings.get('scaleVerified'), 'Inspect actual axes and dimensions before preparation'
        assert all(recipe.get('source',{}).get(k) for k in ['url','author','license']), 'Source author, license and URL must be recorded'
    normalization=normalize(objects,settings)
    removed=remove_explicit_interior(objects,recipe)
    adjusted_materials=material_overrides(objects,recipe)
    comps=components(objects,recipe.get('wheelSettings',{}).get('weldToleranceM',1e-5))
    inspection={'id':car,'source':str(source.relative_to(ROOT)),'sourceBytes':source.stat().st_size,'sourceSha256':sha(source),
                'sourceTriangles':source_triangles,'normalization':normalization,'provisionalScale':args.mode=='inspect' and not recipe.get('normalization'),
                'objects':[{'name':o.name,'triangles':triangles([o]),'materials':[m.name for m in o.data.materials if m]} for o in objects],
                'materials':original_materials,'materialOverrides':adjusted_materials,'removedInterior':removed,'components':[public_component(c) for c in comps]}
    try:seeds,candidates=detect_wheels(comps,bounds(objects),recipe.get('wheelSettings',{}));inspection['wheelSeeds']=seeds;inspection['wheelCandidates']=candidates
    except AssertionError as error:
        inspection['wheelDetectionError']=str(error);seeds=None
    write_json(work/'inspection.json',inspection)
    if args.mode=='inspect':
        inspection['render']=render_three_views(work,bounds(objects),'inspection-')
        write_json(work/'inspection.json',inspection)
        print('LUXURY_INSPECTION_READY',car,str(work),flush=True);return
    assert seeds, inspection.get('wheelDetectionError')
    exterior_before=triangles(objects)
    texture_changes=resize_images(objects,int(recipe.get('textureMaxSize',2048)))
    ratio=float(recipe.get('detailDecimateRatio',1));assert 0<ratio<=1
    if ratio<1:
        protected=re.compile(recipe.get('protectMaterialRegex',r'(?i)lamp|light|glass|window|lens|tyre|tire|rim'))
        for o in objects:
            if triangles([o])>1000 and not any(m and protected.search(m.name) for m in o.data.materials):
                bpy.context.view_layer.objects.active=o;mod=o.modifiers.new('Measured detailed asset budget','DECIMATE');mod.ratio=ratio;mod.delimit={'MATERIAL','SEAM'};bpy.ops.object.modifier_apply(modifier=mod.name)
        comps=components(objects,recipe.get('wheelSettings',{}).get('weldToleranceM',1e-5))
    before_rig=triangles(objects);objects,wheels=rig_wheels(objects,comps,seeds,recipe.get('wheelSettings',{}))
    if recipe.get('mergeMeshesByParent',False):objects=merge_meshes_by_parent(objects)
    after_rig=triangles(objects);assert before_rig==after_rig
    runtime_bounds=bounds([o for o in objects if o.type=='MESH'])
    detail=work/'detail.glb';export_glb(objects,detail);detail_info,detail_gltf=glb_summary(detail);assert detail_info['triangles']==after_rig, ('Detailed export triangle mismatch',after_rig,detail_info['triangles'])
    node_map={n.get('name'):n for n in detail_gltf['nodes']}
    for pos in ['FL','FR','RL','RR']:
        for name in ['Wheel_'+pos,'WheelRoll_'+pos]:assert node_map[name].get('rotation',[0,0,0,1])==[0,0,0,1]
    bpy.ops.file.pack_all();editable=work/(car+'.blend');bpy.ops.wm.save_as_mainfile(filepath=str(editable),compress=True)
    traffic_objects,reductions=copied_traffic_scene(objects,int(recipe.get('trafficTargetTriangles',20000)))
    traffic_cleanup=clean_traffic_geometry(traffic_objects)
    if recipe.get('trafficMergeMeshesByParent',True):traffic_objects=merge_meshes_by_parent(traffic_objects)
    traffic_textures=resize_images([o for o in traffic_objects if o.type=='MESH'],int(recipe.get('trafficTextureMaxSize',256)),True)
    validation_before=triangles(traffic_objects);validated_meshes=[]
    for obj in traffic_objects:
        if obj.type=='MESH':
            count=triangles([obj]);changed=obj.data.validate(verbose=True);obj.data.update()
            if changed:validated_meshes.append({'mesh':obj.name,'beforeTriangles':count,'afterTriangles':triangles([obj])})
    traffic_triangles=triangles(traffic_objects)
    traffic_cleanup['meshValidation']={'beforeTriangles':validation_before,'afterTriangles':traffic_triangles,'correctedMeshes':validated_meshes,'reason':'Explicitly apply same Mesh.validate performed by Blender glTF exporter before counting'}
    traffic=work/'traffic.glb';traffic_draco=bool(recipe.get('trafficDraco',False));export_glb(traffic_objects,traffic,draco=traffic_draco)
    traffic_info,_=glb_summary(traffic);traffic_encoding={'method':'Draco' if traffic_draco else 'Uncompressed glTF'}
    if traffic_draco and traffic_info['triangles']!=traffic_triangles:
        preserved=work/('traffic-draco-triangle-mismatch-'+traffic_info['sha256'][:12]+'.glb');shutil.copy2(traffic,preserved)
        traffic_encoding={'method':'Uncompressed glTF','reason':'Draco changed triangle count; preserve exact decoded geometry','beforeTriangles':traffic_triangles,'rejectedDracoTriangles':traffic_info['triangles']}
        traffic_draco=False;export_glb(traffic_objects,traffic,draco=False);traffic_info,_=glb_summary(traffic)
    assert traffic_info['triangles']==traffic_triangles, ('Traffic export triangle mismatch',traffic_triangles,traffic_info['triangles'])
    if traffic_info['bytes']>3_000_000 and recipe.get('trafficTextureMaxSize',256)>128:
        traffic_textures+=resize_images([o for o in traffic_objects if o.type=='MESH'],128)
        preserved=work/('traffic-before-texture-reduction-'+traffic_info['sha256'][:12]+'.glb');shutil.copy2(traffic,preserved)
        export_glb(traffic_objects,traffic,draco=traffic_draco);traffic_info,_=glb_summary(traffic)
    clear_scene();bpy.ops.import_scene.gltf(filepath=str(traffic));traffic_motion=validate_motion(traffic_triangles)
    clear_scene();bpy.ops.import_scene.gltf(filepath=str(detail));detail_motion=validate_motion(after_rig)
    render=render_three_views(work,runtime_bounds)
    wheelbase=(wheels['FL']['centerBlender'][1]+wheels['FR']['centerBlender'][1]-wheels['RL']['centerBlender'][1]-wheels['RR']['centerBlender'][1])/2
    source_meta=recipe['source'];record={'id':car,'car':car,'type':'licensed-exterior','file':'/vehicles/rigged/'+car+'.glb',
        'trafficFile':'/vehicles/rigged/luxury-traffic/'+car+'.glb','preview':'/vehicles/'+car+'-front.png',
        'sourceFile':str(source.relative_to(ROOT)),'sourceUrl':source_meta['url'],'author':source_meta['author'],'license':source_meta['license'],
        'licenseUrl':source_meta.get('licenseUrl'),'sourceYear':source_meta.get('year'),'sourceProvenance':source_meta,
        'sourceSha256':sha(source),'sourceTriangles':source_triangles,'normalization':normalization,
        'dimensionsM':detail_info['dimensionsM'],'wheelbaseM':wheelbase,
        'nominalDimensionsM':recipe.get('nominalDimensionsM'),'nominalWheelbaseM':recipe.get('nominalWheelbaseM'),
        'nominalDimensionsSource':recipe.get('nominalDimensionsSource'),'wheelRig':wheels,
        'runtimeMeshes':detail_info['meshes'],'runtimePrimitives':detail_info['primitives'],'runtimeBytes':detail_info['bytes'],'runtimeTriangles':after_rig,'runtimeSha256':detail_info['sha256'],'sha256':detail_info['sha256'],
        'budgetBytes':10000000,'textureMaxSize':recipe.get('textureMaxSize',2048),'textureChanges':texture_changes,'materialOverrides':adjusted_materials,
        'removedInterior':removed,'removedInteriorTriangles':sum(x['triangles'] for x in removed),'removedHiddenTriangles':0,
        'exteriorTrianglesBeforeBudget':exterior_before,'detailDecimateRatio':ratio,'rigFacesBefore':before_rig,'rigFacesAfter':after_rig,
        'rigValidation':detail_motion,'traffic':{**traffic_info,'rigValidation':traffic_motion,'reductions':reductions,'geometryCleanup':traffic_cleanup,'geometryEncoding':traffic_encoding,'textureChanges':traffic_textures},
        'geometryCompression':'Draco, 18-bit positions / 14-bit normals / 16-bit UV; source alpha-preserving image formats',
        'editable':'assets/blender/vehicles/luxury/'+car+'.blend','renderEvidence':str(work.relative_to(ROOT)),
        'render':render,'visualAccepted':False,'scope':'Existing exterior mesh conversion and four independent wheel rigs; no sculpted replacement body',
        'conversionRun':run_id}
    write_json(work/'quality.json',record)
    print('LUXURY_VEHICLE_STAGED',json.dumps({'id':car,'detail':detail_info,'traffic':traffic_info,'work':str(work)},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
