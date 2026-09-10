"""Build photo-referenced added Puxi loop frontage, with honest evidence gaps.

Run only through scripts/blender-local.sh automatic queue, with --threads 2.
Reference photographs are archived on the external drive, never shipped as
billboards or as unlicensed facade textures. Each accepted building has an
explicit builder and photo observations. Unknown buildings remain separately
labelled OSM massing; exporting such a shape is not photo-fidelity acceptance.
"""
import argparse, datetime, hashlib, json, math, pathlib, shutil, sys
import bpy
from mathutils import Vector

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from loop_frontage_helpers import Mesh, material, polygon_ccw, transformed_box, band, frame, wall_openings, shell, inset, roof_tiles, roof_plant, cornice, front_edge, lettering

OUT=ROOT/'public/streets/districts/loop-frontages'
ASSET=ROOT/'assets/streets/loop-frontages'
EDIT=ROOT/'assets/blender/streets/loop-frontages.blend'
INV=ROOT/'references/tourism/loop-frontage-models-inventory.json'
CONFIG=ROOT/'references/tourism/loop-frontage-models-config.json'
P=argparse.ArgumentParser();P.add_argument('--render',action='store_true');P.add_argument('--render-only',action='store_true');P.add_argument('--ids',nargs='*');P.add_argument('--allow-provisional',action='store_true');P.add_argument('--cycles-review',action='store_true');P.add_argument('--review-missing',action='store_true');P.add_argument('--pbr-ids',nargs='*',default=[])
ARGS=P.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
SPECS=json.loads(CONFIG.read_text())['buildings']
for directory in [OUT,ASSET,EDIT.parent]:directory.mkdir(parents=True,exist_ok=True)
records=[];roots=[]


def preserve(path):
    if not path.exists():return
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    target=ASSET/'preserved'/('sha-'+sha[:16])/path.name
    if not target.exists():target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)

if not ARGS.render_only:
    preserve(EDIT);preserve(pathlib.Path(str(EDIT)+'1'));preserve(OUT/'manifest.json')
    if ARGS.ids and EDIT.exists() and (OUT/'manifest.json').exists():
        bpy.ops.wm.open_mainfile(filepath=str(EDIT))
        records=[r for r in json.loads((OUT/'manifest.json').read_text())['models'] if r['id'] not in ARGS.ids]
        for spec in SPECS:
            if spec['id'] not in ARGS.ids:continue
            old=bpy.data.objects.get(spec['id'])
            if old:
                for obj in list(old.children_recursive)+[old]:bpy.data.objects.remove(obj,do_unlink=True)
        roots=[bpy.data.objects.get(r['id']) for r in records]
    else:
        bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
else:bpy.ops.wm.open_mainfile(filepath=str(EDIT))

WALL=material('loop-puxi-warm-limestone',(.66,.62,.54),.82)
WHITE=material('loop-puxi-fine-white-plaster',(.78,.77,.73),.83)
TRIM=material('loop-puxi-cut-limestone',(.72,.70,.64),.68)
GREY=material('loop-puxi-aged-grey-masonry',(.36,.37,.36),.91)
DARK=material('loop-puxi-charcoal-metal',(.047,.058,.062),.43,.38)
STEEL=material('loop-puxi-satin-aluminium',(.50,.55,.58),.32,.68)
BRONZE=material('loop-puxi-champagne-bronze',(.31,.25,.14),.37,.54)
RED=material('loop-puxi-yueyuan-red-frame',(.30,.073,.048),.78)
ROOF=material('loop-puxi-roof-waterproofing',(.115,.13,.14),.93)
TILE=material('loop-puxi-grey-glazed-tile',(.11,.17,.165),.45)
GLASS=[material('loop-puxi-glass-'+str(i),c,.21,.35) for i,c in enumerate([(.16,.225,.24),(.19,.25,.255),(.22,.29,.29),(.15,.20,.22)])]
PROVISIONAL=material('loop-puxi-unreferenced-massing',(.52,.51,.48),.97)


def geometry(spec):
    c=spec['center'];return polygon_ccw([(x-c[0],-(z-c[1])) for x,z in spec['footprint']])


def front(spec,poly):
    a,b=spec['frontageEdge'];c=spec['center'];return front_edge(poly,((a[0]+b[0])/2-c[0],-((a[1]+b[1])/2-c[1])))


def new(spec):
    root=bpy.data.objects.new(spec['id'],None);bpy.context.collection.objects.link(root)
    root['basis']=spec['confidence'];root['photoFidelityAccepted']=False;root['exteriorOnly']=True
    return root,Mesh(root)


def storeys(m, poly, zs, bays, wall=WALL, trim=TRIM, window_fraction=.55, front_index=None, front_centres=None):
    count=0
    for edge,(a,b) in enumerate(zip(poly,poly[1:]+poly[:1])):
        length=math.dist(a,b);n=bays[edge] if isinstance(bays,list) else max(1,round(length/bays))
        centres=front_centres if edge==front_index and front_centres else [(i+.5)/n for i in range(n)]
        for floor,(z0,z1) in enumerate(zip(zs,zs[1:])):
            height=z1-z0
            openings=[(x,length/max(1,len(centres))*window_fraction,z0+height*.23,z1-height*.17) for x in centres]
            if z0==0:openings=[(x,length/max(1,len(centres))*.74,.20,z1-.32) for x in centres]
            count+=wall_openings(m,a,b,z0,z1,openings,wall,trim,GLASS,DARK,depth=.23)
        band(m,[a,b],zs[-1],.22,.20,trim)
    return count


def neo(spec):
    root,m=new(spec);p=geometry(spec);fi=front(spec,p);count=0
    zs=[0,4,8.2,12.4,16.6]
    # Actual Renmin elevation: asymmetric pairs around a wider central wall.
    centres=[.055,.130,.205,.275,.340,.415,.480,.605,.680,.755,.825,.905,.968]
    count+=storeys(m,p,zs,4.0,WALL,STEEL,.73,fi,centres)
    # Two setback hotel storeys around the photographed courtyard.
    upper=inset(p,.93,.89)
    count+=storeys(m,upper,[16.6,20.1,23.6],2.65,WALL,STEEL,.71)
    for a,b,aa,bb in zip(p,p[1:]+p[:1],upper,upper[1:]+upper[:1]):
        m.face([(*a,16.6),(*b,16.6),(*bb,16.6),(*aa,16.6)],ROOF)
    # Open courtyard starts above the office floors, not a solid roof cap.
    inner=inset(p,.43,.42)
    m.face([(*v,12.4) for v in inner],ROOF)
    for a,b in zip(inner,inner[1:]+inner[:1]):
        wall_openings(m,b,a,12.4,23.6,[(f,2.0,13.3,15.9) for f in [.13,.32,.51,.70,.89]]+[(f,2.0,17.4,19.5) for f in [.13,.32,.51,.70,.89]]+[(f,2.0,20.8,23.0) for f in [.13,.32,.51,.70,.89]],WALL,STEEL,GLASS,DARK)
    # Roof strips surround courtyard. Roof silhouette follows the architect's
    # section and both street views: gentle concave rise and small upturned ends.
    for a,b,aa,bb in zip(upper,upper[1:]+upper[:1],inner,inner[1:]+inner[:1]):
        m.face([(*a,23.6),(*b,23.6),(*bb,23.6),(*aa,23.6)],ROOF)
    for ei in [fi,(fi+2)%4]:
        a,b=upper[ei],upper[(ei+1)%4];av,bv,t,n,L=frame(a,b)
        def pt(x,f):return av+t*x-n*(5.0*f)+Vector((0,0,23.65+1.7*f*f+.25*(abs(2*x/L-1)**8)*(1-f)))
        for k in range(16):m.face([pt(0,k/16),pt(L,k/16),pt(L,(k+1)/16),pt(0,(k+1)/16)],STEEL)
        for j in range(round(L/.55)+1):
            x=min(L,j*.55)
            for k in range(8):m.rod(pt(x,k/8),pt(x,(k+1)/8),.022,STEEL,6)
        # The top front face has narrow repeated vertical blades.
        for j in range(round(L/1.35)+1):
            cp=av+t*(j*L/max(1,round(L/1.35)))+n*.10
            transformed_box(m,cp+Vector((0,0,22.3)),t,n,(.13,.70,2.55),STEEL)
        for z in [20.1,23.6]:band(m,[a,b],z,.16,1.1,STEEL)
    # Continuous canopy projects up to the documented 4 m, clear height 3.4 m.
    for ei,(a,b) in enumerate(zip(p,p[1:]+p[:1])):
        av,bv,t,n,L=frame(a,b);proj=4.0 if ei==fi else 2.05
        transformed_box(m,(av+bv)/2+n*proj/2+Vector((0,0,3.62)),t,n,(L+.3,proj,.22),STEEL)
        for j in range(max(1,round(L/3.4))):
            cp=av+t*(j*L/max(1,round(L/3.4)))+n*.4
            m.rod(cp+Vector((0,0,.45)),cp+Vector((0,0,3.40)),.05,BRONZE,8)
            # Handles on the explicitly glazed shop entrances.
            m.rod(cp+n*.15+Vector((0,0,1.15)),cp+n*.15+Vector((0,0,1.8)),.027,BRONZE,8)
    # Service plant is visible in both bird's-eye photographs; exact models inferred.
    for x,y in [(-17,-10),(-17,0),(-17,10),(17,-8),(17,3),(17,13)]:roof_plant(m,(x,y),3.2,1.6,23.65,STEEL,DARK,2)
    a,b=p[fi],p[(fi+1)%len(p)];av,bv,t,n,L=frame(a,b)
    lettering(root,'外滩 NEO',av+t*(L*.16)+n*.35+Vector((0,0,17.65)),t,n,1.35,BRONZE)
    return root,m,{'independentWindowOpenings':count,'actualStoreys':6,'height':25.6}


