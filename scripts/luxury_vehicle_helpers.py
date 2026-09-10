"""Isolated static-mesh import and configurable wheel partition for luxury cars.

No old fleet manifest or generator is imported. Geometry is expressed in Blender
metres, +Y forward and +Z up; wheel pivots are exported with identity axes.
"""
import bpy, bmesh, math, re
from mathutils import Matrix, Vector


def triangles(objects):
    return sum(len(p.vertices)-2 for o in objects if o.type == 'MESH' for p in o.data.polygons)


def bounds(objects):
    points = [o.matrix_world @ v.co for o in objects if o.type == 'MESH' for v in o.data.vertices]
    assert points, 'Source contains no mesh vertices'
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    return {'min': lo, 'max': hi, 'size': [b-a for a,b in zip(lo,hi)]}


def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for data in [bpy.data.meshes, bpy.data.curves, bpy.data.materials]:
        for item in list(data):
            if not item.users:
                data.remove(item)


def import_source(path):
    clear_scene()
    suffix = path.suffix.lower()
    if suffix in {'.glb', '.gltf'}:
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif suffix == '.fbx':
        bpy.ops.import_scene.fbx(filepath=str(path), use_anim=False)
    elif suffix == '.obj':
        bpy.ops.wm.obj_import(filepath=str(path))
    elif suffix == '.blend':
        with bpy.data.libraries.load(str(path), link=False) as (src, dst):
            dst.objects = list(src.objects)
        for o in dst.objects:
            if o is not None:
                bpy.context.scene.collection.objects.link(o)
    else:
        raise ValueError('Supported sources: GLB, glTF, FBX, OBJ and static Blender libraries')
    bpy.context.view_layer.update()
    return [o for o in bpy.context.scene.objects if o.type == 'MESH']


def normalize(objects, settings):
    raw = bounds(objects)
    from mathutils import Euler
    rotation = Euler([math.radians(v) for v in settings.get('rotationEulerDegrees', [0,0,0])], 'XYZ').to_matrix().to_4x4()
    worlds = {o:rotation @ o.matrix_world.copy() for o in objects}
    deps = bpy.context.evaluated_depsgraph_get()
    data = {o:(bpy.data.meshes.new_from_object(o.evaluated_get(deps), preserve_all_data_layers=True, depsgraph=deps)
               if o.modifiers or o.data.shape_keys else o.data.copy()) for o in objects}
    for o in objects:
        world = worlds[o]
        o.data = data[o]
        o.modifiers.clear(); o.animation_data_clear()
        o.data.transform(world)
        if world.determinant() < 0:
            o.data.flip_normals()
        o.parent = None
        o.matrix_world = Matrix.Identity(4)
        o.data.update()
    posed = bounds(objects)
    factor = float(settings.get('unitScale', 1))
    if settings.get('targetLengthM'):
        factor = float(settings['targetLengthM']) / posed['size'][1]
    assert 0 < factor < 1e7
    center = Vector(((posed['min'][0]+posed['max'][0])/2, (posed['min'][1]+posed['max'][1])/2, posed['min'][2]))
    transform = Matrix.Scale(factor, 4) @ Matrix.Translation(-center)
    for o in objects:
        o.data.transform(transform)
        o.data.update()
    for o in list(bpy.context.scene.objects):
        if o not in objects:
            bpy.data.objects.remove(o, do_unlink=True)
    return {'rawBoundsXYZ':raw, 'posedBoundsXYZ':posed, 'uniformScale':factor,
            'rotationEulerDegrees':settings.get('rotationEulerDegrees',[0,0,0]), 'normalizedBoundsXYZ':bounds(objects)}


def keep_faces(source_mesh, keep):
    """The proven BMesh partition, plus a corner map retaining custom normals."""
    mesh = source_mesh.copy()
    custom = bool(getattr(source_mesh, 'has_custom_normals', False))
    normals = [tuple(n.vector) for n in source_mesh.corner_normals] if custom else None
    marker = mesh.attributes.new('_luxury_source_corner', 'INT', 'CORNER')
    for i, item in enumerate(marker.data):
        item.value = i
    bm = bmesh.new(); bm.from_mesh(mesh); bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in keep], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(mesh); bm.free(); mesh.update()
    marker = mesh.attributes.get('_luxury_source_corner')
    assert marker is not None and len(marker.data) == len(mesh.loops)
    if normals and mesh.loops:
        mesh.normals_split_custom_set([normals[item.value] for item in marker.data])
    mesh.attributes.remove(marker)
    return mesh


