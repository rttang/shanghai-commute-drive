"""Add source-aligned, metre-scale close exterior detail to the Bund district.

Run through scripts/blender-local.sh. Original photo GLBs, generated PNGs and
source photographs are read only. Native source PNGs are embedded. The known
front-elevation windows/columns are measured in build_photo_architecture.py;
secondary-side construction and invisible roof equipment are labelled inferred.
"""
import bpy, bmesh, ast, json, pathlib, math, hashlib, sys, datetime, os
from mathutils import Vector
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from bund_model_helpers import Mesh, material, rectified_front, build_observed_building
OUT=ROOT/'public/streets/districts/bund';OUT.mkdir(parents=True,exist_ok=True)
EDIT=ROOT/'assets/blender/streets';EDIT.mkdir(parents=True,exist_ok=True)
CONFIG=json.loads((ROOT/'src/tour/photo-architecture.json').read_text())[:12]
# Read the existing measured feature declarations, without importing its build,
# cleanup, backup, export or freeze side effects.
tree=ast.parse((ROOT/'scripts/build_photo_architecture.py').read_text())
feature_nodes=[]
for node in tree.body:
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FEATURES' for t in node.targets):feature_nodes.append(node)
    if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call):
        owner=node.value.func.value if isinstance(node.value.func,ast.Attribute) else None
        if isinstance(owner,ast.Name) and owner.id=='FEATURES':feature_nodes.append(node)
        if isinstance(owner,ast.Subscript) and isinstance(owner.value,ast.Name) and owner.value.id=='FEATURES':feature_nodes.append(node)
ns={};exec(compile(ast.Module(body=feature_nodes,type_ignores=[]),'source-feature-measurements','exec'),ns)
FEATURES=ns['FEATURES']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
protected={str(p.relative_to(ROOT)):sha(p) for folder in ['assets/streets/photofacades','public/streets/photo-models'] for p in (ROOT/folder).glob('*') if p.is_file()}
REVIEW_ONLY=os.environ.get('BUND_REVIEW_ONLY')=='1'
ONLY_ID=os.environ.get('BUND_ONLY_ID')
ONLY_IDS=set(ONLY_ID.split(',')) if ONLY_ID else set()
if ONLY_ID and os.environ.get('BUND_OBSERVED_ALL')=='1':
    ONLY_IDS.update(s['id'] for s in json.loads((ROOT/'references/tourism/bund-new-building-config.json').read_text()) if s.get('observedModel'))
