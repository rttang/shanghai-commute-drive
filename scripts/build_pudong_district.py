"""Detailed Pudong exterior district for the Shanghai sightseeing master.

Source authority: OSM footprints + archived exterior photographs. Building heights
explicitly supplied by OSM are retained; architect sources establish the three
supertall silhouettes. Unseen elevations and unphotographed ancillary buildings
are labeled inferred. This is a visually referenced reconstruction, not a survey.

Individual GLBs are local Blender Z-up scenes, exported glTF Y-up. Manifest center
is world east/south and heading is Three Y / Blender Z rotation. No Draco,
quantization, decimation, padding, interior geometry, or texture upsampling.
"""
import bpy, bmesh, json, pathlib, math, sys, hashlib, datetime, argparse, shutil
from mathutils import Vector
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from pudong_model_helpers import Mesh, material, facade, polygon_ccw, roof_equipment
from photo_placement import facade_heading
OUT=ROOT/'public/streets/districts/pudong';EDIT=ROOT/'assets/blender/streets/pudong-detailed.blend'
OUT.mkdir(parents=True,exist_ok=True)
P=argparse.ArgumentParser();P.add_argument('--ids',nargs='*')
ARGS=P.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
CITY=json.loads((ROOT/'public/tour-city.json').read_text());BUILDINGS={b['id']:b for b in CITY['buildings']}
COVER=json.loads((ROOT/'references/tourism/street-frontage-coverage.json').read_text())
CONFIG=json.loads((ROOT/'src/tour/photo-architecture.json').read_text())
PHOTOS={p['id']:p for p in CONFIG if p['id'] in ['super-brand-mall','ocean-aquarium','hang-seng','bea-tower']}
CANDIDATES=[b for b in COVER['buildings'] if b['route']=='pudong' and b['frontage']['classification']=='first-row-sampled']
# The continuous loop traverses streets absent from the historical Pudong route.
# Keep its mapped first row authoritative for candidate membership, without
# upgrading map-only geometry into photographic evidence.
LOOP_CATALOG=json.loads((ROOT/'references/tourism/loop-frontage-catalog.json').read_text())
for b in LOOP_CATALOG['buildings']:
    if b.get('firstRow') and 5800<=b['routeDistanceM']<=9260 and b['wayId'] not in {x['wayId'] for x in CANDIDATES}:
        CANDIDATES.append(dict(wayId=b['wayId'],name=b['name'],height=b['height'],heightSource=b['heightSource'],frontage={**b['frontage'],'classification':'continuous-loop-first-row'},photoRef=None))
EXPANSION=ROOT/'references/tourism/streets-expansion-photos.json'
REFS=json.loads(EXPANSION.read_text()) if EXPANSION.exists() else []
if isinstance(REFS,dict):REFS=REFS.get('photos',REFS.get('items',[]))
REFS=[p for p in REFS if p.get('visualInspection',{}).get('accepted',True) and p.get('usage')!='excluded']
LOOP_REFS_PATH=ROOT/'references/tourism/pudong-loop-photos.json'
LOOP_REFS=json.loads(LOOP_REFS_PATH.read_text()) if LOOP_REFS_PATH.exists() else []
LOOP_REFS=[p for p in LOOP_REFS if p.get('viewed') and p.get('geometryReference') and p.get('photograph',True)]
REFS += LOOP_REFS

def refs_for(way,default=None):
    refs=[p['id'] for p in REFS if way in p.get('wayIds',p.get('ways',[]))]
    return refs or ([default] if default else [])

PREVIOUS=json.loads((OUT/'manifest.json').read_text()) if (OUT/'manifest.json').exists() else None
# Every modeling run preserves the exact overwritten GLBs and editable scene.
# Verification happens before Blender opens or mutates the current scene.
if PREVIOUS:
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup=ROOT/'backups/pudong-loop'/stamp;checks=[]
    sources=[OUT/'manifest.json',EDIT,ROOT/'scripts/build_pudong_district.py',ROOT/'scripts/pudong_model_helpers.py']
    sources += [OUT/(r['id']+'.glb') for r in PREVIOUS['models'] if not ARGS.ids or r['id'] in ARGS.ids]
    for src in sources:
        if not src.exists():continue
        dst=backup/src.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
        original=hashlib.sha256(src.read_bytes()).hexdigest()
        if hashlib.sha256(dst.read_bytes()).hexdigest()!=original:raise RuntimeError('Backup verification failed: '+str(src))
        checks.append(dict(file=str(src.relative_to(ROOT)),bytes=src.stat().st_size,sha256=original))
    (backup/'backup-manifest.json').write_text(json.dumps(dict(createdAt=stamp,files=checks),indent=2))
    print('PUDONG_VERIFIED_BACKUP',backup,len(checks),flush=True)
if ARGS.ids and EDIT.exists():
    bpy.ops.wm.open_mainfile(filepath=str(EDIT))
    for obj in [o for o in bpy.data.objects if o.parent is None]:
        if obj.name in ARGS.ids:
            for child in list(obj.children_recursive):bpy.data.objects.remove(child,do_unlink=True)
            bpy.data.objects.remove(obj,do_unlink=True)
else:
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
stone=material('limestone',(.54,.53,.49),.84)
light=material('aluminium-satin',(.53,.57,.58),.36,.65)
steel=material('dark-bronze',(.12,.135,.14),.38,.6)
roof=material('roof-waterproof',(.21,.23,.24),.92)
warm=material('warm-sandstone',(.56,.43,.30),.8)
terracotta=material('terracotta',(.32,.15,.10),.88)
glass=[material('curtain-glass-'+str(i),co,.23,.38) for i,co in enumerate([(.16,.28,.32),(.19,.32,.35),(.14,.24,.29),(.22,.34,.37),(.18,.285,.33),(.23,.35,.38)])]
blue=[material('blue-glass-'+str(i),co,.20,.43) for i,co in enumerate([(.19,.31,.39),(.23,.35,.42),(.17,.28,.36),(.26,.38,.44)])]
entryglass=material('entrance-glass',(.10,.18,.205),.19,.2)
models=[];records=[]


def new(key):
    root=bpy.data.objects.new(key,None);bpy.context.collection.objects.link(root)
    root['exteriorOnly']=True;root['geometryUnits']='metres';models.append(root)
    return root,Mesh(root)


def center_of(way):
    q=BUILDINGS[way]['points'][:-1]
    # Bounding-box center is stable even for heavily sampled circular footprints.
    return [(min(p[0] for p in q)+max(p[0] for p in q))/2,(min(p[1] for p in q)+max(p[1] for p in q))/2]


def local_polygon(way,center=None,heading=0):
    c=center or center_of(way);co,si=math.cos(heading),math.sin(heading)
    return polygon_ccw([((p[0]-c[0])*co-(p[1]-c[1])*si,-(p[0]-c[0])*si-(p[1]-c[1])*co) for p in BUILDINGS[way]['points']])


def record(root,ways,center,heading,height,referenceIds,detail,confidence='photo-referenced geometry; unobserved elevations inferred',**extra):
    root['sourceWays']=json.dumps(ways);root['referenceIds']=json.dumps(referenceIds);root['detailDescription']=detail;root['confidence']=confidence
    records.append(dict(id=root.name,file='/streets/districts/pudong/'+root.name+'.glb',name=extra.pop('name',BUILDINGS.get(ways[0],{}).get('name') or root.name),ways=ways,center=center,heading=heading,height=height,referenceIds=referenceIds,detailDescription=detail,confidence=confidence,**extra))


def entrance(mesh,aa,bb,height=5.2):
    length=math.dist(aa,bb)
    if length<5:return
    dx,dy=(bb[0]-aa[0])/length,(bb[1]-aa[1])/length
    c=((aa[0]+bb[0])/2,(aa[1]+bb[1])/2);w=min(length*.44,9)
    a=(c[0]-dx*w/2,c[1]-dy*w/2);b=(c[0]+dx*w/2,c[1]+dy*w/2)
    mesh.edge_box(a,b,.10,height-.45,.04,entryglass,offset=-.13)
    mesh.edge_box(a,b,height,.17,1.5,light,offset=-.67)
    for k in range(5):
        x,y=a[0]+dx*w*k/4,a[1]+dy*w*k/4
        mesh.box((x-dy*.06,y+dx*.06,height/2),(.065,.17,height),light,math.atan2(dy,dx))
    # Door pulls and threshold are kept inside the cadastral facade boundary.
    for side in [-1,1]:
        x,y=c[0]+dx*side*.26-dy*.035,c[1]+dy*side*.26+dx*.035
        mesh.rod((x,y,.95),(x,y,1.65),.022,light,8)
    mesh.edge_box(a,b,.08,.10,.9,stone,offset=-.48)


def podium(mesh,way,h=12):
    q=local_polygon(way);facade(mesh,q,h,stone,glass,light,'curtain',4)
    edge=max(zip(q,q[1:]+q[:1]),key=lambda e:math.dist(*e));entrance(mesh,*edge,min(h-1,6))
    return q