def yueyuan(spec):
    root,m=new(spec);p=geometry(spec);fi=front(spec,p);count=0;zs=[0,4.4,8.3,12.2,16.1,20,23.9,27.8]
    for i,(a,b) in enumerate(zip(p,p[1:]+p[:1])):
        av,bv,t,n,L=frame(a,b);bays=6 if i==fi else max(1,round(L/3.85))
        for k,(z0,z1) in enumerate(zip(zs,zs[1:])):
            width=L/bays*.79
            ops=[((j+.5)/bays,width,z0+(.2 if k==0 else .85),z1-.55) for j in range(bays)]
            count+=wall_openings(m,a,b,z0,z1,ops,WHITE,RED,GLASS,DARK,depth=.24)
            band(m,[a,b],z0+.25,.20,.04,RED)
            band(m,[a,b],z1-.35,.30,.10,RED)
        for j in range(bays+1):transformed_box(m,av+t*(j*L/bays)+n*.04+Vector((0,0,16)),t,n,(.23,.12,23.6),RED)
        for z in [4.4,12.2,23.9,27.8]:roof_tiles(m,a,b,True,z,.52,.70,TILE,pitch=.29)
    top=inset(p,.78,.88);storeys(m,top,[27.8,30.0],3.8,WHITE,WHITE,.58)
    for a,b,aa,bb in zip(p,p[1:]+p[:1],top,top[1:]+top[:1]):
        m.face([(*a,27.8),(*b,27.8),(*bb,27.8),(*aa,27.8)],ROOF)
    m.face([(*v,30.0) for v in top],ROOF)
    for a,b in zip(top,top[1:]+top[:1]):roof_tiles(m,a,b,True,30,.7,1.4,TILE)
    # Large rounded vertical sign is visible on the eastern return by Renmin Road.
    a,b=p[fi],p[(fi+1)%len(p)];av,bv,t,n,L=frame(a,b)
    for z in [9,12.2,15.4,18.6]:
        cp=av+t*(L-.8)+n*.24+Vector((0,0,z))
        m.rod(cp,cp+n*.16,1.32,RED,48)
        m.rod(cp+n*.17,cp+n*.20,1.20,WHITE,48)
        m.rod(cp+n*.21,cp+n*.23,1.10,RED,48)
    for ch,z in zip('悦园商厦',[18.6,15.4,12.2,9]):
        cp=av+t*(L-.8)+n*.51+Vector((0,0,z))
        lettering(root,ch,cp,t,n,1.65,WHITE)
    for x,y in [(-7,-12),(5,-10),(5,8)]:roof_plant(m,(x,y),3,1.8,30,STEEL,DARK)
    return root,m,{'independentWindowOpenings':count,'height':30.8,'actualStoreys':8}


def shanghaitan(spec):
    root,m=new(spec);p=geometry(spec);fi=front(spec,p)
    count=storeys(m,p,[0,4.5,8.2,11.9,15.6,19.3,23],3.6,TRIM,WHITE,.42)
    for z in [4.5,11.9,23]:cornice(m,p,z,WHITE)
    # Wide curved ends and two different setbacks are visible across Renmin Road.
    middle=inset(p,.92,.88);count+=storeys(m,middle,[23,26.6,30.2],3.55,TRIM,WHITE,.48)
    top=inset(p,.79,.67);count+=storeys(m,top,[30.2,33.4],3.35,TRIM,WHITE,.45)
    for outer,inner,z in [(p,middle,23),(middle,top,30.2)]:
        for a,b,aa,bb in zip(outer,outer[1:]+outer[:1],inner,inner[1:]+inner[:1]):
            m.face([(*a,z),(*b,z),(*bb,z),(*aa,z)],ROOF)
    cornice(m,middle,30.2,WHITE);cornice(m,top,33.4,WHITE)
    m.face([(*v,33.4) for v in top],ROOF)
    # Recessed terrace bays are deliberately separated from top service housings.
    for a,b in zip(middle,middle[1:]+middle[:1]):
        av,bv,t,n,L=frame(a,b)
        for j in range(max(1,round(L/4))):
            cp=av+t*(j*L/max(1,round(L/4)))+n*.13
            transformed_box(m,cp+Vector((0,0,26.7)),t,n,(.34,.35,7.0),WHITE)
    for x,y in [(-25,0),(-12,0),(5,0),(18,0)]:roof_plant(m,(x,y),4.3,2.0,33.45,STEEL,DARK,3)
    return root,m,{'independentWindowOpenings':count,'height':34.7,'actualStoreys':9}


def park_corner(spec):
    root,m=new(spec);p=geometry(spec);fi=front(spec,p)
    count=storeys(m,p,[0,4.3,8.7,12.4],3.5,WHITE,TRIM,.45)
    for z in [4.3,8.7,12.4]:cornice(m,p,z,TRIM)
    a,b=p[fi],p[(fi+1)%len(p)];av,bv,t,n,L=frame(a,b)
    # The park-side historical corner has tall fluted pilasters and a dome.
    for j in range(5):
        cp=av+t*((j+.5)*L/5)+n*.24
        m.lathe(cp[:2],[(4.4,.28),(4.65,.28),(4.8,.20),(10.6,.18),(10.85,.30),(11.10,.31)],TRIM,24,flutes=10)
    centre=((av+bv)/2-n*8);cx,cy=centre.x,centre.y
    # Dark pitched roof across the long hall; one photographed pale corner lantern.
    slate=material('park-corner-observed-dark-pitched-slate',(.095,.092,.081),.88)
    roofdepth=max((Vector((*pt,0))-av).dot(-n) for pt in p)/2
    roof_tiles(m,a,b,True,12.5,3.1,roofdepth,slate,pitch=.33,curved=False)
    back_i=(fi+2)%4;roof_tiles(m,p[back_i],p[(back_i+1)%4],True,12.5,3.1,roofdepth,slate,pitch=.33,curved=False)
    for ei in [(fi+1)%4,(fi+3)%4]:
        ga,gb=Vector((*p[ei],12.5)),Vector((*p[(ei+1)%4],12.5));ridge=(ga+gb)/2+Vector((0,0,3.1))
        m.face([ga,gb,ridge],WHITE)
    turret=av+t*(L*.83)-n*2.7;tx,ty=turret.x,turret.y
    m.lathe((tx,ty),[(12.3,2.0),(12.7,2.2),(13.0,1.8),(15.1,1.8),(15.4,2.1),(15.6,2.0),(16.0,1.94),(16.6,1.55),(17.1,.9),(17.4,.2)],TRIM,48)
    for j in range(8):
        a=j*math.tau/8;xx,yy=tx+1.85*math.cos(a),ty+1.85*math.sin(a)
        m.rod((xx,yy,13),(xx,yy,15.15),.11,WHITE,8)
    m.rod((tx,ty,17.4),(tx,ty,19.0),.035,DARK,8)
    return root,m,{'independentWindowOpenings':count,'height':19,'actualStoreys':3}


def qianye(spec):
    root,m=new(spec);p=geometry(spec)
    # Three-court plan runs north-south. Gate placement at south short edge is
    # inferred from park/existing-map relationship, recorded in the manifest.
    fi=min(range(len(p)),key=lambda i:(p[i][1]+p[(i+1)%len(p)][1])/2)
    a,b=p[fi],p[(fi+1)%len(p)];av,bv,t,n,L=frame(a,b);inside=-n;depth=31.0
    grey_green=material('qianye-observed-green-grey-stone',(.30,.34,.27),.9)
    wood=material('qianye-black-wood-leaves',(.026,.029,.025),.93)
    def pt(x,y,z):return av+t*x+inside*y+Vector((0,0,z))
    # Exterior side walls; lower hall windows are inferred only where photos
    # cannot see through the bamboo. Roof courtyards remain actual voids.
    for ei,(aa,bb) in enumerate(zip(p,p[1:]+p[:1])):
        if ei!=fi:m.face([(*aa,0),(*bb,0),(*bb,3.4),(*aa,3.4)],WHITE)
    for y0,y1,rise in [(0,3.7,.85),(9.0,16.3,2.7),(23.0,31.0,3.0)]:
        q=[pt(.4,y0,0)[:2],pt(L-.4,y0,0)[:2],pt(L-.4,y1,0)[:2],pt(.4,y1,0)[:2]]
        q=polygon_ccw(q)
        if y0==0:
            # The gateway occupies this facade; keep no backing wall behind its three leaves.
            for qa,qb in zip(q,q[1:]+q[:1]):
                midq=(Vector(qa)+Vector(qb))/2
                if ((Vector((midq.x,midq.y,0))-av).dot(inside))>.15:m.face([(*qa,0),(*qb,0),(*qb,3.4),(*qa,3.4)],WHITE)
            m.face([(*v,3.4) for v in q],ROOF)
        else:shell(m,q,0,3.4,WHITE,ROOF)
        # Two opposing roof planes with clay-tile ribs, high capped ridge.
        aa=pt(.0,y0,0)[:2];bb=pt(L,y0,0)[:2]
        roof_tiles(m,aa,bb,True,3.45,rise,(y1-y0)/2+.3,TILE,pitch=.26)
        aa=pt(L,y1,0)[:2];bb=pt(0,y1,0)[:2]
        roof_tiles(m,aa,bb,True,3.45,rise,(y1-y0)/2+.3,TILE,pitch=.26)
        ridge_a=pt(0,(y0+y1)/2,3.45+rise);ridge_b=pt(L,(y0+y1)/2,3.45+rise)
        for z in [0,.20]:m.rod(ridge_a+Vector((0,0,z)),ridge_b+Vector((0,0,z)),.095,GREY,8)
        for x in [0,L]:
            for side in [-1,1]:m.rod(pt(x,(y0+y1)/2,3.65+rise),pt(x+side*.25,(y0+y1)/2,4.0+rise),.09,GREY,8)
    # Replace the source-observed front wall with actual three arched leaves.
    gate_y=-.25;gate_height=6.7
    portals=[(L*.23,1.22,2.7),(L*.50,1.60,3.2),(L*.77,1.22,2.7)]
    def door_top(x,c,r,spring):return spring+math.sqrt(max(0,r*r-(x-c)**2))
    # Fine vertical strips cut a semicircular head out of the white wall.
    cuts=sorted(set([0,L]+[c-r+2*r*i/40 for c,r,sp in portals for i in range(41)]))
    for x0,x1 in zip(cuts,cuts[1:]):
        middle=(x0+x1)/2;portal=next(((c,r,sp) for c,r,sp in portals if c-r<middle<c+r),None)
        if portal:
            c,r,sp=portal;lo0=door_top(x0,c,r,sp);lo1=door_top(x1,c,r,sp)
            m.face([pt(x0,gate_y,lo0),pt(x1,gate_y,lo1),pt(x1,gate_y,gate_height),pt(x0,gate_y,gate_height)],WHITE)
        else:m.face([pt(x0,gate_y,0),pt(x1,gate_y,0),pt(x1,gate_y,gate_height),pt(x0,gate_y,gate_height)],WHITE)
    for c,r,sp in portals:
        outline=[pt(c-r,gate_y+.12,.20),pt(c+r,gate_y+.12,.20)]+[pt(c+r*math.cos(i*math.pi/40),gate_y+.12,sp+r*math.sin(i*math.pi/40)) for i in range(41)]
        m.face(outline,wood)
        for side in [-1,1]:transformed_box(m,pt(c+side*(r+.13),gate_y,sp/2),t,n,(.26,.50,sp),grey_green)
        for j in range(40):
            aa=j*math.pi/40;bb=(j+1)*math.pi/40
            m.rod(pt(c+(r+.13)*math.cos(aa),gate_y,sp+(r+.13)*math.sin(aa)),pt(c+(r+.13)*math.cos(bb),gate_y,sp+(r+.13)*math.sin(bb)),.14,grey_green,8)
        m.rod(pt(c,gate_y-.04,.25),pt(c,gate_y-.04,sp+r-.1),.018,GREY,6)
        for side in [-1,1]:
            cp=pt(c+side*.26,gate_y-.14,1.72);m.rod(cp,cp+n*.10,.105,BRONZE,12)
        for step in range(3):transformed_box(m,pt(c,-.55-step*.25,.22-step*.055),t,n,(2*r+.3,1.2+step*.3,.22-step*.06),GREY)
    # Carved plaque and three raised tile gables; engraving motifs remain
    # simplified geometry rather than pretending every stone relief is traced.
    mid=pt(L/2,gate_y-.11,5.65)
    transformed_box(m,mid,t,n,(L*.49,.26,.93),grey_green)
    for z in [-.52,.52]:transformed_box(m,mid+Vector((0,0,z)),t,n,(L*.52,.33,.11),TRIM)
    lettering(root,'所公業錢南滬',mid+n*.17,t,n,.67,TRIM)
    for c,width,z in [(L*.23,L*.30,6.5),(L*.5,L*.40,7.55),(L*.77,L*.30,6.5)]:
        aa=pt(c-width/2,-.72,0)[:2];bb=pt(c+width/2,-.72,0)[:2];roof_tiles(m,aa,bb,True,z,.72,2.45,TILE,pitch=.23)
        # Upturned swallow-tail capped ridges are directly visible in aerial.
        for side in [-1,1]:
            base=pt(c+side*width*.38,1.6,z+.77);tip=pt(c+side*width*.56,1.6,z+1.52)
            for k in range(10):
                f0=k/10;f1=(k+1)/10
                def vv(f):return base+(tip-base)*f+Vector((0,0,-.30*math.sin(f*math.pi)))
                m.rod(vv(f0),vv(f1),.09,GREY,8)
    for x in [L*.39,L*.61]:
        cp=pt(x,-1.15,0);m.box(cp+Vector((0,0,.34)),(.62,.70,.68),GREY)
        m.rod(cp+Vector((0,0,1)),cp+t*.16+Vector((0,0,1)),.42,TRIM,32)
    return root,m,{'independentArchedDoorways':3,'independentWindowOpenings':0,'height':9.1,'actualStoreys':1,'actualCourtyards':2,'photoFeatureNotes':'Three black arched entrances, green-grey stone jambs, carved central plaque, three raised swallow-tail roof crests, sequence of tiled court halls. Lion figurines not replicated as generic substitutes.'}