def remove_explicit_interior(objects, recipe):
    object_names = set(recipe.get('removeInteriorObjects', []))
    material_names = set(recipe.get('removeInteriorMaterials', []))
    protect = re.compile(recipe.get('protectMaterialRegex', r'(?i)(lamp|head.?light|tail.?light|window|windscreen|windshield|glass|lens|tyre|tire|rim)'))
    removed = []
    for o in list(objects):
        slots = {i for i,m in enumerate(o.data.materials) if m and m.name in material_names}
        selected = [p for p in o.data.polygons if o.name in object_names or p.material_index in slots]
        if not selected:
            continue
        forbidden = {o.data.materials[p.material_index].name for p in selected
                     if p.material_index < len(o.data.materials) and o.data.materials[p.material_index]
                     and protect.search(o.data.materials[p.material_index].name)}
        assert not forbidden, ('Explicit interior removal overlaps protected exterior materials', o.name, sorted(forbidden))
        remove_ids = {p.index for p in selected}
        removed.append({'object':o.name, 'triangles':sum(len(p.vertices)-2 for p in selected)})
        keep = {p.index for p in o.data.polygons if p.index not in remove_ids}
        if keep:
            o.data = keep_faces(o.data, keep)
        else:
            objects.remove(o); bpy.data.objects.remove(o, do_unlink=True)
    return removed


def components(objects, tolerance=1e-5):
    result = []
    for o in objects:
        weld = {}; parent = []; ids = []
        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]; i = parent[i]
            return i
        for v in o.data.vertices:
            key = tuple(round(float(x)/tolerance) for x in v.co)
            if key not in weld:
                weld[key] = len(parent); parent.append(len(parent))
            ids.append(weld[key])
        for p in o.data.polygons:
            a = find(ids[p.vertices[0]])
            for v in p.vertices[1:]:
                parent[find(ids[v])] = a
        groups = {}
        for p in o.data.polygons:
            groups.setdefault(find(ids[p.vertices[0]]), []).append(p.index)
        for face_ids in groups.values():
            vertex_ids = {v for i in face_ids for v in o.data.polygons[i].vertices}
            lo = [min(o.data.vertices[v].co[i] for v in vertex_ids) for i in range(3)]
            hi = [max(o.data.vertices[v].co[i] for v in vertex_ids) for i in range(3)]
            mats = sorted({o.data.materials[o.data.polygons[i].material_index].name for i in face_ids
                           if o.data.polygons[i].material_index < len(o.data.materials) and o.data.materials[o.data.polygons[i].material_index]})
            result.append({'object':o, 'id':o.name+'#'+str(min(face_ids)), 'faces':face_ids, 'vertices':vertex_ids,
                           'min':lo, 'max':hi, 'center':[(a+b)/2 for a,b in zip(lo,hi)],
                           'size':[b-a for a,b in zip(lo,hi)], 'materials':mats,
                           'triangles':sum(len(o.data.polygons[i].vertices)-2 for i in face_ids)})
    return result


def public_component(c):
    return {k:v for k,v in c.items() if k not in {'object','faces','vertices'}}


