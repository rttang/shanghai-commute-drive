"""Scenery-only Blender build. Never imports/runs a vehicle generation script.

Existing landmark footprints/silhouettes are retained; detail is added in metres.
Textures stay shared at runtime. The editable .blend packs its texture images.
"""
import bpy, math, random, pathlib, json, hashlib
from mathutils import Vector

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / 'public/streets/models'
OUT.mkdir(parents=True, exist_ok=True)
SOURCE = ROOT / 'assets/blender/streets'
SOURCE.mkdir(parents=True, exist_ok=True)
IDS = ['peace-hotel','customs-house','hsbc-bund','bank-china','palace-hotel','bund-heritage','pearl','shanghai-tower','financial-center','jinmao','waibaidu-bridge','plane-tree','streetlamp','river-railing']
PROTECTED = [ROOT/'public/tour-city.json',ROOT/'src/tour/vehicle-assets.json',*sorted((ROOT/'public/vehicles').glob('*')),*sorted((ROOT/'public/cars').glob('*'))]
before = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in PROTECTED if p.is_file()}
FREEZE=json.loads((ROOT/'docs/evidence/tourism/street-freeze.json').read_text())
SCOPE=json.loads((ROOT/'docs/evidence/tourism/driving-scope.json').read_text())
RELEASED=set(SCOPE['releasedFromStreetFreeze'])
assert RELEASED=={'src/tour/drive.ts','src/tour/ui.ts','src/main.ts','src/tour/vehicle-assets.json'},'Unexpected freeze release'
assert RELEASED.issubset(FREEZE),'Released path absent from original baseline'
CURRENT_RELEASED={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in RELEASED}
def assert_frozen():
    for path,expected in FREEZE.items():
        if path not in RELEASED:
            assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected,'Protected asset changed: '+path
    for path,expected in CURRENT_RELEASED.items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected,'Approved driving file changed during scenery build: '+path
assert_frozen()
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
M = {}; chunks = {}; root = None; allroots = []; manifest = []

def material(name, color, metal=0, rough=.7):
    m = bpy.data.materials.new('street-'+name); m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF')
    rgb=tuple((int(color[i:i+2],16)/255)**2.2 for i in (1,3,5))
    p.inputs['Base Color'].default_value=(*rgb,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough
    M[name]=m; return m
for args in [('stone','#c8c1b1',0,.84),('trim','#d3caba',0,.72),('bronze','#514c3e',.65,.3),('glass','#465754',.18,.21),('iron','#39413e',.72,.43),('bark','#9a9580',0,.9),('leaf','#ccd2b3',0,.84),('clock','#e0d8bf',0,.64),('black','#222922',.2,.5)]: material(*args)

def geo(v,f,mat,smooth=False,uv=None):
    vs,fs,uvs=chunks.setdefault((mat,smooth),([],[],[]));n=len(vs);vs.extend(v);fs.extend(tuple(n+i for i in q) for q in f)
    uvs.extend(uv if uv else [None]*len(f))
def box(p,s,m):
    x,y,z=p;a,b,c=[n/2 for n in s]
    v=[(x+i,y+j,z+k) for i,j,k in [(-a,-b,-c),(a,-b,-c),(a,b,-c),(-a,b,-c),(-a,-b,c),(a,-b,c),(a,b,c),(-a,b,c)]]
    geo(v,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],m)
def rod(a,b,r,m,n=10,r2=None):
    a,b=Vector(a),Vector(b);q=(b-a).to_track_quat('Z','Y');v=[]
    for c,rad in [(a,r),(b,r if r2 is None else r2)]:
        for i in range(n):v.append(tuple(c+q@Vector((rad*math.cos(i*math.tau/n),rad*math.sin(i*math.tau/n),0))))
    geo(v,[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],m,True)
def ring(cx,y,cz,r,thick,m,n=48):
    v=[]
    for radius in (r-thick/2,r+thick/2):
        v.extend((cx+radius*math.sin(i*math.tau/n),y,cz+radius*math.cos(i*math.tau/n)) for i in range(n))
    geo(v,[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],m)
