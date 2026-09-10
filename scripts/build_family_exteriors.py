"""Photo-directed exterior rebuild of Li Auto i6 and new battery-electric Q05.

Run through scripts/blender-local.sh --background --python this_file -- --car all.
Reference photos, first renders and later iterations remain on the external disk.
No cabin, engine, chassis simulation or existing vehicle prototype is imported.
"""
import bpy, sys, math, json, pathlib, hashlib, argparse, struct, time, shutil
from mathutils import Vector
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from family_exterior_helpers import *

CONFIG={
 'li-i6':dict(length=4.950,width=1.935,height=1.670,axles=[1.50,-1.50],radius=.3815,tire=.255,rim=.254,
  paint=(.52,.59,.545),kind='i6',year=2025,trim='2025 i6 production exterior, 20-inch aero wheels',
  width_st=[(-2.475,.74),(-2.40,.83),(-2.21,.923),(-1.60,.954),(-.8,.924),(0,.924),(1.45,.954),(2.07,.91),(2.36,.84),(2.475,.74)],
  shoulder=[(-2.475,1.14),(-2.34,1.115),(-1.9,1.095),(-.8,1.105),(.45,1.09),(1.16,1.025),(1.9,.945),(2.4,.875),(2.475,.875)],
  crown=[(-2.475,1.14),(-2.2,1.135),(-1.3,1.13),(0,1.15),(1.0,1.135),(1.55,1.03),(2.30,.955),(2.40,.925),(2.475,.875)],
  cab_top=[(-2.17,1.115),(-2.05,1.27),(-1.7,1.48),(-1.20,1.595),(-.45,1.625),(.1,1.60),(.60,1.47),(1.02,1.29),(1.32,1.088)],
  cab_half=[(-2.17,.817),(-1.85,.852),(-1.2,.846),(-.4,.841),(.35,.828),(.85,.825),(1.32,.825)],
  cab_belt=[(-2.17,1.09),(-1.0,1.115),(.4,1.10),(1.32,1.07)],cab_min=-2.17,cab_max=1.32,
  side_glass=[(1.12,1.105),(.60,1.43),(.10,1.555),(-.52,1.586),(-1.21,1.55),(-1.68,1.425),(-1.97,1.17),(-1.97,1.13)],
  seams=[[(1.04,1.09),(.96,.86),(.94,.47),(.87,.26),(-.23,.24)], [(-.23,1.11),(-.23,.44),(-.23,.24),(-.95,.245),(-1.10,.40),(-1.26,.75),(-1.43,1.10)]],
  handles=[(.03,1.008),(-1.06,1.015)],mirror_y=.88,mirror_z=1.115),
 'qiyuan-q05':dict(length=4.435,width=1.855,height=1.600,axles=[1.3675,-1.3675],radius=.35235,tire=.225,rim=.2286,
  paint=(.57,.62,.64),kind='q05',year=2026,trim='2026 new BEV 506 Laser exterior, 18-inch split-spoke wheels',
  width_st=[(-2.2175,.72),(-2.15,.81),(-1.97,.893),(-1.3675,.916),(-.65,.878),(.4,.882),(1.3675,.916),(1.87,.890),(2.12,.820),(2.2175,.71)],
  shoulder=[(-2.2175,1.15),(-2.09,1.105),(-1.55,1.10),(-.6,1.08),(.5,1.065),(1.25,1.045),(1.8,1.024),(2.13,.963),(2.2175,.947)],
  crown=[(-2.2175,1.15),(-1.9,1.13),(-1.0,1.135),(0,1.135),(.9,1.10),(1.42,1.08),(1.9,1.060),(2.13,1.020),(2.2175,.947)],
  cab_top=[(-2.06,1.13),(-1.97,1.21),(-1.78,1.49),(-1.62,1.545),(-1.30,1.560),(-.60,1.565),(-.15,1.560),(.12,1.530),(.52,1.36),(.95,1.10)],
  cab_half=[(-2.06,.755),(-1.65,.78),(-1.1,.795),(-.3,.793),(.4,.79),(.95,.80)],
  cab_belt=[(-1.98,1.1),(-1.0,1.095),(0,1.085),(.95,1.075)],cab_min=-2.06,cab_max=.95,
  side_glass=[(.83,1.105),(.41,1.36),(.04,1.497),(-.56,1.532),(-1.22,1.501),(-1.52,1.456),(-1.68,1.16),(-1.27,1.135)],
  seams=[[(.81,1.07),(.91,.92),(.94,.66),(.88,.32),(.81,.235),(-.24,.235)], [(-.24,1.09),(-.24,.46),(-.24,.235),(-.99,.245),(-1.025,.50),(-1.26,.81),(-1.51,1.105)]],
  handles=[(.01,.975),(-1.04,.995)],mirror_y=.65,mirror_z=1.095)
}

