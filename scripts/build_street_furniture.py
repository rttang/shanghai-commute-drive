"""Detailed exterior street prototypes, metre scale, photo-informed reconstruction.

Run only via scripts/blender-local.sh. Original assets/photos are never replaced.
Blender: X across, +Y forward, Z up; exported glTF: X across, -Z forward, Y up.
All prototypes are anchored at ground centre. The bridge is an engineering-safe
visual reconstruction of the photographed Waibaidu Bridge, not survey geometry.
"""
import bpy, math, json, pathlib, random, hashlib, datetime, sys, shutil
from mathutils import Vector

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / 'public/streets/districts/furniture'
EDIT = ROOT / 'assets/blender/streets/furniture-detailed.blend'
TREE_ONLY = '--tree-only' in sys.argv
TREE_REVIEW = ROOT / 'assets/streets/plane-tree-review'
RUN_ID = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')
PRESERVED = TREE_REVIEW / 'preserved'

def preserve_file(path):
    if not path.exists(): return None
    PRESERVED.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    destination = PRESERVED / (path.stem + '-' + digest + path.suffix)
    if not destination.exists(): shutil.copy2(path, destination)
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == hashlib.sha256(path.read_bytes()).hexdigest()
    return destination

old_tree = preserve_file(OUT/'plane-tree.glb') if TREE_ONLY else None
if TREE_ONLY:
    preserve_file(EDIT); preserve_file(OUT/'manifest.json')
    if not EDIT.exists(): raise RuntimeError('Tree-only update requires the existing editable furniture library')
    bpy.ops.wm.open_mainfile(filepath=str(EDIT))
    # Keep all other furniture objects and editable data in the library.
    for obj in list(bpy.data.objects):
        if obj.name == 'plane-tree' or obj.name.startswith('plane-tree-'):
            bpy.data.objects.remove(obj, do_unlink=True)
OUT.mkdir(parents=True, exist_ok=True)
EDIT.parent.mkdir(parents=True, exist_ok=True)
if not TREE_ONLY:
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
M = {}

def material(name, srgb, roughness=.65, metal=0, double=False):
    existing = bpy.data.materials.get('furniture-' + name)
    if TREE_ONLY and existing and not name.startswith(('bark', 'leaf')):
        M[name] = existing
        return existing
    rgb = tuple((int(srgb[i:i+2], 16)/255)**2.2 for i in (1,3,5))
    m = bpy.data.materials.new('furniture-' + name)
    m.use_nodes = True
    m.diffuse_color = (*rgb, 1)
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*rgb, 1)
    p.inputs['Roughness'].default_value = roughness
    p.inputs['Metallic'].default_value = metal
    m.use_backface_culling = not double
    M[name] = m
    return m

for args in [
    ('steel', '#777e79', .46, .72), ('edge', '#969e96', .4, .7),
    ('iron', '#353b3c', .64, .65), ('bolt', '#92988f', .42, .7),
    ('stone', '#bdb8ad', .94, 0), ('stone-dark', '#868981', .97, 0),
    ('bark', '#716b58', .98, 0), ('bark-dark', '#514e40', .98, 0),
    ('bark-pale', '#99957e', .98, 0), ('bark-warm', '#807761', .98, 0),
    ('leaf', '#516f36', .95, 0, True), ('leaf-lit', '#728847', .95, 0, True),
    ('leaf-dark', '#3e592f', .97, 0, True), ('leaf-olive', '#6b7d45', .96, 0, True),
    ('wood', '#98704c', .74, 0), ('wood-light', '#ae865c', .72, 0),
    ('lamp', '#ebe6cd', .28, .12), ('lamp-glass', '#c1cec8', .24, .15),
    ('blue', '#22688c', .52, .15), ('white', '#e9e6db', .63, 0),
    ('yellow', '#c6a337', .64, .15), ('rubber', '#323638', .91, 0),
    ('red', '#9d2929', .42, .15), ('green', '#3c715c', .42, .15),
]: material(*args)