def picc(spec):
    root,m=new(spec);p=geometry(spec);fi=front(spec,p);H=64.0;rows=15;panels=0
    # Actual 2020 street photographs: alternating opaque metal strips and blue
    # glazing, with a visibly raked glass entrance slot and suspended canopy.
    blue=material('picc-observed-blue-glazing',(.15,.30,.36),.19,.38)
    for ei,(a,b) in enumerate(zip(p,p[1:]+p[:1])):
        av,bv,t,n,L=frame(a,b);bays=max(2,round(L/3.65))
        for f in range(rows):
            z0=f*H/rows;z1=(f+1)*H/rows
            for j in range(bays):
                x0=j*L/bays;x1=(j+1)*L/bays
                # The offset opaque strip repeats every second curtain-wall bay.
                d=-.13;cp=av+t*((x0+x1)/2)+n*d+Vector((0,0,(z0+z1)/2))
                if ei==fi:
                    sw=min(9.0,L*.8)
                    left=lambda z:L/2-sw*(1-.38*z/(H+3))/2
                    right=lambda z:L-left(z)
                    for low,high in [(0,left),(right,L)]:
                        l0=max(x0+.035,low(z0) if callable(low) else low);l1=max(x0+.035,low(z1) if callable(low) else low)
                        r0=min(x1-.035,high(z0) if callable(high) else high);r1=min(x1-.035,high(z1) if callable(high) else high)
                        if min(r0-l0,r1-l1)>.005:
                            m.face([av+t*l0+n*d+Vector((0,0,z0+.035)),av+t*r0+n*d+Vector((0,0,z0+.035)),av+t*r1+n*d+Vector((0,0,z1-.035)),av+t*l1+n*d+Vector((0,0,z1-.035))],blue);panels+=1
                    if x0+.65<left(z0) or x0+.12>right(z0):
                        transformed_box(m,av+t*(x0+.38)+Vector((0,0,(z0+z1)/2)),t,n,(.52,.13,z1-z0),STEEL)
                        transformed_box(m,av+t*x0+Vector((0,0,(z0+z1)/2)),t,n,(.07,.16,z1-z0),DARK)
                else:
                    transformed_box(m,cp,t,n,(x1-x0-.07,.075,z1-z0-.07),blue);panels+=1
                    transformed_box(m,av+t*(x0+.38)+Vector((0,0,(z0+z1)/2)),t,n,(.52,.13,z1-z0),STEEL)
                    transformed_box(m,av+t*x0+Vector((0,0,(z0+z1)/2)),t,n,(.07,.16,z1-z0),DARK)
            band(m,[a,b],z1,.10,.12,DARK)
        # Open crown frames expose the double-height roof plant screen.
        for j in range(bays+1):
            cp=av+t*(j*L/bays);m.rod(cp+Vector((0,0,H)),cp+Vector((0,0,H+3.1)),.075,STEEL,8)
        band(m,[a,b],H+3.1,.10,.1,STEEL)
    m.face([(*v,H) for v in p],ROOF)
    a,b=p[fi],p[(fi+1)%len(p)];av,bv,t,n,L=frame(a,b);mid=(av+bv)/2
    # This recessed glazed opening is narrower at roof level; the two diagonal
    # stainless jambs are independent rods, not lines painted on a texture.
    w=min(9.0,L*.8)
    # The slot is physically recessed. Remove the normal curtain panels above,
    # and close its two deep reveals, instead of drawing rods on a flat wall.
    for f in range(18):
        z0=f*(H+2.9)/18;z1=(f+1)*(H+2.9)/18
        w0=w*(1-.38*z0/(H+3));w1=w*(1-.38*z1/(H+3))
        m.face([mid-t*w0/2-n*.85+Vector((0,0,z0)),mid+t*w0/2-n*.85+Vector((0,0,z0)),mid+t*w1/2-n*.85+Vector((0,0,z1)),mid-t*w1/2-n*.85+Vector((0,0,z1))],blue)
        for side in [-1,1]:
            aa=mid+t*side*w0/2+Vector((0,0,z0));bb=mid+t*side*w1/2+Vector((0,0,z1))
            m.face([aa,bb,bb-n*.85,aa-n*.85],STEEL)
    for side in [-1,1]:m.rod(mid+t*(side*w/2)+n*.22,mid+t*(side*w*.31)+n*.22+Vector((0,0,H+2.9)),.12,STEEL,12)
    for z in [i*3.55 for i in range(19)]:
        frac=z/(H+3);ww=w*(1-.38*frac);m.rod(mid-t*ww/2+n*.24+Vector((0,0,z)),mid+t*ww/2+n*.24+Vector((0,0,z)),.045,STEEL,8)
    for step in range(7):transformed_box(m,mid+n*(1.6-step*.18)+Vector((0,0,.10+step*.09)),t,n,(w+1.3,3.4-step*.38,.20+step*.18),GREY)
    canopy=mid+n*2.1+Vector((0,0,5.4));transformed_box(m,canopy,t,n,(w+1.3,4.2,.20),STEEL)
    transformed_box(m,canopy-Vector((0,0,.16)),t,n,(w+1.0,3.9,.08),blue)
    for j in [-.4,0,.4]:
        cp=mid+t*(w*j)+n*4.0+Vector((0,0,5.55));m.rod(cp,mid+t*(w*j)+n*.25+Vector((0,0,7.4)),.06,STEEL,10)
    for j in [-1,0,1]:transformed_box(m,mid+t*j*1.6+n*.34+Vector((0,0,2.5)),t,n,(1.5,.12,3.6),blue)
    for x in [-2.3,-.8,.8,2.3]:m.rod(mid+t*x+n*.43+Vector((0,0,.7)),mid+t*x+n*.43+Vector((0,0,4.3)),.055,STEEL,8)
    sign=material('picc-observed-red-lettering',(.58,.035,.04),.47,.12)
    lettering(root,'PICC 中国人民保险',mid+n*4.1+Vector((0,0,6.15)),t,n,.88,sign)
    for x,y in [(-20,0),(0,0),(22,0)]:roof_plant(m,(x,y),5.5,2.6,H,STEEL,DARK,3)
    return root,m,{'independentCurtainWallPanels':panels,'independentWindowOpenings':0,'height':68,'actualStoreys':15,'photoFeatureNotes':'Raked recessed entrance, 7-step entry, hanger canopy, actual Chinese lettering, metal/blue glazing alternation; dimensions estimated from OSM and photographs.'}


def fuyoumen(spec):
    root,m=new(spec);p=geometry(spec);fi=front(spec,p)
    count=storeys(m,p,[0,4.7,8.6,12.5,16.4,20.3,24.2],4.8,WHITE,TRIM,.39)
    for z in [4.7,8.6,24.2]:cornice(m,p,z,TRIM)
    m.face([(*v,24.2) for v in p],ROOF)
    # Four raised corner pavilions and their oversized flat cornices are visible
    # on the source, rather than a continuous extra floor across the block.
    for vertex in p:
        vx,vy=vertex;cx=vx*.86;cy=vy*.78
        q=[(cx-5.3,cy-4.1),(cx+5.3,cy-4.1),(cx+5.3,cy+4.1),(cx-5.3,cy+4.1)]
        count+=storeys(m,q,[24.2,28.5],4.5,WHITE,TRIM,.50);m.face([(*v,28.5) for v in q],ROOF);cornice(m,q,28.5,WHITE)
        for a,b in zip(q,q[1:]+q[:1]):
            av,bv,t,n,L=frame(a,b)
            for j in [.12,.88]:
                cp=av+t*(L*j)+n*.26;m.lathe(cp[:2],[(24,.28),(24.3,.35),(24.6,.22),(27.7,.22),(28,.37)],TRIM,20,flutes=8)
    a,b=p[fi],p[(fi+1)%len(p)];av,bv,t,n,L=frame(a,b);mid=av+t*(L*.68)
    sandstone=material('fuyoumen-entrance-salmon-stone',(.51,.33,.25),.82)
    # Angular deep public entrance portal, visible bronze Chinese shop identity.
    for side in [-1,1]:transformed_box(m,mid+t*(side*8.7)+n*.65+Vector((0,0,5.6)),t,n,(1.6,1.7,11.2),sandstone)
    transformed_box(m,mid+n*.68+Vector((0,0,10.65)),t,n,(19.0,1.75,1.1),sandstone)
    transformed_box(m,mid+n*1.6+Vector((0,0,11.55)),t,n,(19.4,3.0,.25),STEEL)
    lettering(root,'福 佑 门 商 厦',mid+n*1.62+Vector((0,0,9.3)),t,n,1.1,BRONZE)
    for j,ch in enumerate('福佑门小商品市场'):
        lettering(root,ch,av+t*(L*.29)+n*.30+Vector((0,0,26.0-j*1.42)),t,n,1.15,DARK)
    for x,y in [(-30,0),(-15,0),(15,0),(30,0)]:roof_plant(m,(x,y),4.0,2.0,24.25,STEEL,DARK,2)
    return root,m,{'independentWindowOpenings':count,'height':29.0,'actualStoreys':6,'photoFeatureNotes':'Six-storey white market block, four raised corner pavilions, square windows, sandstone angular portal, vertical Chinese market sign.'}