FIX_FILE=ROOT/'references/tourism/bund-loop-readback-corrections.json'
FIX_BATCH=json.loads(FIX_FILE.read_text()) if FIX_FILE.exists() else {}
if ONLY_ID and FIX_BATCH.get('status')=='pending':ONLY_IDS.update(FIX_BATCH['buildIds'])
PREVIOUS_MANIFEST=None
if ONLY_ID:
    PREVIOUS_MANIFEST=json.loads((OUT/'manifest.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(EDIT/'bund-detailed.blend'))
    for target_id in ([] if REVIEW_ONLY else ONLY_IDS):
        original=bpy.data.objects.get('bund-detailed-'+target_id)
        assert original,'Existing revision target missing: '+target_id
        for obj in list(original.children_recursive)+[original]:bpy.data.objects.remove(obj,do_unlink=True)
else:
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
stone=material('bund-carved-limestone',(.56,.51,.435),.8)
edge=material('bund-polished-sill',(.65,.60,.51),.66)
frame=material('bund-bronze-frame',(.085,.073,.048),.34,.52)
iron=material('bund-patinated-iron',(.028,.041,.04),.40,.65)
copper=material('bund-weathered-copper-seams',(.105,.225,.164),.62,.55)
redstone=material('bund-carved-redstone',(.37,.155,.094),.8)
roofmat=material('bund-roof-lead',(.175,.19,.18),.85,.30)
glass=material('bund-secondary-glass',(.075,.10,.12),.22,.30)
records=[];roots=[]

def framed_window(mesh,x,y,z,w,h,masonry,divisions=2,arched=False):
    """True recessed glazing retained from photo mesh, physically profiled surround."""
    t=min(.095,w*.075);outer=min(.16,w*.11)
    # Chiselled masonry reveal with a narrow inner lip.
    for sign in [-1,1]:
        mesh.bevel_box((x+sign*(w/2+outer/2),y+.045,z),(outer,.25,h+outer*2),masonry,.026)
        mesh.bevel_box((x+sign*(w/2-t/2),y-.20,z),(t,.12,h),frame,.012)
    for sign in [-1,1]:
        mesh.bevel_box((x,y+.045,z+sign*(h/2+outer/2)),(w+2*outer,.25,outer),masonry,.025)
        mesh.bevel_box((x,y-.20,z+sign*(h/2-t/2)),(w,.12,t),frame,.012)
    for k in range(1,divisions):mesh.bevel_box((x-w/2+w*k/divisions,y-.20,z),(t*.65,.12,h),frame,.01)
    if h>1.6:mesh.bevel_box((x,y-.19,z+h*.12),(w,.12,t*.7),frame,.01)
    if h>3.8:mesh.bevel_box((x,y-.19,z-h*.19),(w,.12,t*.7),frame,.01)
    # Undercut projecting sill, three layers rather than a flat strip.
    mesh.bevel_box((x,y+.17,z-h/2-.11),(w+.34,.45,.13),edge,.04)
    mesh.bevel_box((x,y+.115,z-h/2-.23),(w+.17,.24,.105),masonry,.025)
    if arched:mesh.arch(x,y+.15,z+h*.32,w*.92,h*.18,.12,.22,masonry)

def enrich_existing(spec):
    key=spec['id'];before=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(ROOT/'public/streets/photo-models'/f'{key}.glb'))
    imported=[o for o in bpy.data.objects if o not in before]
    top=[o for o in imported if o.parent not in imported]
    root=bpy.data.objects.new('bund-detailed-'+key,None);bpy.context.collection.objects.link(root)
    for obj in top:obj.parent=root
    # Imported glTF has Blender's original +Y front / Z up. Native source pixels
    # replace the earlier JPEG: this is not a resized or generatively enlarged map.
    for obj in imported:
        if obj.type!='MESH':continue
        for mat in obj.data.materials:
            if not mat or not mat.use_nodes:continue
            if mat.name.startswith('photo-'):
                image_key=mat.name.removeprefix('photo-').split('.')[0]
                source=ROOT/'assets/streets/photofacades'/f'{image_key}.png'
                if source.exists():
                    for node in mat.node_tree.nodes:
                        if node.type=='TEX_IMAGE':node.image=bpy.data.images.load(str(source),check_existing=True)
    f=FEATURES[key];h=spec.get('facadeHeight',spec['height']);d=spec['depth'];front=math.dist(*spec['front'])
    left,right=f['profile'][0][0],f['profile'][-1][0];width=front/(right-left);mid=(left+right)/2;roofz=(1-spec['bodyTop'])*h
    m=Mesh(root);masonry=redstone if key=='palace-hotel' else stone
    if not spec.get('side'):
        # Replace the previous stretched, repeated facade-strip side walls.
        # Detect the two swept side planes including the mapped rear shear.
        shift=spec.get('backShift',0)
        for obj in imported:
            if obj.type!='MESH':continue
            bm=bmesh.new();bm.from_mesh(obj.data);delete=[]
            for face in bm.faces:
                coords=[v.co for v in face.verts]
                if max(p.y for p in coords)>0.02 or min(p.y for p in coords)>=-.02:continue
                if max(p.z for p in coords)-min(p.z for p in coords)<.2:continue
                if any(all(abs(p.x-(-p.y/d*shift+sign*front/2))<.025 for p in coords) for sign in [-1,1]):delete.append(face)
            if delete:bmesh.ops.delete(bm,geom=delete,context='FACES');bm.to_mesh(obj.data);obj.data.update()
            bm.free()
        side_levels=max(2,round(roofz/(h/max(3,round(h/4.0)))))
        storey=roofz/side_levels
        source_mat=next((ma for ob in imported if ob.type=='MESH' for ma in ob.data.materials if ma and ma.name.split('.')[0]=='photo-'+key),masonry)
        crop=f['windows'][0] if f['windows'] else (.35,.40,.45,.49)
        ca,cb,cc,ce=crop;photo_uv=[(ca,1-ce),(cb,1-ce),(cb,1-cc),(ca,1-cc)]
        for sign in [-1,1]:
            bays=max(2,round(d/3.8));pitch=d/bays
            for level in range(side_levels):
                for bay in range(bays):
                    yy=-(bay+.5)*pitch;xx=sign*front/2-yy/d*shift;zc=(level+.5)*storey
                    ww=pitch*.48;hh=storey*.55
                    def pt(a,b,c):return (xx-a/d*shift+sign*b,yy+a,zc+c)
                    def sideface(coords,mat,uv=None):
                        if sign<0:coords=coords[::-1];uv=uv[::-1] if uv else None
                        m.face(coords,mat,uv)
                    for aa,bb,c0,c1 in [(-pitch/2,-ww/2,-storey/2,storey/2),(ww/2,pitch/2,-storey/2,storey/2),(-ww/2,ww/2,-storey/2,-hh/2),(-ww/2,ww/2,hh/2,storey/2)]:sideface([pt(aa,0,c0),pt(bb,0,c0),pt(bb,0,c1),pt(aa,0,c1)],masonry)
                    sideface([pt(-ww/2,-.24,-hh/2),pt(ww/2,-.24,-hh/2),pt(ww/2,-.24,hh/2),pt(-ww/2,-.24,hh/2)],source_mat,photo_uv)
                    for a,b in [((-ww/2,-hh/2),(ww/2,-hh/2)),((ww/2,-hh/2),(ww/2,hh/2)),((ww/2,hh/2),(-ww/2,hh/2)),((-ww/2,hh/2),(-ww/2,-hh/2))]:sideface([pt(a[0],0,a[1]),pt(b[0],0,b[1]),pt(b[0],-.26,b[1]),pt(a[0],-.26,a[1])],edge)
                    for x in [-ww/2,0,ww/2]:m.rod(pt(x,-.13,-hh/2),pt(x,-.13,hh/2),.045,frame,8)
                    for z in [-hh/2,hh*.12,hh/2]:m.rod(pt(-ww/2,-.13,z),pt(ww/2,-.13,z),.045,frame,8)
                    m.rod(pt(-ww/2-.13,.12,-hh/2-.12),pt(ww/2+.13,.12,-hh/2-.12),.11,edge,8)
    count=0
    for a,b,c,e in f['windows']:
        x=(mid-(a+b)/2)*width;z=(1-(c+e)/2)*h;w=(b-a)*width;wh=(e-c)*h
        y=-1.3 if (c+e)/2<spec['bodyTop'] else 0
        framed_window(m,x,y,z,w,wh,masonry,divisions=3 if w>2.5 else 2,arched=key in ['russo-chinese-bank','china-merchants'] and wh>2.3)
        count+=1
    # Each column is measured on its building's source elevation. Astragals,
    # torus base rings, chamfered plinth, entasis and fluting are explicit geometry.
    for u,v0,v1,rad in f['columns']:
        x=(mid-u)*width;r=rad*width;z0=(1-v1)*h;z1=(1-v0)*h
        m.bevel_box((x,.04,z0-.20),(r*2.70,r*2.30,.26),masonry,.055)
        m.lathe((x,.035),[(z0-.07,r*1.30),(z0+.025,r*1.34),(z0+.11,r*1.26),(z0+.18,r*1.11),(z0+.27,r*1.055)],masonry,64)
        rings=[(z0+.24,r*1.03),(z0+(z1-z0)*.33,r*1.045),(z0+(z1-z0)*.70,r*.986),(z1-.24,r*.95)]
        m.lathe((x,.035),rings,masonry,96,flutes=20)
        m.lathe((x,.035),[(z1-.27,r*.99),(z1-.18,r*1.08),(z1-.10,r*1.16),(z1-.03,r*1.3),(z1+.09,r*1.30)],masonry,64)
        m.bevel_box((x,.02,z1+.14),(r*2.75,r*2.30,.15),edge,.045)
        if key in ['hsbc-bund','bank-taiwan','russo-chinese-bank']:
            for sign in [-1,1]:
                # Ionic corner volutes, visible spiral stone scrolls.
                pts=[]
                for j in range(33):
                    theta=j/32*math.tau*1.45;rr=r*.27*(1-j/42)
                    pts.append((x+sign*r*.89+math.cos(theta)*rr,r*.88,z1-.035+math.sin(theta)*rr))
                for a,b in zip(pts,pts[1:]):m.rod(a,b,r*.04,masonry,8)
    for a,b,offset in f['bands']:
        z=(1-(a+b)/2)*h;bh=(b-a)*h
        if z>roofz+3:continue
        # Multilevel cornice fascia and shadow groove.
        m.bevel_box((0,offset+.045,z+bh*.42),(front+.18,.15,.12),edge,.03)
        m.bevel_box((0,offset+.09,z-bh*.42),(front+.26,.24,.12),masonry,.03)
        if bh>.6:
            pitch=.55 if front<45 else .65
            for i in range(max(2,int(front/pitch))):
                x=-front/2+pitch*.5+i*pitch
                m.bevel_box((x,offset+.02,z-bh*.21),(.17,.21,.19),masonry,.026)
    # Source-specific pilasters receive actual recessed edge molding.
    for a,b,c,e,offset in f.get('pilasters',[]):
        if offset<=0:continue
        x=(mid-(a+b)/2)*width;z=(1-(c+e)/2)*h;w=(b-a)*width;hh=(e-c)*h
        for sign in [-1,1]:m.bevel_box((x+sign*w*.43,offset+.03,z),(.07,.09,hh),edge,.02)
    # Side roof parapets follow the measured depth and rear shear. The unseen
    # construction details are documented as inferred, not photographic facts.
    shift=spec.get('backShift',0)
    for sign in [-1,1]:
        x=sign*front/2
        m.rod((x,0,roofz+.29),(x+shift,-d,roofz+.29),.30,masonry,8)
        m.rod((x,0,roofz+.62),(x+shift,-d,roofz+.62),.20,edge,8)
    m.box((shift,-d+.20,roofz+.29),(front,.32,.58),masonry)
    m.box((shift,-d+.20,roofz+.62),(front+.15,.48,.14),edge)
    # Individual weathering coping joints and roof drains at practical spacing.
    for sign in [-1,1]:
        for j in range(max(2,int(d/2.2))):
            y=-.6-j*2.2
            m.box((sign*front/2-y/d*shift,y,roofz+.70),(.52,.025,.025),roofmat)
        for yy in [-d*.25,-d*.75]:
            m.rod((sign*(front/2+.12)-yy/d*shift,yy,.45),(sign*(front/2+.12)-yy/d*shift,yy,roofz-.3),.065,iron,12)
    if key=='hsbc-bund':
        z=(1-.215)*h;r=width*.092;cy=-r-1.3
        # Cupola drum's separate pilasters and radial masonry ribs.
        for i in range(32):
            th=i*math.tau/32
            for j in range(12):
                a=j*math.pi/32;b=(j+1)*math.pi/32
                p=(r*math.cos(a)*math.cos(th),cy+r*math.cos(a)*math.sin(th),z+.67*r*math.sin(a))
                q=(r*math.cos(b)*math.cos(th),cy+r*math.cos(b)*math.sin(th),z+.67*r*math.sin(b))
                m.rod(p,q,.042,edge,8)
        for i in range(16):
            th=i*math.tau/16;x=r*.94*math.cos(th);y=cy+r*.94*math.sin(th)
            m.rod((x,y,z-1.4),(x,y,z+.2),.15,masonry,24)
        m.lathe((0,cy),[(z-.35,r*1.01),(z-.22,r*1.055),(z-.10,r*1.055),(z+.025,r*1.01)],edge,128)
    if key=='customs-house':
        cy=-5.5
        for nx,ny in [(0,1),(1,0),(0,-1),(-1,0)]:
            n=Vector((nx,ny,0));t=Vector((ny,-nx,0));up=Vector((0,0,1))
            for z,half,hgt in [(44.5,4.58,11.8),(58.5,3.84,13.0),(69.6,2.86,6.0)]:
                for off in [-half+.18,half-.18]:
                    p=Vector((0,cy,z))+n*half+t*off
                    m.rod(p-up*hgt/2,p+up*hgt/2,.09,edge,12)
            # Deep louver bays under the clock, with separate horizontal blades.
            for offset in [-2.2,0,2.2]:
                c=Vector((0,cy,45))+n*5.10+t*offset
                for j in range(14):
                    a=c+t*(-.47)+up*(-2.4+j*.36);b=c+t*.47+up*(-2.4+j*.36)
                    m.rod(a,b,.075,iron,8)
            c=Vector((0,cy,58.5))+n*3.94
            # Cast clock rim with layered rings, 96 segments keeps it circular.
            for radius,rr in [(2.80,.075),(2.65,.025)]:
                for j in range(96):
                    a=j*math.tau/96;b=(j+1)*math.tau/96
                    m.rod(c+(t*math.sin(a)+up*math.cos(a))*radius,c+(t*math.sin(b)+up*math.cos(b))*radius,rr,frame,8)
    if key=='peace-hotel':
        z0=(1-.163)*h;z1=(1-.064)*h;a=width*.181;b=width*.048;cy=-a-1.3
        low=[Vector(v) for v in [(-a,cy-a,z0),(a,cy-a,z0),(a,cy+a,z0),(-a,cy+a,z0)]]
        high=[Vector(v) for v in [(-b,cy-b,z1),(b,cy-b,z1),(b,cy+b,z1),(-b,cy+b,z1)]]
        # Horizontal copper sheet laps, individual standing seams already in base.
        for i in range(4):
            for j in range(1,18):
                f=j/18;p=low[i].lerp(high[i],f);q=low[(i+1)%4].lerp(high[(i+1)%4],f)
                m.rod(p,q,.027,copper,8)
        for i in range(4):m.rod(low[i],low[(i+1)%4],.095,copper,12)
    detail=m.flush()
    root['detailBasis']='Measured source elevation windows, pilasters and columns; explicit secondary construction inference'
    root['inferredDetails']='Hidden elevations, parapet construction, drainpipe locations and roof joints; not a surveyed replica'
    root['windowDetailCount']=count
    center=[sum(v[i] for v in spec['front'])/2 for i in range(2)]
    heading=math.atan2(-(spec['front'][1][1]-spec['front'][0][1]),spec['front'][1][0]-spec['front'][0][0])
    return root,dict(id=key,name=spec['name'],ways=spec['ways'],center=center,heading=heading,height=spec['height'],referenceIds=[spec['reference']],detailDescription=f'{count} source-aligned recessed windows; profiled stone surrounds and bronze mullions; column entasis/flutes/bases/capitals; cornice dentils, roof coping/drains; landmark-specific roof and clock detailing',inferredDetails=root['inferredDetails'],measuredWindows=count)


def save_one(root,entry):
    bpy.ops.object.select_all(action='DESELECT');root.select_set(True)
    for obj in root.children_recursive:obj.select_set(True)
    bpy.context.view_layer.objects.active=root
    path=OUT/(entry['id']+'.glb')
    if path.exists():
        backup=ROOT/'assets/streets/bund-loop-backup-20260909-observed'/(path.stem+'-'+sha(path)[:12]+path.suffix)
        if not backup.exists():
            import shutil
            shutil.copy2(path,backup)
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_apply=True,export_extras=True,export_image_format='AUTO',export_draco_mesh_compression_enable=entry['id'] not in {x['id'] for x in CONFIG},export_draco_mesh_compression_level=4,export_draco_position_quantization=22,export_draco_normal_quantization=16,export_draco_texcoord_quantization=20)
    meshes=[o for o in root.children_recursive if o.type=='MESH']
    vertices=[o.matrix_world@Vector(corner) for o in meshes for corner in o.bound_box]
    bounds=dict(min=[min(p[i] for p in vertices) for i in range(3)],max=[max(p[i] for p in vertices) for i in range(3)])
    entry.update(file=str(path.relative_to(ROOT/'public')),bytes=path.stat().st_size,triangles=sum(len(p.vertices)-2 for o in meshes for p in o.data.polygons),meshes=len(meshes),sha256=sha(path),geometryCompression=('none' if entry['id'] in {x['id'] for x in CONFIG} else 'Draco position22 normal16 UV20; unchanged triangle count'),texturePolicy=('Photographs inspected as reference only; no embedded raster textures' if entry.get('referenceOnlyTextures') else 'existing facade PNG or matched reference JPEG at source pixels; no resizing; unreferenced facades have explicit procedural materials'),localBlenderBounds=bounds,actualModelHeight=bounds['max'][2]-bounds['min'][2])
    if root.get('rectifiedFacadeFile'):
        image_path=ROOT/root['rectifiedFacadeFile']
        entry['rectifiedFacade']=dict(file=root['rectifiedFacadeFile'],sha256=sha(image_path),sourceAlignedWindows=root['sourceAlignedWindows'],sourceAlignedColumns=root['sourceAlignedColumns'],mapping=root['facadeMapping'])
    records.append(entry);roots.append(root)
    print('BUND_DETAILED_MODEL',json.dumps(entry,ensure_ascii=False),flush=True)