class Mesh:
    def __init__(self, name):
        self.name = name
        self.groups = {}
        self.root = bpy.data.objects.new(name, None)
        bpy.context.collection.objects.link(self.root)
    def geo(self, vs, fs, mat, smooth=False):
        verts, faces = self.groups.setdefault((mat,smooth), ([],[]))
        n = len(verts)
        verts.extend(tuple(v) for v in vs)
        faces.extend(tuple(n+i for i in f) for f in fs)
    def face(self, vs, mat): self.geo(vs, [tuple(range(len(vs)))], mat)
    def box(self, p, s, mat, rotation=0):
        x,y,z = p; a,b,c = [n/2 for n in s]; co,si = math.cos(rotation), math.sin(rotation)
        vs = [(x+i*co-j*si,y+i*si+j*co,z+k) for i,j,k in
            [(-a,-b,-c),(a,-b,-c),(a,b,-c),(-a,b,-c),(-a,-b,c),(a,-b,c),(a,b,c),(-a,b,c)]]
        self.geo(vs, [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)], mat)
    def prism(self, a, b, width, depth, mat, across=None):
        a,b = Vector(a),Vector(b); direction = (b-a).normalized()
        if across is None:
            across = Vector((1,0,0)) if abs(direction.x)<.9 else Vector((0,1,0))
        u = (Vector(across)-direction*Vector(across).dot(direction)).normalized()
        v = direction.cross(u).normalized()
        vs = [c+u*x*width/2+v*y*depth/2 for c in (a,b) for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]]
        self.geo(vs, [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)], mat)
    def ibeam(self, a, b, width, depth, thick=.018, mat='steel'):
        a,b = Vector(a),Vector(b); d=(b-a).normalized()
        across=Vector((1,0,0)) if abs(d.x)<.9 else Vector((0,1,0))
        u=(across-d*across.dot(d)).normalized(); v=d.cross(u).normalized()
        self.prism(a,b,thick,depth-2*thick,mat,across=u)
        for sign in (-1,1):
            off=v*sign*(depth-thick)/2
            self.prism(a+off,b+off,width,thick,mat,across=u)
    def rod(self, a,b,r,mat,n=12,r2=None,irregular=0):
        a,b=Vector(a),Vector(b); q=(b-a).to_track_quat('Z','Y'); vs=[]
        for c,rad in [(a,r),(b,r if r2 is None else r2)]:
            for i in range(n):
                t=i*math.tau/n; radius=rad*(1+irregular*math.sin(i*5.231))
                vs.append(c+q@Vector((radius*math.cos(t),radius*math.sin(t),0)))
        self.geo(vs,[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],mat,True)
    def lathe(self, rings, mat, x=0,y=0,n=32):
        vs=[(x+r*math.cos(i*math.tau/n),y+r*math.sin(i*math.tau/n),z) for z,r in rings for i in range(n)]
        fs=[(j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i) for j in range(len(rings)-1) for i in range(n)]
        fs += [tuple(range(n-1,-1,-1)),tuple(range((len(rings)-1)*n,len(rings)*n))]
        self.geo(vs,fs,mat,True)
    def curve(self, points, radius, mat, n=12):
        for a,b in zip(points,points[1:]): self.rod(a,b,radius,mat,n)
    def rivet(self, p, axis=(1,0,0), radius=.023, mat='bolt'):
        p=Vector(p); d=Vector(axis)
        self.rod(p-d*.005,p+d*.018,radius,mat,8,r2=radius*.76)
    def finish(self):
        for (mat,smooth),(vs,fs) in self.groups.items():
            mesh=bpy.data.meshes.new(self.name+'-'+mat)
            mesh.from_pydata(vs,[],fs); mesh.update(); mesh.materials.append(M[mat])
            for face in mesh.polygons: face.use_smooth=smooth
            obj=bpy.data.objects.new(mesh.name,mesh); bpy.context.collection.objects.link(obj); obj.parent=self.root
        self.groups.clear()
        return self.root