def ji_hotel(spec):
    root,m=new(spec);p=geometry(spec);fi=front(spec,p)
    count=storeys(m,p,[0,5.0,9.0,13.0,17.0],5.5,WALL,TRIM,.34)
    for z in [5,17]:cornice(m,p,z,TRIM)
    m.face([(*v,17.0) for v in p],ROOF)
    # The tower is a separate OSM component directly above the curved podium.
    c=spec['center'];q=polygon_ccw([(x-c[0],-(z-c[1])) for x,z in spec['upperFootprint']])
    green=material('ji-hotel-observed-green-glass',(.14,.27,.255),.21,.27)
    for ei,(a,b) in enumerate(zip(q,q[1:]+q[:1])):
        av,bv,t,n,L=frame(a,b);bays=max(1,round(L/3.2))
        for f in range(26):
            z0=17+f*3.7;z1=z0+3.7
            count+=wall_openings(m,a,b,z0,z1,[((j+.5)/bays,L/bays*.80,z0+.50,z1-.48) for j in range(bays)],WHITE,WHITE,green,DARK,depth=.15,sill=False,crossbar=.17)
        band(m,[a,b],113.2,.22,.2,WHITE)
    m.face([(*v,113.2) for v in q],ROOF)
    crown=inset(q,.69,.75);storeys(m,crown,[113.2,117.3],4,WHITE,TRIM,.65);m.face([(*v,117.3) for v in crown],ROOF)
    # Curved high metal crown is visible in 2013, while the 2024 street image
    # independently confirms the tower's white/green facade and rounded podium.
    cx=sum(x for x,y in crown)/len(crown);cy=sum(y for x,y in crown)/len(crown)
    for x,y in [(cx-5,cy),(cx+5,cy)]:roof_plant(m,(x,y),3.8,2.2,117.3,STEEL,DARK)
    a,b=p[fi],p[(fi+1)%len(p)];av,bv,t,n,L=frame(a,b);mid=(av+bv)/2
    transformed_box(m,mid+n*.25+Vector((0,0,3)),t,n,(L*.92,.36,4.8),DARK)
    lettering(root,'全 季 酒 店',mid+n*.46+Vector((0,0,4.25)),t,n,1.0,WHITE)
    lettering(root,'J I H O T E L',mid+n*.47+Vector((0,0,2.5)),t,n,.58,WHITE)
    return root,m,{'independentWindowOpenings':count,'height':119,'actualStoreys':31,'componentWays':[369238001,447021394],'heightSource':'OSM upper component119m, level subdivision inferred from photographs'}


def henan_heritage(spec):
    root,m=new(spec);p=geometry(spec)
    # Narrow 100 m long three-storey block: the 2012 facade and 2024 roofline
    # photographs are geolocated at exactly the same Renmin/Henan intersection.
    fi=max(range(len(p)),key=lambda i:math.dist(p[i],p[(i+1)%len(p)]))
    a,b=p[fi],p[(fi+1)%len(p)];av,bv,t,n,L=frame(a,b);count=0
    cream=material('henan-heritage-cream-render',(.70,.64,.49),.92)
    clay=material('henan-heritage-red-brown-roof',(.24,.10,.063),.85)
    count=storeys(m,p,[0,4.2,8.3,12.1],4.4,cream,TRIM,.56)
    for z in [4.2,8.3,12.1]:cornice(m,p,z,TRIM)
    # Continuous narrow balconies and separate bulb-shaped balusters.
    for ei,(ea,eb) in enumerate(zip(p,p[1:]+p[:1])):
        aa,bb,tt,nn,ll=frame(ea,eb)
        if ll<40:continue
        for z in [4.25,8.35,12.15]:
            transformed_box(m,(aa+bb)/2+nn*.5+Vector((0,0,z)),tt,nn,(ll,.95,.18),TRIM)
            for j in range(round(ll/.52)):
                pp=aa+tt*(.25+j*.52)+nn*.85;m.lathe(pp[:2],[(z+.1,.07),(z+.25,.10),(z+.48,.15),(z+.72,.09),(z+.95,.075)],TRIM,8)
            band(m,[ea,eb],z+1.02,.12,1.0,TRIM)
    # Gabled terracotta attic roof with individual dormer boxes and pediments.
    inner=-n;depth=11.0
    def pt(u,v,z):return av+t*u+inner*v+Vector((0,0,z))
    m.face([pt(0,0,12.7),pt(L,0,12.7),pt(L,depth/2,15.2),pt(0,depth/2,15.2)],clay)
    m.face([pt(0,depth/2,15.2),pt(L,depth/2,15.2),pt(L,depth,12.7),pt(0,depth,12.7)],clay)
    m.face([(*v,12.65) for v in p],clay)
    band(m,p,12.4,.55,.04,cream)
    for u in [0,L]:m.face([pt(u,0,12.7),pt(u,depth,12.7),pt(u,depth/2,15.2)],cream)
    for j in range(round(L/.32)+1):
        u=min(L,j*.32);m.rod(pt(u,0,12.74),pt(u,depth/2,15.24),.035,clay,6);m.rod(pt(u,depth/2,15.24),pt(u,depth,12.74),.035,clay,6)
    dormers=19
    for j in range(dormers):
        pos=av+t*((j+.5)*L/dormers)+inner*1.1
        transformed_box(m,pos+Vector((0,0,13.5)),t,n,(2.2,2.2,1.6),cream)
        transformed_box(m,pos+n*1.15+Vector((0,0,13.65)),t,n,(1.2,.12,1.10),DARK)
        for side in [-1,1]:
            m.face([pos+t*(side*1.55)+n*1.5+Vector((0,0,14.2)),pos+n*1.5+Vector((0,0,15.15)),pos-n*1.5+Vector((0,0,15.15)),pos+t*(side*1.55)-n*1.5+Vector((0,0,14.2))],clay)
        m.rod(pos-t*1.55+n*1.55+Vector((0,0,14.2)),pos+n*1.55+Vector((0,0,15.15)),.10,TRIM,8);m.rod(pos+n*1.55+Vector((0,0,15.15)),pos+t*1.55+n*1.55+Vector((0,0,14.2)),.10,TRIM,8)
    # A high central arched gateway is the photographed local identifying motif.
    mid=av+t*(L*.53)+n*.35
    for side in [-1,1]:transformed_box(m,mid+t*(side*2.4)+Vector((0,0,5.6)),t,n,(.72,.5,11.2),TRIM)
    for k in range(32):
        a0=k*math.pi/32;a1=(k+1)*math.pi/32
        p0=mid+t*(2.4*math.cos(a0))+Vector((0,0,10.7+2.4*math.sin(a0)));p1=mid+t*(2.4*math.cos(a1))+Vector((0,0,10.7+2.4*math.sin(a1)));m.rod(p0,p1,.30,TRIM,8)
    return root,m,{'independentWindowOpenings':count,'height':15.6,'actualStoreys':3,'actualAtticDormers':dormers,'restorationEvidence':'Facade scaffold visible in June2024. Permanent building modeled using2012 facade plus2024 roof silhouette; 2026 scaffold state unknown, scaffold omitted.'}


def fuyou_market(spec):
    root,m=new(spec);p=geometry(spec);count=0
    # The photographed wholesale market has a deep three-storey commercial
    # base with slot windows, then six more regular upper rows.
    ivory=material('fuyou-market-ivory-cladding',(.70,.70,.65),.82)
    oxblood=material('fuyou-market-sign-red',(.32,.05,.048),.79)
    for ei,(a,b) in enumerate(zip(p,p[1:]+p[:1])):
        av,bv,t,n,L=frame(a,b);bays=max(3,round(L/4.6))
        count+=wall_openings(m,a,b,0,4.0,[((j+.5)/bays,L/bays*.89,.12,3.65) for j in range(bays)],ivory,TRIM,GLASS,DARK)
        count+=wall_openings(m,a,b,4.0,11.3,[((j+.5)/bays,L/bays*.70,4.7,8.65) for j in range(bays)],ivory,TRIM,GLASS,DARK)
        # Continuous horizontal clerestory slots, separated by structural piers.
        count+=wall_openings(m,a,b,11.3,13.9,[((j+.5)/bays,L/bays*.94,11.75,12.70) for j in range(bays)],ivory,TRIM,GLASS,DARK,depth=.38)
        for floor in range(5):
            z=13.9+floor*3.25
            count+=wall_openings(m,a,b,z,z+3.25,[((j+.5)/bays,L/bays*.45,z+.85,z+2.5) for j in range(bays)],ivory,TRIM,GLASS,DARK,depth=.22)
        for z in [4.0,10.8,13.9,30.15]:band(m,[a,b],z,.35,1.0,TRIM)
        for j in range(bays+1):
            cp=av+t*j*L/bays
            # Paired stepped brackets visible between lower advertisement bays.
            for side in [-1,1]:
                for z,width,depth,height in [(8.1,.28,.42,1.6),(9.25,.40,.68,.65),(9.8,.44,.88,.50)]:
                    transformed_box(m,cp+t*side*.30+n*depth/2+Vector((0,0,z)),t,n,(width,depth,height),TRIM)
            if 0<j<bays:
                for z in [24.0,27.25]:
                    transformed_box(m,cp+n*.30+Vector((0,0,z)),t,n,(.38,.65,2.1),TRIM)
        # Small unprinted signboards preserve the source's shop/billboard rhythm.
        for j in range(bays):
            cp=av+t*(j+.5)*L/bays+n*.16
            transformed_box(m,cp+Vector((0,0,3.6)),t,n,(L/bays-.25,.25,.62),DARK)
            if L>50 and j%2==0:transformed_box(m,cp+n*.65+Vector((0,0,6.9)),t,n,(L/bays*.66,.16,3.45),oxblood)
    m.face([(*v,30.15) for v in p],ROOF)
    # Southwest corner has the slender white identity pylon and fan-shaped crown.
    fi=min(range(len(p)),key=lambda i:(p[i][0]+p[(i+1)%len(p)][0])/2)
    a,b=p[fi],p[(fi+1)%len(p)];av,bv,t,n,L=frame(a,b);cp=av+t*(L*.08)+n*.8
    transformed_box(m,cp+Vector((0,0,17.0)),t,n,(2.4,.9,18.0),WHITE)
    for j,ch in enumerate('上海福佑小商品市场'):
        lettering(root,ch,cp+n*.49+Vector((0,0,24.6-j*1.3)),t,n,.79,oxblood)
    for radius,z0 in [(2.0,27.0),(2.6,28.5),(3.2,30.0)]:
        for j in range(28):
            aa=j*math.pi/28;bb=(j+1)*math.pi/28
            m.rod(cp+t*(radius*math.cos(aa))+Vector((0,0,z0+radius*.5*math.sin(aa))),cp+t*(radius*math.cos(bb))+Vector((0,0,z0+radius*.5*math.sin(bb))),.055,BRONZE,8)
    for x,y in [(-9,-20),(9,-20),(-9,16),(9,16)]:roof_plant(m,(x,y),3.8,2.0,30.2,STEEL,DARK)
    return root,m,{'independentWindowOpenings':count,'height':31.5,'actualStoreys':9,'photoFeatureNotes':'Deep lower shop bays, narrow slot windows, paired projecting brackets, ivory square cladding, market pylon with metal fan crown. Current merchant graphics not verified.'}