def flush():
    for (mat,smooth),(vs,fs,uvs) in chunks.items():
        mesh=bpy.data.meshes.new(root.name+'-'+mat);mesh.from_pydata(vs,[],fs);mesh.update();mesh.materials.append(M[mat]);uv=mesh.uv_layers.new()
        for p,coords in zip(mesh.polygons,uvs):
            p.use_smooth=smooth
            axis=max(range(3),key=lambda k:abs(p.normal[k]))
            for j,li in enumerate(p.loop_indices):
                co=mesh.vertices[mesh.loops[li].vertex_index].co
                uv.data[li].uv=coords[j] if coords else ((co.y if axis==0 else co.x)/2,(co.y if axis==2 else co.z)/2)
        obj=bpy.data.objects.new('detail-'+mat,mesh);bpy.context.collection.objects.link(obj);obj.parent=root
    chunks.clear()
def project_uv(obj):
    mesh=obj.data;uv=mesh.uv_layers.active or mesh.uv_layers.new()
    for p in mesh.polygons:
        axis=max(range(3),key=lambda k:abs(p.normal[k]))
        for li in p.loop_indices:
            co=mesh.vertices[mesh.loops[li].vertex_index].co
            uv.data[li].uv=((co.y if axis==0 else co.x)/2,(co.y if axis==2 else co.z)/2)

def face_detail(w,d,h,floors,offset=(0,0,0)):
    # Match the inherited window centres; build surrounds around, not over, glass.
    ox,oy,oz=offset
    def b(p,s,m):box((p[0]+ox,p[1]+oy,p[2]+oz),s,m)
    for side in (-1,1):
        y=side*(d/2+.19)
        for i in range(max(2,int(w/4.2))):
            x=-w/2+2.1+i*(w-4.2)/max(1,int(w/4.2)-1)
            for j in range(floors):
                z=3+(h-6)*j/max(1,floors-1)
                for dx in (-.97,.97): b((x+dx,y,z),(.19,.32,2.75),'trim')
                for dz in (-1.35,1.35):b((x,y,z+dz),(2.16,.4,.18),'trim')
                b((x,side*(d/2+.13),z),(.065,.12,2.35),'bronze')
                b((x,side*(d/2+.14),z+.42),(1.7,.13,.06),'bronze')
            if i%2==0:
                b((x+2.04,side*(d/2+.16),h/2),(.3,.32,h-3),'trim')
        for z,thick in [(1,.3),(h*.19,.35),(h*.9,.42),(h,.55)]:
            for dz,depth in [(-.18,.48),(0,.8),(.18,1.02)]:b((0,side*(d/2+.08),z+dz),(w+depth,depth,thick/2),'trim')
        # Entrance recess with bronze doors and a layered stone hood.
        b((0,side*(d/2+.07),2.4),(2.8,.12,4.6),'glass')
        for x in (-1.7,1.7):b((x,side*(d/2+.22),2.6),(.42,.6,5.2),'trim')
        for dz,width in [(5.15,3.9),(5.36,4.2),(5.55,4.5)]:b((0,side*(d/2+.27),dz),(width,.85,.17),'trim')
        b((0,side*(d/2+.2),2.3),(.08,.11,4.5),'bronze')