for spec in CONFIG:
    if ONLY_ID:continue
    if os.environ.get('BUND_NEW_ONLY')=='1':
        path=OUT/(spec['id']+'.glb');before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(path));objects=[o for o in bpy.data.objects if o not in before];root=[o for o in objects if o.parent not in objects][0]
        previous=json.loads((OUT/'manifest.json').read_text());entry=next(x for x in previous['models'] if x['id']==spec['id']);records.append(entry);roots.append(root)
    else:
        root,entry=enrich_existing(spec);save_one(root,entry)

# Optional new buildings are emitted by the same deterministic script, using a
# separately audited photo/OSM catalog. No missing reference silently falls back.
NEW_CONFIG=ROOT/'references/tourism/bund-new-building-config.json'
if NEW_CONFIG.exists():
    from bund_model_helpers import Mesh
    new_specs=json.loads(NEW_CONFIG.read_text())
    for spec in new_specs:
        if REVIEW_ONLY:continue
        if ONLY_IDS and spec['id'] not in ONLY_IDS:continue
        root=bpy.data.objects.new('bund-detailed-'+spec['id'],None);bpy.context.collection.objects.link(root)
        if spec.get('observedModel'):
            entry=build_observed_building(root,spec);save_one(root,entry);continue
        m=Mesh(root);h=spec['height']*(.72 if spec.get('roofType')=='stepped-tower' else 1);pts=spec['localFootprint'];rect=spec.get('rectifiedFacade')
        if rect:
            bottom=rect.get('groundV',.98);top=min(v for u,v in rect['profile']);h=spec['height']*(bottom-rect.get('bodyTopV',top))/(bottom-top)
        roofz=h
        mats={}
        for name,color in spec['colors'].items():mats[name]=material('bund-'+spec['id']+'-'+name,color)
        wall=mats['wall'];trim=mats['trim'];levels=round(spec['levels']*.72) if spec.get('roofType')=='stepped-tower' else spec['levels'];floor=h/levels
        window_mat=glass
        if rect or spec.get('windowCrops'):
            photo=ROOT/(rect['file'] if rect else spec['photoPath']);assert photo.exists(),photo
            window_mat=material('bund-source-window-'+spec['id'],(1,1,1),.48)
            node=window_mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(photo),check_existing=True)
            window_mat.node_tree.links.new(node.outputs['Color'],window_mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
        def window_uv(bay,level):
            if rect:
                a,b,c,d=rect['windows'][(bay+level)%len(rect['windows'])]
                return [(a,1-d),(b,1-d),(b,1-c),(a,1-c)]
            if not spec.get('windowCrops'):return None
            crop=spec['windowCrops'][(bay+level)%len(spec['windowCrops'])];a,b,c,d=crop
            coords=[(a,d),(b,d),(b,c),(a,c)]
            if spec.get('imageOrientation')==6:return [(v,u) for u,v in coords]
            if spec.get('imageOrientation')==8:return [(1-v,1-u) for u,v in coords]
            return [(u,1-v) for u,v in coords]
        building_front=spec.get('frontEdge')
        minx=min(p[0] for p in pts);maxx=max(p[0] for p in pts);miny=min(p[1] for p in pts);maxy=max(p[1] for p in pts)

        for a,b in zip(pts,pts[1:]+pts[:1]):
            av=Vector((a[0],a[1],0));bv=Vector((b[0],b[1],0));t=(bv-av).normalized();n=Vector((t.y,-t.x,0));length=(bv-av).length
            # Footprint vertices are counterclockwise; right-hand normal is outward.
            is_front=building_front is not None and math.dist(a,building_front[0])+math.dist(b,building_front[1])<.5
            if is_front and rect:
                basis=rectified_front(m,spec,av,bv,window_mat,trim,frame)
                root['rectifiedFacadeFile']=rect['file'];root['sourceAlignedWindows']=basis['windowCount'];root['sourceAlignedColumns']=len(rect.get('columns',[]));root['facadeMapping']='UV on actual recessed wall and window bottom; no offset billboard'
                continue
            bays=spec.get('frontBays',0) if is_front else max(1,round(length/spec.get('bayWidth',3.8)))
            bays=max(spec.get('minimumBays',1),bays);bw=length/bays
            for level in range(levels):
                z0=level*floor;z1=(level+1)*floor
                for bay in range(bays):
                    p=av+t*(bay*bw);q=p+t*bw
                    # Recessed bay centre and solid corner piers give every wall
                    # real silhouette at oblique viewing directions.
                    ww=spec.get('windowWidth',bw*.52);wh=floor*spec.get('windowHeightFraction',.55);wc=(p+q)*.5+Vector((0,0,z0+floor*.53))
                    def v(x,y,z):return tuple(wc+t*x+n*y+Vector((0,0,z)))
                    for x0,x1,zz0,zz1 in [(-bw/2,-ww/2,-floor*.53,floor*.47),(ww/2,bw/2,-floor*.53,floor*.47),(-ww/2,ww/2,-floor*.53,-wh/2),(-ww/2,ww/2,wh/2,floor*.47)]:
                        m.face([v(x0,0,zz0),v(x1,0,zz0),v(x1,0,zz1),v(x0,0,zz1)],wall)
                    m.face([v(-ww/2,-.24,-wh/2),v(ww/2,-.24,-wh/2),v(ww/2,-.24,wh/2),v(-ww/2,-.24,wh/2)],window_mat,window_uv(bay,level))
                    for x in [-ww/2,0,ww/2]:m.rod(wc+t*x-n*.14+Vector((0,0,-wh/2)),wc+t*x-n*.14+Vector((0,0,wh/2)),.055,frame,8)
                    for z in [-wh/2,0,wh/2]:m.rod(wc-t*ww/2-n*.14+Vector((0,0,z)),wc+t*ww/2-n*.14+Vector((0,0,z)),.055,frame,8)
                    # Four masonry reveal return surfaces.
                    for v0,v1 in [((-ww/2,-wh/2),(ww/2,-wh/2)),((ww/2,-wh/2),(ww/2,wh/2)),((ww/2,wh/2),(-ww/2,wh/2)),((-ww/2,wh/2),(-ww/2,-wh/2))]:m.face([v(*[v0[0],0,v0[1]]),v(v1[0],0,v1[1]),v(v1[0],-.26,v1[1]),v(v0[0],-.26,v0[1])],trim)
                    if ((level==0 and spec.get('arches')) or (level==levels-1 and spec.get('roofType')=='signal-mast')) and is_front:
                        # Entrance arches in the wall's own tangent frame.
                        archroot=bpy.data.objects.new(spec['id']+'-entrance',None);bpy.context.collection.objects.link(archroot);archroot.parent=root
                        archmesh=Mesh(archroot);archmesh.arch(0,.08,0,ww,wh*.25,.14,.20,trim);archmesh.flush()
                        archroot.location=wc+Vector((0,0,wh*.25));archroot.rotation_euler.z=math.atan2(t.y,t.x)
                for z,off in [(z0,.18),(z1-.18,.24)]:m.rod(av+n*off+Vector((0,0,z)),bv+n*off+Vector((0,0,z)),.12,trim,8)
                if is_front and level in spec.get('balconyLevels',[]):
                    for j in range(max(1,int(length/.32))):
                        p=av+t*(j*.32)+n*.35+Vector((0,0,z0+.05))
                        m.rod(p,p+Vector((0,0,.85)),.035,iron,8)
                    m.rod(av+n*.35+Vector((0,0,z0+.92)),bv+n*.35+Vector((0,0,z0+.92)),.045,iron,8)
            if is_front:
                for frac in spec.get('columns',[]):
                    p=av+t*(length*frac)+n*.22;radius=spec.get('columnRadius',.45)
                    lo=floor*spec.get('columnStartLevel',1);hi=floor*spec.get('columnEndLevel',levels-1)
                    m.lathe((p.x,p.y),[(lo-.15,radius*1.35),(lo,radius*1.35),(lo+.18,radius),(hi-.2,radius*.88),(hi-.1,radius*1.25),(hi+.15,radius*1.25)],trim,64,flutes=20 if spec.get('fluted') else 0)
                for j in range(max(1,int(length/.5))):
                    p=av+t*(j*.5)+n*.20+Vector((0,0,h-.28));m.rod(p,p+Vector((0,0,.18)),.10,trim,8)
                roof_type=spec.get('roofType')
                if roof_type=='corner-mansards':
                    for frac in [.10,.90]:
                        p=av+t*(length*frac)-n*1.5
                        m.lathe((p.x,p.y),[(h,2.6),(h+.4,2.8),(h+1.8,2.4),(h+2.5,1.5),(h+2.8,0)],roofmat,48)
                if roof_type in ['corner-turret','paired-turrets']:
                    p=av+t*(length*.08)-n*2.0
                    m.lathe((p.x,p.y),[(h-.1,2.5),(h+.3,2.7),(h+.7,2.3),(h+4.5,2.3),(h+4.7,2.6),(h+5.1,2.6)],trim,16)
                    for j in range(8):
                        th=j*math.tau/8;x=p.x+2.15*math.cos(th);y=p.y+2.15*math.sin(th)
                        m.rod((x,y,h+.8),(x,y,h+4.3),.18,trim,16)
                    if spec['id']=='union-building':m.lathe((p.x,p.y),[(h+5.1,1.4),(h+6.0,1.8),(h+7.1,1.3),(h+7.8,.2),(h+8.6,0)],copper,48)
                    if roof_type=='paired-turrets':
                        p2=av+t*(length*.92)-n*2.0
                        m.lathe((p2.x,p2.y),[(h-.1,2.5),(h+.3,2.7),(h+.7,2.3),(h+4.5,2.3),(h+4.7,2.6),(h+5.1,2.6)],trim,16)
                        for j in range(8):
                            th=j*math.tau/8;x=p2.x+2.15*math.cos(th);y=p2.y+2.15*math.sin(th)
                            m.rod((x,y,h+.8),(x,y,h+4.3),.18,trim,16)
                        for pp in [p,p2]:m.lathe((pp.x,pp.y),[(h+5.1,1.8),(h+5.9,1.5),(h+6.8,.3),(h+7.4,0)],trim,48)
                if roof_type=='paired-pediments':
                    for frac in [.16,.84]:
                        p=av+t*(length*frac);w=length*.23
                        m.face([tuple(p-t*w/2+Vector((0,0,h))),tuple(p+t*w/2+Vector((0,0,h))),tuple(p+Vector((0,0,h+2.1)))],trim)
                        m.rod(p-t*w/2+Vector((0,0,h)),p+Vector((0,0,h+2.1)),.17,trim,8);m.rod(p+Vector((0,0,h+2.1)),p+t*w/2+Vector((0,0,h)),.17,trim,8)
                if spec.get('awnings'):
                    for j in range(bays):
                        p=av+t*(j*bw+bw/2)+Vector((0,0,floor*.65));q=p+n*1.25-Vector((0,0,.5));red=material('bund-astor-oxblood-canopy',(.31,.027,.035),.9)
                        m.face([tuple(p-t*bw*.30),tuple(p+t*bw*.30),tuple(q+t*bw*.30),tuple(q-t*bw*.30)],red)

            m.rod(av+Vector((0,0,h+.18)),bv+Vector((0,0,h+.18)),.24,trim,8)
        # Top roof uses the actual multi-corner footprint, no rectangular filler.
        m.face([(x,y,h) for x,y in pts],roofmat)
        if spec.get('roofType')=='signal-mast':
            # Gutzlaff tower: the banded base, round shaft and steel signal mast
            # have completely separate geometry. No photograph plane on a pole.
            brick=material('bund-signal-red-sandstone',(.39,.15,.105),.82)
            for a,b in zip(pts,pts[1:]+pts[:1]):
                av=Vector((a[0],a[1],0));bv=Vector((b[0],b[1],0));t=(bv-av).normalized();n=Vector((t.y,-t.x,0));length=(bv-av).length
                for j in range(1,17):
                    z=j*h/17
                    for k in range(max(1,int(length/.9))):
                        front=spec.get('frontEdge');on_front=front and math.dist(a,front[0])+math.dist(b,front[1])<.5
                        nb=spec.get('frontBays',1) if on_front else max(spec.get('minimumBays',1),round(length/spec.get('bayWidth',3.8)))
                        pitch=length/nb;along=(k*.9+.42)%pitch
                        in_opening=abs(along-pitch*.5)<spec.get('windowWidth',pitch*.52)/2+.45 and abs((z%floor)-floor*.53)<floor*spec.get('windowHeightFraction',.55)/2+.18
                        if in_opening:continue
                        p=av+t*(k*.9)+n*.018+Vector((0,0,z));q=av+t*min(length,k*.9+.84)+n*.018+Vector((0,0,z))
                        m.face([tuple(p),tuple(q),tuple(q+Vector((0,0,.17))),tuple(p+Vector((0,0,.17)))],brick)
            cx=sum(p[0] for p in pts)/len(pts);cy=sum(p[1] for p in pts)/len(pts)
            z0=h;z1=h+22;r=1.22
            m.lathe((cx,cy),[(z0,1.5),(z0+.4,1.5),(z0+.8,r),(z1-.7,r),(z1-.3,1.55),(z1+.1,1.55),(z1+.6,1.30)],trim,96)
            for z in [h+6,h+12,h+18]:m.lathe((cx,cy),[(z,r+.025),(z+.35,r+.025)],brick,96)
            for i in range(32):
                a=i*math.tau/32;b=(i+1)*math.tau/32
                m.rod((cx+1.55*math.cos(a),cy+1.55*math.sin(a),z1+.2),(cx+1.55*math.cos(a),cy+1.55*math.sin(a),z1+1.1),.026,iron,8)
                m.rod((cx+1.55*math.cos(a),cy+1.55*math.sin(a),z1+1.1),(cx+1.55*math.cos(b),cy+1.55*math.sin(b),z1+1.1),.035,iron,8)
            m.rod((cx,cy,z1+.5),(cx,cy,z1+10),.055,iron,12)
            for z in [z1+4.5,z1+7.8]:m.rod((cx-2.3,cy,z),(cx+2.3,cy,z),.042,iron,8)
            for j in range(27):m.rod((cx-.24,cy+.18,z1+.6+j*.31),(cx+.24,cy+.18,z1+.6+j*.31),.018,iron,8)
            for x in [-.24,.24]:m.rod((cx+x,cy+.18,z1+.6),(cx+x,cy+.18,z1+9),.025,iron,8)
        if not rect and spec.get('roofType') in ['central-pavilion','stepped-tower']:
            cx=(minx+maxx)/2;cy=(miny+maxy)/2;w=maxx-minx;d=maxy-miny
            if spec['roofType']=='stepped-tower':
                for j,scale in enumerate([.75,.56,.36]):
                    zh=(spec['height']-h)/3;zc=h+(j+.5)*zh
                    m.bevel_box((cx,cy,zc),(w*scale,d*scale,zh),wall,.1)
                    m.box((cx,cy,zc+zh/2),(w*scale+.4,d*scale+.4,.25),trim)
                    for sign in [-1,1]:
                        for k in range(max(2,int(w*scale/3))):
                            x=cx-w*scale/2+(k+.5)*w*scale/max(2,int(w*scale/3))
                            m.box((x,cy+sign*(d*scale/2+.02),zc),(.65,.06,zh*.65),glass)
            else:
                m.lathe((cx,cy),[(h,3),(h+.25,3.3),(h+.55,2.7),(h+3.2,2.7),(h+3.5,3.1),(h+3.8,3.1),(h+4.8,2.1),(h+5.1,0)],trim,8)
                m.rod((cx,cy,h+4.7),(cx,cy,h+10),.04,iron,8)
        m.flush();root['inferredDetails']=spec.get('inferredDetails','Secondary elevations and unobserved details inferred; OSM footprint with photograph-observed main floor/bay rhythm, color and roof silhouette')
        save_one(root,dict(id=spec['id'],name=spec['name'],ways=spec['ways'],center=spec['center'],heading=0,height=h,referenceIds=spec['referenceIds'],detailDescription=spec.get('observedDetails','OSM footprint and estimated height; physically recessed glazing, jambs, mullions, cornices and parapet; facade appearance inferred without matched photo')+(' Source-aligned rectified facade texture mapped onto recessed wall geometry and true column shafts.' if rect else ''),inferredDetails=root['inferredDetails'],photoVerified=bool(spec.get('photoVerified')),heightSource=spec.get('heightSource','OSM'),routeDistance=spec.get('routeDistance'),frontageClassification=spec.get('frontageClassification')))

# Editable scene is laid out in the actual world, with Blender Y = -world Z.
for root,entry in zip(roots,records):
    root.location=(entry['center'][0],-entry['center'][1],0);root.rotation_euler.z=entry['heading']
for img in bpy.data.images:
    if img.source=='FILE' and not img.packed_file:img.pack()
blend=EDIT/'bund-detailed.blend'
if not REVIEW_ONLY:
    if blend.exists():
        import shutil
        backup=ROOT/'assets/streets/bund-loop-backup-20260909-observed'/('bund-detailed-'+sha(blend)[:12]+'.blend')
        if not backup.exists():shutil.copy2(blend,backup)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
for rel,digest in protected.items():assert sha(ROOT/rel)==digest,'Protected original altered: '+rel
if PREVIOUS_MANIFEST:
    updated={m['id']:m for m in records}
    records=[updated.get(m['id'],m) for m in PREVIOUS_MANIFEST['models']]
manifest=dict(generator='scripts/build_bund_district.py',models=records,totalBytes=sum(x['bytes'] for x in records),triangles=sum(x['triangles'] for x in records),averageBytes=sum(x['bytes'] for x in records)/len(records),editableSource=str(blend.relative_to(ROOT)),sourceImagesPreserved=True,originalPhotoModelsPreserved=True,method='Source-elevation measurements + original PNG + explicit masonry geometry; non-visible details marked inferred',generatedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
manifest['photoVerificationDefinition']='Matched and individually viewed exterior photographs support identity and listed visible features only. Geometry intervals are estimates unless explicitly measured; this is not full-building or surveyed reconstruction acceptance.'
if not REVIEW_ONLY:(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print('BUND_DISTRICT_COMPLETE',len(records),manifest['totalBytes'],flush=True)

if os.environ.get('BUND_REVIEW')=='1':
    # Review the exported, compressed GLBs, rather than the in-memory source.
    review=OUT/'review';review.mkdir(exist_ok=True)
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=12;scene.cycles.use_denoising=True
    if os.environ.get('BUND_CYCLES_REVIEW')!='1':
        for engine in ['BLENDER_EEVEE','BLENDER_EEVEE_NEXT']:
            try:scene.render.engine=engine;break
            except TypeError:pass
    scene.render.resolution_x=1280;scene.render.resolution_y=960;scene.render.resolution_percentage=100
    scene.world.color=(.6,.6,.6);scene.view_settings.view_transform='AgX'
    checks=[]
    for record in records:
        if record['id'] not in ONLY_IDS and record['id'] not in (FIX_BATCH.get('reviewExtraIds',[]) if FIX_BATCH.get('status')=='pending' else []):continue
        spec=next(s for s in new_specs if s['id']==record['id'])
        bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
        bpy.ops.import_scene.gltf(filepath=str(ROOT/'public'/record['file']))
        objects=[o for o in bpy.context.scene.objects if o.type=='MESH'];coords=[o.matrix_world@Vector(v) for o in objects for v in o.bound_box]
        lo=Vector(tuple(min(v[i] for v in coords) for i in range(3)));hi=Vector(tuple(max(v[i] for v in coords) for i in range(3)));center=(lo+hi)*.5;size=hi-lo
        a,b=[Vector((*v,0)) for v in spec['frontEdge']];t=(b-a).normalized();n=Vector((t.y,-t.x,0))
        for tag,normal in [('front',n),('side',(n+t*.8).normalized())]:
            for o in list(scene.objects):
                if o.type in ['LIGHT','CAMERA']:bpy.data.objects.remove(o,do_unlink=True)
            bpy.ops.object.camera_add();cam=bpy.context.object;scene.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=max(size.z*1.37,size.x*1.45,size.y*1.45);cam.location=center+normal*max(size)*2.5+Vector((0,0,max(size)*.32));cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
            basis=cam.rotation_euler.to_matrix();right=basis@Vector((1,0,0));up=basis@Vector((0,1,0));px=[(v-center).dot(right) for v in coords];py=[(v-center).dot(up) for v in coords]
            cam.data.ortho_scale=max((max(px)-min(px))*1.16,(max(py)-min(py))*scene.render.resolution_x/scene.render.resolution_y*1.16)
            bpy.ops.object.light_add(type='AREA',location=center+n*max(size)*1.5+Vector((0,0,max(size)*1.5)));light=bpy.context.object;light.data.energy=max(2500,max(size)**2*60);light.data.shape='DISK';light.data.size=max(size)*1.5;light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler()
            output_image=review/(record['id']+'-observed-'+tag+'.png')
            if output_image.exists():
                import shutil
                backup=ROOT/'assets/streets/bund-loop-backup-20260909-observed'/(output_image.stem+'-'+sha(output_image)[:12]+'.png')
                if not backup.exists():shutil.copy2(output_image,backup)
            scene.render.filepath=str(output_image);bpy.ops.render.render(write_still=True)
        checks.append(dict(id=record['id'],sha256=sha(ROOT/'public'/record['file']),bounds={'min':list(lo),'max':list(hi)},views=['front','side'],source='Actual exported GLB imported in new empty scene'))
    checkfile=review/'bund-loop-readback-review.json'
    if checkfile.exists():
        previous={e['id']:e for e in json.loads(checkfile.read_text())};previous.update({e['id']:e for e in checks});checks=list(previous.values())
    checkfile.write_text(json.dumps(checks,ensure_ascii=False,indent=2))
    if FIX_BATCH.get('status')=='pending' and set(FIX_BATCH['buildIds'])<=ONLY_IDS:
        FIX_BATCH['status']='rendered-awaiting-visual-inspection';FIX_BATCH['readbackFile']=str(checkfile.relative_to(ROOT));FIX_FILE.write_text(json.dumps(FIX_BATCH,ensure_ascii=False,indent=2))
    print('BUND_GLB_READBACK_REVIEW_COMPLETE',len(checks),flush=True)