def zijin(spec):
    root,m=new(spec);p=geometry(spec);count=0
    timber=material('zijin-observed-red-brown-timber',(.215,.075,.06),.80)
    gold=material('zijin-observed-gold-lift-frame',(.54,.36,.14),.35,.48)
    # Main older entrance faces Fuyou Road to the south. The east side is
    # independently visible in the architect's 2021 narrow-street photograph.
    fi=min(range(len(p)),key=lambda i:(p[i][1]+p[(i+1)%len(p)][1])/2)
    east=max(range(len(p)),key=lambda i:(p[i][0]+p[(i+1)%len(p)][0])/2)
    for ei,(a,b) in enumerate(zip(p,p[1:]+p[:1])):
        av,bv,t,n,L=frame(a,b);bays=max(3,round(L/5.3));zs=[0,4.4,9.0,13.6,18.2,22.8]
        if ei==east:zs=[0,4.4,9.0,13.6]
        for floor,(z0,z1) in enumerate(zip(zs,zs[1:])):
            count+=wall_openings(m,a,b,z0,z1,[((j+.5)/bays,L/bays*.73,z0+.60,z1-.65) for j in range(bays)],WHITE,timber,GLASS,DARK,depth=.30)
            band(m,[a,b],z1-.20,.32,.18,timber)
            for j in range(bays+1):transformed_box(m,av+t*j*L/bays+Vector((0,0,(z0+z1)/2)),t,n,(.25,.32,z1-z0),timber)
            if floor>0:
                # Geometric timber screens: visible independently of glazing.
                for j in range(bays):
                    cp=av+t*(j+.5)*L/bays+n*.15
                    for k in range(6):
                        xx=(k-2.5)*L/bays*.10
                        transformed_box(m,cp+t*xx+Vector((0,0,(z0+z1)/2)),t,n,(.065,.09,z1-z0-1.45),timber)
                    for k in range(5):
                        transformed_box(m,cp+Vector((0,0,z0+.9+k*(z1-z0-1.8)/4)),t,n,(L/bays*.65,.09,.07),timber)
            if z1 in [4.4,9.0,13.6,22.8]:roof_tiles(m,a,b,False,z1,.7,1.75,TILE,pitch=.33)
        if ei==east:
            # Source obscures the higher core: set it back from the three-storey
            # timber frontage and explicitly mark that hidden return inferred.
            ea=(av-n*4.0)[:2];eb=(bv-n*4.0)[:2]
            count+=wall_openings(m,ea,eb,13.6,22.8,[((j+.5)/bays,L/bays*.5,16.0,20.5) for j in range(bays)],WHITE,timber,GLASS,DARK)
            m.face([av+Vector((0,0,13.6)),bv+Vector((0,0,13.6)),bv-n*4+Vector((0,0,13.6)),av-n*4+Vector((0,0,13.6))],ROOF)
            for f in [.25,.75]:
                cp=av+t*(L*f)+n*.25+Vector((0,0,11.25));m.rod(cp,cp+n*.12,.78,timber,32)
                for k in range(8):
                    aa=k*math.tau/8;bb=aa+math.pi/3
                    m.rod(cp+t*.7*math.cos(aa)+Vector((0,0,.7*math.sin(aa))),cp+t*.7*math.cos(bb)+Vector((0,0,.7*math.sin(bb))),.05,TRIM,6)
            for j in range(bays):
                cp=av+t*(j+.5)*L/bays+n*.5
                transformed_box(m,cp+Vector((0,0,3.6)),t,n,(L/bays-.3,.18,.7),timber)
                for k in range(11):transformed_box(m,cp+Vector((0,0,.25+k*.25)),t,n,(L/bays*.75,.12,.05),STEEL)
    m.face([(*v,22.8) for v in p],ROOF)
    a,b=p[fi],p[(fi+1)%len(p)];av,bv,t,n,L=frame(a,b);mid=(av+bv)/2
    # The photographed front portal projects between two external glass lifts.
    transformed_box(m,mid+n*.25+Vector((0,0,17.5)),t,n,(17.0,.50,25.0),timber)
    for side in [-1,1]:transformed_box(m,mid+t*side*5.8+n*.25+Vector((0,0,2.5)),t,n,(5.4,.50,5.0),timber)
    # Separate recessed glazed entrance below the main poster/sign bay.
    transformed_box(m,mid+n*.12+Vector((0,0,2.15)),t,n,(5.6,.12,4.3),GLASS[1])
    for x in [-2.8,-.93,.93,2.8]:
        m.rod(mid+t*x+n*.21,mid+t*x+n*.21+Vector((0,0,4.3)),.055,gold,8)
    for x in [-1.2,-.65,.65,1.2]:
        m.rod(mid+t*x+n*.34+Vector((0,0,1.25)),mid+t*x+n*.34+Vector((0,0,2.05)),.032,gold,8)
    for side in [-1,1]:
        cp=mid+t*side*8.5+n*1.0
        m.rod(cp,cp+Vector((0,0,31.0)),.42,timber,16)
        lift=mid+t*side*6.3+n*2.0
        # Six-sided glazed car enclosure, individual floor rings and mullions.
        outline=[(lift+t*(1.55*math.cos(k*math.tau/6))+n*(1.0*math.sin(k*math.tau/6))) for k in range(6)]
        for pa,pb in zip(outline,outline[1:]+outline[:1]):
            for f in range(7):
                z0=.2+f*4.0;z1=z0+4
                m.face([pa+Vector((0,0,z0)),pb+Vector((0,0,z0)),pb+Vector((0,0,z1)),pa+Vector((0,0,z1))],GLASS[2])
                m.rod(pa+Vector((0,0,z0)),pb+Vector((0,0,z0)),.055,gold,8)
            m.rod(pa+Vector((0,0,.2)),pa+Vector((0,0,28.4)),.085,gold,10)
        for z,width in [(28.5,3.7),(29.0,3.2),(29.45,2.5)]:transformed_box(m,lift+Vector((0,0,z)),t,n,(width,2.6,.45),TRIM)
    transformed_box(m,mid+n*.70+Vector((0,0,22.7)),t,n,(4.0,.30,7.5),RED)
    for z in [18.8,26.6]:transformed_box(m,mid+n*.9+Vector((0,0,z)),t,n,(4.3,.12,.16),gold)
    for side in [-1,1]:transformed_box(m,mid+t*side*2.13+n*.90+Vector((0,0,22.7)),t,n,(.16,.12,7.8),gold)
    for ch,z in zip('紫锦城',[25.1,22.7,20.3]):lettering(root,ch,mid+n*.92+Vector((0,0,z)),t,n,1.6,gold)
    for z in [4.3,17.2,29.4]:
        aa=mid-t*8.2+n*.95;bb=mid+t*8.2+n*.95;roof_tiles(m,aa[:2],bb[:2],False,z,.9,2.1,TILE,pitch=.30)
    lettering(root,'紫锦城珠宝交易中心',mid+n*.92+Vector((0,0,5.15)),t,n,.80,TRIM)
    return root,m,{'independentWindowOpenings':count,'height':31.5,'actualStoreys':'five main floors; older projecting entrance rises above, east side three floors','photoFeatureNotes':'Twin gold-frame polygonal glazed lifts, vertical red-gold title, red-brown structure, white infill, layered tiled eaves and east timber screens. Hidden roof composition is inferred.'}


def clip_axis(poly, axis, lo, hi):
    """Clip mapped outline to a photo-observed block without changing its perimeter."""
    for cut,sign in [(lo,1),(hi,-1)]:
        output=[]
        for a,b in zip(poly,poly[1:]+poly[:1]):
            da=(a[0]*axis[0]+a[1]*axis[1]-cut)*sign;db=(b[0]*axis[0]+b[1]*axis[1]-cut)*sign
            if da>=-1e-6:output.append(a)
            if (da<0)!=(db<0):
                f=da/(da-db);output.append((a[0]+f*(b[0]-a[0]),a[1]+f*(b[1]-a[1])))
        poly=output
        if len(poly)<3:break
    return polygon_ccw(poly)


def bfc_frame_block(m, p, height, granite, bronze, glass, base=0):
    """Photographed BFC large stone frame, tapered piers and bronze glazing."""
    panels=0
    for a,b in zip(p,p[1:]+p[:1]):
        av,bv,t,n,L=frame(a,b)
        if L<.12:continue
        bays=max(1,round(L/1.48));floor=3.7;floors=max(2,round((height-base)/floor))
        for f in range(floors):
            z0=base+(height-base)*f/floors;z1=base+(height-base)*(f+1)/floors
            for j in range(bays):
                x0=L*j/bays;x1=L*(j+1)/bays
                m.face([av+t*x0-n*.30+Vector((0,0,z0)),av+t*x1-n*.30+Vector((0,0,z0)),av+t*x1-n*.30+Vector((0,0,z1)),av+t*x0-n*.30+Vector((0,0,z1))],glass[(j+f)%len(glass)])
                panels+=1
            # Narrow shadowed spandrel bands, independent of every glass pane.
            transformed_box(m,(av+bv)/2-n*.24+Vector((0,0,z1-.22)),t,n,(L,.11,.30),bronze)
        for j in range(bays+1):
            cp=av+t*(j*L/bays)-n*.18
            transformed_box(m,cp+Vector((0,0,(height+base)/2)),t,n,(.045,.22,height-base),bronze)
        # Continuous outer stone picture frame. Its top opening and piers are
        # readable from both the architect's elevation and the current hotel photo.
        for x in [0,L]:
            cp=av+t*x
            lower=.68;upper=.32
            for side in [-1,1]:
                m.face([cp+t*(side*lower)+n*.12+Vector((0,0,base)),cp+t*(side*upper)+n*.12+Vector((0,0,height)),cp+t*(side*upper)-n*.40+Vector((0,0,height)),cp+t*(side*lower)-n*.40+Vector((0,0,base))],granite)
            m.face([cp-t*lower+n*.12+Vector((0,0,base)),cp+t*lower+n*.12+Vector((0,0,base)),cp+t*upper+n*.12+Vector((0,0,height)),cp-t*upper+n*.12+Vector((0,0,height))],granite)
        for z,th in [(base+.60,1.2),(height-.45,.90)]:
            transformed_box(m,(av+bv)/2+Vector((0,0,z)),t,n,(L+.45,.82,th),granite)
        if height>25:
            transformed_box(m,(av+bv)/2+Vector((0,0,12.4)),t,n,(L,.78,1.1),granite)
            # Paired champagne fins bridge the tall ground/first-floor glazing.
            for j in range(1,max(2,round(L/5))):
                x=j*L/max(2,round(L/5));cp=av+t*x+n*.12
                for dx in [-.14,.14]:transformed_box(m,cp+t*dx+Vector((0,0,6.4)),t,n,(.09,.30,11.0),bronze)
    m.face([(*v,height) for v in p],ROOF)
    return panels