def tower_shanghai():
    root,m=new('shanghai-tower');c=center_of(165792123)
    # Gensler: rounded triangular plan, 120 degree twist, 55% scale at the top.
    # A smooth harmonic rounded-triangle approximation keeps independent glazing bays.
    n=144;rows=128;h=632
    def point(k,j,offset=0):
        t=j/rows;angle=k*math.tau/n+t*math.pi*2/3
        rad=(47*(1-.45*t))*(1+.12*math.cos(3*k*math.tau/n))+offset
        z=t*632
        return (rad*math.cos(angle),rad*math.sin(angle),z)
    for j in range(rows):
        for k in range(n):
            a,b,c1,d=point(k,j),point(k+1,j),point(k+1,j+1),point(k,j+1)
            m.face([a,b,c1,d],blue[(k//6+j//9)%len(blue)],True)
            # Fine aluminum transoms and vertical glazing joints follow the twisted skin.
            m.rod(point(k,j,.08),point(k+1,j,.08),.058,light,5)
            m.rod(point(k,j,.085),point(k,j+1,.085),.054,light,5)
    for j in [0,14,28,42,57,72,87,102,116,128]:
        for k in range(n):m.rod(point(k,j,.13),point(k+1,j,.13),.19,light,8)
    # Crown is an open, stepped structural lip, visibly asymmetric at street level.
    for k in range(n):
        p=point(k,128);q=point(k+1,128)
        lip=2.2+2.0*math.sin(k*math.tau/n)**2
        m.face([p,q,(q[0],q[1],632-lip),(p[0],p[1],632-lip)],light)
    for i in range(3):
        a=math.tau*i/3
        for k in range(22):
            t=-.32+k*.64/21;p=(45*math.cos(a+t),45*math.sin(a+t),0)
            m.rod((p[0],p[1],.2),(p[0],p[1],8),.09,light,8)
    # Entrance curtain wall lives within actual tower footprint, no road-covering plaza.
    q=local_polygon(165792123);entrance(m,*max(zip(q,q[1:]+q[:1]),key=lambda e:math.dist(*e)),7.5)
    m.flush();record(root,[165792123],c,0,h,refs_for(165792123,'gensler-shanghai-tower'),'128 levels of independently framed curved glazing; 120-degree twisted rounded triangular shell; 55% top scale; ten sky-garden belts; crown lip and glazed entrance',architectSource='https://www.gensler.com/projects/shanghai-tower',formSource='https://global.ctbuh.org/resources/papers/download/1006-the-parametric-design-of-shanghai-towers-form-and-facade.pdf')


def tower_jinmao():
    root,m=new('jinmao');way=376075961;c=center_of(way);q=local_polygon(way)
    # Cross arms in this cadastral outline contain the actual entrance canopies.
    # Keep their underside open; the old twelve-metre extrusion closed it off.
    body=[(31*math.cos(math.pi/8+k*math.tau/8),31*math.sin(math.pi/8+k*math.tau/8)) for k in range(8)]
    facade(m,body,12,stone,blue,light,'curtain',4)
    for side in range(4):
        angle=side*math.pi/2;nx,ny=math.sin(angle),math.cos(angle);tx,ty=ny,-nx
        end=max(x*nx+y*ny for x,y in q)-.3;back=28.7;half=8.7
        def cp(t,dep):return (tx*half*math.cos(t)+nx*dep,ty*half*math.cos(t)+ny*dep,14+5.8*math.sin(t))
        for k in range(48):
            a=k*math.pi/48;b=(k+1)*math.pi/48
            m.face([cp(a,back),cp(a,end),cp(b,end),cp(b,back)],blue[1])
            if k%3==0:m.rod(cp(a,back),cp(a,end),.12,light,8)
            for dep in [back,end]:m.rod(cp(a,dep),cp(b,dep),.18,light,10)
        for j in range(1,7):
            dep=back+(end-back)*j/7
            for k in range(32):m.rod(cp(k*math.pi/32,dep),cp((k+1)*math.pi/32,dep),.11,light,8)
        for sign in [-1,1]:
            px,py=tx*sign*8.3+nx*(end-1),ty*sign*8.3+ny*(end-1)
            m.box((px,py,7),(1.2,1.2,14),stone)
            for z in [0,1,12.5,13.4]:m.box((px,py,z+.15),(1.55,1.55,.3),light)
        # Raised circular metal glazing motif on the main wall behind the canopy.
        for k in range(64):
            a=k*math.tau/64;b=(k+1)*math.tau/64
            pa=(nx*28.9+tx*5.2*math.cos(a),ny*28.9+ty*5.2*math.cos(a),6.5+5.2*math.sin(a));pb=(nx*28.9+tx*5.2*math.cos(b),ny*28.9+ty*5.2*math.cos(b),6.5+5.2*math.sin(b));m.rod(pa,pb,.23,light,10)
    # Eight-sided pagoda setbacks, as visible in SOM's design and source photos.
    z=12;counts=[8,8,8,8,6,6,6,6,4,4,4,4,2,2,2,2];fh=(380-12)/sum(counts)
    for tier,count in enumerate(counts):
        rad=31-tier*1.13
        pts=[(rad*math.cos(math.pi/8+k*math.tau/8),rad*math.sin(math.pi/8+k*math.tau/8)) for k in range(8)]
        for a,b in zip(pts,pts[1:]+pts[:1]):
            length=math.dist(a,b);dx,dy=(b[0]-a[0])/length,(b[1]-a[1])/length;bays=max(3,round(length/1.55))
            for j in range(count):
                for k in range(bays):
                    aa=(a[0]+dx*length*k/bays,a[1]+dy*length*k/bays);bb=(a[0]+dx*length*(k+1)/bays,a[1]+dy*length*(k+1)/bays)
                    m.edge_box(aa,bb,z+j*fh+.28,fh-.40,.035,blue[(tier+k//2)%4],offset=-.13)
                    m.edge_box(aa,bb,z+j*fh,.28,.34,light,offset=-.03)
                    m.edge_box(aa,bb,z+(j+1)*fh-.12,.12,.5,light,offset=.03)
            for k in range(bays+1):
                p=(a[0]+dx*length*k/bays,a[1]+dy*length*k/bays)
                m.box((p[0]+dy*.08,p[1]-dx*.08,z+count*fh/2),(.10,.30,count*fh),light,math.atan2(dy,dx))
            # The projecting pagoda cornices have stepped metal soffits.
            for off,hh in [(0,.20),(.18,.20),(.37,.25)]:m.edge_box(a,b,z+count*fh+off,hh,.5+off*2,light,offset=.12)
        m.polygon(pts,z+count*fh,roof)
        for p in pts:m.rod((p[0],p[1],z),(p[0],p[1],z+count*fh+.8),.36,light,8)
        z+=count*fh
    for level in range(9):
        zz=380+level*3.2;r=11*(1-level/11)
        m.ring(zz,r,.18,light,8)
        for k in range(8):
            a=k*math.tau/8;ra=11*(1-(level+1)/11)
            m.rod((r*math.cos(a),r*math.sin(a),zz),(ra*math.cos(a),ra*math.sin(a),zz+3.2),.16,light,8)
    m.rod((0,0,404),(0,0,420.5),.45,light,12,r2=.08)
    m.flush();record(root,[way],c,0,420.5,refs_for(way,'som-jin-mao'),'Octagonal pagoda tower, sixteen setbacks, individual curtain-wall bays, projecting layered cornices, eight corner columns, open lattice crown and 420.5 m mast; mapped open entry canopy arms with curved glass roofs, physical soffit ribs, stone piers and circular glazing motif',observedParts=['north main entrance canopy and its ribbed soffit','side covered passage','circular entry motif','close upper mullions and shelf profiles'],unverifiedParts=['unphotographed south/east canopy detail inferred from north photo','precise roof and bracket dimensions'],architectSource='https://www.som.com/projects/jin-mao-tower/')


def tower_swfc():
    root,m=new('financial-center');way=10691100;c=center_of(way);h=492
    # Align square ground plan to the actual OSM facade bearing.
    q=local_polygon(way);a,b=max(zip(q,q[1:]+q[:1]),key=lambda e:math.dist(*e));angle=math.atan2(b[1]-a[1],b[0]-a[0])
    def p(x,y,z):return (x*math.cos(angle)-y*math.sin(angle),x*math.sin(angle)+y*math.cos(angle),z)
    rows=100
    for j in range(rows):
        z0=j*430/rows;z1=(j+1)*430/rows;w0=61-19*z0/492;w1=61-19*z1/492;d0=61-19*z0/492;d1=61-19*z1/492
        r0=[(-w0/2,-d0/2),(w0/2,-d0/2),(w0/2,d0/2),(-w0/2,d0/2)];r1=[(-w1/2,-d1/2),(w1/2,-d1/2),(w1/2,d1/2),(-w1/2,d1/2)]
        for side in range(4):
            aa,bb=r0[side],r0[(side+1)%4];cc,dd=r1[side],r1[(side+1)%4]
            for k in range(28):
                def lerp(a,b,t):return (a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t)
                v=[p(*lerp(aa,bb,k/28),z0),p(*lerp(aa,bb,(k+1)/28),z0),p(*lerp(cc,dd,(k+1)/28),z1),p(*lerp(cc,dd,k/28),z1)]
                m.face(v,blue[(k//4+side)%4]);m.rod(v[0],v[1],.05,light,5);m.rod(v[0],v[3],.046,light,5)
    # True trapezoidal aperture, no surface across the central opening.
    # The four inner reveals and the crown frame remain visible from both sides.
    for sign in [-1,1]:
        xs=[sign*x for x in [21.9,14,10,21]]
        for side in [-1,1]:
            v=[p(xs[0],side*21.9,430),p(xs[1],side*21.9,430),p(xs[2],side*21,480),p(xs[3],side*21,480)]
            m.face(v if sign*side<0 else v[::-1],blue[0])
        m.face([p(xs[1],-21.9,430),p(xs[1],21.9,430),p(xs[2],21,480),p(xs[2],-21,480)],light)
        m.face([p(xs[0],-21.9,430),p(xs[3],-21,480),p(xs[3],21,480),p(xs[0],21.9,430)],blue[1])
        for k in range(13):
            z=430+k*50/12;inn=14-4*k/12;out=21.9-.9*k/12
            for s in [-1,1]:m.rod(p(sign*inn,s*(21.9-.9*k/12),z),p(sign*out,s*(21.9-.9*k/12),z),.055,light,5)
    # Bridge across the top of the aperture from 480 to 492 m.
    m.box((0,0,486),(42,42,12),blue[1],angle)
    for z in [480,484,488,492]:
        for a,b in [((-21,-21),(21,-21)),((21,-21),(21,21)),((21,21),(-21,21)),((-21,21),(-21,-21))]:m.rod(p(*a,z),p(*b,z),.075,light,6)
    for sx,sy in [(-1,-1),(1,-1),(1,1),(-1,1)]:m.rod(p(sx*30.5,sy*30.5,0),p(sx*21,sy*21,492),.22,light,8)
    entrance(m,*max(zip(q,q[1:]+q[:1]),key=lambda e:math.dist(*e)),7)
    m.flush();record(root,[way],c,0,h,refs_for(way,'kpf-shanghai-world-financial-center'),'Tapered square tower aligned to mapped footprint; independently framed glazing; open trapezoidal aperture with modeled inner reveals and skybridge at crown; entrance doors',architectSource='https://www.kpf.com/project/shanghai-world-financial-center')


def import_photo(key):
    spec=PHOTOS[key];root,m=new(key)
    before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(ROOT/'public/streets/photo-models'/f'{key}.glb'))
    added=set(bpy.data.objects)-before
    for obj in added:
        if obj.parent not in added:obj.parent=root
    w=math.dist(*spec['front']);d=spec['depth'];h=spec.get('facadeHeight',spec['height']);body=h*(1-spec['bodyTop'])
    if key=='super-brand-mall':
        # The previous silhouette extrusion joined shallow upper roof edges to
        # a full-depth back plane, producing black triangular wings above the
        # curved storefront. Preserve the photographic FRONT, replace those
        # inferred caps and side walls with a coherent stepped roof envelope.
        for obj in list(added):
            if obj.type!='MESH':continue
            names=[mat.name for mat in obj.data.materials if mat]
            if any(name.startswith('photo-roof') for name in names):
                bpy.data.objects.remove(obj,do_unlink=True);continue
            bm=bmesh.new();bm.from_mesh(obj.data)
            remove=[]
            for face in bm.faces:
                coords=[obj.matrix_world@v.co for v in face.verts]
                if any(name.startswith('photo-side-stone') for name in names):
                    if min(v.y for v in coords)<-1:remove.append(face)
                elif any(name.startswith('photo-super-brand-mall') for name in names):
                    is_old_side=(max(v.x for v in coords)-min(v.x for v in coords)<.03 and abs(abs(sum(v.x for v in coords)/len(coords))-w/2)<.06)
                    if is_old_side and min(v.y for v in coords)<-.5:remove.append(face)
            bmesh.ops.delete(bm,geom=remove,context='FACES');bm.to_mesh(obj.data);bm.free();obj.data.update()
        # Roof follows the photo-observed red cylindrical wing, rounded central
        # gold atrium and rectangular glazed east wing; sign poles are excluded.
        profile=[(.008,.389),(.025,.331),(.12,.295),(.125,.169),(.167,.121),(.19,.088),(.224,.066),(.29,.056),(.4,.056),(.491,.108),(.51,.153),(.995,.157)]
        fullw=w/(.995-.008);mid=(.995+.008)/2
        def pt(u,v):return ((mid-u)*fullw,9*(math.sin(math.pi*u/.51)-1) if u<.51 else 0,(1-v)*h)
        for (u,v),(u1,v1) in zip(profile,profile[1:]):
            a,b=pt(u,v),pt(u1,v1)
            m.face([a,b,(b[0],-d,b[2]),(a[0],-d,a[2])],roof)
            m.face([(a[0],-d,a[2]),(b[0],-d,b[2]),(b[0],-d,0),(a[0],-d,0)],warm)
            m.rod(a,b,.10,light,8)
        for idx in [0,-1]:
            u,v=profile[idx];x,y,ztop=pt(u,v);base=terracotta if idx==0 else light
            a,b=((x,-d),(x,y)) if idx==0 else ((x,y),(x,-d))
            m.edge_panel(a,b,0,ztop,glass[0])
            for z in range(0,int(ztop),4):m.edge_box(a,b,z,.62,.23,base)
            for k in range(1,max(2,round(d/2))):
                yy=y+(-d-y)*k/max(2,round(d/2));m.box((x,yy,ztop/2),(.11,.075,ztop),light)
            m.rod((x,y,ztop),(x,-d,ztop),.12,light,8)
        root['roofCorrection']='Removed invalid old full-depth triangular caps; reconstructed photo-aligned stepped roof, bounded by facade and back wall.'

    # Existing photo front is preserved. New side modules occupy the existing
    # closed volume; the front image is neither replaced nor overpainted.
    if key in ['hang-seng','bea-tower']:
        for side in [-1,1]:
            a=(side*w/2,-d);b=(side*w/2,-.4)
            levels=max(1,round(body/3.8));step=body/levels
            for j in range(levels):
                m.edge_box(a,b,j*step+.3,.065,.15,light)
                m.edge_box(a,b,(j+1)*step-.15,.15,.24,light)
            for k in range(max(1,round(d/1.6))+1):
                y=-d+k*d/max(1,round(d/1.6));m.box((side*(w/2+.02),y,body/2),(.19,.07,body),light)
        roof_equipment(m,(0,-d*.56),body,max(2,w*.09),roof,steel)
        entrance(m,(-min(w*.24,8),-.13),(min(w*.24,8),-.13),6)
    elif key=='super-brand-mall':
        # The source shows separate floor-spandrel bands, tall cylindrical entry
        # columns and a glass awning, not a single flat printed frontage.
        for x in [-w*.05,-w*.25,-w*.40]:
            m.rod((x,-.45,.3),(x,-.45,9.7),.5,light,32)
            m.rod((x,-.45,9.7),(x,-.45,10.2),.62,light,32)
        for level in range(2,8):
            z=level*4.45
            m.edge_box((-w*.48,-.23),(-w*.025,-.23),z,.09,.22,light)
        for side in [-1,1]:
            x=side*w*.49;sideheight=h*(1-.389) if side>0 else h*(1-.157)
            for y in range(3,int(d),3):m.box((x,-y,sideheight/2),(.18,.07,sideheight),light)
            for z in range(5,int(sideheight),4):m.box((x,-d/2,z),(.20,d,.12),light)
        roof_equipment(m,(-w*.27,-d*.4),body,7,roof,steel)
    elif key=='ocean-aquarium':
        for x in [-w*.03,-w*.1,-w*.18]:entrance(m,(x-1.9,-.18),(x+1.9,-.18),4.3)
        for x in [-w*.17,-w*.39]:
            m.rod((x,-1,.3),(x,-1,6),.12,light,12)
            m.box((x,-1,6.1),(5,2.2,.13),entryglass)
        # Separate stone panel seams on the inferred side of the sloping wing.
        for y in range(2,int(d),2):m.box((w*.48,-y,7.5),(.12,.035,15),stone)
    m.flush();a,b=spec['front'];c=[(a[0]+b[0])/2,(a[1]+b[1])/2];heading=facade_heading(spec['front'],BUILDINGS[spec['ways'][0]]['points'])
    record(root,spec['ways'],c,heading,spec['height'],refs_for(spec['ways'][0],spec['reference']),'Preserved unique photo-referenced front and silhouette; added physical side mullions, transoms, entrance doors, canopy supports and service-roof louvers',name=spec['name'])


def pearl():
    root,m=new('pearl');before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(ROOT/'public/streets/photo-models/pearl.glb'))
    added=set(bpy.data.objects)-before
    for obj in added:
        if obj.parent not in added:obj.parent=root
    # Add fine tower-cladding rings and the split rings visible below observation
    # globes. Existing rose triangles, inclined legs and arrival canopy remain.
    for z,r in [(72,10),(78,15),(111,18),(116,13),(241,12),(245,16),(278,17),(284,10)]:m.ring(z,r,.13,light,128)
    for z in range(125,238,4):
        for a in [0,math.tau/3,math.tau*2/3]:
            cx,cy=10*math.cos(a),10*math.sin(a);m.ring(z,4.22,.025,light,48,cx,cy)
    m.flush();o=CITY['origin'];lon,lat=121.495265,31.2418972
    # Exact same Web Mercator-like local tangent projection as src/tour/data.ts.
    c=[(lon-o[0])*111320*math.cos(o[1]*math.pi/180),-(lat-o[1])*111320]
    record(root,[40778038],c,0,468,refs_for(40778038,'pearl-base'),'Preserved three inclined legs, rose-glazed spheres, lattice, arrival canopy; added individual concrete cladding joints and observation-belt rings')



def text_sign(root,text,center,angle,size,mat):
    curve=bpy.data.curves.new(root.name+'-nameplate','FONT');curve.body=text;curve.align_x='CENTER';curve.size=size;curve.extrude=.018;curve.bevel_depth=.004;curve.bevel_resolution=1;curve.resolution_u=3
    obj=bpy.data.objects.new(curve.name,curve);bpy.context.collection.objects.link(obj);obj.parent=root;obj.location=center;obj.rotation_euler=(math.pi/2,0,angle);curve.materials.append(mat)
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj;bpy.ops.object.convert(target='MESH')


def canonical_way(way):
    """Keep the cadastral center and put the southward long axis along local +Y."""
    c=center_of(way);q=local_polygon(way);a,b=max(zip(q,q[1:]+q[:1]),key=lambda e:math.dist(*e))
    dx,dy=b[0]-a[0],b[1]-a[1]
    if dy>0:dx,dy=-dx,-dy
    angle=math.atan2(-dx,dy)
    return c,angle,local_polygon(way,c,angle)


def panel_skin(m,q,z0,z1,rows,materials,metal,fold=0,slant=0,recess=False):
    """Exterior-only framed panes. Folded skins have true 0.3–0.6 m relief."""
    q=polygon_ccw(q);floor=(z1-z0)/rows
    for edge_no,(a,b) in enumerate(zip(q,q[1:]+q[:1])):
        length=math.dist(a,b)
        if length<.1:continue
        dx,dy=(b[0]-a[0])/length,(b[1]-a[1])/length
        bays=max(1,round(length/1.5));bw=length/bays
        def p(t,z,depth):return (a[0]+dx*t+dy*depth,a[1]+dy*t-dx*depth,z)
        for row in range(rows):
            za,zb=z0+row*floor,z0+(row+1)*floor
            margin=math.ceil(rows*abs(slant)/bw)+1
            for k in range(-margin,bays+margin):
                # Adjacent panels share their diagonal division exactly. Border
                # panels taper at the corner instead of extending over the road.
                shear=slant*(1 if edge_no%2 else -1)
                aa=max(0,min(length,k*bw+shear*row))
                bb=max(0,min(length,(k+1)*bw+shear*row))
                cc=max(0,min(length,(k+1)*bw+shear*(row+1)))
                dd=max(0,min(length,k*bw+shear*(row+1)))
                if max(bb-aa,cc-dd)<.01:continue
                depth=-1.6 if recess and za>=81 and zb<=105 and .33<=(aa+bb)/2/length<=.67 else -.08
                va,vb,vc,vd=p(aa,za,depth),p(bb,za,depth),p(cc,zb,depth),p(dd,zb,depth)
                def emit(vertices,mat):
                    clean=[]
                    for v in vertices:
                        if not any(math.dist(v,old)<1e-5 for old in clean):clean.append(v)
                    if len(clean)>2:m.face(clean,mat)
                if fold:
                    lo,hi=p((aa+bb)/2,za,-fold),p((cc+dd)/2,zb,-fold)
                    emit([va,lo,hi,vd],materials[0]);emit([lo,vb,vc,hi],materials[1%len(materials)])
                    m.rod(lo,hi,.026,metal,5)
                else:emit([va,vb,vc,vd],materials[(k//4+edge_no)%len(materials)])
                m.rod(va,vd,.037,metal,5);m.rod(va,vb,.032,metal,5)
        m.edge_box(a,b,z1,.14,.24,metal,offset=-.1)


def foxconn():
    way=165985305;c,angle,q=canonical_way(way);root,m=new('pudong-way-165985305')
    width=min(max(x for x,y in q)-min(x for x,y in q),44.4);depth=max(y for x,y in q)-min(y for x,y in q);r=width/2;cy=(depth-width)/2
    clear=[material('foxconn-silver-glass',(.38,.51,.59),.16,.45),material('foxconn-blue-glass',(.20,.35,.45),.18,.42)]
    # 21 floors and 95 m are supplied by the facade manufacturer; 300–600 mm
    # cavities are built as real alternating outer-pane normals, not a bitmap.
    panel_skin(m,q,0,5,1,[entryglass],light)
    panel_skin(m,q,5,17.5,3,clear,light,.50,.30);m.polygon(q,17.5,stone)
    center=[(-r+3,cy-r+3),(r-3,cy-r+3),(r-3,cy+r-3),(-r+3,cy+r-3)]
    panel_skin(m,center,17.5,91.5,17,[blue[0]],light)
    for sx in [-1,1]:
        for sy in [-1,1]:
            xa,xb=(-r,-3) if sx<0 else (3,r);ya,yb=(cy-r,cy-3) if sy<0 else (cy+3,cy+r)
            qq=[(xa,ya),(xb,ya),(xb,yb),(xa,yb)]
            panel_skin(m,qq,17.5,95,18,clear,light,.48,.65)
            m.polygon(qq,94.75,roof)
            for a,b in zip(qq,qq[1:]+qq[:1]):m.edge_box(a,b,95,.16,.50,light,offset=-.15)
    # Ground entry observed on the south elevation: broad clear doors, thin
    # canopy soffit and angled supports; all sit inside the mapped footprint.
    entrance(m,(r,cy+r),(-r,cy+r),5.0)
    for x in [-8,8]:m.rod((x,cy+r-.7,0),(x*.65,cy+r-1.4,5),.12,light,10)
    # The terrace footprint comes from the real podium outline. Planting itself
    # remains approximate; roof rails and paired planters are photograph backed.
    garden_y=-depth/2+5
    for x in [-r+5,r-5]:
        m.box((x,garden_y+3,17.9),(5,7,.8),stone)
        m.box((x,garden_y+3,18.32),(4.6,6.6,.12),material('garden-soil',(.15,.12,.075),1))
    rail=[(-r+1,-depth/2+1),(r-1,-depth/2+1),(r-1,cy-r),(-r+1,cy-r)]
    for a,b in zip(rail,rail[1:]+rail[:1]):
        m.edge_panel(a,b,17.6,1.15,entryglass,offset=-.03);m.rod((*a,18.8),(*b,18.8),.035,light,8)
    signmat=material('foxconn-name-blue',(.055,.28,.52),.35,.15)
    text_sign(root,'FOXCONN',(-r/2-1,cy+r-.06,90.8),math.pi,1.7,signmat)
    m.flush();record(root,[way],c,angle,95,refs_for(way),'Photo-matched four slender volumes and deep center slots; real folded silver/blue glazing with 0.48 m relief; 21-floor proportions; low faceted podium, south entry canopy, terrace balustrade and paired planters',heightSource='Facade manufacturer: 95 m / 21 storeys',heightSourceUrl='https://josef-gartner.permasteelisagroup.com/project/shanghai-foxconn-plaza/',observedParts=['four volumes','folded outer skin','recessed center slots','south entry','podium terrace'],unverifiedParts=['precise tower/podium cadastral split','concealed doors and planting species'])


def mirae():
    way=448242492;c=center_of(way);root,m=new('pudong-way-448242492');q=local_polygon(way)
    # The only OSM outline includes the flowing low podium. It must not be
    # extruded to 180 m. Tower location inside that envelope is photo inferred.
    panel_skin(m,q,0,23,5,glass,light);m.polygon(q,23,roof)
    n=128;cx=-2;cy=7;rx=20;ry=23
    qq=[]
    for i in range(n):
        a=i*math.tau/n;co,si=math.cos(a),math.sin(a)
        qq.append((cx+rx*math.copysign(abs(co)**.48,co),cy+ry*math.copysign(abs(si)**.48,si)))
    jade=[material('mirae-jade-glass',(.12,.31,.26),.2,.40),material('mirae-light-glass',(.20,.39,.32),.2,.38)]
    panel_skin(m,qq,0,179,32,jade,light)
    for j in range(33):
        z=j*179/32
        for a,b in zip(qq,qq[1:]+qq[:1]):
            m.edge_box(a,b,z,.12,.26,light,offset=-.02)
            m.edge_box(a,b,z+.48,.065,.21,light,offset=-.02)
    for a,b in zip(qq,qq[1:]+qq[:1]):m.edge_box(a,b,179,.8,.6,light,offset=-.15)
    m.polygon(qq,179.3,roof)
    # Name lettering is geometry; source images remain local references only.
    text_sign(root,'MIRAE ASSET',(cx,cy+ry-.1,169.5),math.pi,1.7,light)
    m.flush();record(root,[way],c,0,180,refs_for(way),'Rounded pillow-plan jade curtain-wall tower separated from 23 m flowing mapped podium; paired horizontal bands, narrow vertical mullions and pale rounded crown; geometric tower name',heightSource='CTBUH architectural height',heightSourceUrl='https://www.skyscrapercenter.com/building/mirae-asset-tower/2345',observedParts=['rounded tower skin','jade glazing','paired belts','pale cap'],unverifiedParts=['tower placement inside combined OSM footprint','concealed ground entries','podium bay spacing'])


def one_lujiazui():
    way=-129810530;c,angle,q=canonical_way(way);root,m=new('pudong-way-r129810530');h=269.1
    panel_skin(m,q,0,251,47,blue,light)
    xs=[x for x,y in q];ys=[y for x,y in q];x0,x1=min(xs),max(xs);y0,y1=min(ys),max(ys)
    # Paired outer wings frame the recessed facade; an open, sloped screen
    # around the roof replaces the former featureless flat top.
    def top(x,y):return 254+15.1*((y-y0)/(y1-y0))
    for a,b in zip(q,q[1:]+q[:1]):
        length=math.dist(a,b)
        if length<5:continue
        bays=max(2,round(length/1.7))
        for k in range(bays):
            aa=(a[0]+(b[0]-a[0])*k/bays,a[1]+(b[1]-a[1])*k/bays);bb=(a[0]+(b[0]-a[0])*(k+1)/bays,a[1]+(b[1]-a[1])*(k+1)/bays)
            m.face([(*aa,251),(*bb,251),(*bb,top(*bb)),(*aa,top(*aa))],glass[2])
            m.rod((*aa,251),(*aa,top(*aa)),.07,light,6)
            # Roof bracing sits behind the screen and is visible from above.
            if k%3==0:m.rod((*aa,top(*aa)-.3),(aa[0]*.80,aa[1]*.80,251),.14,light,8)
        m.rod((*a,top(*a)),(*b,top(*b)),.13,light,8)
    inset=[(x*.87,y*.87) for x,y in q];m.polygon(inset,251,roof)
    # Dominant road-facing lower pavilion remains its own cadastral model.
    for a,b in zip(q,q[1:]+q[:1]):
        if math.dist(a,b)<15:continue
        for j in range(1,48):m.edge_box(a,b,j*251/47,.20,.55,steel,offset=-.05)
    entrance(m,*max(zip(q,q[1:]+q[:1]),key=lambda e:(e[0][1]+e[1][1])/2),6)
    m.flush();record(root,[way],c,angle,h,refs_for(way),'Two photographs establish deep horizontal facade shelves, asymmetric sloping glass crown with open recessed roof and internal braces; original mapped entrance cutout preserved',heightSource='CTBUH architectural height',heightSourceUrl='https://www.skyscrapercenter.com/building/one-lujiazui/689',observedParts=['sloped roof wings','recessed top','horizontal shelves'],unverifiedParts=['exact crown slope bearing','unphotographed rear facade','measured shelf depth'])


def arched_band(m,a,b,z,height,stone_mat,glass_mat,bays):
    length=math.dist(a,b);dx,dy=(b[0]-a[0])/length,(b[1]-a[1])/length;bw=length/bays
    for i in range(bays):
        center=(i+.5)*bw;half=bw*.32;spring=z+height*.58
        points=[(center-half,z),(center+half,z),(center+half,spring)]
        points += [(center+half*math.cos(t*math.pi/16),spring+half*math.sin(t*math.pi/16)) for t in range(1,17)]
        verts=[(a[0]+dx*x-dy*.2,a[1]+dy*x+dx*.2,zz) for x,zz in points]
        m.face(verts,glass_mat)
        for k in range(16):
            t0=k*math.pi/16;t1=(k+1)*math.pi/16
            pa=(a[0]+dx*(center+half*math.cos(t0)),a[1]+dy*(center+half*math.cos(t0)),spring+half*math.sin(t0))
            pb=(a[0]+dx*(center+half*math.cos(t1)),a[1]+dy*(center+half*math.cos(t1)),spring+half*math.sin(t1))
            m.rod(pa,pb,.22,stone_mat,6)
        for t in [center-half,center+half]:m.rod((a[0]+dx*t,a[1]+dy*t,z),(a[0]+dx*t,a[1]+dy*t,spring),.21,stone_mat,6)
        mid=(a[0]+dx*center,a[1]+dy*center);m.rod((*mid,z),(*mid,spring+half),.045,light,6)


def golden():
    way=164903482;c,angle,q=canonical_way(way);root,m=new('pudong-way-164903482');h=206
    pale=material('golden-landmark-stone',(.59,.55,.46),.78);dark=material('golden-landmark-window',(.095,.15,.17),.25,.35)
    facade(m,q,173,pale,[dark],light,'masonry',173/35)
    # The upper storeys, arched openings and hipped roof are distinctive in the
    # 2025 street photograph; they are not repeated on unrelated buildings.
    for scale,z,hh,bays in [(1,173,9,7),(.83,182,9,5),(.69,191,6,3)]:
        qq=[(x*scale,y*scale) for x,y in q]
        for a,b in zip(qq,qq[1:]+qq[:1]):
            m.edge_panel(a,b,z,hh,pale,offset=-.6);arched_band(m,a,b,z+.7,hh-.8,pale,dark,bays)
            for zz in [z,z+.30,z+hh-.45]:m.edge_box(a,b,zz,.23,.85,pale,offset=.01)
        m.polygon(qq,z+hh,pale)
    qq=[(x*.70,y*.70) for x,y in q];top=[(x*.06,y*.06) for x,y in q]
    for i in range(len(qq)):m.face([(*qq[i],197),(*qq[(i+1)%len(qq)],197),(*top[(i+1)%len(q)],203),(*top[i],203)],roof)
    for z,r in [(203,1.4),(204.7,1.1),(205.4,.5)]:m.ring(z,r,.10,steel,16)
    for k in range(8):
        a=k*math.tau/8;m.rod((1.1*math.cos(a),1.1*math.sin(a),203),(1.1*math.cos(a),1.1*math.sin(a),205),.075,steel,6)
    m.rod((0,0,204.8),(0,0,206),.13,steel,8,r2=.02)
    m.flush();record(root,[way],c,angle,h,refs_for(way),'Stone vertical piers and grouped dark windows, three stepped tiers of modeled arched upper windows with curved stone reveals, horizontal crown courses, hipped dark roof and lantern',heightSource='CTBUH 2008 published architectural height 206 m / 41 floors',heightSourceUrl='https://global.ctbuh.org/resources/papers/38-TBIN_2008.pdf',observedParts=['stone piers','upper arches','roof silhouette'],unverifiedParts=['ground entrance hidden in photo','side and rear window counts','exact crown tier heights'])


def merchants():
    way=164972436;c,angle,q=canonical_way(way);root,m=new('pudong-way-164972436')
    cyan=[material('merchants-cyan-glass',(.16,.39,.40),.21,.40),material('merchants-dark-glass',(.08,.23,.27),.21,.38)]
    panel_skin(m,q,0,138,33,cyan,light,recess=True)
    for aa,bb in zip(q,q[1:]+q[:1]):
        length=math.dist(aa,bb);dx,dy=(bb[0]-aa[0])/length,(bb[1]-aa[1])/length
        for j in range(1,34):
            zz=j*138/33
            if 83<zz<105:
                left=(aa[0]+dx*length*.33,aa[1]+dy*length*.33);right=(aa[0]+dx*length*.67,aa[1]+dy*length*.67)
                m.edge_box(aa,left,zz,.68,.38,light,offset=-.05);m.edge_box(right,bb,zz,.68,.38,light,offset=-.05)
            else:m.edge_box(aa,bb,zz,.68,.38,light,offset=-.05)
        for t in [.11,.89]:
            p=(aa[0]+dx*length*t,aa[1]+dy*length*t)
            m.box((*p,69),(1.2,.44,138),light,math.atan2(dy,dx))
        # Two large recessed vertical glazing fields and crossing cornice seen
        # in both the close photograph and the pedestrian-bridge panorama.
        center=((aa[0]+bb[0])/2,(aa[1]+bb[1])/2);w=length*.33
        a=(center[0]-dx*w/2,center[1]-dy*w/2);b=(center[0]+dx*w/2,center[1]+dy*w/2)
        field_lo=20*138/33;field_hi=25*138/33
        # Real inward return surfaces give the central field a visible shadow.
        ox,oy=dy*1.55,-dx*1.55
        for pa,pb in [(a,b)]:
            m.face([(*pa,field_lo),(*pb,field_lo),(pb[0]-ox,pb[1]-oy,field_lo),(pa[0]-ox,pa[1]-oy,field_lo)],light)
            m.face([(*pb,field_hi),(*pa,field_hi),(pa[0]-ox,pa[1]-oy,field_hi),(pb[0]-ox,pb[1]-oy,field_hi)],light)
        for side in [a,b]:m.face([(*side,field_lo),(*side,field_hi),(side[0]-ox,side[1]-oy,field_hi),(side[0]-ox,side[1]-oy,field_lo)],light)
        m.edge_box(a,b,field_lo,.9,1.4,light,offset=-.7)
        m.edge_box(aa,bb,104,3.8,.4,light,offset=-.03)
    r=min(max(x for x,y in q)-min(x for x,y in q),max(y for x,y in q)-min(y for x,y in q))*.36
    circle=[(r*math.cos(i*math.tau/80),r*math.sin(i*math.tau/80)) for i in range(80)]
    panel_skin(m,circle,138,153,4,cyan,light)
    for z in [138,142,146,150,153]:m.ring(z,r,.32,light,96)
    # A real open white lattice pyramid surrounds the dark central cap.
    corners=[(-r,-r),(r,-r),(r,r),(-r,r)]
    for a,b in zip(corners,corners[1:]+corners[:1]):
        m.rod((*a,152),(*b,152),.18,light,8);m.rod((*a,152),(0,0,163),.22,light,8)
        for j in range(1,8):
            t=j/8;p0=(a[0]*(1-t),a[1]*(1-t),152+11*t);p1=(b[0]*(1-t),b[1]*(1-t),152+11*t)
            m.rod(p0,p1,.075,light,6)
    for i in range(4):m.face([(*corners[i],152),(*corners[(i+1)%4],152),(0,0,163)],roof)
    for z in [163.5,164.1,164.7]:m.ring(z,.55,.09,light,20)
    m.rod((0,0,163),(0,0,186),.22,light,12,r2=.035)
    entrance(m,*max(zip(q,q[1:]+q[:1]),key=lambda e:math.dist(*e)),5)
    m.flush();record(root,[way],c,angle,186,refs_for(way),'Photo-matched turquoise glazing and broad silver floor bands; paired inset central glazing fields, vertical corner piers, round upper pavilion and white lattice pyramidal crown with mast',heightSource='CVU / CTBUH architectural height 186 m / 38 floors',heightSourceUrl='https://www.skyscrapercenter.com/building/id/2108',observedParts=['turquoise body','silver bands','central facade fields','round crown and lattice pyramid'],unverifiedParts=['precise recessed-field depths','ground doors obscured by trees','rear facade arrangement'])


def huaneng():
    way=-129813021;c,angle,q=canonical_way(way);root,m=new('pudong-way-r129813020');pod=local_polygon(-129813020,c,angle)
    russet=material('huaneng-rose-stone',(.47,.31,.25),.85)
    facade(m,pod,21,russet,blue,light,'curtain',4.2)
    # OSM relation outer 020 is the podium; 021 is the separate tower. The
    # previous model wrongly extended the wide podium to the entire 188 m.
    facade(m,q,178,russet,blue,light,'masonry',4.25)
    xs=[x for x,y in q];ys=[y for x,y in q];x0,x1=min(xs),max(xs);y0,y1=min(ys),max(ys)
    mid=(x0+x1)/2;half=(x1-x0)*.27
    for j in range(38):
        za=21+j*157/38;zb=21+(j+1)*157/38
        for k in range(18):
            def p(t,z):
                x=mid-half+2*half*t;return (x,y1-.35+1.3*math.sin(t*math.pi),z)
            aa,bb,cc,dd=p(k/18,za),p((k+1)/18,za),p((k+1)/18,zb),p(k/18,zb)
            m.face([aa,bb,cc,dd][::-1],blue[0]);m.rod(aa,bb,.045,light,6);m.rod(aa,dd,.042,light,6)
    for x in [x0+1.5,x1-1.5]:
        m.box((x,(y0+y1)/2,93),(1.2,y1-y0,186),russet)
        m.box((x,y1-.5,181),(.8,2.5,14),russet)
    m.box((mid,y1-.25,184),(x1-x0,.9,1.3),russet)
    m.rod((mid,(y0+y1)/2,181),(mid,(y0+y1)/2,188),.14,steel,8)
    # Photo-backed arched portal, tall lower glass, and canopy truss.
    aa,bb=max(zip(pod,pod[1:]+pod[:1]),key=lambda e:math.dist(*e));ln=math.dist(aa,bb);dx,dy=(bb[0]-aa[0])/ln,(bb[1]-aa[1])/ln;px,py=(aa[0]+bb[0])/2,(aa[1]+bb[1])/2
    arched_band(m,(px-dx*9,py-dy*9),(px+dx*9,py+dy*9),4,22,light,blue[1],1)
    entrance(m,aa,bb,6)
    text_sign(root,'HUANENG UNION TOWER',(px,py,10),math.atan2(dy,dx),.85,material('name-gold',(.67,.44,.13),.32,.7))
    m.flush();record(root,[-129813020,-129813021],c,angle,188,refs_for(-129813020),'Correct OSM podium/tower split; rose stone flanks with curved blue center glass, projected central piers, open upper fins, arched street portal and supported canopy',heightSource='OSM explicit tower height 188 m; podium 21 m photo proportion estimate',observedParts=['tower color and central glazing','upper fins','arched entrance','low podium'],unverifiedParts=['exact podium height','entrance bearing selected by longest cadastral edge','unseen rear bays'])


def world_finance(way):
    c=center_of(way);root,m=new('pudong-way-'+str(way).replace('-','r'));q=local_polygon(way);h=188
    copper=material('world-finance-sandstone',(.48,.36,.25),.83);green=[material('world-finance-green-glass',(.13,.29,.24),.2,.42)]
    panel_skin(m,q,0,h,43,green,light)
    for aa,bb in zip(q,q[1:]+q[:1]):
        for j in range(43):m.edge_box(aa,bb,j*h/43,.97,.30,copper,offset=-.08)
        for z in [11,14,17,93,97]:m.edge_box(aa,bb,z,.7,.40,copper,offset=-.05)
    # Both real OSM parts share a curved envelope. The front part receives the
    # visible fan crown; only this component carries the single central mast.
    if way==-129813031:
        cx=sum(x for x,y in q)/len(q);cy=sum(y for x,y in q)/len(q)
        for aa,bb in zip(q,q[1:]+q[:1]):
            za=193-4*abs(aa[1]-cy)/38;zb=193-4*abs(bb[1]-cy)/38
            m.face([(*aa,188),(*bb,188),(*bb,zb),(*aa,za)],green[0]);m.rod((*aa,za),(*bb,zb),.14,light,8)
        m.rod((cx,cy,191),(cx,cy,212),.23,light,12,r2=.045)
    else:m.polygon(q,188,roof)
    entrance(m,*max(zip(q,q[1:]+q[:1]),key=lambda e:math.dist(*e)),5.8)
    m.flush();record(root,[way],c,0,212 if way==-129813031 else 193,refs_for(way),'Curved mapped green-glass facade with 43 continuous warm stone spandrels, broader midheight belt, angular lower entrance and separate open curved crown; single mast on inner part',heightSource='CTBUH 212 m architectural top for whole building; component massing inferred from photo',heightSourceUrl='https://www.skyscrapercenter.com/building/id/1412',observedParts=['curved body','warm continuous bands','fan crown','mast'],unverifiedParts=['relative heights of OSM component roofs','rear elevations','exact entry bearing'])


def pingan():
    way=520990201;c,angle,q=canonical_way(way);root,m=new('pudong-way-520990201')
    pale=material('pingan-pale-stone',(.65,.59,.46),.80);black=material('pingan-deep-glazing',(.07,.13,.145),.24,.36)
    # Bank-supplied photo + contractor project description: 170 m main body,
    # 203 m dome. The broad outline belongs to podium plus tower, not one slab.
    facade(m,q,19,pale,[black],light,'masonry',4.6)
    cx,cy=0,0;w=48;d=45;tower=[(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]
    facade(m,tower,164,pale,[black],light,'masonry',4.35)
    for aa,bb in zip(tower,tower[1:]+tower[:1]):
        length=math.dist(aa,bb);dx,dy=(bb[0]-aa[0])/length,(bb[1]-aa[1])/length
        for j in range(1,38):
            z=j*164/38
            for off,hh,dep in [(0,.22,.95),(.23,.18,.70),(.43,.14,.5)]:m.edge_box(aa,bb,z+off,hh,dep,pale,offset=.05)
        for k in range(13):
            t=k/12;x,y=aa[0]+dx*length*t,aa[1]+dy*length*t
            m.box((x,y,83),(.44,.8,162),pale,math.atan2(dy,dx))
        px,py=(aa[0]+bb[0])/2,(aa[1]+bb[1])/2
        m.edge_panel((px-dx*1.3,py-dy*1.3),(px+dx*1.3,py+dy*1.3),0,170,black,offset=.48)
    # Explicit stepped crown avoids scaling the main tower or any mapped podium.
    for scale,z,hh in [(.92,164,3),(.83,167,3),(.70,170,5)]:
        qq=[(x*scale,y*scale) for x,y in tower]
        panel_skin(m,qq,z,z+hh,1,[black],light)
        for aa,bb in zip(qq,qq[1:]+qq[:1]):m.edge_box(aa,bb,z,.55,1.0,pale,offset=-.1)
    radius=16.4;base=175;rows=32;n=96
    for j in range(rows):
        t0=j*math.pi/2/rows;t1=(j+1)*math.pi/2/rows
        for k in range(n):
            def pt(k,t):
                a=k*math.tau/n;rr=radius*math.cos(t);return (rr*math.cos(a),rr*math.sin(a),base+24*math.sin(t))
            v=[pt(k,t0),pt(k+1,t0),pt(k+1,t1),pt(k,t1)];m.face(v if j<rows-1 else [v[0],v[1],(0,0,199)],blue[0],True)
            if k%4==0:m.rod(v[0],v[3],.12,steel,8)
            if j%3==0:m.rod(v[0],v[1],.075,steel,6)
    for k in range(32):
        a=k*math.tau/32;m.rod((16.4*math.cos(a),16.4*math.sin(a),171),(16.4*math.cos(a),16.4*math.sin(a),175),.35,pale,12)
    m.ring(175,16.8,.35,pale,96);m.ring(199,1.7,.18,steel,32)
    m.rod((0,0,199),(0,0,202.2),1.15,pale,24,r2=.75);m.rod((0,0,202.2),(0,0,203),.50,steel,20,r2=.08)
    text_sign(root,'PING AN',(0,d/2+.5,152),math.pi,1.8,material('pingan-name-gold',(.83,.62,.25),.32,.62))
    m.flush();record(root,[way],c,angle,203,refs_for(way),'Photo-matched pale classical tower on low mapped podium; paired stone piers, deeply layered cornices and dark axial slot, stepped drum, colonnade and physically ribbed 203 m glass dome',heightSource='Ping An Shanghai Branch supplied article and construction contractor: body170 m / dome203 m',heightSourceUrl='https://www.shobserver.com/sgh/detail?id=1756967',observedParts=['stone tower','cornices','central slot','colonnaded dome drum','ribbed dome'],unverifiedParts=['tower position inside single combined OSM outline','low podium elevation not visible','ground entrance hidden by trees'])


def disney():
    way=427786590;c=center_of(way);q=local_polygon(way);root,m=new('pudong-way-427786590');h=6.8
    bronze=material('disney-bronze-ribs',(.35,.25,.14),.46,.58);pale=material('disney-clock-stone',(.60,.48,.32),.77)
    facade(m,q,h,bronze,[entryglass],light,'curtain',h)
    # Physical ribbed metal upper shop fascia follows the concave OSM outline.
    for aa,bb in zip(q,q[1:]+q[:1]):
        length=math.dist(aa,bb);n=max(1,round(length/.24));dx,dy=(bb[0]-aa[0])/length,(bb[1]-aa[1])/length
        m.edge_panel(aa,bb,4.3,2.5,bronze,offset=-.05)
        for k in range(n):
            x,y=aa[0]+dx*length*k/n,aa[1]+dy*length*k/n;m.box((x,y,5.55),(.08,.17,2.5),bronze,math.atan2(dy,dx))
    # Keep lettering inside the concave storefront. This is extruded generic
    # type, explicitly not an exact reproduction of Disney's proprietary script.
    sign=material('disney-name-light',(.83,.54,.30),.35,.1);sign.node_tree.nodes.get('Principled BSDF').inputs['Emission Color'].default_value=(1,.35,.18,1);sign.node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'].default_value=.25
    text_sign(root,'Disney',(94.1-c[0],-(-138-c[1]),4.9),math.pi/2,1.25,sign)
    # The separate 18 m clock sits on the shop plaza east of the concave facade.
    # This placement is an explicit visual inference; verify all nearby roads.
    clock_world=(114,-138);cx,cy=clock_world[0]-c[0],-(clock_world[1]-c[1])
    def segment_distance(p,a,b):
        dx,dy=b[0]-a[0],b[1]-a[1];t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/max(dx*dx+dy*dy,1e-9)));return math.dist(p,(a[0]+dx*t,a[1]+dy*t))
    clearance=[]
    for rd in CITY['roads']:
        if rd.get('tunnel') or rd.get('highway') in ['footway','pedestrian','path','steps','cycleway'] or rd.get('kind') in ['footway','pedestrian','path','cycleway','steps']:continue
        pts=rd.get('points',[])
        if len(pts)<2:continue
        dist=min(segment_distance(clock_world,a,b) for a,b in zip(pts,pts[1:]));width=rd.get('width',rd.get('widthM',8))
        if isinstance(width,str):width=float(width.replace('m','').strip())
        clearance.append(dist-width/2-4)
    if clearance and min(clearance)<1:raise ValueError('Disney plaza clock intersects mapped carriageway envelope')
    m.rod((cx,cy,.0),(cx,cy,.45),3.8,pale,96)
    m.box((cx,cy,2.2),(4.1,4.1,3.5),pale)
    # Official and lighting-contractor photographs show arched lower doors,
    # a projecting first-floor deck and an open colonnaded pavilion below the
    # clock shaft. They are distinct exterior components, not a solid plinth.
    for side in range(4):
        ang=side*math.pi/2;nx,ny=math.cos(ang),math.sin(ang);tx,ty=-ny,nx
        def dp(u,z,r=2.065):return (cx+nx*r+tx*u,cy+ny*r+ty*u,z)
        arch=[dp(-.77,.6),dp(.77,.6)]+[dp(.77*math.cos(k*math.pi/24),2.75+.77*math.sin(k*math.pi/24)) for k in range(25)]
        m.face(arch,entryglass)
        for k in range(24):m.rod(dp(.87*math.cos(k*math.pi/24),2.75+.87*math.sin(k*math.pi/24),2.11),dp(.87*math.cos((k+1)*math.pi/24),2.75+.87*math.sin((k+1)*math.pi/24),2.11),.075,bronze,8)
        for u in [-.83,0,.83]:m.rod(dp(u,.58,2.12),dp(u,2.74,2.12),.055,bronze,8)
        for z in [1.2,1.9,2.7]:m.rod(dp(-.77,z,2.12),dp(.77,z,2.12),.04,bronze,8)
        for z in [.8,1.3,1.8,2.3,2.8,3.3]:m.edge_box((cx+nx*2.07-tx*2,cy+ny*2.07-ty*2),(cx+nx*2.07+tx*2,cy+ny*2.07+ty*2),z,.022,.035,bronze)
    for sx,sy in [(-1,-1),(1,-1),(1,1),(-1,1)]:
        for zz,rad in [(4.05,.3),(4.25,.22),(5.75,.3)]:m.rod((cx+sx*2.0,cy+sy*2.0,zz),(cx+sx*2.0,cy+sy*2.0,zz+.16),rad,pale,20)
        m.rod((cx+sx*2.0,cy+sy*2.0,4.3),(cx+sx*2.0,cy+sy*2.0,5.8),.16,pale,20)
    for side in range(4):
        aa=side*math.pi/2+math.pi/4;bb=aa+math.pi/2
        outer=[(cx+3.65*math.cos(t),cy+3.65*math.sin(t),5.87) for t in [aa,bb]];inner=[(cx+2.45*math.cos(t),cy+2.45*math.sin(t),6.30) for t in [aa,bb]]
        m.face([outer[0],outer[1],inner[1],inner[0]],entryglass)
        m.rod(outer[0],outer[1],.07,bronze,8)
        for k in range(7):
            t=k/6;p=tuple(outer[0][j]*(1-t)+outer[1][j]*t for j in range(3));r=tuple(inner[0][j]*(1-t)+inner[1][j]*t for j in range(3));m.rod(p,r,.055,bronze,8)
    for z,ww in [(3.85,4.9),(4.05,5.1),(6.0,4.7),(12.7,4.2),(13.0,4.5)]:m.box((cx,cy,z),(ww,ww,.18),bronze)
    m.box((cx,cy,9.45),(3.1,3.1,6.5),entryglass)
    for sx,sy in [(-1,-1),(1,-1),(1,1),(-1,1)]:
        m.box((cx+sx*1.7,cy+sy*1.7,9.4),(.34,.34,6.5),pale)
        for j in range(30):m.box((cx+sx*1.7,cy+sy*1.7,6.3+j*.2),(.42,.42,.055),bronze)
    # Four clock faces carry real 3D ticks and hands, with glass-front detailing.
    ivory=material('clock-ivory',(.88,.81,.63),.65)
    for side in range(4):
        ang=side*math.pi/2;nx,ny=math.cos(ang),math.sin(ang);tx,ty=-ny,nx
        origin=(cx+nx*1.76,cy+ny*1.76,13.7)
        disk=[]
        for k in range(64):
            a=k*math.tau/64;disk.append((origin[0]+tx*math.cos(a)*1.05,origin[1]+ty*math.cos(a)*1.05,origin[2]+math.sin(a)*1.05))
        m.face(disk,ivory)
        # Proud dial surround, small rim lamps and the arched clock-head profile.
        for k in range(64):
            a=k*math.tau/64;b=(k+1)*math.tau/64
            pa=(origin[0]+tx*math.cos(a)*1.12+nx*.06,origin[1]+ty*math.cos(a)*1.12+ny*.06,origin[2]+math.sin(a)*1.12)
            pb=(origin[0]+tx*math.cos(b)*1.12+nx*.06,origin[1]+ty*math.cos(b)*1.12+ny*.06,origin[2]+math.sin(b)*1.12)
            m.rod(pa,pb,.11,bronze,8)
            if k%2==0:m.rod(pa,(pa[0]+nx*.06,pa[1]+ny*.06,pa[2]),.035,ivory,8)
        for k in range(12):
            a=k*math.tau/12
            p0=(origin[0]+tx*math.sin(a)*.82,origin[1]+ty*math.sin(a)*.82,origin[2]+math.cos(a)*.82);p1=(origin[0]+tx*math.sin(a)*.97,origin[1]+ty*math.sin(a)*.97,origin[2]+math.cos(a)*.97)
            m.rod(p0,p1,.03,steel,6)
        m.rod(origin,(origin[0]+tx*.40,origin[1]+ty*.40,origin[2]+.28),.035,steel,8);m.rod(origin,(origin[0]-tx*.18,origin[1]-ty*.18,origin[2]+.74),.03,steel,8)
    # Shallow exposed mechanical silhouettes visible through the shaft glazing.
    # These model the photograph-visible gears, not concealed clock internals.
    for side in range(4):
        ang=side*math.pi/2;nx,ny=math.cos(ang),math.sin(ang);tx,ty=-ny,nx
        for z,rad,shift in [(7.4,.67,-.25),(8.9,.79,.28),(10.55,.51,-.15)]:
            gx,gy=cx+nx*1.59+tx*shift,cy+ny*1.59+ty*shift
            for k in range(32):
                a=k*math.tau/32;b=(k+1)*math.tau/32
                pa=(gx+tx*rad*math.cos(a),gy+ty*rad*math.cos(a),z+rad*math.sin(a));pb=(gx+tx*rad*math.cos(b),gy+ty*rad*math.cos(b),z+rad*math.sin(b))
                m.rod(pa,pb,.055,bronze,6)
                if k%2==0:m.rod(pa,(gx+tx*(rad+.10)*math.cos(a),gy+ty*(rad+.10)*math.cos(a),z+(rad+.10)*math.sin(a)),.05,bronze,6)
                if k%8==0:m.rod((gx,gy,z),pa,.035,bronze,6)
    for j in range(8):
        z0=14.7+j*.28;z1=z0+.28;r0=1.85*(1-j/11)**1.5;r1=1.85*(1-(j+1)/11)**1.5
        for i in range(4):
            a=i*math.pi/2+math.pi/4;b=a+math.pi/2;m.face([(cx+r0*math.cos(a),cy+r0*math.sin(a),z0),(cx+r0*math.cos(b),cy+r0*math.sin(b),z0),(cx+r1*math.cos(b),cy+r1*math.sin(b),z1),(cx+r1*math.cos(a),cy+r1*math.sin(a),z1)],bronze)
    m.ring(17.3,.62,.055,bronze,48,cx,cy);m.ring(17.6,.52,.05,bronze,48,cx,cy);m.rod((cx,cy,16.9),(cx,cy,18),.06,bronze,8)
    # Visible curved glass canopy on the east end, all within shop/plaza boundary.
    for k in range(16):
        a=2.03+k*2.16/16;b=2.03+(k+1)*2.16/16
        def cp(t,r):return (113-c[0]+r*math.cos(t),138+c[1]+r*math.sin(t),4.4)
        m.face([cp(a,16),cp(b,16),cp(b,20),cp(a,20)],entryglass)
        m.rod(cp(a,16),cp(a,20),.10,light,8)
        if k%4==0:
            p=cp(a,17.3);m.rod((p[0],p[1],0),p,.16,light,12)
    m.flush();record(root,[way],c,0,18,refs_for(way),'Mapped concave bronze-ribbed shop front with modeled glass canopy; separate 18 m plaza clock with stone base, glazed shaft, physical cornices, four dial faces and hands, sloping cap and orbital rings',heightSource='OSM shop6.8m; Disney official clock18m',heightSourceUrl='https://thewaltdisneycompany.com/news/new-clock-tower-debuts-at-shanghai-disney-store-plaza/',clockPlacement=dict(center=clock_world,source='photo-inferred plaza position',minimumMappedRoadClearanceM=min(clearance) if clearance else None),observedParts=['bronze ribs','curved facade','canopy','clock silhouette and dials'],unverifiedParts=['exact clock cadastral position','Disney script lettering simplified','character figurines and mechanical animation not modeled','rear shop facade'])


def lanhai():
    way=957451688;c=center_of(way);q=local_polygon(way);root,m=new('pudong-way-957451688')
    # The 2021 photographer's corner view shows the circular arrival pavilion,
    # pale sign fascia and adjacent rectilinear glass volume. The OSM outline
    # explicitly traces this round northern head and the thin wraparound mall.
    pale=material('lanhai-grey-cladding',(.49,.48,.44),.61,.22)
    glazing=[material('lanhai-front-glass',(.29,.37,.40),.19,.34)]
    facade(m,q,17,pale,glazing,steel,'curtain',4.25)
    rc=(962.5-c[0],-(231.4-c[1]));r=16.2
    # Keep the existing polygon ring; these radial members enhance its north head
    # rather than adding a second overlapping closed cylinder shell.
    for k in range(64):
        a=k*math.tau/64;b=(k+1)*math.tau/64
        aa=(rc[0]+r*math.cos(a),rc[1]+r*math.sin(a));bb=(rc[0]+r*math.cos(b),rc[1]+r*math.sin(b))
        if math.sin(a)<-.42:continue
        m.edge_panel(aa,bb,3.8,10.5,glazing[0],offset=-.03)
        m.edge_panel(aa,bb,14.3,2.2,pale,offset=.10)
        m.edge_panel(aa,bb,16.5,.70,steel,offset=-.35)
        m.edge_box(aa,bb,17.25,.18,.78,pale,offset=.15)
        for z in [3.8,7.3,10.8,14.3]:m.edge_box(aa,bb,z,.07,.15,light,offset=.16)
        if k%2==0:m.rod((*aa,3.8),(*aa,16.5),.055,light,8)
    text_sign(root,'LANHAI INTERNATIONAL PLAZA',(rc[0],rc[1]+r+.15,14.75),math.pi,.67,light)
    for off in [-8,-4,0,4,8]:
        x=rc[0]+off;y=rc[1]+math.sqrt(r*r-off*off)
        m.box((x,y,2.0),(3.8,.12,3.7),entryglass)
        for dx in [-1.9,0,1.9]:m.box((x+dx,y+.08,2.0),(.06,.18,3.7),light)
        m.box((x,y+.12,.12),(3.9,.5,.14),pale)
    # Separate public stair lies within the mapped west side of the circular head.
    for k in range(18):
        m.box((rc[0]-13.5,rc[1]-4.0+k*.31,(k+1)*.15/2),(2.5,.32,(k+1)*.15),pale)
    for side in [-1,1]:m.rod((rc[0]-13.5+side*1.25,rc[1]-4.0,1.1),(rc[0]-13.5+side*1.25,rc[1]+1.4,3.8),.035,light,8)
    m.flush();record(root,[way],c,0,17.43,refs_for(way),'Mapped wraparound mall with curved glazed arrival pavilion; raised oval fascia, independent metal glazing supports, open dark roof slot, projecting rim, metal building name, entry doors and public stair',name='览海国际广场',heightSource='OSM five-storey / 17 m estimate retained; fascia height inferred by photo proportions',observedParts=['round arrival pavilion','pale name fascia','roof rim and dark slot','glass entrance','public stair'],unverifiedParts=['precise fascia elevation','unphotographed wraparound shop fronts','advertisement contents omitted','stair bearing inferred within footprint'])


def top_profile_skin(m,q,z0,top,stone_mat,glass_mat,metal,rows=48,bay=1.55,stone_width=.18):
    """Individually framed exterior panels clipped to a sloping roof line."""
    q=polygon_ccw(q)
    for aa,bb in zip(q,q[1:]+q[:1]):
        length=math.dist(aa,bb);n=max(1,round(length/bay))
        dx,dy=(bb[0]-aa[0])/length,(bb[1]-aa[1])/length
        for k in range(n):
            a=(aa[0]+dx*length*k/n,aa[1]+dy*length*k/n);b=(aa[0]+dx*length*(k+1)/n,aa[1]+dy*length*(k+1)/n)
            ta,tb=top(*a),top(*b)
            fh=(max(top(x,y) for x,y in q)-z0)/rows
            for j in range(rows):
                za=z0+j*fh;zb=z0+(j+1)*fh
                if za>=max(ta,tb):continue
                vs=[(*a,min(za,ta)),(*b,min(za,tb)),(*b,min(zb,tb)),(*a,min(zb,ta))]
                clean=[]
                for v in vs:
                    if not any(math.dist(v,p)<1e-7 for p in clean):clean.append(v)
                if len(clean)>=3:m.face(clean,glass_mat)
                if za<min(ta,tb):m.rod((*a,za),(*b,za),.055,metal,6)
            m.rod((*a,z0),(*a,ta),stone_width,stone_mat,6)
        m.rod((*aa,top(*aa)),(*bb,top(*bb)),.18,metal,8)
    m.face([(x,y,top(x,y)) for x,y in q],roof)


def bank_shanghai():
    way=-129809231;c=center_of(way);angle=.691;root,m=new('pudong-way-r129809231');q=local_polygon(way,c,angle)
    pale=material('bank-shanghai-grey-stone',(.56,.56,.53),.76);g=material('bank-shanghai-blue-glass',(.21,.31,.35),.24,.36)
    # Tange's completed-building photos show tall outer stone wings and a
    # concave central glazing crown, not the solid 17 m map extrusion.
    # The photographed tower is on the south-east part of the two-part outline.
    tower=[(-35.5,-16.4),(-12,-16.4),(-12,-12),(12,-12),(12,-16.4),(35.4,-16.4),(35.4,16.5),(-35.5,16.5)]
    facade(m,tower,192,pale,[g],light,'curtain',4.45)
    for side in [-1,1]:
        for x in [side*14,side*20.8,side*27.5,side*34.7]:
            m.box((x,-16.7,96),(1.25,.75,192),pale)
            for z in [44,113,170,191]:m.box((x,-16.9,z),(1.65,.9,1.0),pale)
        wing=[(side*12,-16.4),(side*35.4,-16.4),(side*35.4,16.5),(side*12,16.5)]
        panel_skin(m,wing,192,222,7,[g],light)
        for x in [side*14,side*33.8]:m.box((x,-16.5,211),(1.75,1.8,38),pale)
        # Long dark louvres in the high stone shoulder are physically separate.
        m.box((side*23.5,-16.6,207),(8.5,.25,20),steel)
        for j in range(24):m.box((side*23.5,-16.9,197+j*.8),(8.6,.55,.11),light)
        m.box((side*23.5,-16.6,225),(12.0,2.0,10),pale)
        for x in [side*17.5,side*29.5]:m.box((x,-16.8,226),(1.0,2.4,8),pale)
        m.rod((side*23.5,-15.6,230),(side*23.5,-15.6,252),.16,light,12,r2=.045)
    for j in range(39):m.edge_box((-11.8,-12.2),(11.8,-12.2),16+j*4.45,.7,.5,pale,offset=.06)
    # Curved upper screen has actual varying depth and individual glazed bays.
    curve=[(-12+24*k/32,-16.4+4.4*(1-((-12+24*k/32)/12)**2)) for k in range(33)]
    for aa,bb in zip(curve,curve[1:]):
        for j in range(7):m.face([(*aa,192+j*4),(*bb,192+j*4),(*bb,196+j*4),(*aa,196+j*4)],g)
        m.rod((*aa,192),(*aa,223),.075,light,8)
        m.rod((*aa,218),(*aa,225),.17,light,8)
    for z in [192,196,200,204,208,212,216,220]:
        for aa,bb in zip(curve,curve[1:]):m.rod((*aa,z),(*bb,z),.055,light,6)
    for side in [-1,1]:
        m.box((side*24.2,-17,23.2),(23,1.1,46),pale)
        for x in [side*16,side*22,side*28,side*34]:
            for j in range(9):m.box((x,-17.62,3.8+j*4.55),(3.4,.12,3.5),g)
    # Low north-west mapped part is a separately recorded podium. Its image
    # visibility is partial; the architectural render is never photo evidence.
    pq=local_polygon(-129809230,c,angle);facade(m,pq,17.8,pale,[g],light,'curtain',4.45)
    edge=max(zip(pq,pq[1:]+pq[:1]),key=lambda e:math.dist(*e));entrance(m,*edge,5.7)
    m.flush();record(root,[way,-129809230],c,angle,252,refs_for(way),'230 m paired stone shoulders, blue inset glazing, recessed central horizontal bands, curved glazed crown, louvre shoulders and two 22 m aerials; distinct mapped north-west low podium',name='上海银行大厦',heightSource='Tange Architects: 230 m building; 252 m tip from CTBUH historical listing',heightSourceUrl='https://www.tangeweb.com/works/works_no-137/',observedParts=['tower front','stone shoulder piers','concave upper glazing','crown louvres','aerials'],unverifiedParts=['podium entrance hidden by trees in actual photographs','rear facade exact bays','north-west podium height estimated from facade proportions'],partEvidence={'-129809231':'tower-matched-exterior-photographs','-129809230':'associated-podium-only-partly-visible'})


def bank_china():
    way=164957811;c=center_of(way);angle=-.446;root,m=new('pudong-way-164957811')
    pale=material('boc-silver-stone',(.48,.53,.57),.58,.24);g=material('boc-blue-silver-glass',(.22,.35,.43),.20,.49)
    # Nikken's front, reverse corner and arrival photos resolve the curved upper
    # tower, sloping lower sleeve and rounded three-storey entrance separately.
    tq=[(24*math.cos(k*math.tau/112),4+19*math.sin(k*math.tau/112)) for k in range(112)]
    panel_skin(m,tq,13,216.8,50,[g],light)
    for z in [13+j*4.076 for j in range(51)]:
        for aa,bb in zip(tq,tq[1:]+tq[:1]):m.rod((*aa,z),(*bb,z),.055,light,6)
    # Broad lower triangular sleeve rises toward its two outer corners.
    sleeve=[(-34,-23),(34,-23),(34,22),(-34,22)]
    # A single planar oblique cut avoids an invented saddle roof between the
    # rounded tower and its rectilinear lower sleeve.
    def collar(x,y):return 94+55*(x+34)/68
    top_profile_skin(m,sleeve,14,collar,pale,g,light,rows=30,bay=1.7,stone_width=.20)
    # Crown colonnade and elliptical roof overhang remain open between ribs.
    for i in range(112):
        aa=tq[i];bb=tq[(i+1)%112];za=226.1-1.7*(1-aa[0]/24);zb=226.1-1.7*(1-bb[0]/24)
        m.rod((*aa,216.8),(*aa,za),.14,pale,8)
        m.rod((*aa,za),(*bb,zb),.22,light,8)
    m.face([(x,y,226.1-1.7*(1-x/24)) for x,y in tq],roof)
    # Single exposed side mast and triangular truss visible in architect photos.
    for off in [-.65,.65]:m.rod((24.5,4+off,213),(24.5,4+off,249),.12,light,8,r2=.07)
    for j in range(8):m.rod((24.5,3.35,214+j*4),(24.5,4.65,218+j*4),.065,light,6)
    m.rod((24.5,4,246),(24.5,4,258),.095,light,10,r2=.025)
    # Rounded western arrival hall, contained by the mapped 75 x 64 m base.
    pq=[]
    for cx,cy,a in [(25,-19,-math.pi/2),(25,19,0),(-25,19,math.pi/2),(-25,-19,math.pi)]:
        pq.extend((cx+11.3*math.cos(a+k*math.pi/2/20),cy+11.3*math.sin(a+k*math.pi/2/20)) for k in range(21))
    pq=polygon_ccw(pq);panel_skin(m,pq,.12,13.2,6,[g],steel)
    for aa,bb in zip(pq,pq[1:]+pq[:1]):
        m.edge_panel(aa,bb,13.2,3.8,pale)
        for j in range(20):m.edge_box(aa,bb,13.4+j*.17,.045,.21,steel,offset=.05)
        m.edge_box(aa,bb,3.8,.14,.55,pale,offset=.09)
    for x in [-17,-5,7,19]:
        m.rod((x,-30.3,0),(x,-30.3,3.8),.22,steel,12)
        a=(x-2.2,-30.4);b=(x+2.2,-30.4);m.edge_panel(a,b,.12,3.6,entryglass)
        for xx in [x-2.2,x,x+2.2]:m.rod((xx,-30.5,.12),(xx,-30.5,3.7),.045,light,8)
    m.flush();record(root,[way],c,angle,258,refs_for(way),'Nikken photo-matched elliptical tower, open crown ribs, 258 m side mast, sloping silver lower sleeve and rounded multi-level glass arrival hall with dark columns and closely spaced metal fascia louvres',name='中银大厦',heightSource='Nikken 226.10 m building; CTBUH 258 m tip',heightSourceUrl='https://www.nikken.co.jp/en/projects/office/bank_of_china_tower_shanghai.html',observedParts=['curved tower','open crown ribs','side aerial','sloping silver sleeve','curved entrance curtain wall and black columns'],unverifiedParts=['tower and hall position inside single undivided map polygon','exact ellipse radii and sleeve slope','concealed doors','rear lobby elevation'])


def bocom():
    way=164971470;c=center_of(way);angle=-.9273;root,m=new('pudong-way-164971470');q=local_polygon(way,c,angle)
    pale=material('bocom-pale-panel',(.60,.59,.53),.8);g=material('bocom-grey-glass',(.19,.28,.30),.26,.34)
    for x0,x1,y0,y1,h0,h1,floors in [(-43,37,14,30,230.4,195,50),(-5,50,-17,-1,197.4,172,44)]:
        qq=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
        def top(x,y):return h0+(h1-h0)*(x-x0)/(x1-x0)
        top_profile_skin(m,qq,0,top,pale,g,steel,rows=floors,bay=1.5,stone_width=.22)
        m.face([(x,y,top(x,y)+.035) for x,y in qq],g)
        # Opaque side walls and window fields are different surfaces. Heavy
        # horizontal slab lips wrap the exposed corners at each full floor.
        for xx in [x0,x1]:
            m.edge_panel((xx,y0+.8),(xx,y1-.8),0,min(top(xx,y0),top(xx,y1))-2,pale)
            for z in range(0,int(top(xx,y0)),4):m.edge_box((xx,y0),(xx,y1),z,.38,.9,steel,offset=.06)
        for yy in [y0,y1]:
            for z in range(4,int(min(h0,h1))-1,4):m.edge_box((x0,yy),(x1,yy),z,.42,.70,pale,offset=.08)
            # Rows of small stone piers and vertical window groups seen in
            # both street photographs are retained below the roof wedge.
            for k in range(2,18):
                xx=x0+(x1-x0)*k/19;hh=top(xx,yy)-1.5
                m.box((xx,yy,hh/2),(.20,.34,hh),pale)
        # Sloping roof-glass frame, verified by the Jin Mao observation photo.
        for k in range(1,31):
            xx=x0+(x1-x0)*k/31;m.rod((xx,y0,top(xx,y0)+.12),(xx,y1,top(xx,y1)+.12),.08,light,8)
    cq=[(12,-1),(32,-1),(32,14),(12,14)];panel_skin(m,cq,0,163.4,40,[g],light)
    for z in range(4,164,4):m.edge_box((12,-1),(32,-1),z,.16,.55,light)
    # Low circular annex is visible to the west in the aerial photograph.
    aq=[(-26+17.5*math.cos(k*math.tau/96),-16+17.5*math.sin(k*math.tau/96)) for k in range(96)]
    panel_skin(m,aq,0,16,4,[g],pale)
    for aa,bb in zip(aq,aq[1:]+aq[:1]):
        for z in [3.6,7.6,11.6,15.6]:m.edge_box(aa,bb,z,.48,.36,pale)
    for x in [-4,4,12,20]:
        m.box((x,8,2.5),(.6,.6,5),pale)
    m.box((8,6,5.2),(32,8,.6),pale)
    entrance(m,(-7,-17),(17,-17),5.4)
    # Paired mast rods and their open braces, no opaque spire box.
    for xx in [-42,-37]:m.rod((xx,29,230),(xx,29,265),.17,light,12,r2=.04)
    for j in range(7):
        z=231+j*3.5;m.rod((-42,29,z),(-37,29,z+3.5),.09,light,8);m.rod((-37,29,z),(-42,29,z+3.5),.09,light,8)
    m.flush();record(root,[way],c,angle,265,refs_for(way),'Two separate slender slabs with different heights and sloping glazed roof wedges; 163 m recessed glass connection; physical horizontal slab lips, stone end walls, small glazing piers, open paired mast and low circular annex',name='交银金融大厦',heightSource='CTBUH north230.4 m; contractor south198 m; mast tip265 m',heightSourceUrl='https://www.skyscrapercenter.com/building/bocom-financial-towers/718',observedParts=['paired unequal towers','diagonal roof glass','stone side walls','horizontal floor lips','connecting glass','low round annex'],unverifiedParts=['tower positions within undivided mapped outline','ground entry mostly obscured','annex facade exact bay count'])


def chen_mansion():
    way=165168180;c=center_of(way);angle=.2547;root,m=new('pudong-way-165168180')
    greybrick=material('chen-grey-brick',(.24,.255,.25),.94);red=material('chen-red-brick',(.40,.19,.12),.92);tile=material('chen-dark-roof-tile',(.16,.18,.18),.91);wood=material('chen-wood-lattice',(.36,.24,.13),.85)
    # The map's 17 m fallback conflicts with the photographed single-storey
    # traditional residence. The 8.4 m gable is a stated photo proportion estimate.
    # Three halls are joined by narrow wings, leaving the two courts open.
    for y0,y1 in [(-21.5,-13.5),(-6.5,1.5),(11.5,21.5)]:
        qq=[(-13,y0),(13,y0),(13,y1),(-13,y1)]
        for aa,bb in zip(qq,qq[1:]+qq[:1]):m.edge_box(aa,bb,0,5.2,.22,greybrick,offset=-.10)
        mid=(y0+y1)/2
        for side in [-1,1]:
            yy=y0 if side<0 else y1
            m.face([(-13.3,yy,5.15),(13.3,yy,5.15),(13.3,mid,7.2),(-13.3,mid,7.2)],tile)
            for k in range(90):
                xx=-13.3+k*26.6/89;m.rod((xx,yy,5.22),(xx,mid,7.26),.075,tile,8)
        m.rod((-13.5,mid,7.25),(13.5,mid,7.25),.15,tile,10)
    for x0,x1 in [(-13,-9),(9,13)]:
        for y0,y1 in [(-13.5,-6.5),(1.5,11.5)]:
            qq=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
            for aa,bb in zip(qq,qq[1:]+qq[:1]):m.edge_box(aa,bb,0,4.4,.22,greybrick,offset=-.10)
            m.polygon(qq,4.55,tile)
    # The photograph sees the brick gable END beside the long timber facade.
    # Keep the gable perpendicular to the east-west ridge, never place both
    # the end pediment and the eaves screen on a single invented elevation.
    yy=-21.56;gx=-13.06;gy=-17.5
    profile=[(-4,4.9),(-4,5.65),(-3.3,5.65),(-1.1,7.5),(-1.1,8.2),(1.1,8.2),(1.1,7.5),(3.3,5.65),(4,5.65),(4,4.9)]
    m.face([(gx,gy+t,z) for t,z in profile],greybrick)
    for (ta,za),(tb,zb) in zip(profile,profile[1:]):m.rod((gx-.08,gy+ta,za),(gx-.08,gy+tb,zb),.12,red,8)
    for z in [1.1,2.2,3.35,4.75,5.2]:m.box((gx-.08,gy,z),(.17,8,.15),red)
    for k in range(28):
        t=-4+k*8/28;row=k%2
        for z in [.5,1.5,2.55,3.75,4.35]:m.box((gx-.085,gy+t,z+row*.08),(.018,.018,.30),red)
    for side in [-1,1]:
        t=side*.85;aa=(gx-.12,gy+t-.38);bb=(gx-.12,gy+t+.38)
        arched_band(m,aa,bb,5.3,1.4,red,entryglass,1)
        a=(gx-.13,gy+t-.48);b=(gx-.13,gy+t+.48)
        m.edge_panel(a,b,.7,2.9,wood)
        for z in [.8+j*.14 for j in range(19)]:m.edge_box(a,b,z,.027,.07,greybrick)
    # Timber lattice screens and central doors are real exterior relief;
    # their repeating pattern is simplified, not copied from signage or art.
    for k in range(13):
        x=-12+k*2;m.box((x,yy-.20,2.65),(.14,.20,4.4),wood)
    for z in [.55,1.4,3.55,4.6]:m.box((0,yy-.24,z),(24,.17,.12),wood)
    for k in range(48):
        x=-11.8+k*.5;m.box((x,yy-.24,2.7),(.045,.08,2.6),wood)
        if k%4==0:
            m.rod((x,yy-.26,3.75),(x+.5,yy-.26,4.35),.045,wood,6);m.rod((x+.5,yy-.26,3.75),(x,yy-.26,4.35),.045,wood,6)
    m.box((0,yy-.25,.18),(3.3,.60,.36),greybrick)
    for t in [-3.8,3.8,-1.0,1.0]:m.sphere((gx,gy+t,5.9 if abs(t)>3 else 8.4),.18,red,20,12)
    # Separate daytime source resolves the plastered rear wall and timber
    # shutters. Do not repeat the brick gable/lattice treatment on that face.
    plaster=material('chen-rear-plaster',(.67,.65,.57),.92)
    m.edge_panel((-13,21.58),(13,21.58),.18,5.02,plaster)
    for z in [.45,1.15,4.30,5.08]:m.edge_box((-13,21.6),(13,21.6),z,.10,.16,red)
    for x in [-11.3,-9.1,-6.9,-4.1,-1.9,1.9,4.1,6.9,9.1,11.3]:
        a=(x-.49,21.66);b=(x+.49,21.66)
        arched_band(m,a,b,1.2,3.05,red,wood,1)
        for z in [1.5+j*.12 for j in range(18)]:m.edge_box(a,b,z,.028,.08,greybrick)
        m.rod((x,21.71,1.25),(x,21.71,4.05),.045,red,8)
    m.flush();record(root,[way],c,angle,8.8,refs_for(way),'Grey brick three-hall courtyard residence with two open courts, red brick string courses and stepped end gable, ribbed tiled roofs, paired arched attic windows, separate timber eaves screen and plastered rear shutter elevation',name='陈桂春住宅',heightSource='8.8 m photo-proportioned gable estimate; rejected OSM 17 m default',heightSourceUrl='https://commons.wikimedia.org/wiki/File:Chen%27s_Mansion_Lujiazui.JPG',observedParts=['red and grey brick','stepped end gable','paired arched openings','timber lattice','tiled eaves','plastered rear and timber shutters'],unverifiedParts=['courtyard dimensions inferred within mapped rectangle','roof pitch and ridge elevations estimated','eastern end wall decoration'])


def generic_build(b):
    way=b['wayId'];key='pudong-way-'+str(way).replace('-','r');root,m=new(key);c=center_of(way);q=local_polygon(way);h=b['height'];refs=refs_for(way,b.get('photoRef'))
    name=b['name'];height_authority=b['heightSource'];height_url=None
    overrides={-129809240:(168.8,'https://www.skyscrapercenter.com/building/azia-center/2887'),448242492:(180,'https://www.skyscrapercenter.com/building/mirae-asset-tower/2345'),520990202:(180,'https://www.skyscrapercenter.com/building/citigroup-tower/2326'),-129810530:(269.1,'https://www.skyscrapercenter.com/building/one-lujiazui/689'),-128821601:(121,'https://www.mdpi.com/2075-5309/16/1/93'),967281056:(104,'https://www.skyscrapercenter.com/building/grand-kempinski-hotel-shanghai/21637')}
    if way in overrides:h,height_url=overrides[way];height_authority='CTBUH Skyscraper Center'
    style='curtain' if h>45 or any(s in name for s in ['金融','银行','国金','平安','时代','未来资产','凯宾斯基','广场']) else 'masonry'
    # Names don't establish height; an estimate remains an explicit estimate.
    facstone=warm if '香格里拉' in name or way==-128821601 else stone
    if way==-128821601:style='masonry';height_authority='original published research table; 26 floors / 121 m'
    if way==165591946:style='curtain';name='Shanghai World Financial Center podium'
    if way==135840678:style='masonry';facstone=material('insurance-pale-stone',(.62,.59,.51),.78)
    if way==967281056:height_authority='CVU / CTBUH statistical estimate from 27 hotel floors, not measured'

    observed_tints={164905211:(.20,.31,.35),967281056:(.22,.34,.32),113520430:(.18,.28,.32),956369929:(.18,.28,.32),-129809240:(.21,.32,.35),165591946:(.30,.37,.39)}
    palette=[material('source-glass-'+str(way),observed_tints[way],.21,.38)] if way in observed_tints else glass
    facade(m,q,h,facstone,palette if style=='curtain' else blue,light if style=='curtain' else steel,style,4.0 if style=='curtain' else 3.4,abs(way)%6)
    edge=max(zip(q,q[1:]+q[:1]),key=lambda e:math.dist(*e));entrance(m,*edge,min(5.4,h-1))
    xs=[p[0] for p in q];ys=[p[1] for p in q];span=min(max(xs)-min(xs),max(ys)-min(ys))
    if span>14:roof_equipment(m,(0,0),h,min(span*.12,7),roof,steel)
    # Tall bank façades have projecting vertical aluminum blades, street-visible
    # shadow depth, not merely dark painted strips.
    if style=='curtain' and h>50:
        for a,bp in zip(q,q[1:]+q[:1]):
            l=math.dist(a,bp)
            if l<8:continue
            dx,dy=(bp[0]-a[0])/l,(bp[1]-a[1])/l
            for k in range(1,max(2,round(l/4))):
                t=k/max(2,round(l/4));x,y=a[0]+(bp[0]-a[0])*t,a[1]+(bp[1]-a[1])*t
                m.box((x-dy*.10,y+dx*.10,h/2),(.11,.48,h),light,math.atan2(dy,dx))
    if way==-128821601:
        # Photo-visible warm stone pier strips run almost the full tower height;
        # broad opaque cornice and black rooftop mechanical louvres are distinct.
        for aa,bb in zip(q,q[1:]+q[:1]):
            length=math.dist(aa,bb);bays=max(1,round(length/4.0));dx,dy=(bb[0]-aa[0])/length,(bb[1]-aa[1])/length
            for k in range(bays+1):
                x,y=aa[0]+dx*length*k/bays,aa[1]+dy*length*k/bays;m.box((x-dy*.12,y+dx*.12,58),(.74,.34,104),warm,math.atan2(dy,dx))
            m.edge_box(aa,bb,111,9,.36,warm,offset=-.12)
            for k in range(6):m.edge_box(aa,bb,111+k*.22,.065,.40,steel,offset=-.08)
    if way==520990202:
        fa,fb=b['frontage']['edge'];aa=(fa[0]-c[0],-(fa[1]-c[1]));bb=(fb[0]-c[0],-(fb[1]-c[1]));length=math.dist(aa,bb);dx,dy=(bb[0]-aa[0])/length,(bb[1]-aa[1])/length
        x,y=(aa[0]+bb[0])/2,(aa[1]+bb[1])/2
        if x*dy-y*dx<0:aa,bb=bb,aa;dx,dy=-dx,-dy
        # Name engraved on the thin glass screen seen beside the entrance.
        m.edge_panel((x-dx*6,y-dy*6),(x+dx*6,y+dy*6),.3,2.8,entryglass,offset=-1.5)
        text_sign(root,'CITIGROUP TOWER',(x-dy*1.45,y+dx*1.45,1.0),math.atan2(dy,dx),.64,light)
        m.edge_box(aa,bb,5.2,.45,2.8,light,offset=-1.4)
    if way==164905211:
        # StudioSZ 2021 corner photographs show broad dark continuous spandrels,
        # paired shallow rails and rooftop DBS lettering on two visible sides.
        for aa,bb in zip(q,q[1:]+q[:1]):
            for j in range(1,23):
                z=j*h/23
                m.edge_box(aa,bb,z,.45,.30,steel,offset=-.02)
                for dz in [-.26,.55]:m.edge_box(aa,bb,z+dz,.08,.42,steel,offset=-.02)
        for aa,bb in sorted(zip(q,q[1:]+q[:1]),key=lambda e:math.dist(*e),reverse=True)[:2]:
            angle=math.atan2(bb[1]-aa[1],bb[0]-aa[0]);x,y=(aa[0]+bb[0])/2,(aa[1]+bb[1])/2
            text_sign(root,'DBS',(x,y,h-5),angle,2.8,light)
    if way==967281056:
        # This facade is visible in two street photographs. The main outline has
        # a genuine concave curved side, already preserved by the OSM polygon.
        for aa,bb in zip(q,q[1:]+q[:1]):
            for j in range(1,28):m.edge_box(aa,bb,j*104/28,.12,.20,light,offset=-.04)
        aa,bb=max(zip(q,q[1:]+q[:1]),key=lambda e:math.dist(*e));x,y=(aa[0]+bb[0])/2,(aa[1]+bb[1])/2
        text_sign(root,'KEMPINSKI',(x,y,98),math.atan2(bb[1]-aa[1],bb[0]-aa[0]),1.3,light)
    if way==135840678:
        for aa,bb in zip(q,q[1:]+q[:1]):
            length=math.dist(aa,bb)
            if length<10:continue
            dx,dy=(bb[0]-aa[0])/length,(bb[1]-aa[1])/length
            for k in range(1,6):
                x,y=aa[0]+dx*length*k/6,aa[1]+dy*length*k/6
                m.box((x,y,86),(.5,.40,155),facstone,math.atan2(dy,dx))
            for z in [161,165,180,188]:m.edge_box(aa,bb,z,.95,.5,facstone,offset=-.05)
            m.edge_box(aa,bb,193,2.4,.42,facstone,offset=-.03)
    if way in [113520430,956369929]:
        # Hines's actual corner photograph proves the three-storey clear ground
        # facade and metal-blade canopy, but does not show the tower crown.
        for aa,bb in zip(q,q[1:]+q[:1]):
            m.edge_panel(aa,bb,.15,min(12.6,h-.6),entryglass,offset=.06)
            for z in [0,4.6,8.6,12.6]:m.edge_box(aa,bb,z,.12,.38,steel,offset=.10)
            n=max(1,round(math.dist(aa,bb)/2));dx,dy=(bb[0]-aa[0])/n,(bb[1]-aa[1])/n
            for k in range(n+1):m.rod((aa[0]+dx*k,aa[1]+dy*k,0),(aa[0]+dx*k,aa[1]+dy*k,min(12.6,h)),.055,steel,8)
            if h>100:
                for j in range(4,50):m.edge_box(aa,bb,j*h/50,.19,.52,steel,offset=.12)
        aa,bb=max(zip(q,q[1:]+q[:1]),key=lambda e:math.dist(*e));length=math.dist(aa,bb);dx,dy=(bb[0]-aa[0])/length,(bb[1]-aa[1])/length;px,py=(aa[0]+bb[0])/2,(aa[1]+bb[1])/2
        for k in range(9):
            shift=-2+k*.48;can_a=(px-dx*6-dy*shift,py-dy*6+dx*shift);can_b=(px+dx*6-dy*shift,py+dy*6+dx*shift);m.edge_box(can_a,can_b,4.5,.12,.16,light)
        for off in [-4.5,4.5]:m.rod((px+dx*off-dy*1.5,py+dy*off+dx*1.5,0),(px+dx*off-dy*1.5,py+dy*off+dx*1.5,4.5),.17,stone,12)
    if way==165591946:
        # Actual 2024 traveler photo: black projecting rectangular portal,
        # clear glass above revolving doors and SWFC metal letters. The mapped
        # eastern edge is established, precise entrance station is inferred.
        aa=(929.47-c[0],-(242.34-c[1]));bb=(933.86-c[0],-(347.73-c[1]));length=math.dist(aa,bb);dx,dy=(bb[0]-aa[0])/length,(bb[1]-aa[1])/length
        nx,ny=-dy,dx;station=32;px,py=aa[0]+dx*station,aa[1]+dy*station
        a=(px-dx*8,py-dy*8);b0=(px+dx*8,py+dy*8)
        for k in range(9):
            x,y=px+dx*(-8+k*2),py+dy*(-8+k*2);m.rod((x+nx*.14,y+ny*.14,0),(x+nx*.14,y+ny*.14,13.2),.065,light,8)
        m.edge_box(a,b0,12.7,.55,1.4,steel,offset=-.60)
        m.edge_box(a,b0,5.3,.65,1.2,steel,offset=-.50)
        for pa in [a,b0]:m.box((pa[0]+nx*.55,pa[1]+ny*.55,6.6),(.62,1.2,13.2),steel,math.atan2(dy,dx))
        text_sign(root,'SWFC',(px+nx*1.33,py+ny*1.33,13.3),math.atan2(dy,dx)+math.pi,1.45,light)
        text_sign(root,'SHANGHAI WORLD FINANCIAL CENTER',(px+nx*1.15,py+ny*1.15,5.50),math.atan2(dy,dx)+math.pi,.39,light)
        door_clear=material('swfc-door-clear-glass',(.22,.31,.35),.13,.1)
        door_clear.node_tree.nodes.get('Principled BSDF').inputs['Alpha'].default_value=.27
        try:door_clear.surface_render_method='BLENDED'
        except Exception:pass
        for off in [-4.5,0,4.5]:
            gx,gy=px+dx*off,py+dy*off
            for k in range(48):
                a0=k*math.tau/48;a1=(k+1)*math.tau/48
                pa=(gx+math.cos(a0)*1.35,gy+math.sin(a0)*1.35);pb=(gx+math.cos(a1)*1.35,gy+math.sin(a1)*1.35)
                m.edge_panel(pa,pb,.12,3.8,door_clear)
                if k%8==0:m.rod((*pa,.12),(*pa,3.92),.055,light,8)
            for ang in [0,math.pi/2,math.pi,math.pi*1.5]:m.edge_panel((gx,gy),(gx+math.cos(ang)*1.3,gy+math.sin(ang)*1.3),.12,3.8,door_clear)
            m.ring(3.95,1.35,.08,light,64,gx,gy)
    if way==-129809240:
        fa,fb=b['frontage']['edge'];aa=(fa[0]-c[0],-(fa[1]-c[1]));bb=(fb[0]-c[0],-(fb[1]-c[1]));length=math.dist(aa,bb);dx,dy=(bb[0]-aa[0])/length,(bb[1]-aa[1])/length
        px,py=(aa[0]+bb[0])/2,(aa[1]+bb[1])/2
        if px*dy-py*dx<0:aa,bb=bb,aa;dx,dy=-dx,-dy
        theta=math.atan2(dy,dx)
        # Deep glazing recess and sloping metal reveals visible above the entry.
        a=(px-dx*4,py-dy*4);b0=(px+dx*4,py+dy*4)
        m.face([(*a,0),(*b0,0),(px,py,22)],blue[2])
        for side in [-1,1]:m.rod((px+dx*side*4,py+dy*side*4,0),(px,py,22),.11,light,10)
        for k in range(7):m.edge_box((px-dx*6,py-dy*6),(px+dx*6,py+dy*6),5.1,.12,.11,light,offset=-.4-k*.40)
        m.edge_box((px-dx*8,py-dy*8),(px+dx*8,py+dy*8),.0,1.05,.6,stone,offset=-1.6)
        text_sign(root,'AZIA',(px-dy*1.25,py+dx*1.25,1.1),theta,2.25,light)
        text_sign(root,'center',(px-dy*1.27,py+dx*1.27,.35),theta,.5,light)
    matched_changes={165591946:['black projecting entry portal','slender silver glazing frames','SWFC metal letters','three revolving exterior doors'],164905211:['dark broad continuous spandrels','paired shallow metal rails','DBS rooftop lettering'],967281056:['concave curved facade','narrow horizontal metal bands','KEMPINSKI rooftop name'],135840678:['pale stone piers','vertical glazing strips','opaque broad upper cornice'],113520430:['three-storey clear glass ground facade','black pane frames','slender canopy blades and columns'],956369929:['three-storey clear glass ground facade','black pane frames','slender canopy blades and columns'],-129809240:['AZIA entry letters','low granite name plinth','sloping glass recess','supported entry canopy']}
    m.flush();record(root,[way],c,0,h,refs,'Exact mapped polygon, independent inset glass panes and jambs, physical mullions/transoms, sill/coping profiles, doors and roof ventilation; side/rear bay layout inferred',confidence=('OSM footprint; matched photo observations plus inferred unobserved bays; height from '+height_authority if refs else 'OSM footprint and '+height_authority+' height; facade bay arrangement inferred'),name=name,heightSource=height_authority,heightSourceUrl=height_url,frontage=b['frontage'],photoMatchedChanges=matched_changes.get(way,[]),unverifiedParts=['unphotographed elevations and roof plant','exact bay count and entrance bearing outside matched image'])


def apple():
    way=255624910;root,m=new('apple-pudong');c=center_of(way)
    # The map tags this open entrance cylinder as a 17 m estimated building. Use
    # the photo-observed 12.8 m all-glass cylinder instead of an opaque high-rise.
    n=96;r=6.8;h=12.8
    clear=material('apple-clear-glass',(.65,.79,.82),.13,.1)
    clear.node_tree.nodes.get('Principled BSDF').inputs['Alpha'].default_value=.32
    try:clear.surface_render_method='BLENDED'
    except (TypeError,AttributeError):pass
    for k in range(n):
        a=math.tau*k/n;b=math.tau*(k+1)/n
        m.face([(r*math.cos(a),r*math.sin(a),0),(r*math.cos(b),r*math.sin(b),0),(r*math.cos(b),r*math.sin(b),h),(r*math.cos(a),r*math.sin(a),h)],clear,True)
        if k%8==0:m.rod((r*math.cos(a),r*math.sin(a),0),(r*math.cos(a),r*math.sin(a),h),.035,light,5)
    m.ring(.1,r,.12,light,128);m.ring(h,r,.09,light,128)
    # Steps are a recessed local entrance; no invented underground interior.
    for i in range(10):
        rr=r+2+i*.55;m.ring(.07,rr,.07,stone,128)
    m.flush();record(root,[way],c,0,h,refs_for(way,'apple-pudong-exterior'),'Freestanding glazed cylindrical entrance and radial plaza paving joints; no interior',heightSource='supplier report via Shanghai Songjiang government, 12.8 m glass panels',heightSourceUrl='https://www.songjiang.gov.cn/xwzx/001001/20240807/24c52b60-1fa9-4fcf-b3d2-24797d2a7d5e.html')


def ifc(way,key,height):
    root,m=new(key);c=center_of(way);q=local_polygon(way)
    # The faceted polygon is not replaced with a box. The upper plane is slanted
    # across the actual plan and receives short crown mullions.
    facade(m,q,height-12,stone,blue,light,'curtain',4.0)
    xs=[p[0] for p in q];lo,hi=min(xs),max(xs)
    def top(x):return height-12+12*(x-lo)/(hi-lo)
    for a,b in zip(q,q[1:]+q[:1]):
        l=math.dist(a,b);n=max(1,round(l/1.5))
        for i in range(n):
            aa=(a[0]+(b[0]-a[0])*i/n,a[1]+(b[1]-a[1])*i/n);bb=(a[0]+(b[0]-a[0])*(i+1)/n,a[1]+(b[1]-a[1])*(i+1)/n)
            m.face([(*aa,height-12),(*bb,height-12),(*bb,top(bb[0])),(*aa,top(aa[0]))],blue[i%4])
            m.rod((*aa,height-12),(*aa,top(aa[0])),.055,light,6)
        m.rod((*a,top(a[0])),(*b,top(b[0])),.13,light,8)
    m.face([(x,y,top(x)) for x,y in q],roof)
    for aa,bb in zip(q,q[1:]+q[:1]):
        for z in [height*.16,height*.59]:
            for k in range(12):m.edge_box(aa,bb,z+k*.25,.09,.22,steel,offset=-.015)
    entrance(m,*max(zip(q,q[1:]+q[:1]),key=lambda e:math.dist(*e)),7)
    m.flush();record(root,[way],c,0,height,refs_for(way,'ifc-pudong-exterior'),'Mapped faceted tower plan; each glazing bay and 4 m story joint modeled; sloped crown planes, parapet cap and recessed entry',heightSource='OSM explicit height')


def export_all():
    for root,rec in zip(models,records):
        bpy.ops.object.select_all(action='DESELECT');root.select_set(True)
        for obj in root.children_recursive:obj.select_set(True)
        bpy.context.view_layer.objects.active=root
        meshes=[o for o in [root,*root.children_recursive] if o.type=='MESH']
        triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes)
        assert triangles>0
        file=OUT/(root.name+'.glb')
        bpy.ops.export_scene.gltf(filepath=str(file),export_format='GLB',use_selection=True,export_yup=True,export_apply=True,export_texcoords=True,export_normals=True,export_materials='EXPORT',export_extras=True,export_animations=False,export_cameras=False,export_lights=False,export_draco_mesh_compression_enable=False)
        points=[o.matrix_world@Vector(v) for o in meshes for v in o.bound_box]
        bounds=[min(v[i] for v in points) for i in range(3)]+[max(v[i] for v in points) for i in range(3)]
        rec.update(bytes=file.stat().st_size,triangles=triangles,meshes=len(meshes),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),localBlenderBounds=bounds)
        print('PUDONG_ASSET',rec['id'],rec['bytes'],triangles,flush=True)
    for root,rec in zip(models,records):
        root.location=(rec['center'][0],-rec['center'][1],.12);root.rotation_euler.z=rec['heading']
    bpy.ops.wm.save_as_mainfile(filepath=str(EDIT),compress=True)
    if ARGS.ids and PREVIOUS:
        published=sorted([r for r in PREVIOUS['models'] if r['id'] not in ARGS.ids]+records,key=lambda r:r['id'])
    else:published=records
    latest_refs=json.loads(EXPANSION.read_text()) if EXPANSION.exists() else []
    if isinstance(latest_refs,dict):latest_refs=latest_refs.get('photos',latest_refs.get('items',[]))
    rejected_reference_ids={p['id'] for p in latest_refs if not p.get('visualInspection',{}).get('accepted',True) or p.get('usage')=='excluded'}
    latest_refs=[p for p in latest_refs if p.get('visualInspection',{}).get('accepted',True) and p.get('usage')!='excluded']+LOOP_REFS
    original_refs=json.loads((ROOT/'references/tourism/architecture-photos.json').read_text())
    for rec in published:
        matched=[p for p in latest_refs if any(w in p.get('wayIds',p.get('ways',[])) for w in rec['ways'])]
        matched += [p for p in original_refs if p['id'] in rec['referenceIds'] and p.get('usage')=='exterior-reference']
        rec['referenceIds']=list(dict.fromkeys([rid for rid in rec['referenceIds'] if rid not in rejected_reference_ids]+[p['id'] for p in matched]))
        rec['photoReferenceFiles']=list(dict.fromkeys(p['file'] for p in matched if 'file' in p))
        rec['loopPhotoObservations']=[dict(id=p['id'],observations=p.get('observations',[]),limitations=p.get('limitations',[]),sourceUrl=p.get('sourceUrl'),license=p.get('license')) for p in matched if p in LOOP_REFS]
        direct_photos=[p for p in matched if p.get('viewed') or p.get('visualInspection',{}).get('accepted')]
        rec['photoEvidenceByWay']={str(w):[p['id'] for p in direct_photos if w in p.get('wayIds',p.get('ways',[]))] for w in rec['ways']}
        rec['photoVerified']=all(rec['photoEvidenceByWay'][str(w)] for w in rec['ways'])
        rec['realPhotoAcceptance']=False
        rec['photoVerificationMeaning']='Every constituent mapped way has a directly associated inspected exterior photograph; unseen surfaces and fidelity acceptance remain separate.'
        rec['unobservedSurfaces']='Rear elevations, roof equipment and unphotographed bay arrangements are inferred from mapped massing and local construction vocabulary.'
    output=dict(version=1,generator='scripts/build_pudong_district.py',createdAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),coordinateSystem='Individual GLBs local; manifest center world X east, Z south; heading Three Y = Blender Z',quality=dict(draco=False,decimation=False,interiors=False,textureUpsampling=False),models=published,totalBytes=sum(r['bytes'] for r in published),totalTriangles=sum(r['triangles'] for r in published),coveredWays=sorted({w for r in published for w in r['ways']}),sourceMapSha256=hashlib.sha256((ROOT/'public/tour-city.json').read_bytes()).hexdigest(),editable=str(EDIT.relative_to(ROOT)),limitation='Exterior visual reconstruction from OSM and referenced photographs. Unseen elevations and bays without matched imagery are inferred. This is not a measured city model.')
    (OUT/'manifest.json').write_text(json.dumps(output,ensure_ascii=False,indent=2))
    print('PUDONG_COMPLETE',len(published),len(output['coveredWays']),output['totalBytes'],output['totalTriangles'],flush=True)

builds=[('shanghai-tower',tower_shanghai),('jinmao',tower_jinmao),('financial-center',tower_swfc),('pearl',pearl),('apple-pudong',apple),('ifc-north',lambda:ifc(164968674,'ifc-north',249.9)),('ifc-south',lambda:ifc(423304682,'ifc-south',259.9))]
SPECIAL={165985305:foxconn,448242492:mirae,-129810530:one_lujiazui,164903482:golden,164972436:merchants,-129813020:huaneng,-129813030:lambda:world_finance(-129813030),-129813031:lambda:world_finance(-129813031),520990201:pingan,427786590:disney,957451688:lanhai,-129809231:bank_shanghai,164957811:bank_china,164971470:bocom,165168180:chen_mansion}
for key in PHOTOS:builds.append((key,lambda key=key:import_photo(key)))
handled={165792123,376075961,10691100,40778038,255624910,164968674,423304682,-129809230,*[w for p in PHOTOS.values() for w in p['ways']]}
for aux in [167061959,967281058]:
    if aux not in {b['wayId'] for b in CANDIDATES}:
        b=BUILDINGS[aux];CANDIDATES.append(dict(wayId=aux,name=b.get('name') or 'Mapped landmark podium '+str(aux),height=b['height'],heightSource=b['heightSource'],frontage={'classification':'landmark-associated-podium'},photoRef=None))
for b in CANDIDATES:
    if b['wayId'] not in handled:builds.append(('pudong-way-'+str(b['wayId']).replace('-','r'),SPECIAL.get(b['wayId'],lambda b=b:generic_build(b))))
for key,build in builds:
    if not ARGS.ids or key in ARGS.ids:
        print('PUDONG_BUILD',key,flush=True);build()
export_all()