def build(car):
    c=CONFIG[car];L=c['length'];half=L/2;kind=c['kind'];wb=c['axles'];wr=c['radius']
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    for d in list(bpy.data.materials):bpy.data.materials.remove(d)
    mats={
     'paint':material(car+' metallic body',c['paint'],.68,.25),
     'black':material('Obsidian gloss trim',(.010,.014,.017),.42,.19),
     'glass':material('Dark neutral exterior glazing',(.006,.010,.013) if kind=='q05' else (.014,.021,.024),.06 if kind=='q05' else .32,.23 if kind=='q05' else .17),
     'grille':material('Matte black moulded intake',(.008,.010,.012),.04,.46),
     'projector':material('Smoked projector optical face',(.30,.37,.40),.25,.22,.20),
     'rubber':material('Tyre rubber',(.022,.024,.026),0,.74),
     'groove':material('Tyre recessed tread',(.005,.006,.007),0,.90),
     'seam':material('Panel gaps 3 mm',(.007,.009,.010),.0,.53),
     'alloy':material('Machined satin aluminium',(.42,.46,.50),.80,.34),
     'rotor':material('Brake rotor steel',(.27,.29,.30),.78,.55),
     'led':material('Daytime running light',(.88,.97,1),.0,.17,2.0),
     'red':material('Red rear lens',(.30,.003,.008),.38,.20),
     'redled':material('Rear LED light guide',(.9,.009,.016),.15,.21,1.15),
     'lens':material('Smoked light housing',(.014,.019,.023),.48,.16),
     'plate':material('Satin display plate',(.025,.029,.032),.12,.50),
    }
    front_depth=.36 if kind=='i6' else .24;rear_depth=.32
    def width(y):
        # Shallow elliptical bumper returns avoid the old flat frontal slab.
        if y>half-front_depth:
            f=(y-(half-front_depth))/front_depth
            return interp(c['width_st'],half-front_depth)*math.sqrt(max(0,1-f*f))
        if y<-half+rear_depth:
            f=((-half+rear_depth)-y)/rear_depth
            return interp(c['width_st'],-half+rear_depth)*math.sqrt(max(0,1-f*f))
        return interp(c['width_st'],y)
    shoulder=lambda y:interp(c['shoulder'],y)
    crown=lambda y:interp(c['crown'],y)
    # These are independently hand-drawn sections, sampled densely for smooth normals.
    def bodyx(y,z):
        top=shoulder(y);t=max(0,min(1,(z-.205)/(top-.205)))
        waist=.012*math.sin(math.pi*t)+.020*(math.exp(-((t-.83)/.15)**2)-t*math.exp(-((1-.83)/.15)**2))
        flare=sum((.025 if kind=='q05' else .008)*math.exp(-((y-a)/.52)**4)*math.exp(-((z-.62)/.4)**2)*math.sin(math.pi*t) for a in wb)
        # Q05 has a scooped lower door; i6 uses a much quieter concave section.
        if kind=='q05':
            # The photographed lower door hollow rises toward the rear wheel.
            # Draw the crease in metres so it remains distinct from the roof belt.
            crease_z=.400+.155*max(0,min(1,(.90-y)/1.90))
            door_mask=math.exp(-((y+.02)/.96)**6)
            scoop=.070*math.exp(-((z-crease_z)/.205)**2)*door_mask
        else:
            scoop=.028*math.exp(-((z-.43)/.19)**2)*math.exp(-((y-.05)/1.15)**4)
        return width(y)*(1+(-.055*(1-t)**2+waist+flare-scoop)/(c['width']/2))
    def body_y(y,z,x=0):
        # Different stamped bumper and hatch sections, kept continuous with the
        # side skins. Returns are mapped here and all fascia parts use the same map.
        if y>half-front_depth:
            f=((y-(half-front_depth))/front_depth)**3
            recess=.040*math.exp(-((z-.25)/.095)**2)+.013*math.exp(-((z-.59)/.12)**2)+.032*math.exp(-((z-.88)/.095)**2)
            if kind=='q05':
                # Broad central concavity between the high lamp brow and the
                # raised intake edge, with proud outer projector cheeks.
                recess+=.055*math.exp(-((z-.69)/.18)**2)*math.exp(-(x/.64)**8)
                recess-=.018*math.exp(-((abs(x)-.74)/.13)**2)*math.exp(-((z-.66)/.19)**2)
            return y-f*recess
        if y<-half+rear_depth:
            f=(((-half+rear_depth)-y)/rear_depth)**3
            if kind=='q05':
                recess=.074*math.exp(-((z-.865)/.102)**2)+.025*math.exp(-((z-.27)/.07)**2)
            else:
                recess=.046*math.exp(-((z-.76)/.165)**4)+.020*math.exp(-((z-.25)/.07)**2)
            return y+f*recess
        return y
    def topz(y,t):
        return shoulder(y)+(crown(y)-shoulder(y))*math.sqrt(max(0,1-min(1,abs(t))**4))
    arch_r=wr+(.043 if kind=='i6' else .070)
    def bottom(y):
        z=.215
        for a in wb:
            dy=abs(y-a)
            if dy<arch_r:z=max(z,wr+math.sqrt(max(0,arch_r*arch_r-dy*dy)))
        return z
    for s in [-1,1]:
        def side(u,v):
            y=-half+L*u;z=bottom(y)+(shoulder(y)-bottom(y))*v
            return(s*bodyx(y,z),body_y(y,z,s*bodyx(y,z)),z)
        grid(car+' continuous sculpted side '+str(s),side,300,36,mats['paint'])
    def top(u,v):
        y=-half+L*u;x=(v*2-1)*width(y);t=abs(2*v-1)
        z=topz(y,t)
        return(x,body_y(y,z,x),z)
    grid(car+' hood and shoulder continuous crown',top,300,72,mats['paint'])
    # Wheel arch lips follow the actual cut edge; no disks hide body intersections.
    for s in [-1,1]:
        for ay in wb:
            def arch(u,v):
                a=-.36+(math.pi+.72)*u;r=arch_r+(.012 if kind=='i6' else .040)*v
                y=ay+r*math.cos(a);z=wr+r*math.sin(a)
                return(s*(bodyx(y,z)+.002+(.007 if kind=='q05' else .001)*math.sin(v*math.pi)),y,z)
            grid('Wheel arch rim '+str((s,ay)),arch,112,6,mats['paint'] if kind=='i6' else mats['black'])
            def liner(u,v):
                a=-.35+(math.pi+.7)*u;y=ay+(arch_r-.002)*math.cos(a);z=wr+(arch_r-.002)*math.sin(a)
                return(s*(bodyx(y,z)-.004-.17*v),y,z)
            grid('Shadowed wheelwell liner '+str((s,ay)),liner,100,8,mats['rubber'])
            def wheelwell_back(u,v):
                a=-.35+(math.pi+.70)*u;r=.035+(arch_r-.039)*v
                y=ay+r*math.cos(a);z=wr+r*math.sin(a)
                return(s*(bodyx(y,z)-.18),y,z)
            grid('Opaque inner wheelwell back '+str((s,ay)),wheelwell_back,100,24,mats['groove'])
    # Gloss canopy has a continuous, hand-shaped crown. Glass panels lie on it.
    cabtop=lambda y:interp(c['cab_top'],y)
    cabw=lambda y:interp(c['cab_half'],y)
    belt=lambda y:interp(c['cab_belt'],y)
    roof_exponent=.16 if kind=='i6' else .145
    q05_roof_section=[(0,1),(.65,.997),(.77,.95),(.85,.77),(.93,.42),(1,0)]
    def cab_point(y,t,lift=0):
        # t 0=center roof, 1=outer belt. Broad roof with smoothly tucked shoulders.
        if kind=='q05':
            x=cabw(y)*t;fraction=interp(q05_roof_section,t)
        else:
            x=cabw(y)*math.sin(t*math.pi/2);fraction=max(0,math.cos(t*math.pi/2))**roof_exponent
        z=belt(y)+(cabtop(y)-belt(y))*fraction+lift
        return(x,y,z)
    wind_limits=(.35,1.29) if kind=='i6' else (.11,.925)
    rear_limits=(-2.125,-1.47) if kind=='i6' else (-2.025,-1.73)
    def glass_width(y,label):
        if kind=='i6':return .74 if label=='Windshield' else .78
        ys=wind_limits if label=='Windshield' else rear_limits
        u=max(0,min(1,(y-ys[0])/(ys[1]-ys[0])))
        return .81+.16*u if label=='Windshield' else .96-.15*u
    def inside_poly(y,z,poly):
        odd=False
        for a,b in zip(poly,poly[1:]+poly[:1]):
            if (a[1]>z)!=(b[1]>z) and y<(b[0]-a[0])*(z-a[1])/(b[1]-a[1])+a[0]:odd=not odd
        return odd
    for s in [-1,1]:
        # Omit glazing footprints from the opaque carrier. This prevents
        # coplanar triangles when curved glazing is exported and quantized.
        nu,nv=220,80
        vs=[];fs=[]
        for i in range(nu+1):
            y=c['cab_min']+(c['cab_max']-c['cab_min'])*i/nu
            for j in range(nv+1):
                p=cab_point(y,j/nv);vs.append((s*p[0],p[1],p[2]))
        for i in range(nu):
            for j in range(nv):
                y=c['cab_min']+(c['cab_max']-c['cab_min'])*(i+.5)/nu;t=(j+.5)/nv;p=cab_point(y,t)
                glazed=(wind_limits[0]<y<wind_limits[1] and t<glass_width(y,'Windshield')) or (rear_limits[0]<y<rear_limits[1] and t<glass_width(y,'Rear hatch glazing')) or inside_poly(y,p[2],c['side_glass'])
                if not glazed:
                    a=i*(nv+1)+j;fs.append((a,a+nv+1,a+nv+2,a+1))
        mesh('Continuous black canopy '+str(s),vs,fs,mats['black'])
        def glazing_foot(u,v):
            y=c['cab_min']+(c['cab_max']-c['cab_min'])*u;x=cabw(y)
            body_z=topz(y,x/max(.001,width(y)))
            return(s*x,y,body_z+(belt(y)-body_z)*v)
        grid('Canopy lower bonded black reveal '+str(s),glazing_foot,180,5,mats['black'])
    for yy in [c['cab_min'],c['cab_max']]:
        def glazing_cap(u,v):
            t=2*u-1;p=cab_point(yy,abs(t));x=math.copysign(p[0],t)
            base=topz(yy,abs(x)/max(.001,width(yy)))
            return(x,yy,base+(p[2]-base)*v)
        grid('Canopy curved end bond '+str(yy),glazing_cap,64,8,mats['black'])
    # Front and back glazing are large curved patches with broad uninterrupted highlights.
    for label,ys in [('Windshield',wind_limits),('Rear hatch glazing',rear_limits)]:
        def wind(u,v):
            y=ys[0]+(ys[1]-ys[0])*u;t=(2*v-1)*glass_width(y,label)
            p=cab_point(y,abs(t),.003)
            return(math.copysign(p[0],t),p[1]+(.002 if label=='Windshield' else -.002),p[2])
        grid(label,wind,70,70,mats['glass'])
    # Side window boundaries were read from the reference profiles. Project onto the canopy.
    def cabx(y,z):
        denom=max(.001,cabtop(y)-belt(y));frac=max(0,min(.999,(z-belt(y))/denom))
        if kind=='q05':
            lo=0.;hi=1.
            for _ in range(24):
                t=(lo+hi)/2
                if interp(q05_roof_section,t)>frac:lo=t
                else:hi=t
            return cabw(y)*(lo+hi)/2
        co=frac**(1/roof_exponent);return cabw(y)*math.sqrt(max(0,1-co*co))
    def side_patch(name,outline,mat,s,offset=.009):
        ps=smooth_path([(y,z,0) for y,z in outline],8,True)
        cy=sum(p[0] for p in ps)/len(ps);cz=sum(p[1] for p in ps)/len(ps)
        vs=[(s*(cabx(cy,cz)+offset),cy,cz)];fs=[];n=len(ps)
        for ring in range(1,33):
            frac=ring/32
            for p in ps:
                y=cy+(p[0]-cy)*frac;z=cz+(p[1]-cz)*frac
                vs.append((s*(cabx(y,z)+offset),y,z))
            for j in range(n):
                a=1+(ring-1)*n+j;b=1+(ring-1)*n+(j+1)%n
                fs.append((0,a,b) if ring==1 else (a-n,a,b,b-n))
        return mesh(name,vs,fs,mat)
    for s in [-1,1]:
        outline=smooth_path([(y,z,0) for y,z in c['side_glass']],8,True)
        sidepts=[(s*(cabx(p[0],p[1])+.004),p[0],p[1]) for p in outline]
        # fan with radial projection retains the canopy curvature instead of a flat polygon.
        cy=sum(p[1] for p in sidepts)/len(sidepts);cz=sum(p[2] for p in sidepts)/len(sidepts)
        verts=[(s*(cabx(cy,cz)+.004),cy,cz)];faces=[];n=len(sidepts)
        for ring in range(1,25):
            t=ring/24
            for p in sidepts:
                yy=cy+(p[1]-cy)*t;zz=cz+(p[2]-cz)*t
                verts.append((s*(cabx(yy,zz)+.004),yy,zz))
            for k in range(n):
                a=1+(ring-1)*n+k;b=1+(ring-1)*n+(k+1)%n
                faces.append((0,a,b) if ring==1 else (a-n,a,b,b-n))
        mesh('Side window glazing '+str(s),verts,faces,mats['glass'])
        tube('Bright window waist trim '+str(s),[(s*(cabw(y)+.006),y,belt(y)+.015) for y in [c['cab_min']+.19+(c['cab_max']-c['cab_min']-.40)*j/100 for j in range(101)]],.005,mats['alloy'] if kind=='i6' else mats['black'])
        for py,pw in ([(-.23,.090),(-1.18,.052)] if kind=='q05' else [(-.23,.049),(-1.18,.030)]):
            zs=[belt(py)+.027+(cabtop(py)-belt(py)-.077)*k/50 for k in range(51)]
            grid('B or C pillar '+str((s,py)),lambda u,v:(s*(cabx(py+(u-.5)*pw,zs[0]+(zs[-1]-zs[0])*v)+.007),py+(u-.5)*pw,zs[0]+(zs[-1]-zs[0])*v),4,50,mats['black'])
        # Four separate manufactured door joints with a ~3 mm visible shut line.
        for di,path in enumerate(c['seams']):
            pts=smooth_path([(y,z,0) for y,z in path],10)
            pts=[(p[0],max(p[1],bottom(p[0])+.004),0) for p in pts]
            tube('Door shutline '+str((s,di)),[(s*(bodyx(p[0],p[1])+.0018),p[0],p[1]) for p in pts],.0018,mats['seam'])
        for hy,hz in c['handles']:
            xx=s*(bodyx(hy,hz)+.009)
            black=box('Recessed door handle pocket',(xx,hy,hz),(.010,.195,.039),mats['black'],.018)
            box('Flush door handle',(xx+s*.003,hy,hz+.009),(.012,.166,.024),mats['paint'],.010)
        # Side skirts follow the lower door sculpt rather than a rectangular beam.
        pts=[(-1.05,.215),(-1.03,.285),(.94,.291),(1.03,.215)] if kind=='i6' else [(-.99,.300),(-.82,.279),(.77,.274),(.94,.294),(.77,.322),(-.30,.354),(-.75,.344)]
        boundary=smooth_path([(y,z,0) for y,z in pts],8,True)
        cy=sum(p[0] for p in boundary)/len(boundary);cz=sum(p[1] for p in boundary)/len(boundary);n=len(boundary)
        vs=[(s*(bodyx(cy,cz)+.006),cy,cz)];fs=[]
        for ring in range(1,17):
            for p in boundary:
                y=cy+(p[0]-cy)*ring/16;z=cz+(p[1]-cz)*ring/16
                vs.append((s*(bodyx(y,z)+.006),y,z))
            for j in range(n):
                a=1+(ring-1)*n+j;b=1+(ring-1)*n+(j+1)%n
                fs.append((0,a,b) if ring==1 else (a-n,a,b,b-n))
        mesh('Sculpted lower side black insert '+str(s),vs,fs,mats['black'])
        # Mirror stalk, tapered cap, reflective rear glass and indicator repeater.
        my=c['mirror_y'];mz=c['mirror_z'];mx=s*(c['width']/2+.058)
        stem=sphere('Aerodynamic mirror stalk',(s*(c['width']/2-.025),my,mz-.045),(.085,.082,.060),mats['black'])
        sphere('Body-colour mirror cap',(mx,my-.025,mz+.018),(.113,.135,.071),mats['black'] if kind=='i6' else mats['paint'])
        sphere('Mirror dark underside',(mx,my-.023,mz-.015),(.110,.130,.039),mats['black'])
        sphere('Exterior mirror glass',(mx,my-.144,mz+.016),(.095,.004,.050),mats['glass'])
        tube('Mirror indicator',[(mx+s*t*.090,my+.087-.015*t*t,mz+.006) for t in [j/20 for j in range(-20,21)]],.003,mats['led'])
        # Camera and charge flap appear in photographed production vehicles.
        sy=.98 if kind=='i6' else 1.06;sz=.925 if kind=='i6' else .812
        box('Fender side camera',(s*(bodyx(sy,sz)+.006),sy,sz),(.022,.105,.045),mats['black'],.016)
        if (kind=='q05' and s==1) or (kind=='i6' and s==-1):
            cy=1.2 if kind=='q05' else -1.95;cz=.99 if kind=='q05' else .94
            pts=smooth_path([(cy-.095,cz-.065,0),(cy+.095,cz-.065,0),(cy+.103,cz+.060,0),(cy-.085,cz+.067,0)],8,True)
            tube('Charging door perimeter',[(s*(bodyx(p[0],p[1])+.002),p[0],p[1]) for p in pts],.0017,mats['seam'],True)
    # Model-specific fascia details use y=f(x), avoiding floating flat light bars.
    def fascia_y(x,z,front):
        # Invert the actual side panel section, making every lens sit outside
        # the curved bumper rather than disappearing underneath its corners.
        sign=1 if front else -1;edge=sign*half
        def inside(y):
            roof=topz(y,abs(x)/max(.0001,width(y)))
            return abs(x)<=bodyx(y,z) and z<=roof
        if inside(edge):return edge
        lo=0.;hi=front_depth+.12 if front else rear_depth+.10
        assert inside(edge-sign*hi),('Lamp or trim outline leaves its bumper surface',car,front,x,z)
        for _ in range(24):
            d=(lo+hi)/2
            if not inside(edge-sign*d):lo=d
            else:hi=d
        return edge-sign*hi
    def front_y(x,z):return body_y(fascia_y(x,z,True),z,x)+.003
    def rear_y(x,z):return body_y(fascia_y(x,z,False),z,x)-.003
    def face_shape(name,xzs,mat,front=True):
        fun=front_y if front else rear_y
        boundary=smooth_path([(x,z,0) for x,z in xzs],10,True)
        cx=sum(p[0] for p in boundary)/len(boundary);cz=sum(p[1] for p in boundary)/len(boundary)
        lift=.004 if front else -.004;n=len(boundary)
        verts=[(cx,fun(cx,cz)+lift,cz)];faces=[]
        for ring in range(1,9):
            t=ring/8
            for p in boundary:
                x=cx+(p[0]-cx)*t;z=cz+(p[1]-cz)*t;verts.append((x,fun(x,z)+lift,z))
            for j in range(n):
                a=1+(ring-1)*n+j;b=1+(ring-1)*n+(j+1)%n
                faces.append((0,a,b) if ring==1 else (a-n,a,b,b-n))
        return mesh(name,verts,faces,mat)
    def fascia_bezel(name,xzs,mat,width=.022):
        boundary=smooth_path([(x,z,0) for x,z in xzs],10,True)
        cx=sum(p[0] for p in boundary)/len(boundary);cz=sum(p[1] for p in boundary)/len(boundary)
        vs=[];fs=[];n=len(boundary)
        for j in range(7):
            v=j/6
            for x,z,_ in boundary:
                r=math.hypot(x-cx,z-cz);xx=x+width*v*(x-cx)/r;zz=z+width*v*(z-cz)/r
                vs.append((xx,front_y(xx,zz)+.004*(1-v)+.004*math.sin(math.pi*v),zz))
        for j in range(6):
            for i in range(n):
                a=j*n+i;b=j*n+(i+1)%n;fs.append((a,b,b+n,a+n))
        mesh(name,vs,fs,mat)
    def lightline(name,pts,rad,mat,front=True):
        fun=front_y if front else rear_y
        tube(name,[(x,fun(x,z)+(.013 if front else -.013),z) for x,z in pts],rad,mat)
    if kind=='i6':
        # i6 signature elevated star-ring daytime light at base of the windscreen.
        def star_point(u):
            x=-.810+1.620*u;t=x/.810
            return(x,1.337-.092*t*t,1.108+.028*t*t)
        pts=[star_point(i/120) for i in range(121)]
        def star_mount(u,v):
            x,y,z=star_point(u);ratio=min(.9999,abs(x)/cabw(y))
            glass_z=cab_point(y,2*math.asin(ratio)/math.pi)[2] if y<=c['cab_max'] else -1
            base=max(topz(y,abs(x)/width(y)),glass_z)+.001
            return(x,y-.007+.009*v,base+(z-.003-base)*v)
        grid('i6 thin curved bonded star ring socket',star_mount,120,5,mats['lens'])
        tube('i6 seamless elevated star ring smoked surround',pts,.008,mats['lens'])
        tube('i6 seamless elevated star ring LED',[(x,y+.005,z+.004) for x,y,z in pts],.0055,mats['led'])
        for s in [-1,1]:
            face_shape('i6 vertical lamp enclosure',[(s*.651,.242),(s*.814,.245),(s*.819,.762),(s*.678,.790)],mats['lens'])
            for z in [.704,.750]:
                face_shape('i6 stacked projector bezel',[(s*.69,z-.015),(s*.785,z-.015),(s*.785,z+.021),(s*.69,z+.021)],mats['alloy'])
                face_shape('i6 rounded rectangular projector lens',[(s*.702,z-.008),(s*.777,z-.008),(s*.777,z+.017),(s*.702,z+.017)],mats['glass'])
                box('i6 rectangular projector optical cell',(s*.740,front_y(s*.740,z)+.019,z+.004),(.050,.008,.014),mats['led'],.005)
            lightline('i6 indicator horizontal',[(s*(.69+.097*j/20),.580) for j in range(21)],.006,mats['led'])
        face_shape('i6 lower intake aperture',[(-.585,.285),(.585,.285),(.567,.452),(-.567,.452)],mats['black'])
        for z in [.313,.365,.420]:lightline('i6 horizontal intake vane',[(-.56+1.12*j/60,z) for j in range(61)],.006,mats['black'])
        # Entire rear light housing and slim continuous optical guide.
        face_shape('i6 continuous rear light smoked housing',[(-.88,.992),(-.83,1.099),(.83,1.099),(.88,.992),(.72,.963),(-.72,.963)],mats['lens'],False)
        lightline('i6 rear full-width light guide',[(-.86+1.72*j/120,1.042+.006*abs(-1+2*j/120)) for j in range(121)],.009,mats['redled'],False)
        face_shape('i6 rear lower protection',[(-.81,.249),(.81,.249),(.87,.412),(-.87,.412)],mats['rubber'],False)
        for s in [-1,1]:
            lightline('i6 rear reflector',[(s*(.48+.25*j/30),.371) for j in range(31)],.007,mats['red'],False)
    else:
        # Short upturned blades above separate trapezoidal projector lamps.
        for s in [-1,1]:
            face_shape('Q05 swept upper running light lens',[(s*.26,.944),(s*.68,.991),(s*.84,1.025),(s*.79,.955),(s*.37,.929)],mats['lens'])
            lightline('Q05 wing LED blade',[(s*(.29+.51*j/60),.939+.069*(j/60)**1.4) for j in range(61)],.006,mats['led'])
            lamp_outline=[(s*.56,.517),(s*.70,.482),(s*.83,.530),(s*.817,.762),(s*.739,.787)]
            face_shape('Q05 rounded trapezoid projector housing',lamp_outline,mats['lens'])
            fascia_bezel('Q05 stamped projector cheek surround',lamp_outline,mats['paint'],.024)
            for z in [.608,.664,.715]:
                lightline('Q05 stacked optical shelf',[(s*(.722+.074*j/12),z) for j in range(13)],.003,mats['rotor'])
                box('Q05 rectangular projector',(s*.76,front_y(s*.76,z)+.013,z+.007),(.031,.008,.016),mats['projector'],.004)
            lightline('Q05 projector lower separator',[(s*(.61+.20*j/25),.56-.015*j/25) for j in range(26)],.004,mats['alloy'])
        lightline('Q05 central narrow dark strip',[(-.31+.62*j/50,.949) for j in range(51)],.009,mats['black'])
        inlet=[(-.82,.245),(.82,.245),(.75,.310),(.54,.490),(.39,.510),(-.39,.510),(-.54,.490),(-.75,.310)]
        face_shape('Q05 broad rounded lower air inlet',inlet,mats['grille'])
        fascia_bezel('Q05 sculpted intake surround',inlet,mats['grille'],.017)
        for x in [i*.040 for i in range(-13,14)]:
            lightline('Q05 vertical intake grille fin',[(x,.266+.209*j/32) for j in range(33)],.004,mats['grille'])
        for sgn in [-1,1]:
            for z in [.280,.330,.380,.430]:
                outer=.790-1.20*(z-.27)
                pts=[(sgn*(.53+(outer-.53)*j/24),z) for j in range(25)]
                pts=[(x,z) for x,z in pts if inside_poly(x,z,inlet)]
                if len(pts)>1:lightline('Q05 outer grille horizontal louvre',pts,.003,mats['grille'])
        # Q05's light bar has two stacked outer optical rows and a bent lower boundary.
        face_shape('Q05 rear sculpted smoked lens',[(-.88,.964),(-.80,1.112),(.8,1.112),(.88,.964),(.52,.977),(.36,1.02),(-.36,1.02),(-.52,.977)],mats['lens'],False)
        lightline('Q05 rear primary light guide',[(-.80+1.6*j/120,1.080+.008*(abs(-1+2*j/120))) for j in range(121)],.008,mats['redled'],False)
        for s in [-1,1]:
            lightline('Q05 lower outer tail guide',[(s*(.54+.27*j/40),1.008+.005*j/40) for j in range(41)],.008,mats['redled'],False)
            for z in [1.041,1.061]:
                lightline('Q05 horizontal tail optical divider',[(s*(.555+.23*j/30),z) for j in range(31)],.0017,mats['rotor'],False)
        face_shape('Q05 piano black lower rear apron',[(-.81,.285),(.81,.285),(.83,.580),(.68,.669),(-.68,.669),(-.83,.580)],mats['black'],False)
        for s in [-1,1]:lightline('Q05 rear low reflector',[(s*(.47+.21*j/30),.359) for j in range(31)],.007,mats['red'],False)
        # Painted D-pillar rises into the dark floating roof, distinctive to new Q05.
        for s in [-1,1]:
            p=[(-2.025,1.118),(-1.83,1.23),(-1.47,1.43),(-1.26,1.485),(-1.41,1.285),(-1.40,1.17),(-1.32,1.12)]
            pts=smooth_path([(y,z,0) for y,z in p],8,True)
            side_patch('Q05 painted swept D pillar '+str(s),p,mats['paint'],s,.012)
    # Hood outline including both shoulder shutlines and front leading edge.
    for s in [-1,1]:
        y0=1.25 if kind=='i6' else .92
        pts=[]
        for i in range(80):
            y=y0+(half-.12-y0)*i/79;t=.87-.13*i/79;x=s*width(y)*t
            pts.append((x,y,topz(y,t)+.002))
        tube('Hood side panel gap',pts,.0018,mats['seam'])
    # Tailgate perimeter follows the high upper corners and lowered latch section.
    rearpath=[(-.78,1.08),(-.78,.73),(-.71,.58),(-.57,.535),(.57,.535),(.71,.58),(.78,.73),(.78,1.08)] if kind=='i6' else [(-.70,1.09),(-.71,.90),(-.70,.67),(.70,.67),(.71,.90),(.70,1.09)]
    pts=smooth_path([(x,z,0) for x,z in rearpath],10)
    tube('Rear liftgate shutline',[(p[0],rear_y(p[0],p[1])-.006,p[1]) for p in pts],.0018,mats['seam'])
    # Roof spoiler is profiled along the actual descending roof line.
    spy=-1.52 if kind=='i6' else -1.66
    def spoiler_surface(u,v):
        t=abs(2*u-1)*.80;p=cab_point(spy,t)
        x=math.copysign(p[0],2*u-1)
        y=spy-(.18 if kind=='i6' else .20)*v
        z=p[2]+.009-.018*v+.004*math.sin(v*math.pi)
        return(x,y,z)
    spoiler=grid('Roof-conformed upper hatch aero spoiler',spoiler_surface,96,16,mats['black'])
    m=spoiler.modifiers.new('Spoiler thin formed shell','SOLIDIFY');m.thickness=.017
    # Closed outer/end returns bond the cantilever to the descending roof.
    for sg in [-1,1]:
        def spoiler_return(u,v):
            top=spoiler_surface(1 if sg>0 else 0,u)
            roof=cab_point(top[1],.80)
            return(top[0],top[1],roof[2]+(top[2]-roof[2])*v)
        grid('Integrated spoiler outer return '+str(sg),spoiler_return,24,6,mats['black'])
    tube('High mounted brake lamp',[(x,spy-(.184 if kind=='i6' else .204),cabtop(spy)-.012) for x in [-.18+.36*j/35 for j in range(36)]],.004,mats['redled'])
    # Low roof lidar, rear wiper, front camera, 12 parking sensors.
    ly=-.08 if kind=='q05' else -.10;lz=cabtop(ly)
    lidar_h=.043 if kind=='q05' else .053
    box('Roof lidar base',(0,ly,lz+lidar_h*.48),(.170,.145,lidar_h),mats['black'],.030)
    box('Roof lidar window',(0,ly+.074,lz+lidar_h*.53),(.122,.012,lidar_h*.64),mats['lens'],.010)
    wy=-1.90 if kind=='i6' else -1.995;wz=cabtop(wy)+.015
    tube('Rear hatch wiper',[(.25,wy,wz),(.08,wy-.012,wz+.003),(-.25,wy-.013,wz+.015)],.008,mats['black'])
    for front in [True,False]:
        z=.529 if front else .492
        for x in [-.77,-.46,.46,.77]:
            y=(front_y if front else rear_y)(x,z)
            sphere('Ultrasonic parking sensor',(x,y+(.007 if front else -.007),z),(.010,.0025,.010),mats['paint'])
        platez=.545 if front else (.775 if kind=='i6' else .497)
        y=front_y(0,platez)+.012 if front else rear_y(0,platez)-.012
        box('Front display plate' if front else 'Rear display plate',(0,y,platez),(.46,.014,.145),mats['plate'],.009)
        sphere('Exterior parking camera',(0,y+(.018 if front else -.018),platez+.11),(.014,.009,.010),mats['lens'])
    # Small exterior logos use clean geometry, never photographic baked body textures.
    def hood_badge_point(x,y):return(x,y,topz(y,abs(x)/max(.001,width(y)))+.004)
    if kind=='i6':
        tube('Li hood emblem L',[hood_badge_point(-.023,1.927),hood_badge_point(-.023,1.981),hood_badge_point(.005,1.981)],.005,mats['alloy'])
        tube('Li hood emblem i',[hood_badge_point(.024,1.932),hood_badge_point(.024,1.980)],.005,mats['alloy'])
        for x in [-.025,.018]:
            tube('Rear Li emblem',[(x,-half-.014,1.136),(x,-half-.014,1.111),(x+.017,-half-.014,1.111)],.004,mats['alloy'])
    else:
        pts=[hood_badge_point(.026*math.sin(i*math.tau/40),1.990+.018*math.cos(i*math.tau/40)) for i in range(41)]
        tube('Q05 front emblem oval',pts,.003,mats['black'])
        for x in [-.041,.041]:tube('Q05 front emblem side stroke',[hood_badge_point(x,1.973),hood_badge_point(x,2.007)],.003,mats['black'])
        pts=[(.014*math.sin(i*math.tau/40),-half-.020,1.082+.014*math.cos(i*math.tau/40)) for i in range(41)]
        tube('Q05 rear luminous emblem',pts,.003,mats['redled'])
    for word,x,z in [('i6' if kind=='i6' else 'Q05',.635,.76 if kind=='i6' else .744)]:
        data=bpy.data.curves.new('Production model badge','FONT');data.body=word;data.align_x='CENTER';data.size=.041;data.extrude=.001;data.bevel_depth=.0005
        ob=bpy.data.objects.new('Production model badge '+word,data);bpy.context.collection.objects.link(ob)
        ob.location=(x,rear_y(x,z)-.008,z);ob.rotation_euler=(math.pi/2,0,0);data.materials.append(mats['alloy'])
    wheelparts=[]
    for front,ay in [(True,wb[0]),(False,wb[1])]:
        for s in [-1,1]:
            name=('F' if front else 'R')+('L' if s<0 else 'R')
            track=(1.668 if kind=='i6' else (1.580 if front else 1.590))
            pivot,roll=wheel(name,(s*track/2,ay,wr),wr,c['tire'],c['rim'],mats,kind);wheelparts.append(pivot)
    apply_meshes();join_by_parent_material()
    # Scale only the tiny mirror protrusion remains outside the body width specification.
    bpy.context.view_layer.update()
    return c,wheelparts