def stregis(spec):
    root,m=new(spec);p=geometry(spec)
    u=Vector((2**-.5,-2**-.5,0));v=Vector((2**-.5,2**-.5,0))
    stone=material('stregis-hand-worked-granite',(.53,.51,.46),.90)
    bronze=material('stregis-bronze-framing',(.33,.26,.16),.37,.57)
    glazing=[material('stregis-reflective-neutral-'+str(i),c,.16,.42) for i,c in enumerate([(.12,.15,.17),(.16,.18,.18),(.18,.20,.20)])]
    # Mapped footprint + architect's dimensioned north elevation: the rear
    # eighty-metre tower and lower river volume are separate, offset blocks.
    rear=clip_axis(p,v,-30,-3);frontp=clip_axis(p,v,-3,33)
    count=bfc_frame_block(m,rear,79.0,stone,bronze,glazing)
    count+=bfc_frame_block(m,frontp,54.3,stone,bronze,glazing)
    crown=clip_axis(inset(rear,.60,.63),u,-20,12)
    count+=bfc_frame_block(m,crown,85,bronze,bronze,glazing,79.0)
    # Recessed roof plant crown is open at its upper granite corner, as shown
    # in the 2024 ST REGIS photograph; the roof is not a generic solid cap.
    for z in [79.8,81.2,82.6]:
        for a,b in zip(crown,crown[1:]+crown[:1]):band(m,[a,b],z,.16,.10,bronze)
    # Main entrance is on the northwest/Longtan return, not the river side.
    entrance=-u*29+v*7
    transformed_box(m,entrance-u*3.15+Vector((0,0,7.0)),v,-u,(21,6.7,.55),bronze)
    for j in range(11):
        cp=entrance+v*((j-5)*1.8)-u*3.1
        transformed_box(m,cp+Vector((0,0,6.67)),v,-u,(.09,6.4,.16),stone)
    for side in [-1,1]:
        cp=entrance+v*side*8.6-u*4.2
        transformed_box(m,cp+Vector((0,0,3.4)),v,-u,(.42,.48,6.8),bronze)
    for dx in [-4.5,0,4.5]:
        cp=entrance+v*dx-u*.35
        for k in range(16):
            th0=k*math.tau/16;th1=(k+1)*math.tau/16
            a=cp+u*1.1*math.cos(th0)+v*1.1*math.sin(th0);b=cp+u*1.1*math.cos(th1)+v*1.1*math.sin(th1)
            m.face([a+Vector((0,0,.3)),b+Vector((0,0,.3)),b+Vector((0,0,4.7)),a+Vector((0,0,4.7))],glazing[1])
            m.rod(a+Vector((0,0,.3)),a+Vector((0,0,4.7)),.035,bronze,6)
    lettering(root,'ST REGIS',v*31.75+u*2+Vector((0,0,52.5)),u,v,1.6,WHITE)
    lettering(root,'THE ST. REGIS',entrance-u*6.55+Vector((0,0,7.48)),v,-u,.74,WHITE)
    for x,y in [(-8,-15),(4,-15)]:roof_plant(m,(x,y),4,2,79.1,bronze,DARK)
    return root,m,{'independentCurtainWallPanels':count,'height':85,'actualStoreys':'21 occupied levels; roof crown','photoFeatureNotes':'Separate river and rear volumes, tapered granite frames, bronze paired lobby fins, recessed panes, northwest porte-cochere, revolving glazed doors, current ST REGIS sign. Elevation height scaled from architect drawing, hidden rear subdivision inferred.'}


def bfc_river_row(spec):
    root,m=new(spec);p=geometry(spec);u=Vector((2**-.5,-2**-.5,0));v=Vector((2**-.5,2**-.5,0))
    stone=material('bfc-river-row-granite',(.53,.50,.44),.91)
    bronze=material('bfc-river-row-bronze',(.32,.23,.13),.37,.57)
    glass=[material('bfc-river-row-glass-'+str(i),c,.17,.38) for i,c in enumerate([(.13,.17,.18),(.18,.21,.20),(.16,.20,.20)])]
    count=0;cuts=[-42,-21,-2,20,42];heights=[44.5,48.0,51.0,43.5]
    # Four attached but differently articulated volumes are explicit in the
    # architect's North Plot plan and 2017 drone photograph. Current OSM N3
    # label conflicts with architect N3 hotel terminology, so no tenant sign.
    for i,(lo,hi,h) in enumerate(zip(cuts,cuts[1:],heights)):
        q=clip_axis(p,u,lo,hi);count+=bfc_frame_block(m,q,h,stone,bronze,glass)
        cx=sum(x for x,y in q)/len(q);cy=sum(y for x,y in q)/len(q)
        roof_plant(m,(cx,cy),3.6,2,h+.05,bronze,DARK)
        for side in [-1,1]:
            cp=u*((lo+hi)/2)+v*side*9.5
            transformed_box(m,cp+Vector((0,0,4.8)),u,v,(hi-lo-1.6,1.5,.26),bronze)
            for j in [-1,0,1]:
                door=cp+u*j*3.0
                transformed_box(m,door+Vector((0,0,2.3)),u,v,(2.6,.10,3.8),glass[i%3])
                m.rod(door+v*.14+Vector((0,0,1.25)),door+v*.14+Vector((0,0,2.0)),.025,bronze,8)
    return root,m,{'independentCurtainWallPanels':count,'height':52.2,'actualStoreys':'up to 15; subdivided from OSM and architect exterior photos','photoFeatureNotes':'Four contiguous river retail-office volumes, nonuniform roof levels, deep granite rectangle borders and tall double-height bronze storefront frames. OSM N3 building number remains identity ambiguity, deliberately not labelled hotel.'}


def riviera(spec):
    root,m=new(spec);p=geometry(spec);u=Vector((2**-.5,-2**-.5,0));v=Vector((2**-.5,2**-.5,0));count=0
    stone=material('riviera-pale-square-stone',(.67,.66,.61),.90)
    metal=material('riviera-black-aluminium',(.075,.095,.105),.42,.52)
    for a,b in zip(p,p[1:]+p[:1]):
        av,bv,t,n,L=frame(a,b)
        if L<1:continue
        is_river=n.dot(v)>.7 and L>45;is_street=n.dot(v)<-.7 and L>45
        openings=[]
        for z0,z1 in [(0,4.2),(4.2,9.3)]:
            if L>45:
                # The observed facade has two broad ribbon windows separated
                # by an off-centre full-height narrow glazed stair slot.
                ops=([(.17,L*.30,.28,3.56),(.46,L*.24,.28,3.56),(.78,L*.32,.28,3.56)] if z0==0 else [(.17,L*.30,5.18,7.75),(.425,L*.065,4.28,7.82),(.70,L*.32,5.18,7.75),(.96,L*.06,5.18,7.75)])
            else:
                ops=[(.50,L*.65,z0+.6,z1-.9)] if L>7 else []
            openings+=ops
            count+=wall_openings(m,a,b,z0,z1,ops,stone,stone,GLASS,metal,depth=.38,sill=False,crossbar=.30)
            for f,w,lo,hi in ops:
                for j in range(1,max(2,round(w/2.2))):
                    cp=av+t*(L*f-w/2+j*w/max(2,round(w/2.2)))-n*.25
                    transformed_box(m,cp+Vector((0,0,(lo+hi)/2)),t,n,(.065,.13,hi-lo),metal)
        # Source's square cladding joints are real narrow inset reveals.
        for z in [.8,1.8,2.8,3.8,4.8,5.8,6.8,7.8,8.8]:
            cuts=sorted({0,L}|{max(0,min(L,L*f+side*w/2)) for f,w,lo,hi in openings if lo<z<hi for side in [-1,1]})
            for x0,x1 in zip(cuts,cuts[1:]):
                x=(x0+x1)/2
                if not any(abs(x-L*f)<w/2 and lo<z<hi for f,w,lo,hi in openings):transformed_box(m,av+t*x+n*.008+Vector((0,0,z)),t,n,(x1-x0,.014,.015),GREY)
        for j in range(1,round(L/1.6)):
            x=j*L/round(L/1.6);cuts=sorted({0,9.3}|{z for f,w,lo,hi in openings if abs(x-L*f)<w/2 for z in [lo,hi]})
            for lo,hi in zip(cuts,cuts[1:]):
                z=(lo+hi)/2
                if not any(abs(x-L*f)<w/2 and z0<z<z1 for f,w,z0,z1 in openings):transformed_box(m,av+t*x+n*.008+Vector((0,0,z)),t,n,(.012,.014,hi-lo),GREY)
        for z in [4.18,9.35]:transformed_box(m,(av+bv)/2+n*.22+Vector((0,0,z)),t,n,(L+.25,.65,.24),stone)
        if is_river:
            lettering(root,'RIVIERA 松鹤楼',av+t*(L*.69)+n*.20+Vector((0,0,8.45)),t,n,1.32,metal)
            # Offset recessed entrance with three steps and separate access ramp.
            entry=av+t*(L*.44)
            for k in range(4):transformed_box(m,entry+n*(1.35-.22*k)+Vector((0,0,.09+k*.11)),t,n,(11.4,2.6-.38*k,.18+k*.22),GREY)
            for f in [.40,.48]:
                cp=av+t*L*f-n*.40
                for dx in [-.42,.42]:m.rod(cp+t*dx+Vector((0,0,1.1)),cp+t*dx+Vector((0,0,1.85)),.025,BRONZE,8)
            ramp=av+t*(L*.70)+n*1.0
            for j in range(8):
                cp=ramp+t*(j-3.5)*1.1;m.rod(cp,cp+Vector((0,0,1.05)),.025,STEEL,8)
            for z in [.5,1.05]:m.rod(ramp-t*4+Vector((0,0,z)),ramp+t*4+Vector((0,0,z)),.03,STEEL,8)
    m.face([(*q,9.45) for q in p],ROOF)
    # Set-back rooftop restaurant/terrace: photograph has an open pergola,
    # glass perimeter and separate plant room, not a tall full third storey.
    q=clip_axis(clip_axis(p,u,-24,17),v,-8,3)
    count+=storeys(m,q,[9.45,12.25],3.2,stone,metal,.84)
    for a,b in zip(q,q[1:]+q[:1]):band(m,[a,b],12.3,.16,.25,STEEL)
    m.face([(*pt,12.3) for pt in q],ROOF)
    for j in range(18):
        cp=u*(-25+j*2.6)+v*4.6
        transformed_box(m,cp+Vector((0,0,11.7)),u,v,(.095,7.4,.12),STEEL)
    for side in [-1,1]:
        cp=u*side*25+v*5.6
        m.rod(cp+Vector((0,0,9.4)),cp+Vector((0,0,11.7)),.055,STEEL,8)
    for x in [-23,-12,0,12,24]:
        cp=u*x+v*10.8;m.rod(cp+Vector((0,0,9.45)),cp+Vector((0,0,10.6)),.025,STEEL,8)
    m.rod(-u*26+v*10.8+Vector((0,0,10.6)),u*26+v*10.8+Vector((0,0,10.6)),.035,STEEL,8)
    return root,m,{'independentWindowOpenings':count,'height':12.4,'actualStoreys':'two full floors plus set-back roof terrace restaurant','photoFeatureNotes':'White square-clad long river restaurant, broad recessed ribbon bays, offset street entrance and stair/ramp rail, rooftop pergola, extruded RIVIERA 松鹤楼 identity. Rear facade opening rhythm inferred where no close photograph exists.'}