assets=[]
def save_asset(mesh, description, references, footprint, extras=None):
    root=mesh.finish()
    for obj in bpy.context.selected_objects: obj.select_set(False)
    root.select_set(True)
    for obj in root.children: obj.select_set(True)
    bpy.context.view_layer.objects.active=root
    path=OUT/(mesh.name+'.glb')
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,
        export_yup=True,export_extras=True,export_apply=True,export_draco_mesh_compression_enable=False)
    triangles=0; lo=[math.inf]*3; hi=[-math.inf]*3
    for obj in root.children:
        obj.data.calc_loop_triangles(); triangles+=len(obj.data.loop_triangles)
        for corner in obj.bound_box:
            # Blender to glTF coordinates.
            p=obj.matrix_world@Vector(corner); point=(p.x,p.z,-p.y)
            for axis in range(3): lo[axis]=min(lo[axis],point[axis]);hi[axis]=max(hi[axis],point[axis])
    item=dict(id=mesh.name,file='streets/districts/furniture/'+mesh.name+'.glb',
        name=description,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),triangles=triangles,
        bounds=dict(min=lo,max=hi),dimensions=[hi[i]-lo[i] for i in range(3)],
        origin='ground-centre',axes=dict(up='+Y',forward='-Z',across='+X'),
        lowObstacleFootprint=footprint,referenceIds=references,
        provenance='Original photo-informed exterior reconstruction; unmeasured dimensions inferred, with explicit road clearance constraints.')
    if extras:item.update(extras)
    if mesh.name == 'waibaidu-bridge':
        def clip_polygon(poly, axis, bound, greater):
            result=[]
            for a,b in zip(poly,poly[1:]+poly[:1]):
                ina=a[axis]>=bound if greater else a[axis]<=bound
                inb=b[axis]>=bound if greater else b[axis]<=bound
                if ina: result.append(a)
                if ina != inb:
                    t=(bound-a[axis])/(b[axis]-a[axis]);result.append(a.lerp(b,t))
            return result
        lowest=math.inf; crossed=0
        for obj in root.children:
            for polygon in obj.data.polygons:
                poly=[obj.matrix_world@obj.data.vertices[i].co for i in polygon.vertices]
                for axis,bound,greater in [(0,-4.8,True),(0,4.8,False),(2,.15,True)]:
                    if poly: poly=clip_polygon(poly,axis,bound,greater)
                if poly:
                    crossed+=1;lowest=min(lowest,min(v.z for v in poly))
        assert lowest>=5.2, 'Actual bridge mesh intrudes road clearance: '+str(lowest)
        item['geometryClearanceValidation']=dict(method='All mesh polygons clipped against carriageway x slab and above-road plane',
            roadHalfWidth=4.8,aboveRoadPlane=.15,minimumActualHeight=lowest,testedCrossingFaces=crossed,passClearance=True)
    assets.append(item)
    print('FURNITURE_ASSET',mesh.name,item['bytes'],triangles,flush=True)

# Shanghai plane tree: five staggered, curved scaffold limbs, with branching
# starting inside the sidewalk footprint. The broad, filled summer crown and
# peeling olive/grey/brown bark are compared against individually reviewed photos.
rng=random.Random(20260909)
m=Mesh('plane-tree')

def wood_path(points, radii, sides=18, patches=0):
    """Connected rings avoid overlapping straight cylinders and bright cap seams."""
    points=[Vector(p) for p in points]
    frames=[]; verts=[]
    for i,p in enumerate(points):
        tangent=(points[min(i+1,len(points)-1)]-points[max(i-1,0)]).normalized()
        q=tangent.to_track_quat('Z','Y'); frames.append(q)
        for j in range(sides):
            angle=j*math.tau/sides
            radius=radii[i]*(1+.035*math.sin(j*2.61)+.016*math.sin(i*.8+j*.71))
            verts.append(p+q@Vector((radius*math.cos(angle),radius*math.sin(angle),0)))
    faces=[tuple(range(sides-1,-1,-1)),tuple(range((len(points)-1)*sides,len(points)*sides))]
    faces += [(i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j)
              for i in range(len(points)-1) for j in range(sides)]
    m.geo(verts,faces,'bark',True)
    # Irregular six/eight-sided exfoliation islands conform to the actual curved
    # trunk; shallow relief only. Pale patches never become an entire white limb.
    for k in range(patches):
        at=rng.uniform(.1,len(points)-1.1); angle=rng.uniform(0,math.tau)
        width=rng.uniform(.24,.85); height=rng.uniform(.13,.60)
        perimeter=[]
        for j in range(8):
            t=j*math.tau/8
            v=max(.01,min(len(points)-1.01,at+math.sin(t)*height*(.7+rng.random()*.4)))
            idx=int(v); fraction=v-idx
            p=points[idx].lerp(points[idx+1],fraction)
            q=frames[idx].slerp(frames[idx+1],fraction)
            a=angle+math.cos(t)*width*(.75+rng.random()*.3)
            radius=(radii[idx]*(1-fraction)+radii[idx+1]*fraction)*(1+.038*math.sin(a*sides/math.tau*2.61))+.0025
            perimeter.append(p+q@Vector((radius*math.cos(a),radius*math.sin(a),0)))
        m.face(perimeter,rng.choices(['bark-dark','bark-pale','bark-warm'],[.43,.23,.34])[0])

def curved(a,b,c,steps=9):
    a,b,c=Vector(a),Vector(b),Vector(c)
    return [a*(1-t)**2+b*2*t*(1-t)+c*t*t for t in [i/steps for i in range(steps+1)]]

trunk=[(.07*math.sin(t*.9),.035*math.sin(t*1.4),t) for t in [i*5.45/18 for i in range(19)]]
trunk_radii=[.31*(1-.60*i/18)+(.035*(1-i/3) if i<3 else 0) for i in range(19)]
wood_path(trunk,trunk_radii,28,185)
leaf_centres=[]
scaffolds=[(.25,4.28,2.9,8.45),(1.65,4.67,2.65,9.10),(2.93,5.04,2.95,9.00),
           (4.20,4.46,3.15,8.55),(5.37,5.30,2.35,9.55)]