def export(car,c,wheels,revision):
    out=ROOT/'public/vehicles/rigged';out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'assets/vehicles/family-exteriors'/car;source.mkdir(parents=True,exist_ok=True)
    objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
    tris=lambda obs:sum(sum(len(p.vertices)-2 for p in ob.data.polygons) for ob in obs)
    total=tris(objects)
    wheelstats={}
    for ob in wheels:
        pieces=[p for p in ob.children_recursive if p.type=='MESH']
        wheelstats[ob['wheelPosition']]={'centerBlender':list(ob.location),'radius':ob['wheelRadius'],'triangles':tris(pieces),'components':len(pieces)}
    dest=out/(car+'.glb')
    if dest.exists():
        old=hashlib.sha256(dest.read_bytes()).hexdigest()[:12]
        archived=source/(car+'-previous-'+old+'.glb')
        if not archived.exists():archived.write_bytes(dest.read_bytes())
    bpy.ops.export_scene.gltf(filepath=str(dest),export_format='GLB',export_apply=True,export_extras=True,
        export_draco_mesh_compression_enable=True,export_draco_mesh_compression_level=6,
        export_draco_position_quantization=18,export_draco_normal_quantization=14,export_draco_texcoord_quantization=14)
    editable=ROOT/'assets/blender/tourism'/(car+'-exterior.blend')
    if editable.exists():
        old=hashlib.sha256(editable.read_bytes()).hexdigest()[:12]
        archived=source/(car+'-previous-'+old+'.blend')
        if not archived.exists():shutil.copy2(editable,archived)
    reproducible=source/'source-revisions'/revision;reproducible.mkdir(parents=True,exist_ok=True)
    for fn in ['build_family_exteriors.py','family_exterior_helpers.py']:
        p=reproducible/fn
        if not p.exists():shutil.copy2(ROOT/'scripts'/fn,p)
    bpy.ops.wm.save_as_mainfile(filepath=str(editable))
    pts=[ob.matrix_world@v.co for ob in objects for v in ob.data.vertices]
    bounds=[max(p[i] for p in pts)-min(p[i] for p in pts) for i in range(3)]
    raw=dest.read_bytes();gltf=json.loads(raw[20:20+struct.unpack_from('<I',raw,12)[0]])
    gltf_triangles=sum(gltf['accessors'][p['indices']]['count']//3 for m in gltf.get('meshes',[]) for p in m['primitives'])
    assert gltf_triangles==total,('Exporter changed triangle count',car,total,gltf_triangles)
    nodes={n.get('name'):n for n in gltf['nodes']}
    for name in ['FL','FR','RL','RR']:
        for n in ['Wheel_'+name,'WheelRoll_'+name]:assert nodes[n].get('rotation',[0,0,0,1])==[0,0,0,1]
        assert nodes['Wheel_'+name]['extras']['wheelPosition']==name
    report=dict(car=car,type='photo-reconstructed-exterior',sourceYear=c['year'],sourceTrim=c['trim'],visualAccepted=False,highFidelityAccepted=False,
      fidelity='Custom photo-directed exterior reconstruction; visual acceptance remains pending',
      revision=revision,sourceFile='scripts/build_family_exteriors.py',sourceUrl='https://commons.wikimedia.org/wiki/Category:Li_Auto_i6' if car=='li-i6' else 'https://www.dongchedi.com/auto/series/25634/images-wg',
      sourceLicense='Original generated geometry; photos used as visual reference only; see reference manifest',
      license='Original procedural geometry authored for this project; underlying car design and marks belong to their owners',
      referencePhotosEmbedded=False,interiorIncluded=False,originalPrototypeImported=False,
      file='/vehicles/rigged/'+car+'.glb',preview='/vehicles/rigged/'+car+'-front.png',editable=str(editable.relative_to(ROOT)),runtimeBytes=len(raw),runtimeTriangles=total,budgetBytes=10000000,
      sourceTriangles=total,rigFacesBefore=total,rigFacesAfter=total,wheelRig=wheelstats,
      boundsXYZMetres=bounds,dimensionsM=[bounds[1],bounds[0],bounds[2]],nominalDimensionsMetres=[c['length'],c['width'],c['height']],dimensionNote='Runtime bounds include exterior mirrors, license plate mount and badges; nominal body dimensions exclude those appendages.',textureMaxSize=0,geometryCompression='Draco 18-bit positions / 14-bit normals',sha256=hashlib.sha256(raw).hexdigest(),runtimeSha256=hashlib.sha256(raw).hexdigest(),
      rigValidation=dict(fourWheelPivots=True,faceCountPreserved=True,minimumWheelTriangles=min(w['triangles'] for w in wheelstats.values()),identityGltfAxes=True,exportedTrianglesMatch=True),
      unfinishedComparison=['Surface curvature is estimated from perspective photographs rather than OEM CAD or photogrammetry.','Lighting internals, exact badges and tire sidewall lettering are simplified.','Rendered front, rear and side must be visually inspected; geometry counts do not establish fidelity.'],
      renderDirectory=str((source/'review'/revision).relative_to(ROOT)))
    (out/(car+'-quality.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (source/'quality.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('FAMILY_EXTERIOR_EXPORT',json.dumps(report),flush=True)
    return report

def render(car,revision,quick=False):
    # Re-import the delivered compressed GLB, so previews are evidence of runtime geometry.
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(ROOT/'public/vehicles/rigged'/(car+'.glb')))
    report=json.loads((ROOT/'assets/vehicles/family-exteriors'/car/'quality.json').read_text())
    imported_meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    imported_triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in imported_meshes)
    assert imported_triangles==report['sourceTriangles'],('GLB reimport lost source triangles',car,imported_triangles,report['sourceTriangles'])
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=12 if quick else 32;scene.cycles.use_denoising=True
    scene.render.resolution_x=900 if quick else 1280;scene.render.resolution_y=600 if quick else 850;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
    scene.world.use_nodes=True;bg=scene.world.node_tree.nodes.get('Background');bg.inputs['Color'].default_value=(.53,.59,.66,1);bg.inputs['Strength'].default_value=.35
    scene.view_settings.view_transform='AgX'
    for loc,power,sx,sy in [((3,4,6),1500,5,3),((-4,1,4),1300,6,3),((1,-5,5),1700,5,3)]:
        data=bpy.data.lights.new('Review strip softbox','AREA');data.energy=power;data.shape='RECTANGLE';data.size=sx;data.size_y=sy
        ob=bpy.data.objects.new('Review strip softbox',data);bpy.context.collection.objects.link(ob);ob.location=loc;ob.rotation_euler=(Vector((0,0,.6))-ob.location).to_track_quat('-Z','Y').to_euler()
    ground=material('Review studio floor',(.10,.12,.135),.1,.7)
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.001));bpy.context.object.data.materials.append(ground)
    data=bpy.data.cameras.new('Exterior review camera');cam=bpy.data.objects.new('Exterior review camera',data);bpy.context.collection.objects.link(cam);scene.camera=cam;data.lens=60
    dest=ROOT/'assets/vehicles/family-exteriors'/car/'review'/revision;dest.mkdir(parents=True,exist_ok=True)
    views=[('front-three-quarter',(6.0,8.0,2.45)),('rear-three-quarter',(-6.0,-8.0,2.45)),('side',(8.9,0,.82)),('front',(0,9.7,.82)),('rear',(0,-9.7,.82))]
    if car=='qiyuan-q05':
        views.insert(0,('front-low-three-quarter',(-5.3,8.5,1.05)))
        views=[(name,(-8.9,0,.82) if name=='side' else loc) for name,loc in views]
    for name,loc in views:
        data.lens=75 if name=='front-low-three-quarter' else 60
        data.type='ORTHO' if name in ['side','front','rear'] else 'PERSP';data.ortho_scale=(4.96 if car=='qiyuan-q05' else 5.60) if name=='side' else 3.15
        cam.location=loc;cam.rotation_euler=(Vector((0,0,.82))-cam.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(dest/(name+'.png'));bpy.ops.render.render(write_still=True)
    # Meaningful moving-wheel check: car body positions unchanged, pivots steer, children roll.
    body=[o for o in scene.objects if o.type=='MESH' and o.parent is None]
    before={o.name:[tuple(o.matrix_world@v.co) for v in o.data.vertices] for o in body}
    wheel_before={}
    for name in ['FL','FR','RL','RR']:
        p=bpy.data.objects['Wheel_'+name]
        wheel_before[name]=[tuple(o.matrix_world@v.co) for o in p.children_recursive if o.type=='MESH' for v in o.data.vertices]
    for name in ['FL','FR','RL','RR']:
        p=bpy.data.objects['Wheel_'+name];r=bpy.data.objects['WheelRoll_'+name]
        p.rotation_mode='XYZ';r.rotation_mode='XYZ'
        if p.get('frontWheel'):p.rotation_euler.z=math.radians(25)
        r.rotation_euler.x=math.radians(45)
    bpy.context.view_layer.update()
    assert before=={o.name:[tuple(o.matrix_world@v.co) for v in o.data.vertices] for o in body}
    wheel_changes={}
    for name in ['FL','FR','RL','RR']:
        p=bpy.data.objects['Wheel_'+name]
        after=[tuple(o.matrix_world@v.co) for o in p.children_recursive if o.type=='MESH' for v in o.data.vertices]
        changed=sum((Vector(a)-Vector(b)).length>1e-5 for a,b in zip(wheel_before[name],after))
        assert changed>len(after)*.98,('Wheel geometry did not rotate with its rig',name,changed,len(after))
        wheel_changes[name]=dict(vertices=len(after),changedVertices=changed,centerUnchanged=list(p.location),frontSteering=bool(p.get('frontWheel')))
    data.type='PERSP';cam.location=(6,5,1.7);cam.rotation_euler=(Vector((0,.5,.6))-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(dest/'steering.png');bpy.ops.render.render(write_still=True)
    (dest/'rig-review.json').write_text(json.dumps(dict(fourWheels=True,frontSteerDegrees=25,rollDegrees=45,bodyStationary=True,runtimeReimport=True,sourceTriangles=report['sourceTriangles'],reimportTriangles=imported_triangles,wheelGeometryChanges=wheel_changes),indent=2))
    preview=ROOT/'public/vehicles/rigged'/(car+'-front.png')
    if preview.exists():
        old=hashlib.sha256(preview.read_bytes()).hexdigest()[:12]
        archived=dest.parent/(car+'-previous-preview-'+old+'.png')
        if not archived.exists():archived.write_bytes(preview.read_bytes())
    preview.write_bytes((dest/'front-three-quarter.png').read_bytes())
    report['rigValidation'].update(runtimeReimport=True,reimportTrianglesMatch=True,allFourWheelMeshesMoved=True,bodyStationary=True)
    report['rigReviewFile']=str((dest/'rig-review.json').relative_to(ROOT))
    report['renderedViews']=[name for name,_ in views]+['steering']
    report['renderSettings']={'resolution':[scene.render.resolution_x,scene.render.resolution_y],'samples':scene.cycles.samples,'engine':'CYCLES','deliveredGlbReimport':True}
    for rp in [ROOT/'public/vehicles/rigged'/(car+'-quality.json'),ROOT/'assets/vehicles/family-exteriors'/car/'quality.json']:
        rp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('FAMILY_EXTERIOR_REVIEW',car,str(dest),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--car',default='all');parser.add_argument('--revision',default='v1');parser.add_argument('--no-render',action='store_true');parser.add_argument('--render-only',action='store_true');parser.add_argument('--quick',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    bpy.context.preferences.filepaths.use_scripts_auto_execute=False
    for car in ['qiyuan-q05','li-i6'] if args.car=='all' else [args.car]:
        if not args.render_only:c,w=build(car);export(car,c,w,args.revision)
        if not args.no_render:render(car,args.revision,args.quick)