def one_step(spec):
    root,m=new(spec);p=geometry(spec)
    red=material('one-step-photographed-oxblood-steel',(.36,.065,.063),.76,.12)
    brick=material('one-step-grey-tile-brick',(.25,.265,.26),.94)
    mortar=material('one-step-grey-mortar',(.55,.53,.46),.99)
    bronze=material('one-step-glass-edge-bronze',(.13,.145,.12),.42,.43)
    glass=material('one-step-neutral-garden-reflective-glass',(.20,.27,.235),.18,.26)
    # Bent elevated glass gallery uses the actual mapped L-shaped contour.
    # Original estimated17m is rejected: the official photo shows one raised
    # glazed storey, open supports, lower curved service room and roof terrace.
    for z in [2.25,5.75]:
        m.face([(*pt,z) for pt in p],red)
        band(m,p,z+.24,.48,.04,red)
    panels=0
    for a,b in zip(p,p[1:]+p[:1]):
        av,bv,t,n,L=frame(a,b);bays=max(1,round(L/1.35))
        for j in range(bays):
            aa=av+t*j*L/bays;bb=av+t*(j+1)*L/bays
            m.face([aa+Vector((0,0,2.74)),bb+Vector((0,0,2.74)),bb+Vector((0,0,5.52)),aa+Vector((0,0,5.52))],glass)
            m.rod(aa+Vector((0,0,2.72)),aa+Vector((0,0,5.55)),.026,bronze,6);panels+=1
        # Terrace rail has red posts and fine steel wires, independently modeled.
        count=max(1,round(L/1.7))
        for j in range(count+1):
            cp=av+t*j*L/count;m.rod(cp+Vector((0,0,6.0)),cp+Vector((0,0,7.04)),.05,red,8)
        for z in [6.26,6.55,6.84]:m.rod(av+Vector((0,0,z)),bv+Vector((0,0,z)),.012,STEEL,6)
        m.rod(av+Vector((0,0,7.02)),bv+Vector((0,0,7.02)),.06,red,8)
    # Only discrete square red columns touch ground; preserve the open space
    # seen through the undercroft rather than filling in a generic first floor.
    for i in [0,3,5,7,9]:
        x,y=p[i];m.box((x,y,1.15),(.47,.47,2.30),red)
    centre=Vector((1.3,-1.8,0));radius=4.3
    ring=[(centre+Vector((radius*math.cos(k*math.tau/64),radius*math.sin(k*math.tau/64),0)))[:2] for k in range(64)]
    # Curving grey masonry plinth with actual entrance and round porthole.
    shell(m,ring,0,2.24,brick,ROOF)
    for z in [.12+i*.155 for i in range(14)]:band(m,ring,z,.022,.012,mortar)
    for k in range(64):
        a=k*math.tau/64
        if k%2==0:
            cp=centre+Vector((radius*math.cos(a),radius*math.sin(a),0))
            for f in range(7):m.rod(cp+Vector((0,0,.05+f*.31)),cp+Vector((0,0,.20+f*.31)),.012,mortar,4)
    n=Vector((0,-1,0));t=Vector((1,0,0));entry=centre+n*radius
    transformed_box(m,entry+n*.04+Vector((0,0,1.1)),t,n,(2.8,.16,2.15),glass)
    for dx in [-1.4,0,1.4]:m.rod(entry+t*dx+n*.12,entry+t*dx+n*.12+Vector((0,0,2.22)),.04,bronze,8)
    port=centre+Vector((radius*.707,-radius*.707,1.15));pn=Vector((.707,-.707,0));pt=Vector((.707,.707,0))
    m.rod(port,port+pn*.05,.50,DARK,32)
    for k in range(36):
        a0=k*math.tau/36;a1=(k+1)*math.tau/36
        m.rod(port+pt*.52*math.cos(a0)+Vector((0,0,.52*math.sin(a0))),port+pt*.52*math.cos(a1)+Vector((0,0,.52*math.sin(a1))),.075,mortar,6)
    # Straight flight from glazed-gallery level to roof and the tall grey
    # marker wall appear clearly in the independent entrance photograph.
    start=Vector((4.3,2.0,2.55));direction=Vector((-.63,.776,0));tangent=Vector((direction.y,-direction.x,0))
    for k in range(17):transformed_box(m,start+direction*k*.25+Vector((0,0,k*.195)),tangent,direction,(1.65,.29,.14),red)
    for side in [-1,1]:
        a=start+tangent*side*.92+Vector((0,0,.85));b=a+direction*4.1+Vector((0,0,3.2));m.rod(a,b,.045,red,8)
        for k in range(9):
            cp=start+tangent*side*.92+direction*k*.5+Vector((0,0,k*.39));m.rod(cp,cp+Vector((0,0,.85)),.026,STEEL,8)
    wall=start+tangent*1.5+direction*1.8
    transformed_box(m,wall+Vector((0,0,1.3)),direction,tangent,(5.3,.5,7.7),brick)
    for k in range(32):transformed_box(m,wall+tangent*.265+Vector((0,0,-2.4+k*.23)),direction,tangent,(5.25,.012,.018),mortar)
    return root,m,{'independentCurtainWallPanels':panels,'height':7.2,'actualStoreys':'raised glazed gallery plus lower curved room and accessible roof terrace','photoFeatureNotes':'Official One Step Garden images show the exact bent red-steel gallery in front of PICC, grey round lower room with porthole, raised open supports, cable roof rail, red exterior stair, grey marker wall. Tenant differs from stale OSM club name; dimensions proportional, hidden foundations inferred.'}


def park_toilet(spec):
    root,m=new(spec);p=geometry(spec)
    # The government park diagram locates this specific 8th-gate toilet at
    # the NW corner. Its photograph must not be reused for the SE toilet.
    fi=front(spec,p)
    brick=material('gucheng-toilet-grey-tile',(.42,.43,.37),.94)
    mortar=material('gucheng-toilet-white-mortar',(.64,.63,.56),.99)
    trim=material('gucheng-toilet-charcoal-lintel',(.21,.23,.19),.91)
    steel=material('gucheng-toilet-brushed-door',(.49,.53,.42),.42,.63)
    blue=material('gucheng-toilet-blue-sign',(.03,.13,.23),.67)
    count=0
    for i,(a,b) in enumerate(zip(p,p[1:]+p[:1])):
        av,bv,t,n,L=frame(a,b)
        if i==fi:
            ops=[(.18,1.10,1.63,2.43),(.50,1.85,.04,2.38),(.82,1.10,1.63,2.43)]
        else:ops=[(.25,.85,1.7,2.4),(.75,.85,1.7,2.4)] if L>4 else []
        count+=wall_openings(m,a,b,0,2.9,ops,brick,trim,DARK,steel,depth=.22,sill=False,crossbar=False)
        # Mortar belongs only to brick, never across door/window voids.
        holes=[(frac*L-width/2,frac*L+width/2,z0,z1) for frac,width,z0,z1 in ops]
        for z in [.10+k*.13 for k in range(22)]:
            spans=[(0,L)]
            for lo,hi,z0,z1 in holes:
                if z0-.05<=z<=z1+.05:
                    spans=[part for x0,x1 in spans for part in [(x0,min(x1,lo-.05)),(max(x0,hi+.05),x1)] if part[1]-part[0]>.02]
            for x0,x1 in spans:
                cp=av+n*.014+Vector((0,0,z));m.rod(cp+t*x0,cp+t*x1,.008,mortar,4)
        for k in range(round(L/.38)):
            for row in range(22):
                x=min(L,(k+.5*(row%2))*.38);z0=.04+row*.13;z1=z0+.11
                if any(lo-.05<=x<=hi+.05 and z0<top+.05 and z1>bottom-.05 for lo,hi,bottom,top in holes):continue
                cp=av+t*x+n*.014+Vector((0,0,z0));m.rod(cp,cp+Vector((0,0,.11)),.008,mortar,4)
        band(m,[a,b],2.84,.23,.24,trim)
    a,b=p[fi],p[(fi+1)%len(p)];av,bv,t,n,L=frame(a,b);mid=(av+bv)/2
    # The entrance is independently legible: outward double doors, grille
    # transom, two open casement windows, 333 address plaque and blue WC sign.
    for side in [-1,1]:
        hinge=mid+t*side*.93+n*.20;leaf_t=(t*side*.70+n*.714).normalized();leaf_n=Vector((leaf_t.y,-leaf_t.x,0))
        cp=hinge+leaf_t*.42+Vector((0,0,1.06));transformed_box(m,cp,leaf_t,leaf_n,(.84,.055,2.08),steel)
        transformed_box(m,cp+leaf_n*.034+Vector((0,0,.30)),leaf_t,leaf_n,(.62,.02,.70),DARK)
        for k in range(5):
            centre=cp+leaf_t*((k-2)*.115)+leaf_n*.057+Vector((0,0,.30));m.rod(centre-Vector((0,0,.35)),centre+Vector((0,0,.35)),.014,WHITE,6)
        for k in range(4):
            centre=cp+leaf_n*.057+Vector((0,0,.02+k*.18));m.rod(centre-leaf_t*.30,centre+leaf_t*.30,.014,WHITE,6)
        # Black casement returns open at sixty degrees outside photographed windows.
        ww=mid+t*(side*L*.32)+n*.17
        for s in [-1,1]:
            hinge=ww+t*s*.54;tt=(t*s*.5+n*.866).normalized();nn=Vector((tt.y,-tt.x,0))
            transformed_box(m,hinge+tt*.25+Vector((0,0,2.03)),tt,nn,(.50,.045,.80),steel)
    for k in range(11):
        cp=mid+t*((k-5)*.16)+n*.23+Vector((0,0,2.55));m.rod(cp-Vector((0,0,.15)),cp+Vector((0,0,.15)),.012,WHITE,6)
    transformed_box(m,mid+n*.20+Vector((0,0,2.94)),t,n,(2.0,.09,.54),blue)
    lettering(root,'公共厕所  WC',mid+n*.255+Vector((0,0,2.94)),t,n,.21,WHITE)
    address=mid+t*(L*.40)+n*.08+Vector((0,0,2.3));transformed_box(m,address,t,n,(.45,.06,.29),GREY);lettering(root,'333',address+n*.04,t,n,.16,WHITE)
    # The OSM west/east walls contain collinear vertices: opposite-index logic
    # would leave crossed roof strips and a large flat hole. Use the actual
    # north entrance baseline and measured depth for two complete roof planes.
    inside=-n;depth=max((Vector((*q,0))-av).dot(inside) for q in p)
    def rp(x,y,z):return av+t*x+inside*y+Vector((0,0,z))
    for x0,x1,z0,z1 in [(0,L/2,3.0,3.52),(L/2,L,3.52,3.0)]:
        m.face([rp(x0,0,z0),rp(x1,0,z1),rp(x1,depth,z1),rp(x0,depth,z0)],TILE)
        for k in range(round(depth/.27)+1):
            y=min(depth,k*.27);m.rod(rp(x0,y,z0+.025),rp(x1,y,z1+.025),.027,TILE,6)
    for y in [0,depth]:
        m.face([rp(0,y,2.86),rp(L,y,2.86),rp(L/2,y,3.52)],brick)
        m.rod(rp(0,y,3.03),rp(L/2,y,3.55),.10,trim,8);m.rod(rp(L/2,y,3.55),rp(L,y,3.03),.10,trim,8)
    m.rod(rp(L/2,0,3.55),rp(L/2,depth,3.55),.085,trim,8)
    return root,m,{'independentWindowOpenings':count,'height':3.7,'actualStoreys':1,'photoFeatureNotes':'NW8th-gate toilet specifically geolocated by government map; grey small tile courses, low Chinese tile roof, dark lintels, outward steel door leaves, barred transom, twin casements, WC and333 signs. Unseen sides inferred.'}