for branch,(angle,start_z,extent,tip_z) in enumerate(scaffolds):
    direction=Vector((math.cos(angle),math.sin(angle),0))
    start=Vector((.07*math.sin(start_z*.9),.035*math.sin(start_z*1.4),start_z))
    knee=direction*.52+Vector((0,0,5.85+branch*.045))
    tip=direction*extent+Vector((0,0,tip_z))
    lower=curved(start,start.lerp(knee,.52)+Vector((-.06,.045,.10)),knee,5)
    upper=curved(knee,direction*(extent*.71)+Vector((-.16,.22,7.95+branch*.10)),tip,10)
    stem=lower+upper[1:]
    # Smaller upper limbs and steady taper preserve real structure behind leaves.
    wood_path(stem,[.142*(1-i/(len(stem)-1))**1.22+.014 for i in range(len(stem))],18,35)
    for sub in range(8):
        t=.10+sub*.112; at=min(len(upper)-2,int(t*(len(upper)-1)))
        base=upper[at].lerp(upper[at+1],t*(len(upper)-1)-at)
        th=angle+(-1 if sub%2 else 1)*rng.uniform(.48,1.45)
        spread=rng.uniform(.78,1.40)
        end=base+Vector((math.cos(th)*spread,math.sin(th)*spread,rng.uniform(.50,1.25)))
        lateral=curved(base,base.lerp(end,.47)+Vector((0,0,.22)),end,4)
        wood_path(lateral,[.034,.027,.020,.013,.006],9)
        for twig in range(4):
            tb=lateral[twig].lerp(lateral[twig+1],.70)
            te=tb+Vector((rng.uniform(-.57,.57),rng.uniform(-.57,.57),rng.uniform(-.08,.65)))
            wood_path([tb,tb.lerp(te,.5)+Vector((0,0,.08)),te],[.008,.005,.0025],6)
            leaf_centres.extend([te,te.lerp(tb,.40)])
# 3,200 individually folded, seven-lobed leaves. Leaf clusters start well below
# the outer twig tips so the centre of the crown is filled, with small sky gaps.
leaf_outline=[(0,-1),(-.26,-.42),(-.78,-.54),(-.55,-.09),(-1,.14),(-.42,.28),(-.36,.81),(0,.47),(.37,.90),(.44,.29),(1,.12),(.58,-.11),(.79,-.49),(.26,-.40)]
for ci,centre in enumerate(leaf_centres):
    for j in range(10):
        p=centre+Vector((rng.uniform(-.49,.49),rng.uniform(-.49,.49),rng.uniform(-.37,.46)))
        theta=rng.uniform(0,math.tau); normal=Vector((rng.uniform(-.8,.8),rng.uniform(-.8,.8),rng.uniform(.25,1))).normalized()
        u=Vector((math.cos(theta),math.sin(theta),0)); v=normal.cross(u).normalized();u=v.cross(normal).normalized()
        size=rng.uniform(.15,.225)
        verts=[p+normal*.027]+[p+u*x*size+v*y*size for x,y in leaf_outline]
        mat=rng.choices(['leaf','leaf-lit','leaf-dark','leaf-olive'],[.42,.15,.26,.17])[0]
        m.geo(verts,[(0,k+1,(k+1)%len(leaf_outline)+1) for k in range(len(leaf_outline))],mat)
# Ground tree grate: actual narrow radial gaps, a square frame, no solid road slab.
for y in (-.675,.675):m.box((0,y,.022),(1.39,.045,.045),'iron')
for x in (-.675,.675):m.box((x,0,.022),(.045,1.39,.045),'iron')
for side in (-1,1):
    for j in range(16):
        x=-.655+j*.0873; free=math.sqrt(max(0,.32**2-x*x))
        length=.68-free
        if length>0:m.box((x,side*(free+length/2),.019),(.029,length,.037),'iron')
save_asset(m,'悬铃木：褐灰斑驳树皮、五组错落曲枝、3200片折叠掌状叶与铸铁树池格栅',
    ['bund-zhongshan-2015','shanghai-maoming-canopy','shanghai-pruned-branches','shanghai-trunk-closeup'],
    dict(radius=1.0,height=5),dict(canopyClearHeight=5.0,instanceRecommended=True,
    leafCount=3200,scaffoldBranches=5,referenceReview='references/tourism/plane-tree-reference-review.json'))