for name in IDS:
    if name in ('plane-tree','streetlamp','river-railing'):
        root=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(root)
    else:
        old=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(ROOT/'public/tour-models'/f'{name}.glb'))
        imported=set(bpy.data.objects)-old;top=[o for o in imported if o.parent not in imported]
        root=bpy.data.objects.new(name+'-street',None);bpy.context.collection.objects.link(root)
        for o in top:o.parent=root
        for o in imported:
            if o.type=='MESH':
                for slot in o.material_slots:
                    nm=slot.material.name.split('.')[0]
                    if nm in ('stone','limestone'):slot.material=M['stone' if nm=='stone' else 'trim']
                    elif nm=='window':slot.material=M['glass']
                    elif nm in ('steel','chrome') and name=='waibaidu-bridge':slot.material=M['iron']
                project_uv(o)
    root['streetAssetId']=name;root['units']='metres';allroots.append(root)
    dims={'peace-hotel':(55,53,43,9),'customs-house':(66,47,34,7),'hsbc-bund':(82,50,30,6),'bank-china':(45,42,64,15),'palace-hotel':(50,45,32,7),'bund-heritage':(34,28,30,7)}
    if name in dims:face_detail(*dims[name])
    if name=='peace-hotel':face_detail(25,27,61,12);face_detail(52,100,40,9,(0,-63,0))
    if name=='customs-house':
        # Side faces were blank in the baseline. Four clock faces with radial detail.
        for z,w,t in [(34,17,.7),(51,16,.8),(62,14,.7),(70,14,.8)]:box((0,0,z),(w,w,t),'trim')
        for a in range(4):
            before_chunk={k:len(v[0]) for k,v in chunks.items()}
            geo([(math.sin(k*math.tau/64)*3.63,-7.735,57+math.cos(k*math.tau/64)*3.63) for k in range(64)],[tuple(range(63,-1,-1))],'clock')
            ring(0,-7.75,57,3.65,.13,'bronze')
            ring(0,-7.77,57,3.9,.28,'trim')
            box((0,-7.56,43),(2.8,.15,8.5),'glass')
            for x in [-1.62,1.62]:box((x,-7.68,43),(.25,.4,9),'trim')
            for z in [38.5,47.5]:box((0,-7.7,z),(3.5,.55,.22),'trim')
            box((0,-7.7,43),(.1,.11,8.5),'bronze')
            for k in range(60):
                theta=k*math.tau/60;r1=2.95 if k%5==0 else 3.2
                rod((math.sin(theta)*r1,-7.76,57+math.cos(theta)*r1),(math.sin(theta)*3.45,-7.76,57+math.cos(theta)*3.45),.045 if k%5 else .09,'black',6)
            rod((0,-7.78,57),(0,-7.78,59.6),.095,'black');rod((0,-7.79,57),(1.9,-7.79,56),.11,'black')
            # Rotate only newly emitted clock details around tower Z.
            for key,(vs,_,_) in chunks.items():
                start=before_chunk.get(key,0);co,si=math.cos(a*math.pi/2),math.sin(a*math.pi/2)
                for k in range(start,len(vs)):
                    x,y,z=vs[k];vs[k]=(x*co-y*si,x*si+y*co,z)
        for s in (-1,1):
            for x in (-6.3,6.3):box((x,s*7.65,43),(.65,.5,15),'trim')
    if name=='financial-center':
        # Curtain-wall vertical mullions on both long faces, at full metre scale.
        for side in (-1,1):
            for i in range(-13,14):rod((i*2,side*24.1,0),(i*2*38/58,side*19.6,430),.085,'bronze',6)
    if name=='plane-tree':
        rng=random.Random(121494)
        trunk=[(0,0,0),(.04,-.06,1.7),(-.1,.06,3.3),(.12,.03,4.8)]
        for i,(a,b) in enumerate(zip(trunk,trunk[1:])):rod(a,b,.31-i*.04,'bark',14,r2=.27-i*.04)
        for arm in range(18):
            a=arm*2.399;phi=math.acos(1-2*(arm+.5)/18);rad=3.5*math.sin(phi);end=Vector((math.cos(a)*rad,math.sin(a)*rad,7.9+2.1*math.cos(phi)))
            base=Vector(trunk[-2 if arm%3==0 else -1]);mid=base.lerp(end,.55)+Vector((0,0,.45))
            rod(base,mid,.13,'bark',9,r2=.075);rod(mid,end,.075,'bark',8,r2=.021)
            for spray in range(4):
                tip=end+Vector((rng.uniform(-1.05,1.05),rng.uniform(-1.05,1.05),rng.uniform(-.65,.8)))
                rod(end,tip,.022,'bark',6,r2=.005)
                for leaf in range(3):
                    c=tip+Vector((rng.uniform(-.38,.38),rng.uniform(-.38,.38),rng.uniform(-.32,.32)))
                    ang=rng.uniform(0,math.tau);tilt=rng.uniform(-.65,.65);size=rng.uniform(.65,1.02)
                    u=Vector((math.cos(ang),math.sin(ang),tilt))*size;v=Vector((-math.sin(ang)*.35,math.cos(ang)*.35,.8))*size
                    geo([tuple(c-u-v),tuple(c+u-v),tuple(c+u+v),tuple(c-u+v)],[(0,1,2,3)],'leaf',True,[[(0,0),(1,0),(1,1),(0,1)]])
    if name=='streetlamp':
        rod((0,0,0),(0,0,.25),.29,'iron',16);rod((0,0,.25),(0,0,1.5),.17,'iron',12,r2=.11)
        rod((0,0,1.5),(0,0,8.8),.1,'iron',12,r2=.065)
        for z in (1.45,1.6,8.6):rod((0,0,z),(0,0,z+.09),.15,'bronze',12)
        pts=[(0,0,8.7),(0,.5,9.1),(0,1.35,9.25),(0,2.3,9.25)]
        for a,b in zip(pts,pts[1:]):rod(a,b,.06,'iron',8)
        box((0,2.35,9.23),(.48,1.1,.15),'iron');box((0,2.35,9.14),(.38,.85,.03),'clock')
    if name=='river-railing':
        for y in (-1.5,1.5):
            box((0,y,.58),(.28,.28,1.16),'stone');box((0,y,1.18),(.4,.4,.12),'trim')
        for z in (.22,1.02):rod((0,-1.5,z),(0,1.5,z),.038,'iron',8)
        for k in range(-6,7):rod((0,k*.215,.22),(0,k*.215,1.03),.023,'iron',6)
    flush()
    bpy.ops.object.select_all(action='DESELECT')
    root.select_set(True)
    for obj in root.children_recursive:obj.select_set(True)
    bpy.context.view_layer.objects.active=root
    p=OUT/f'{name}.glb'
    bpy.ops.export_scene.gltf(filepath=str(p),export_format='GLB',use_selection=True,export_apply=True,export_extras=True,export_draco_mesh_compression_enable=True,export_draco_mesh_compression_level=6,export_draco_position_quantization=16,export_draco_normal_quantization=12,export_draco_texcoord_quantization=14)
    meshes=[o for o in root.children_recursive if o.type=='MESH']
    manifest.append({'id':name,'bytes':p.stat().st_size,'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes),'meshes':len(meshes)})

# Pack the actual shared maps into the editable project after exporting geometry.
for key,prefix in [('stone','stone'),('trim','stone'),('bark','bark')]:
    m=M[key];nodes=m.node_tree.nodes;bsdf=nodes.get('Principled BSDF')
    path=ROOT/'public/streets/textures'/('plane-bark.png' if prefix=='bark' else f'{prefix}-diff.jpg')
    if path.exists():
        img=bpy.data.images.load(str(path),check_existing=True);img.pack();tex=nodes.new('ShaderNodeTexImage');tex.image=img;m.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
leafpath=ROOT/'public/streets/textures/plane-leaf.png'
if leafpath.exists():
    m=M['leaf'];img=bpy.data.images.load(str(leafpath));img.pack();tex=m.node_tree.nodes.new('ShaderNodeTexImage');tex.image=img;bsdf=m.node_tree.nodes.get('Principled BSDF');m.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color']);m.node_tree.links.new(tex.outputs['Alpha'],bsdf.inputs['Alpha'])
for i,obj in enumerate(allroots):obj.location.x=i*180
bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE/'shanghai-streets.blend'))
after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in PROTECTED if p.is_file()}
assert before==after,'Scenery build modified a protected car/map asset'
assert_frozen()
(OUT/'manifest.json').write_text(json.dumps({'generator':'scripts/build_streetscape.py','models':manifest,'protectedFilesUnchanged':True,'protectedHashes':after,'protectedFileCount':len(FREEZE)-len(RELEASED),'approvedDrivingFilesUnchangedDuringBuild':CURRENT_RELEASED},indent=2))
print('STREET_BUILD_COMPLETE',len(manifest),sum(x['bytes'] for x in manifest),flush=True)
