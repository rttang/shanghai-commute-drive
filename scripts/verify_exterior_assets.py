"""Reimport runtime GLBs with Blender's Draco decoder and check actual geometry."""
import bpy, json, math, pathlib, struct
ROOT=pathlib.Path(__file__).resolve().parents[1]
assets=json.loads((ROOT/'src/tour/vehicle-assets.json').read_text())
results=[]
for car,asset in assets.items():
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    file=ROOT/'public'/asset['file'].lstrip('/')
    bpy.ops.import_scene.gltf(filepath=str(file))
    objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
    assert objects
    points=[o.matrix_world@v.co for o in objects for v in o.data.vertices]
    assert all(math.isfinite(c) for p in points for c in p)
    dims=[max(p[i] for p in points)-min(p[i] for p in points) for i in range(3)]
    assert 4<dims[1]<5.1 and 1.7<dims[0]<2.4 and 1.3<dims[2]<1.8,(car,dims)
    assert abs(min(p.z for p in points))<.005
    triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objects)
    expected=json.loads((ROOT/'public'/asset['quality'].lstrip('/')).read_text())
    assert triangles==expected['runtimeTriangles']
    assert expected['rigFacesBefore']==expected['rigFacesAfter']==triangles
    textures=[n.image for o in objects for m in o.data.materials if m and m.use_nodes for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
    assert all(max(im.size)<=4096 for im in textures)
    raw=file.read_bytes();gltf=json.loads(raw[20:20+struct.unpack_from('<I',raw,12)[0]])
    nodes={n.get('name'):n for n in gltf['nodes']}
    wheel_results=[]
    for name in ['FL','FR','RL','RR']:
        pivot=bpy.data.objects['Wheel_'+name];roll=bpy.data.objects['WheelRoll_'+name]
        assert roll.parent==pivot
        assert pivot['wheelPosition']==name and pivot['frontWheel']==name.startswith('F')
        radius=pivot['wheelRadius'];center=pivot.matrix_world.translation
        assert .25<radius<.45 and abs(center.z-radius)<.005
        assert center.y>0 if name.startswith('F') else center.y<0
        assert center.x<0 if name.endswith('L') else center.x>0
        # Empty nodes are emitted in glTF Y-up with no residual basis rotation.
        for node_name in ['Wheel_'+name,'WheelRoll_'+name]:
            node=nodes[node_name]
            assert node.get('rotation',[0,0,0,1])==[0,0,0,1]
            assert node.get('scale',[1,1,1])==[1,1,1]
            assert 'matrix' not in node
        pieces=[o for o in pivot.children_recursive if o.type=='MESH']
        assert pieces
        wheel_points=[o.matrix_world@v.co-center for o in pieces for v in o.data.vertices]
        wheel_dims=[max(p[i] for p in wheel_points)-min(p[i] for p in wheel_points) for i in range(3)]
        wheel_triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in pieces)
        assert wheel_triangles==expected['wheelRig'][name]['triangles'] and wheel_triangles>1000
        assert .1<wheel_dims[0]<.5 and .5<wheel_dims[1]<.9 and .5<wheel_dims[2]<.9,(car,name,wheel_dims)
        assert abs(wheel_dims[1]-wheel_dims[2])<.04
        assert all(math.hypot(p.y,p.z)<radius+.02 for p in wheel_points)
        wheel_results.append({'position':name,'triangles':wheel_triangles,'radiusM':radius,'boundsXYZMetres':wheel_dims,'identityGltfAxes':True})
    results.append({'car':car,'decoded':True,'triangles':triangles,'bytes':file.stat().st_size,'boundsXYZMetres':dims,'textureMax':max([max(im.size) for im in textures]or[0]),'wheels':wheel_results,'rigFaceCountPreserved':True})
(ROOT/'docs/evidence/tourism/wheel-exterior-reimport.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