if TREE_ONLY:
    item=assets[0];item['sourcePhotosEmbedded']=False
    assert item['bytes']<10_000_000, 'Ordinary tree prototype exceeds 10 MB'
    manifest=json.loads((OUT/'manifest.json').read_text())
    manifest['models']=[item if previous['id']=='plane-tree' else previous for previous in manifest['models']]
    manifest['treeRevisionAt']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    bpy.ops.wm.save_as_mainfile(filepath=str(EDIT))
    # Validation renders always re-import the exported GLBs; no procedural-only
    # preview can accidentally hide lost normals, material assignments or leaves.
    render_dir=TREE_REVIEW/('renders-'+RUN_ID);render_dir.mkdir(parents=True,exist_ok=True)
    validation=[]
    for label,path in [('before',old_tree),('after',OUT/'plane-tree.glb')]:
        if not path: continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(path))
        tree_objects=[obj for obj in bpy.context.scene.objects if obj.type=='MESH']
        imported_triangles=0
        for obj in tree_objects:obj.data.calc_loop_triangles();imported_triangles+=len(obj.data.loop_triangles)
        if label=='after': assert imported_triangles==item['triangles']
        scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24
        scene.cycles.use_denoising=True;scene.render.threads_mode='FIXED';scene.render.threads=2
        scene.render.resolution_x=1280;scene.render.resolution_y=960;scene.render.resolution_percentage=100
        scene.world=bpy.data.worlds.new('Tree review neutral daylight');scene.world.use_nodes=True
        background=scene.world.node_tree.nodes.get('Background');background.inputs[0].default_value=(.64,.73,.79,1);background.inputs[1].default_value=.65
        scene.view_settings.view_transform='AgX'
        bpy.ops.object.light_add(type='SUN',location=(8,-12,18));sun=bpy.context.object
        sun.rotation_euler=(.42,-.48,-.6);sun.data.energy=2.0;sun.data.angle=.16
        bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.025));floor=bpy.context.object
        mat=bpy.data.materials.new('Review paving');mat.diffuse_color=(.26,.28,.27,1);floor.data.materials.append(mat)
        bpy.ops.object.camera_add();camera=bpy.context.object;scene.camera=camera
        views=[('front',(14,-23,8),(0,0,6),'ORTHO',15),('side',(-22,-11,8),(0,0,6),'ORTHO',15),
               ('driver',(6,-11,1.65),(0,0,5.2),'PERSP',27),('bark',(1.5,-2.6,2.7),(0,0,2.5),'PERSP',58)]
        for name,position,target,projection,lens in views:
            if label=='before' and name in ('side','bark'):continue
            camera.location=position;camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
            camera.data.type=projection
            if projection=='ORTHO':camera.data.ortho_scale=lens
            else:camera.data.lens=lens
            image_path=render_dir/(label+'-'+name+'.png');scene.render.filepath=str(image_path)
            bpy.ops.render.render(write_still=True)
            validation.append(dict(asset=label,view=name,file=str(image_path.relative_to(ROOT)),triangles=imported_triangles))
    (render_dir/'validation.json').write_text(json.dumps(dict(asset=item,renders=validation),ensure_ascii=False,indent=2))
    print('TREE_REVIEW_COMPLETE',str(render_dir),item['bytes'],item['triangles'],flush=True)
    sys.exit(0)

# Bund street photograph shows a tall central historic lantern and a single
# curved side arm ending in a slim modern lamp, rather than two globe lamps.
m=Mesh('streetlamp')
m.lathe([(0,.245),(.10,.245),(.17,.215),(.28,.215),(.37,.16),(.52,.13),(1.0,.115),(1.06,.14),(1.12,.14),(1.18,.093),(7.10,.065),(7.15,.10),(7.2,.09)],'iron',n=36)
for a in range(4):
    th=a*math.tau/4+math.pi/4;x=.175*math.cos(th);y=.175*math.sin(th)
    m.rod((x,y,.08),(x,y,.13),.019,'bolt',6)
pts=[(.05+2.0*t,0,6.18+.55*math.sin(t*math.pi*.54)) for t in [i/30 for i in range(31)]]
m.curve(pts,.033,'iron',12)
m.box((2.03,0,6.74),(.68,.16,.045),'iron',rotation=.11)
m.box((2.04,0,6.714),(.58,.125,.008),'lamp')
m.lathe([(7.15,.11),(7.22,.18),(7.29,.13)],'iron',n=24)
m.lathe([(7.27,.108),(7.69,.108)],'lamp-glass',n=12)
for a in range(6):
    t=a*math.tau/6;x=.117*math.cos(t);y=.117*math.sin(t)
    m.rod((x,y,7.27),(x,y,7.71),.011,'iron',8)