def detect_wheels(comps, car_bounds, settings):
    width, length, height = car_bounds['size']
    diameter_range = settings.get('diameterRangeM', [max(.35, height*.26), min(width*.60, height*.78)])
    seeds = []
    excluded = re.compile(settings.get('excludeSeedRegex', r'(?i)(spare|steering|stuur|volant|lenkrad)'))
    for c in comps:
        x,y,z = c['center']; sx,sy,sz = c['size']; diameter = max(sy,sz)
        label = c['id']+' '+' '.join(c['materials'])
        if excluded.search(label): continue
        if (diameter_range[0] <= diameter <= diameter_range[1] and
            abs(sy-sz) < diameter*settings.get('roundnessTolerance',.16) and
            diameter*.025 < sx < diameter*.80 and
            abs(x) > width*settings.get('minimumLateralFraction',.24) and
            c['min'][2] < height*.14 and z < height*.52):
            seeds.append(c)
    if settings.get('centers'):
        result = settings['centers']
        assert set(result) == {'FL','FR','RL','RR'}
        return result, [public_component(c) for c in seeds]
    clusters = []
    for c in sorted(seeds, key=lambda c:max(c['size'][1:]), reverse=True):
        radius = max(c['size'][1:])/2
        if not any((Vector(c['center'])-Vector(old['center'])).length < radius*.40 for old in clusters):
            clusters.append(c)
    assert len(clusters) == 4, ('Four unambiguous complete tyre components required; inspect and configure diameterRangeM or centers', [public_component(c) for c in clusters])
    by_y = sorted(clusters, key=lambda c:c['center'][1])
    result = {}
    for pair, prefix in [(by_y[:2],'R'),(by_y[2:],'F')]:
        assert abs(pair[0]['center'][1]-pair[1]['center'][1]) < max(pair[0]['size'][1],pair[1]['size'][1])*.24
        for c in pair:
            name = prefix+('L' if c['center'][0] < 0 else 'R')
            result[name] = {'center':c['center'], 'radius':max(c['size'][1:])/2, 'width':c['size'][0], 'seed':c['id']}
    assert set(result) == {'FL','FR','RL','RR'}
    wheelbase = (result['FL']['center'][1]+result['FR']['center'][1]-result['RL']['center'][1]-result['RR']['center'][1])/2
    assert length*.32 < wheelbase < length*.85, ('Wheelbase inconsistent with source length', wheelbase, length)
    return result, [public_component(c) for c in seeds]


def rig_wheels(objects, comps, seeds, settings):
    before = triangles(objects); assignments = {}; pivots = {}; rolls = {}; stats = {}; output = []
    tolerance = settings.get('partRadiusMarginM', .018)
    for name, seed in seeds.items():
        center = Vector(seed['center']); radius = seed['radius']
        pivot = bpy.data.objects.new('Wheel_'+name, None); bpy.context.collection.objects.link(pivot)
        pivot.location = center; pivot['wheelPosition'] = name; pivot['wheelRadius'] = radius; pivot['frontWheel'] = name.startswith('F')
        roll = bpy.data.objects.new('WheelRoll_'+name, None); bpy.context.collection.objects.link(roll); roll.parent = pivot
        pivots[name] = pivot; rolls[name] = roll; output += [pivot,roll]
        stats[name] = {'centerBlender':list(center),'radius':radius,'width':seed['width'],'triangles':0,'components':0}
        half_width = max(seed['width']/2+settings.get('partWidthMarginM',.055), radius*.50)
        for c in comps:
            if (max(abs(c['min'][0]-center.x),abs(c['max'][0]-center.x)) > half_width or
                c['size'][1] > radius*2+tolerance*2 or c['size'][2] > radius*2+tolerance*2): continue
            if all(math.hypot(c['object'].data.vertices[v].co.y-center.y,c['object'].data.vertices[v].co.z-center.z) < radius+tolerance for v in c['vertices']):
                assert c['id'] not in assignments, ('Component fits two wheels',c['id'])
                assignments[c['id']] = name; stats[name]['components'] += 1
    for o in objects:
        groups = {}
        for c in comps:
            if c['object'] != o: continue
            name = assignments.get(c['id'], 'body')
            caliper = name != 'body' and (re.search(settings.get('caliperRegex',r'(?i)cal+ip(?:er|_)|brake.?pad'), c['id']+' '+' '.join(c['materials'])) or bool(set(c['materials']) & set(settings.get('caliperMaterials',[]))))
            group = (name, bool(caliper))
            groups.setdefault(group,set()).update(c['faces'])
        for (name,caliper), keep in groups.items():
            mesh = keep_faces(o.data, keep) if len(keep) != len(o.data.polygons) else o.data.copy()
            part = bpy.data.objects.new(o.name+'_'+name+('_upright' if caliper else ''),mesh); bpy.context.collection.objects.link(part)
            if name != 'body':
                mesh.transform(Matrix.Translation(-pivots[name].location)); part.parent = pivots[name] if caliper else rolls[name]
                stats[name]['triangles'] += triangles([part])
            output.append(part)
        bpy.data.objects.remove(o, do_unlink=True)
    after = triangles(output)
    assert before == after, ('Rig partition changed triangle count', before,after)
    assert all(w['triangles'] >= settings.get('minimumWheelTriangles',200) for w in stats.values()), stats
    bpy.context.view_layer.update()
    return output,stats


