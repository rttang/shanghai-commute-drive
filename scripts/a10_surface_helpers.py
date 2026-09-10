"""A10-only parametric glazing and quick exact-GLB shape review.

This module never changes shared SUV helper behavior or the final wheel test.
"""
import math
from mathutils import Vector

def parametric_patch(name, outline, coordinates, material, rings=28):
    # Uniform surface cells avoid radial-fan normal interpolation artifacts.
    from suv_exterior_helpers import mesh, rounded_polygon
    boundary=[(p.x,p.y) for p in rounded_polygon([(u,v,0) for u,v in outline],.13,8)]
    lo=[min(p[i] for p in boundary) for i in range(2)];hi=[max(p[i] for p in boundary) for i in range(2)]
    nu=max(5,math.ceil((hi[0]-lo[0])/.020));nv=max(5,math.ceil((hi[1]-lo[1])/.015))
    verts=[];faces=[];known={}
    def clip(poly,axis,bound,above):
        out=[]
        for i,a in enumerate(poly):
            b=poly[(i+1)%len(poly)];aa=a[axis]>=bound if above else a[axis]<=bound;bb=b[axis]>=bound if above else b[axis]<=bound
            if aa:out.append(a)
            if aa!=bb:
                q=(bound-a[axis])/(b[axis]-a[axis]);out.append(tuple(a[j]+(b[j]-a[j])*q for j in range(2)))
        return out
    for i in range(nu):
        for j in range(nv):
            poly=boundary
            for axis,low,high in [(0,lo[0]+(hi[0]-lo[0])*i/nu,lo[0]+(hi[0]-lo[0])*(i+1)/nu),(1,lo[1]+(hi[1]-lo[1])*j/nv,lo[1]+(hi[1]-lo[1])*(j+1)/nv)]:
                poly=clip(clip(poly,axis,low,True),axis,high,False)
                if not poly:break
            face=[]
            for q in poly:
                key=tuple(round(v,10) for v in q)
                if key not in known:known[key]=len(verts);verts.append(coordinates(*q))
                idx=known[key]
                if not face or idx!=face[-1]:face.append(idx)
            if len(face)>1 and face[0]==face[-1]:face.pop()
            if len(set(face))>=3:faces.append(tuple(face))
    meanx=sum(v[0] for v in verts)/len(verts)
    for f in faces:
        normal=(Vector(verts[f[1]])-Vector(verts[f[0]])).cross(Vector(verts[f[2]])-Vector(verts[f[0]]))
        if normal.length>1e-10:
            if normal.x*meanx<0:faces=[f[::-1] for f in faces]
            break
    return mesh(name,verts,faces,material)

def shape_preview():
    """Build and reimport a separate preview GLB; do not overwrite runtime."""
    import sys,pathlib,importlib.util,bpy,bmesh
    root=pathlib.Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('a10_current_builder',root/'scripts/build_suv_exteriors.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    review=mod.REVIEW
    file=review/'leap-a10-shape.glb'
    if '--render-only' not in sys.argv:
        mod.build_a10()
        for obj in list(bpy.context.scene.objects):
            if obj.type=='MESH':
                bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free()
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.export_scene.gltf(filepath=str(file),export_format='GLB',use_selection=True,export_apply=True,export_extras=True,export_draco_mesh_compression_enable=True,export_draco_mesh_compression_level=6,export_draco_position_quantization=18,export_draco_normal_quantization=14)
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);bpy.ops.import_scene.gltf(filepath=str(file))
    scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE'
    if hasattr(scene,'eevee') and hasattr(scene.eevee,'taa_render_samples'):scene.eevee.taa_render_samples=32
    scene.render.resolution_x=1100;scene.render.resolution_y=740;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.world.use_nodes=True
    bg=scene.world.node_tree.nodes.get('Background');bg.inputs['Color'].default_value=(.32,.36,.4,1);bg.inputs['Strength'].default_value=.55
    from suv_exterior_helpers import mat
    for loc,power,size in [((-3,5,7),950,3.5),((4,1,6),600,5),((3,-4,6),1050,4)]:
        data=bpy.data.lights.new('Shape softbox','AREA');data.energy=power;data.shape='DISK';data.size=size
        obj=bpy.data.objects.new('Shape softbox',data);bpy.context.collection.objects.link(obj);obj.location=loc;obj.rotation_euler=(-obj.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.006));bpy.context.object.data.materials.append(mat('ShapeFloor',(.08,.095,.115),0,.75))
    data=bpy.data.cameras.new('Shape camera');camera=bpy.data.objects.new('Shape camera',data);bpy.context.collection.objects.link(camera);scene.camera=camera;data.lens=58
    for label,loc in [('front',(6.4,8.3,3.2)),('side',(9,0,.8)),('side-high',(9,0,1.7)),('rear',(-6.4,-8.3,3.1))]:
        camera.location=loc;camera.rotation_euler=(Vector((0,0,.8))-camera.location).to_track_quat('-Z','Y').to_euler()
        data.type='ORTHO' if label.startswith('side') else 'PERSP';data.ortho_scale=5.2
        scene.render.filepath=str(review/f'leap-a10-shape-{label}.png');bpy.ops.render.render(write_still=True)
    print('A10_SHAPE_PREVIEW_READY',str(file),flush=True)

if __name__=='__main__':shape_preview()