m.lathe([(7.68,.15),(7.72,.15),(7.84,.035),(7.9,.015)],'iron',n=24)
m.rod((0,0,7.88),(0,0,8.06),.013,'iron',10)
save_asset(m,'外滩实景灯杆：中央历史灯笼、单侧弯曲灯臂及细长道路照明灯',['bund-street-wide'],dict(radius=.32,height=8.06),dict(styleConfidence='silhouette traced from inspected 2025 Bund photograph; dimensions inferred'))

# No invented business names: direction sign uses only a physical arrow.
m=Mesh('road-sign')
m.lathe([(0,.15),(.06,.15),(.11,.11),(.18,.065),(3.05,.045)],'steel',n=20)
m.box((0,.03,2.70),(1.0,.06,.34),'steel')
m.box((0,.067,2.70),(.955,.012,.297),'blue')
for z in (2.571,2.829):m.box((0,.076,z),(.9,.006,.013),'white')
for x in (-.45,.45):m.box((x,.076,2.70),(.013,.006,.264),'white')
m.box((-.06,.08,2.70),(.38,.01,.042),'white')
m.face([(.13,.087,2.80),(.26,.087,2.70),(.13,.087,2.60)],'white')
for z in (2.59,2.81):m.rod((0,-.03,z),(0,-.09,z),.024,'bolt',8)
save_asset(m,'无商业标识的蓝底方向牌：边框、箭头和背面抱箍',['lujiazui-intersection'],dict(radius=.23,height=3.05))

m=Mesh('bench')
for i in range(6):m.box((0,-.225+i*.088,.47),(1.80,.071,.038),'wood' if i%2 else 'wood-light')
for i in range(5):m.box((0,-.29-.02*i,.63+i*.071),(1.8,.045,.055),'wood' if i%2 else 'wood-light')
for x in (-.64,.64):
    m.prism((x,-.24,.04),(x,-.20,.46),.05,.065,'iron')
    m.prism((x,.23,.04),(x,.19,.46),.05,.065,'iron')
    m.prism((x,-.22,.43),(x,.23,.43),.055,.065,'iron')
    m.prism((x,-.21,.40),(x,-.405,.97),.045,.06,'iron')
    pts=[(x,-.28,.57),(x,-.26,.70),(x,-.16,.72),(x,.18,.72),(x,.26,.66),(x,.23,.48)]
    m.curve(pts,.024,'iron',12)
    for y in (-.23,.23):m.box((x,y,.025),(.12,.12,.045),'iron')
for x in (-.61,.61):
    for j in range(6):m.rod((x,-.225+j*.088,.491),(x,-.225+j*.088,.496),.009,'bolt',8)
save_asset(m,'滨江木条长椅：分离木条、靠背、扶手和螺栓',['bund-street-wide'],dict(radius=.99,height=.99))

m=Mesh('litter-bin')
m.box((0,0,.05),(.40,.37,.10),'iron')
m.box((0,0,.49),(.41,.36,.79),'steel')
for side in (-1,1):
    m.box((0,side*.187,.47),(.33,.02,.64),'stone-dark')
    for x in (-.16,.16):m.box((x,side*.201,.47),(.015,.012,.63),'edge')
    m.box((0,side*.207,.71),(.265,.011,.105),'rubber')
    m.box((0,side*.224,.778),(.30,.067,.025),'steel')
    for x in (-.12,.12):m.rivet((x,side*.21,.19),axis=(0,side,0),radius=.008)
m.box((0,0,.915),(.48,.44,.06),'steel')
m.box((0,0,.952),(.29,.27,.012),'iron')
for i in range(7):m.box((-.113+i*.038,0,.961),(.023,.22,.011),'steel')
save_asset(m,'独立垃圾桶：投口遮雨檐、可拆门板和顶盖条格',['bund-street-wide'],dict(radius=.34,height=.97))

m=Mesh('river-railing')
# The inspected near-shore foreground has stone posts and dark brown handrails;
# it is different from the bridge's fine, light grey steel pedestrian railing.
for x in (-1.40,1.40):
    m.box((x,0,.075),(.19,.19,.15),'stone-dark')
    m.box((x,0,.58),(.16,.16,.92),'stone')
    m.box((x,0,1.055),(.195,.19,.10),'stone-dark')
    m.box((x,0,.20),(.18,.18,.04),'stone-dark')
for z in (.57,1.105):
    m.box((0,0,z),(3.0,.115,.08),'wood')
    m.box((0,0,z+.041),(3.0,.123,.014),'wood-light')
for x in (-1.30,0,1.30):
    m.box((x,0,.82),(.025,.035,.49),'iron')
    m.box((x,0,1.06),(.13,.07,.035),'iron')
    for dx in (-.045,.045):m.rod((x+dx,0,1.075),(x+dx,0,1.085),.009,'bolt',8)