def ancestors(o):
    while o.parent:
        o=o.parent
        yield o


def positions(objects):
    return [tuple(o.matrix_world @ v.co) for o in objects for v in o.data.vertices]


def validate_motion(expected_triangles):
    meshes = [o for o in bpy.context.scene.objects if o.type=='MESH']
    assert triangles(meshes) == expected_triangles, ('GLB reimport triangle mismatch',triangles(meshes),expected_triangles)
    body = [o for o in meshes if not any(a.name.startswith('Wheel_') or a.name.startswith('WheelRoll_') for a in ancestors(o))]
    original_body = positions(body); baseline = {}; records = {}; uprights = {}
    for name in ['FL','FR','RL','RR']:
        group=[o for o in meshes if o.parent and o.parent.name=='Wheel_'+name]
        if group:uprights[name]=(group,positions(group))
    for name in ['FL','FR','RL','RR']:
        p=bpy.data.objects.get('Wheel_'+name);r=bpy.data.objects.get('WheelRoll_'+name)
        assert p and r and r.parent==p
        p.rotation_mode='XYZ';r.rotation_mode='XYZ'
        assert max(abs(v) for v in p.rotation_euler)<1e-5 and max(abs(v) for v in r.rotation_euler)<1e-5
        group=[o for o in r.children_recursive if o.type=='MESH']
        assert group
        baseline[name]=(group,positions(group));r.rotation_euler.x=math.radians(60)
    bpy.context.view_layer.update()
    for name,(group,before) in uprights.items():
        assert before==positions(group), ('Caliper rolled with wheel',name)
    for name,(group,before) in baseline.items():
        after=positions(group);changed=sum((Vector(a)-Vector(b)).length>1e-5 for a,b in zip(before,after))
        assert changed>len(after)*.95, ('Wheel did not actually roll',name,changed,len(after))
        records[name]={'vertices':len(after),'rolledVertices':changed}
        bpy.data.objects['WheelRoll_'+name].rotation_euler.x=0
    bpy.context.view_layer.update()
    for name in ['FL','FR']:
        bpy.data.objects['Wheel_'+name].rotation_euler.z=math.radians(25)
    bpy.context.view_layer.update()
    for name,(group,before) in baseline.items():
        after=positions(group);changed=sum((Vector(a)-Vector(b)).length>1e-5 for a,b in zip(before,after))
        assert (changed>len(after)*.95) if name.startswith('F') else (changed==0), ('Steering isolation failed',name,changed)
        records[name]['steeredVertices']=changed
    upright_records={}
    for name,(group,before) in uprights.items():
        after=positions(group);changed=sum((Vector(a)-Vector(b)).length>1e-5 for a,b in zip(before,after))
        assert (changed>len(after)*.95) if name.startswith('F') else (changed==0), ('Caliper steering failed',name,changed)
        upright_records[name]={'vertices':len(after),'rolledVertices':0,'steeredVertices':changed}
    assert original_body==positions(body), 'Body moved with wheel rig'
    for name in ['FL','FR']:
        bpy.data.objects['Wheel_'+name].rotation_euler.z=0
    bpy.context.view_layer.update()
    return {'fourIndependentRolls':True,'frontSteerOnly':True,'bodyStationary':True,'rollDegrees':60,'steerDegrees':25,'triangles':expected_triangles,'wheelVertexChanges':records,'caliperVertexChanges':upright_records}