def provisional(spec):
    root,m=new(spec);p=geometry(spec);shell(m,p,0,spec['height'],PROVISIONAL,ROOF)
    return root,m,{'independentWindowOpenings':0,'photoFidelityAccepted':False,'notEligibleForPhotoFidelityAcceptance':True}


def save_one(spec,root,m,extra):
    m.flush();bpy.context.view_layer.update();bpy.ops.object.select_all(action='DESELECT');root.select_set(True)
    for obj in root.children_recursive:obj.select_set(True)
    bpy.context.view_layer.objects.active=root;path=OUT/(spec['id']+'.glb')
    preserve(path)
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_apply=True,export_extras=True,export_draco_mesh_compression_enable=False)
    meshes=[o for o in root.children_recursive if o.type=='MESH'];vs=[o.matrix_world@Vector(v) for o in meshes for v in o.bound_box]
    mi=[min(v[i] for v in vs) for i in range(3)];ma=[max(v[i] for v in vs) for i in range(3)]
    record={k:v for k,v in spec.items() if k not in ['footprint','frontageEdge']}
    record.update(extra);record.update({'file':str(path.relative_to(ROOT/'public')),'heading':0,'y':0,'bytes':path.stat().st_size,'triangles':sum(len(p.vertices)-2 for o in meshes for p in o.data.polygons),'meshes':len(meshes),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'localBlenderBounds':{'min':mi,'max':ma},'actualModelHeight':ma[2]-mi[2],'photoFidelityAccepted':False,'quality':{'interiors':False,'imageBillboards':False,'textureUpsampling':False,'decimation':False,'compression':'none','imageTextureCount':0}})
    records.append(record);roots.append(root);print('LOOP_FRONTAGE_MODEL',spec['id'],record['bytes'],record['confidence'],flush=True)


if not ARGS.render_only:
    for spec in SPECS:
        if ARGS.ids and spec['id'] not in ARGS.ids:continue
        if spec['builder']=='provisional' and not ARGS.allow_provisional:continue
        func={'neo':neo,'yueyuan':yueyuan,'shanghaitan':shanghaitan,'park_corner':park_corner,'qianye':qianye,'picc':picc,'fuyoumen':fuyoumen,'ji_hotel':ji_hotel,'henan_heritage':henan_heritage,'fuyou_market':fuyou_market,'zijin':zijin,'stregis':stregis,'bfc_river_row':bfc_river_row,'riviera':riviera,'one_step':one_step,'park_toilet':park_toilet,'provisional':provisional}[spec['builder']]
        root,m,extra=func(spec);save_one(spec,root,m,extra)
    bpy.ops.wm.save_as_mainfile(filepath=str(EDIT),compress=True)
    unresolved=[{'wayId':s['ways'][0],'name':s['name'],'status':'No matched facade photograph; no photo-fidelity acceptance','file':next((r['file'] for r in records if r['id']==s['id']),None)} for s in SPECS if s['builder']=='provisional']
    manifest={'version':1,'generator':'scripts/build_loop_frontages.py','createdAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'coordinateSystem':'GLB local. Manifest center X east / Z south. Blender X east / Y north / Z up. Heading zero.','models':records,'totalBytes':sum(r['bytes'] for r in records),'triangles':sum(r['triangles'] for r in records),'averageBytes':sum(r['bytes'] for r in records)/max(1,len(records)),'editableSource':str(EDIT.relative_to(ROOT)),'sourceImagesPreserved':True,'scopeWayCount':len(SPECS),'photoReferencedModels':sum(s['builder']!='provisional' for s in SPECS),'photoFidelityAcceptedModels':0,'unresolvedBuildings':unresolved,'limitation':'Photo-specific exterior reconstruction with explicitly inferred hidden surfaces; provisional map-only ways are not photo-fidelity completion.'}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
else:
    records=json.loads((OUT/'manifest.json').read_text())['models'];roots=[bpy.data.objects.get(r['id']) for r in records]

if ARGS.render or ARGS.render_only:
    for root in roots:
        if root:
            for obj in list(root.children_recursive)+[root]:bpy.data.objects.remove(obj,do_unlink=True)
    roots=[];roundtrip=[]
    review_records=[r for r in records if not ARGS.ids or r['id'] in ARGS.ids or ARGS.review_missing]
    for r in review_records:
        before=set(bpy.data.objects);path=ROOT/'public'/r['file'];bpy.ops.import_scene.gltf(filepath=str(path));objects=[o for o in bpy.data.objects if o not in before]
        root=bpy.data.objects.new('runtime-review-'+r['id'],None);bpy.context.collection.objects.link(root)
        for obj in objects:
            if obj.parent not in objects:obj.parent=root
        bpy.context.view_layer.update();vs=[o.matrix_world@Vector(v) for o in objects if o.type=='MESH' for v in o.bound_box]
        bounds={'min':[min(v[i] for v in vs) for i in range(3)],'max':[max(v[i] for v in vs) for i in range(3)]}
        error=max(abs(bounds[k][i]-r['localBlenderBounds'][k][i]) for k in ['min','max'] for i in range(3));assert error<.02,(r['id'],error)
        roots.append(root);roundtrip.append({'id':r['id'],'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'runtimeGlbImported':True,'boundsMaxDeviationMetres':error,'photoFidelityAccepted':False})
    scene=bpy.context.scene;scene.render.engine='CYCLES' if ARGS.cycles_review else 'BLENDER_EEVEE';scene.cycles.device='CPU';scene.cycles.samples=12;scene.cycles.use_denoising=True;scene.render.resolution_x=1100;scene.render.resolution_y=850;scene.render.resolution_percentage=100
    scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.63,.72,.78,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.70;scene.view_settings.view_transform='AgX'
    light=bpy.data.lights.new('loop-review-sun','SUN');light.energy=2.0;light.angle=.19;o=bpy.data.objects.new(light.name,light);bpy.context.collection.objects.link(o);o.rotation_euler=(.45,-.40,-.48)
    data=bpy.data.cameras.new('loop-review-camera');camera=bpy.data.objects.new(data.name,data);bpy.context.collection.objects.link(camera);scene.camera=camera;data.lens=40
    rendered=[]
    for r,root in zip(review_records,roots):
        if r['builder']=='provisional':continue
        for other in roots:
            for obj in [other]+list(other.children_recursive):obj.hide_render=other!=root
        mi,ma=r['localBlenderBounds']['min'],r['localBlenderBounds']['max'];width=max(ma[0]-mi[0],ma[1]-mi[1]);height=ma[2];target=Vector(((mi[0]+ma[0])/2,(mi[1]+ma[1])/2,height*.45))
        spec=next(s for s in SPECS if s['id']==r['id']);poly=geometry(spec);fi=front(spec,poly);av,bv,t,n,L=frame(poly[fi],poly[(fi+1)%len(poly)])
        views=[('street',n+t*.15+Vector((0,0,.17))),('rear',-n+t*.18+Vector((0,0,.20))),('side-roof',-n-t*.65+Vector((0,0,.68)))]
        if r['builder'] in ['riviera','stregis']:views.append(('river',Vector((.707,.707,.20))))
        if r['builder'] in ['qianye','zijin']:views.append(('gate',Vector((.1,-1,.24))))
        if r['id'] in ARGS.pbr_ids:views.append(('material',n+t*.25+Vector((0,0,.55))))
        for view,direction in views:
            path=ASSET/'review'/f"{r['id']}-{view}.png"
            if ARGS.review_missing and path.exists() and path.stat().st_mtime>=(ROOT/'public'/r['file']).stat().st_mtime:
                rendered.append({'id':r['id'],'view':view,'file':str(path.relative_to(ROOT)),'status':'retained-existing-view-after-current-glb','sha256':hashlib.sha256(path.read_bytes()).hexdigest()});continue
            camera.location=target+direction.normalized()*max(width*1.9,height*2.25);camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
            scene.render.engine='CYCLES' if ARGS.cycles_review or view=='material' else 'BLENDER_EEVEE'
            path=ASSET/'review'/f"{r['id']}-{view}.png";path.parent.mkdir(parents=True,exist_ok=True);preserve(path);scene.render.filepath=str(path);bpy.ops.render.render(write_still=True);print('LOOP_FRONTAGE_RENDER',path,flush=True)
            rendered.append({'id':r['id'],'view':view,'file':str(path.relative_to(ROOT)),'status':'rendered-current-glb','engine':scene.render.engine,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    checkpath=ASSET/'review/runtime-glb-roundtrip.json';preserve(checkpath)
    (checkpath).write_text(json.dumps({'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'models':roundtrip,'renderedViews':rendered,'validationBoundary':'GLB import, geometry bounds and exterior rendered inspection only. Retained views were rendered after the same current GLB export. EEVEE previews do not alone settle PBR material fidelity; selected doubtful materials require physical render or actual runtime PBR review. Photo fidelity requires separate visual review.'},ensure_ascii=False,indent=2)+'\n')
    print('LOOP_FRONTAGE_REVIEW_COMPLETE',flush=True)