save_asset(m,'近岸三米护栏：混凝土立柱、深色双层扶手和连接件',['waibaidu-side'],dict(halfLength=1.5,halfDepth=.10,height=1.16),dict(moduleLength=3.0,lengthAxis='+X',styleConfidence='Near-shore foreground of inspected bridge photograph; typology reference, not all riverbank sections measured'))

m=Mesh('curb')
# Individual stone blocks with chamfered road-facing upper edge and joints.
for i in range(6):
    x=-1.5+i*.5+.249
    vs=[(x-.245,-.125,0),(x+.245,-.125,0),(x+.245,.125,0),(x-.245,.125,0),
        (x-.245,-.125,.15),(x+.245,-.125,.15),(x+.245,.10,.18),(x-.245,.10,.18),
        (x-.245,.125,.15),(x+.245,.125,.15)]
    m.geo(vs,[(0,3,2,1),(0,1,5,4),(4,5,6,7),(7,6,9,8),(8,9,2,3),(0,4,7,8,3),(1,2,9,6,5)],'stone' if i%3 else 'stone-dark')
save_asset(m,'三米花岗岩路缘：六块独立石材、倒角与石缝',['bund-street-wide'],dict(halfLength=1.5,halfDepth=.125,height=.18),dict(moduleLength=3.0,lengthAxis='+X'))

# Waibaidu Bridge: two eight-panel camelback truss spans, side web planes at
# +/- 5.65m. The roadway is deliberately OPEN: the road surface remains the
# canonical road mesh. Walkways begin at 5.3m; overhead beams clear 5.2m.
m=Mesh('waibaidu-bridge')
placements=ROOT/'public/streets/master/placements.json'
bridge=json.loads(placements.read_text())['bridge'] if placements.exists() else {}
length=bridge.get('length',108.73857871059379)
span=length/2; panels=8; step=span/panels; low=.43
profile=[.43,6.60,7.40,7.85,8.10,7.85,7.40,6.60,.43]
for side in (-1,1):
    x=side*5.70
    # Steel walkway joists stay beyond the driving corridor; walking surface .08m.
    m.box((side*6.47,0,-.04),(1.84,length,.24),'steel')
    m.box((side*6.47,0,.088),(1.84,length,.022),'stone-dark')
    for y in [-length/2+i*3 for i in range(int(length/3)+1)]:
        m.box((side*6.47,y,.103),(1.84,.016,.004),'steel')
    for half in (-1,1):
        centre=half*span/2
        pts=[(x,centre-span/2+i*step,profile[i]) for i in range(panels+1)]
        bottom=[(x,centre-span/2+i*step,low) for i in range(panels+1)]
        # Top and bottom chords are three real plates, not cylinder approximations.
        for a,b in zip(pts,pts[1:]):m.ibeam(a,b,.43,.42,.024)
        for a,b in zip(bottom,bottom[1:]):m.ibeam(a,b,.38,.35,.022)
        for i,(a,b) in enumerate(zip(bottom,pts)):
            if (Vector(b)-Vector(a)).length>.01: m.ibeam(a,b,.30,.28,.018)
            if i<panels:
                # Photo has paired crossing diagonals in its internal panels.
                if 0<i<panels-1:
                    m.ibeam(bottom[i],pts[i+1],.23,.24,.017)
                    m.ibeam(pts[i],bottom[i+1],.23,.24,.017)
            # Gusset plate on both faces, actual fastener rows aligned to joints.
            for level in (low,profile[i]):
                for face in (-1,1):
                    xx=x+face*.229
                    m.box((xx,a[1],level),(.016,.68,.74),'steel')
                    for yy in (-.25,-.13,.0,.13,.25):
                        for zz in (-.26,.26):m.rivet((xx+face*.01,a[1]+yy,level+zz),axis=(face,0,0))
            # Angle splices and individual rivets along the chord web.
            for t in [j/5 for j in range(1,5)]:
                if i<panels:
                    p=Vector(pts[i]).lerp(Vector(pts[i+1]),t)
                    for face in (-1,1):m.rivet((x+face*.223,p.y,p.z),axis=(face,0,0),radius=.018)
    # Railing on the outside edge leaves the two-metre walkway visually legible.
    outer=side*7.43
    for z,r in ((.29,.018),(.88,.018),(1.11,.027)):
        m.rod((outer,-length/2,z),(outer,length/2,z),r,'steel',14)
    for i in range(int(length/.25)+1):
        y=-length/2+i*.25;m.rod((outer,y,.3),(outer,y,1.1),.01,'steel',8)
    for i in range(int(length/2.25)+1):
        y=-length/2+i*2.25;m.box((outer,y,.59),(.067,.07,1.13),'steel')
        m.box((outer,y,.09),(.14,.15,.06),'edge')
# Overhead lateral I beams with bottom always >= 5.2m.
for half in (-1,1):
    centre=half*span/2
    for i,z in enumerate(profile):
        y=centre-span/2+i*step
        if i in (0,panels): continue  # side slopes end at deck; no road-blocking portal
        m.ibeam((-5.7,y,z),(5.7,y,z),.34,.38,.023)
        if i<panels-1:
            z2=profile[i+1];yn=y+step
            m.prism((-5.5,y,z+.05),(5.5,yn,z2+.05),.10,.08,'steel')
            m.prism((5.5,y,z+.05),(-5.5,yn,z2+.05),.10,.08,'steel')
        for x in (-5.49,5.49):
            m.box((x,y,z-.06),(.36,.51,.018),'steel')
# Deck support structure is below road level, never an obstacle across asphalt.
for i in range(13):
    y=-length/2+i*length/12;m.ibeam((-7.5,y,-.32),(7.5,y,-.32),.28,.42,.025)
# End bearing assemblies remain outside the carriageway.
for x in (-5.7,5.7):
    for y in (-length/2,0,length/2):
        m.box((x,y,-.30),(.63,.92,.22),'iron')
        m.box((x,y,-.08),(.70,1,.16),'steel')
        for dy in (-.33,.33):
            for dx in (-.23,.23):m.rod((x+dx,y+dy,-.04),(x+dx,y+dy,.06),.035,'bolt',6)
save_asset(m,'外白渡桥双跨钢桁架：I形钢板截面、节点板、铆钉、侧步道及高净空横梁',
    ['waibaidu-side','waibaidu-deck'],dict(roadHalfWidth=4.8,minimumLowSteelInnerX=5.30),
    dict(lengthAxis='-Z',length=length,carriagewayWidth=9.6,walkwayWidth=2.0,
         minimumCrossbeamBottom=6.41,minimumLowSteelInnerX=5.3,
         reconstruction='Photo-derived silhouette and steelwork type; dimensions constrained to OSM alignment and safe roadway clearance, not survey dimensions.'))

# Supplementary small street furniture; placement is determined by the route plan.
m=Mesh('bollard')
m.lathe([(0,.10),(.05,.10),(.08,.075),(.79,.068),(.85,.06),(.88,.02)],'iron',n=24)
m.lathe([(.61,.070),(.68,.070)],'edge',n=24)
for a in range(4):
    t=a*math.tau/4;m.rod((.07*math.cos(t),.07*math.sin(t),.046),(.07*math.cos(t),.07*math.sin(t),.065),.008,'bolt',6)
save_asset(m,'铸铁短柱：反光金属环和四点地脚',['bund-street-wide'],dict(radius=.11,height=.88))

m=Mesh('traffic-light')
m.lathe([(0,.16),(.09,.16),(.20,.08),(3.0,.058)],'iron',n=20)
m.box((0,.07,2.6),(.29,.22,.87),'iron')
for i,(z,mat) in enumerate([(2.86,'red'),(2.6,'yellow'),(2.34,'green')]):
    m.rod((0,.18,z),(0,.20,z),.094,'rubber',24)
    m.rod((0,.204,z),(0,.211,z),.077,mat,32)
    # Curved visor top and sides; geometry leaves the visible signal circle open.
    for j in range(16):
        a=j*math.pi/16;b=(j+1)*math.pi/16;r=.102
        m.face([(r*math.cos(a),.188,z+r*math.sin(a)),(r*math.cos(b),.188,z+r*math.sin(b)),
                (r*math.cos(b),.34,z+r*math.sin(b)),(r*math.cos(a),.34,z+r*math.sin(a))],'iron')
save_asset(m,'人行道侧交通信号灯：三只分离透镜、遮阳罩和立杆',['lujiazui-intersection'],dict(radius=.23,height=3.0),dict(note='Geometry only; signal timing must be driven by runtime, no fabricated traffic priority.'))

for item in assets:
    item['sourcePhotosEmbedded']=False
manifest=dict(version=1,createdAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    units='metres',axes=dict(up='+Y',forward='-Z',across='+X'),
    sourceLibrary='references/tourism/streets-expansion-photos.json',
    photosAreReferencesOnly=True,models=assets,
    quality=dict(meshDecimation=False,dracoCompression=False,artificialPadding=False,
                 sourcePhotosPreserved=True,treeLeaves='folded lobed polygons, no billboard or canopy spheres'))
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(EDIT))
print('FURNITURE_COMPLETE',sum(a['bytes'] for a in assets),sum(a['triangles'] for a in assets),str(EDIT),flush=True)
