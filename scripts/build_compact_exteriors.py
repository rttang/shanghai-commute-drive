"""Build reference-traced Geely Xingyuan 2025 / Wuling Bingo Pro 2026 exteriors.

Run scripts/blender-local.sh -b --threads 2 --python scripts/build_compact_exteriors.py
-- starwish [--no-render]. No downloaded or rejected vehicle geometry is used.
Public outputs remain explicitly review candidates until photographic QA passes.
"""
import bpy, math, sys, pathlib, json, hashlib, shutil, datetime, struct
import numpy as np
import bmesh
from mathutils import Vector

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from compact_exterior_helpers import *

CAR=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'starwish'
assert CAR in ['starwish','bingo-pro']
BINGO=CAR=='bingo-pro'
L,W,H,WB=(4.050,1.758,1.580,2.560) if BINGO else (4.135,1.805,1.570,2.650)
R=.2032+(.195 if BINGO else .205)*.60
TRACK=.755 if BINGO else .772
FRONT=1.245 if BINGO else 1.345
REAR=FRONT-WB
OUT=ROOT/'assets/vehicles/compact-exteriors'/CAR
OUT.mkdir(parents=True,exist_ok=True)
if (OUT/(CAR+'.glb')).exists():
    history=OUT/('candidate-'+datetime.datetime.now().strftime('%Y%m%dT%H%M%S'))
    history.mkdir()
    prior_blend=ROOT/'assets/blender/tourism'/(CAR+'-exterior.blend')
    if prior_blend.exists():shutil.copy2(prior_blend,history/prior_blend.name)
    for filename in [CAR+'.glb','quality.json']:
        if (OUT/filename).exists():shutil.copy2(OUT/filename,history/filename)
PUBLIC=ROOT/'public/vehicles/rigged'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
for m in list(bpy.data.materials):
    if not m.users:bpy.data.materials.remove(m)

paint=material(('Wuling Hepburn green' if BINGO else 'Geely Innocent Blue'),(.007,.105,.073) if BINGO else (.13,.31,.59),.36,.27,.7)
black=material('Black roof piano lacquer',(.008,.012,.015),.25,.29,.7)
rubber=material('Tyre rubber',(.012,.014,.016),.02,.76)
trim=material('Satin black polymer',(.013,.017,.020),.05,.48)
gap=material('Panel gap inner shadow',(.004,.007,.009),0,.72)
silver=material('Machined aluminium',(.61,.65,.68),.90,.21,.3)
chrome=material('Bright chrome trim',(.76,.80,.83),.96,.15,.25)
glass=material('Smoked exterior glazing',(.006,.010,.014),.02,.23,.25)
optic=material('Headlamp projector optical glass',(.003,.006,.010),.08,.24,.45)
lampglass=material('Smoked headlamp optical cover',(.007,.015,.023),.12,.24,.5)
led=material('White daytime lamp phosphor',(.72,.86,.96),.05,.27,.1,.35)
red=material('Ruby red tail lens',(.35,.004,.006),0,.34,.10,.5)
darkred=material('Tail lamp smoked casing',(.032,.003,.004),0,.40,.10)
reflector=material('Red rear retroreflectors',(.24,.002,.004),.28,.27,.6)
brake=material('Brake rotor steel',(.19,.205,.214),.88,.40)
for optical_material in [glass,lampglass,optic,darkred,red]:
    shader=optical_material.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Specular IOR Level'].default_value=.16
    shader.inputs['Coat Weight'].default_value=.10
for rear_optic in [darkred,red]:
    shader=rear_optic.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Specular IOR Level'].default_value=.045
    shader.inputs['Coat Weight'].default_value=.02
    shader.inputs['Roughness'].default_value=.44

# These longitudinal stations are independently fitted to archived manufacturer
# side photographs; absolute envelope and axle centers use published dimensions.
width_keys=[(-L/2,.0015),(-L/2+.02,.40),(-L/2+.09,.67),(-1.80,.803 if BINGO else .826),(-1.40,W/2-.012),(-.50,W/2),(0.5,W/2-.005),(1.27,W/2-.009),(1.67,.860),(1.82,.830),(1.94,.780),(2.010,.620),(2.045,.370),(L/2,.0015)]
belt_keys=[(-L/2,.990 if BINGO else 1.010),(-1.87,1.045),(-1.50,1.045),(-.8,1.06),(0,1.065),(.85,1.075),(1.35,1.085),(1.65,1.067),(1.9,.940),(L/2,.855 if BINGO else .890)]
roof_keys=[(-1.86,1.01),(-1.65,1.23),(-1.40,1.46),(-1.06,H-.033),(-.55,H),(-.12,H-.012),(.23,1.53),(.49,1.445),(.77,1.255),(1.04,1.069)]

if BINGO:
    # Bingo Pro's shorter bonnet and more upright hatch use a separate profile.
    roof_keys=[(-1.86,1.015),(-1.68,1.238),(-1.43,1.430),(-1.05,1.531),(-.54,H),(-.10,H-.010),(.20,1.535),(.47,1.450),(.77,1.259),(1.04,1.070)]
    width_keys=[(-L/2,.0015),(-L/2+.024,.42),(-L/2+.10,.69),(-1.80,.817),(-1.42,.871),(-.5,.879),(.50,.873),(1.26,.866),(1.50,.862),(1.69,.837),(1.82,.800),(1.92,.710),(1.985,.450),(L/2,.0015)]

def width(y):return interp(width_keys,y)
def belt(y):return interp(belt_keys,y)
def roof(y):return max(belt(y)+.002,interp(roof_keys,y))
def low(y):
    h=.20
    for cy in [FRONT,REAR]:
        d=abs(y-cy);radius=R+(.079 if not BINGO else .074)
        if d<radius:h=max(h,R+math.sqrt(radius*radius-d*d))
    return h
def shoulder_z(y):return belt(y)-(.125 if BINGO else .115)
def shoulder_top(y):return belt(y)+.025-.038*math.exp(-((y+L/2)/.46)**2)
def sidex(y,z):
    # The wheel crowns and door belly share one tangent-continuous section.
    # Upper shoulder is sampled in hoodz, so side and top meet at their widest
    # point with a vertical tangent instead of the old visible flat ledge.
    join=shoulder_z(y)
    t=max(0,min(1,(z-.19)/(join-.19)))
    foundation=width(y)*(1-(.072 if BINGO else .062)*(1-t)**2)
    wheel_shoulders=sum((.017 if BINGO else .022)*math.exp(-((y-cy)/.46)**2)*math.exp(-((z-.65)/.26)**2)*(1-t*t) for cy in [FRONT,REAR])
    door_sculpture=(.038 if BINGO else .046)*math.exp(-((y+.12)/.98)**4)*math.exp(-((z-.48)/.20)**2)*(1-t)**.45
    bumper_corner=(.035 if BINGO else .085)*math.exp(-((y-(1.84 if BINGO else 1.91))/(.16 if BINGO else .14))**2)*math.exp(-((z-.58)/.21)**4)*(1-t*t)
    return foundation+wheel_shoulders-door_sculpture+bumper_corner

def side_y(y,z):
    front_factor=math.exp(-((y-L/2)/.53)**2)
    rear_factor=math.exp(-((y+L/2)/.42)**2)
    # Distinct compound-curved bumpers: inset chin, proud upper brow and
    # shallow bumper-panel recess. This changes the real exterior envelope.
    if BINGO:
        front_profile=interp([(.19,-.107),(.32,-.044),(.51,-.011),(.73,.0),(.84,-.018),(1.0,-.045),(1.2,-.018)],z)
        rear_profile=interp([(.19,.085),(.38,.02),(.57,0),(.78,.018),(1.08,.051)],z)
    else:
        front_profile=interp([(.19,-.095),(.32,-.051),(.45,-.014),(.59,-.018),(.73,-.003),(.82,0),(.95,-.030),(1.2,-.018)],z)
        rear_profile=interp([(.19,.088),(.34,.046),(.55,0),(.76,.014),(1.08,.048)],z)
    return y+front_factor*front_profile+rear_factor*rear_profile

def sidept(y,z,s=1,offset=0):
    join=shoulder_z(y)
    if z>join:
        crown=shoulder_top(y)
        t=max(0,min(.999,(z-join)/(crown-join)))
        x=width(y)*(.865+.135*math.sqrt(1-t*t))
    else:x=sidex(y,z)
    return (s*(x+offset),side_y(y,z),z)
def canopy_width(y):return sidex(y,belt(y))*.88
def canopy_z(x,y):
    q=min(1,abs(x)/max(.01,canopy_width(y)))
    h=roof(y)-belt(y);rounding=min(.058,h*.13)
    if q<=.86:return roof(y)-rounding*(q/.86)**2
    t=(q-.86)/.14
    return belt(y)+(h-rounding)*(1-t)
def canopy_x(y,z):
    h=max(.002,roof(y)-belt(y));rounding=min(.058,h*.13)
    if z>roof(y)-rounding:
        return canopy_width(y)*.86*math.sqrt(max(0,(roof(y)-z)/max(.001,rounding)))
    v=max(0,min(1,(z-belt(y))/max(.001,h-rounding)))
    return canopy_width(y)*(1-.14*v)
def hoodz(x,y):
    q=min(1,abs(x)/max(.01,width(y)))
    join=shoulder_z(y)
    if q<=.865:
        # An individually crowned hood, with a subtle shallow valley beside the
        # raised outer fenders. It is continuous with both swept shoulder skins.
        crown=(.037 if BINGO else .040)*(1-(q/.865)**2)**2*math.exp(-((y-1.38)/.68)**2)
        fender=(.017 if BINGO else .024)*math.exp(-((q-.75)/.15)**2)*math.exp(-((y-1.42)/.58)**2)*(1-(q/.865)**8)**2
        return shoulder_top(y)+crown+fender
    t=(q-.865)/.135
    return join+(shoulder_top(y)-join)*math.sqrt(max(0,1-t*t))

def fascia_y(x,z,front):
    """Locate the closed front/rear compound surface at an X/Z coordinate."""
    if front:
        # Front bumper corners may widen again below the bonnet. Locate the
        # forward-most crossing first; a monotonic binary search can select
        # the rear flank and place a fascia vertex behind the front axle.
        b=L/2;a=1.1
        for step in range(1,65):
            probe=L/2-(L/2-1.1)*step/64
            if sidex(probe,z)>=abs(x):a=probe;break
            b=probe
        for _ in range(32):
            mid=(a+b)/2
            if sidex(mid,z)>abs(x):a=mid
            else:b=mid
    else:
        a,b=-L/2,-1.1
        for _ in range(32):
            mid=(a+b)/2
            if sidex(mid,z)<abs(x):a=mid
            else:b=mid
    lateral_limit=(a+b)/2
    def depth_at(y):
        result=side_y(y,z)
        if front and not BINGO:
            taper=max(0,min(1,(y-SKIN_FRONT)/(L/2-SKIN_FRONT)));taper=taper*taper*(3-2*taper)
            line=.27+.30*abs(x)
            cheek=.012*math.tanh((z-line)/.025)*math.exp(-((abs(x)-.64)/.16)**4)*math.exp(-((z-.47)/.18)**4)
            curtain=-.018*math.exp(-((abs(x)-.805)/.024)**4)*math.exp(-((z-.50)/.17)**4)
            result+=taper*(cheek+curtain)
        return result
    def top(y):
        return hoodz(x,y)
    if z>top(lateral_limit):
        if front:
            a,b=.2,lateral_limit
            for _ in range(32):
                mid=(a+b)/2
                if top(mid)>z:a=mid
                else:b=mid
        else:
            a,b=lateral_limit,-.5
            for _ in range(32):
                mid=(a+b)/2
                if top(mid)<z:a=mid
                else:b=mid
        return depth_at((a+b)/2)
    return depth_at(lateral_limit)

# Split at full-width transverse stations beyond both open wheel wells. The
# nose and hatch are X/Z-domain skins, so no shoulder grid collapses into a
# near-zero-width pole and no thin end-cap can introduce inverted fan triangles.
SKIN_REAR=-1.78 if BINGO else -1.80
SKIN_FRONT=1.73 if BINGO else 1.90
SKIN_SPAN=SKIN_FRONT-SKIN_REAR
for s in [-1,1]:
    surface('Compound curved door and fender skin '+str(s),lambda u,v:sidept(SKIN_REAR+SKIN_SPAN*u,low(SKIN_REAR+SKIN_SPAN*u)+(shoulder_z(SKIN_REAR+SKIN_SPAN*u)-low(SKIN_REAR+SKIN_SPAN*u))*v,s),300,80,paint,reverse=s<0)
def shoulder_patch(u,v):
    y=SKIN_REAR+SKIN_SPAN*u;x=math.sin((2*v-1)*math.pi/2)*width(y);z=hoodz(x,y)
    return (x,side_y(y,z),z)
surface('Continuous crowned bonnet and shoulder',shoulder_patch,300,120,paint,True)
surface('Rounded greenhouse and roof',lambda u,v:((2*v-1)*canopy_width(-1.86+2.9*u),-1.86+2.9*u,canopy_z((2*v-1)*canopy_width(-1.86+2.9*u),-1.86+2.9*u)+.002),138,72,black,True)
for y,is_front in [(SKIN_REAR,False),(SKIN_FRONT,True)]:
    def end_cap(u,v,y=y,is_front=is_front):
        q=math.sin((2*v-1)*math.pi/2)
        z=.20+(hoodz(q*width(y),y)-.20)*u;x=q*sidex(y,z)
        return (x,fascia_y(x,z,is_front),z)
    surface('Full width compound bumper and hatch skin',end_cap,80,120,paint,not is_front)

# Full wheel arch edging follows each true tire circle. The polymer liner is
# recessed and the painted lip uses an annular strip, not a stuck-on torus.
for s in [-1,1]:
    for cy in [FRONT,REAR]:
        ar=R+.045
        start=-.22;end=math.pi+.22
        def arch(u,v):
            a=start+(end-start)*u;rad=ar+v*(.036 if BINGO else .034)
            y=cy+rad*math.cos(a);z=R+rad*math.sin(a)
            return sidept(y,z,s,.003)
        surface('Black wheel arch moulding',arch,100,8,trim,s<0)
        if not BINGO:
            surface('Narrow painted wheel arch shoulder',lambda u,v:sidept(cy+(ar+.034+v*.010)*math.cos(start+(end-start)*u),R+(ar+.034+v*.010)*math.sin(start+(end-start)*u),s,.003),100,4,paint,s<0)
        def liner(u,v):
            a=start+(end-start)*u;y=cy+ar*math.cos(a);z=R+ar*math.sin(a)
            return (s*(sidex(y,z)-.008-v*.16),y,z)
        surface('Wheel well inner return',liner,100,5,gap,s>0)
    # Lower rocker follows the upward door-bottom taper visible in the photos.
    y1=REAR+R+.045;y2=FRONT-R-.045
    surface('Contoured lower rocker',lambda u,v:sidept(y1+(y2-y1)*u,.185+v*(.080+(.07 if not BINGO else .01)*math.sin(math.pi*u)),s,.005),80,8,trim,s<0)
    curve('Rocker chrome inlay',[sidept(y1+.13,.23,s,.014),sidept(y1+.32,.245,s,.012),sidept(y2-.26,.249,s,.010),sidept(y2-.09,.238,s,.009)],.008 if BINGO else .009,chrome)

def mapped_panel(name,yz,mat,s,offset=.007):
    boundary=rounded_boundary(yz,.025,6)
    center=sum(boundary,Vector((0,0)))/len(boundary);n=len(boundary);vs=[]
    def point(p):
        y,z=p
        z=min(z,max(belt(y)+.006,roof(y)-.076))
        return (s*(canopy_x(y,z)+offset),y,z)
    vs.append(point(center))
    for k in range(1,10):
        t=k/9
        for p in boundary:vs.append(point(center+(p-center)*t))
    fs=[(0,1+j,1+(j+1)%n) for j in range(n)]
    for k in range(8):
        for j in range(n):
            a=1+k*n+j;b=1+k*n+(j+1)%n;fs.append((a,a+n,b+n,b))
    ob=mesh(name,vs,fs,mat)
    if sum(p.normal.x*s for p in ob.data.polygons)<0:
        for p in ob.data.polygons:p.flip()
        ob.data.update()
    tube(name+' rubber seal',[point(p) for p in boundary],.0035,trim,True)
    return ob

for s in [-1,1]:
    # Slim B-pillar, a separately traced rear-door pane and fixed C-quarter pane.
    front_window=[(.88,1.090),(.70,1.238),(.32,1.446),(.15,1.496),(-.225,1.506),(-.245,1.090)]
    rear_window=[(-.330,1.091),(-.31,1.506),(-.65,1.506),(-1.01,1.479),(-1.17,1.408),(-1.35,1.086)]
    quarter=[(-1.42,1.082),(-1.245,1.403),(-1.40,1.309),(-1.70,1.080)]
    if BINGO:
        front_window=[(.84,1.091),(.65,1.255),(.32,1.445),(.15,1.487),(-.23,1.507),(-.27,1.095)]
        rear_window=[(-.35,1.095),(-.34,1.517),(-.70,1.51),(-1.03,1.456),(-1.22,1.097)]
        quarter=[(-1.31,1.093),(-1.17,1.407),(-1.37,1.348),(-1.68,1.082)]
    mapped_panel('Front door curved glass',front_window,glass,s)
    mapped_panel('Rear door curved glass',rear_window,glass,s)
    mapped_panel('C pillar quarter glass',quarter,glass,s)
    # Sealed waist trim is independently surfaced and follows the arched belt.
    curve('Window lower bright strip',[sidept(1.0,1.079,s,.011),sidept(.35,1.088,s,.016),sidept(-.6,1.089,s,.016),sidept(-1.55,1.071,s,.010),sidept(-1.80,1.055,s,.004)],.0035,chrome)
    if not BINGO:
        # Blue A-pillar skin, preserving black B/C pillars and roof.
        pts=[(.99,1.082),(.77,1.205),(.43,1.383),(.26,1.445)]
        curve('Body coloured A pillar',[(s*(canopy_x(y,z)+.012),y,z) for y,z in pts],.014,paint)
        # Louver-like quarter trim from the 2025 manufacturer's source photo.
        for j in range(11):
            z=1.10+j*.020;y1=-1.39+(z-1.10)*.4;y2=-1.70+(z-1.10)*1.4
            tube('Quarter pillar fine louvers',[(s*(canopy_x(y1,z)+.010),y1,z),(s*(canopy_x(y2,z)+.010),y2,z)],.0016,trim)
    # Body seams use the curved side surface, preserving an even millimetric gap.
    seam_paths=[[(.99,1.08),(.93,.97),(.91,.73),(.88,.48),(.78,.272)], [(-.285,1.07),(-.30,.82),(-.325,.55),(-.37,.27)], [(-1.32,1.06),(-1.26,.94),(-1.13,.79),(-.985,.55)]]
    for k,p in enumerate(seam_paths):
        curve('Door panel gap '+str(k),[sidept(y,z,s,.0035) for y,z in p],.0026,gap,steps=12)
    # Recessed half-hidden handles: a dark inner pocket and upper painted paddle.
    for cy in [-.05,-1.10]:
        z=.957
        outline=[(cy-.117,z-.015),(cy-.104,z+.031),(cy+.095,z+.034),(cy+.115,z+.012),(cy+.09,z-.020),(cy-.08,z-.023)]
        panel('Half-hidden handle recess',[sidept(y,z,s,.008) for y,z in outline],gap,.003,(s,0,0))
        outline2=[(cy-.108,z+.013),(cy-.091,z+.029),(cy+.095,z+.030),(cy+.107,z+.018)]
        panel('Painted handle upper paddle',[sidept(y,z,s,.015) for y,z in outline2],paint,.012,(s,0,0))
    # Charging flap location differs by model: front wing on Bingo, rear on Geely.
    if (BINGO and s<0) or (not BINGO and s>0):
        cy=1.17 if BINGO else -1.70;cz=.966 if BINGO else .895
        points=[(cy-.095,cz-.072),(cy-.115,cz-.03),(cy-.11,cz+.067),(cy-.07,cz+.086),(cy+.085,cz+.087),(cy+.115,cz+.05),(cy+.108,cz-.056),(cy+.07,cz-.074)]
        curve('Charging flap outline',[sidept(y,z,s,.005) for y,z in points],.0025,gap,True)
    # Aerodynamic mirror: structural neck, black lower shell, painted cap, glass.
    cy=.77 if BINGO else .82
    neck=roundbox('Mirror support',(s*.850,cy,1.088),(.165,.155,.045),trim,.02)
    def mirror_shell(u,v,upper=False):
        theta=(math.pi*.50 if upper else math.pi)*u
        phi=math.tau*v
        return (s*(.961+.122*math.sin(theta)*math.cos(phi)),cy-.024+.080*math.sin(theta)*math.sin(phi),1.136+.060*math.cos(theta))
    surface('Mirror rounded lower housing',lambda u,v:mirror_shell(u,v),24,48,black)
    surface('Mirror smooth upper paint cap',lambda u,v:tuple(Vector(mirror_shell(u,v,True))+Vector((0,0,.002))),14,48,black if BINGO else paint)
    oval('Mirror reflective glass',(s*.960,cy-.104,1.137),(s*.090,0,0),(0,0,.038),glass,.004,(0,-1,0),20)
    curve('Mirror LED repeater',[(s*.874,cy+.027,1.13),(s*.94,cy+.068,1.137),(s*1.035,cy+.012,1.137)],.004,led)

# Front and rear screens lie on the continuous canopy, with separate seals.
def screen(name,ymin,ymax,mat):
    def fn(u,v):
        y=ymin+(ymax-ymin)*u
        half=(.677 if BINGO else .691)-.022*math.sin(math.pi*u)
        x=(2*v-1)*half
        y+=.065*(2*v-1)**2*math.sin(math.pi*u)
        return (x,y,canopy_z(x,y)+.012)
    surface(name,fn,36,54,mat,True)
    for edge in [lambda t:fn(0,t),lambda t:fn(1,t),lambda t:fn(t,0),lambda t:fn(t,1)]:tube(name+' perimeter seal',[edge(i/60) for i in range(61)],.006,trim)
screen('Curved front windshield',.35,1.018,glass)
screen('Curved rear hatch glass',-1.835,-1.43,glass)
for y in [-1.79,-1.75,-1.71,-1.67,-1.63,-1.59,-1.55,-1.51]:
    tube('Rear window heater trace',[(x,y,canopy_z(x,y)+.015) for x in [-.59+j*1.18/36 for j in range(37)]],.00075,brake)
for sign in [-1,1]:
    curve('Front wiper arm',[(sign*.055,.99,canopy_z(sign*.055,.99)+.024),(sign*.30,.947,canopy_z(sign*.30,.947)+.026),(sign*.58,.944,canopy_z(sign*.58,.944)+.027)],.007,trim)
curve('Rear wiper',[(.02,-1.83,canopy_z(.02,-1.83)+.02),(.32,-1.80,canopy_z(.32,-1.80)+.025),(.43,-1.77,canopy_z(.43,-1.77)+.025)],.007,trim)

# Hood seam follows the perimeter of the independently photographed bonnet.
hood=[(-.715,.99,1.087),(-.74,1.35,1.057),(-.67,1.75,.961),(-.47,1.94,.863),(0,1.998,.831),(.47,1.94,.863),(.67,1.75,.961),(.74,1.35,1.057),(.715,.99,1.087)]
if BINGO:hood=[(x*.94,y-.02,z-.007) for x,y,z in hood]
hoodtrace=spline([(x,y) for x,y,z in hood],12)
tube('Bonnet perimeter seam',[(x,side_y(y,hoodz(x,y)),hoodz(x,y)+.0035) for x,y in hoodtrace],.0026,gap)

def lamp_panel(name,outline,mat,bulge,normal):
    return panel(name,outline,mat,bulge,normal)

def scale_outline(outline,center,scale,offset):
    c=Vector(center);off=Vector(offset)
    return [c+(Vector(p)-c)*scale+off for p in outline]

if BINGO:
    for s in [-1,1]:
        c=Vector((s*.665,1.805,.914));u=Vector((s*.145,-.028,0));v=Vector((s*.007,-.137,.149));normal=u.cross(v).normalized()
        if normal.y<0:normal=-normal
        outline=[c+u*math.cos(2*math.pi*i/24)+v*math.sin(2*math.pi*i/24) for i in range(24)]
        lamp_panel('Oval headlamp black bezel',outline,gap,.018,normal)
        inner=scale_outline(outline,c,.927,normal*.010)
        lamp_panel('Oval glass headlamp cover',inner,lampglass,.031,normal)
        for a,b in [(.12,2.02),(2.18,4.04),(4.22,6.10)]:
            tube('Flying ring daytime light',arc_points(c+normal*.012,u*.785,v*.785,a,b,46),.010,led)
        cp=c+normal*.014
        oval('Ellipsoidal LED projector',cp,u*.43,v*.225,brake,.002,normal,16)
        oval('Projector optical lens',cp+normal*.004,u*.345,v*.175,optic,.004,normal,16)

else:
    for s in [-1,1]:
        outline=[(s*.494,1.97,.905),(s*.545,1.95,.856),(s*.70,1.88,.863),(s*.795,1.75,.895),(s*.816,1.66,.994),(s*.795,1.58,1.063),(s*.69,1.75,1.008),(s*.565,1.90,.943)]
        c=sum([Vector(p) for p in outline],Vector())/len(outline);normal=Vector((s*.17,.80,.48)).normalized()
        lamp_panel('Feather headlamp perimeter gasket',outline,gap,.004,normal)
        inner=scale_outline(outline,c,.94,normal*.007)
        lamp_panel('Feather smoked optical cover',inner,lampglass,.009,normal)
        ledline=[(s*.787,1.62,1.041),(s*.69,1.76,.996),(s*.566,1.91,.934),(s*.529,1.95,.900),(s*.571,1.935,.878),(s*.660,1.90,.881),(s*.738,1.82,.901)]
        curve('Feather continuous light guide',ledline,.008,led)
        cp=Vector((s*.707,1.83,.933))
        oval('Headlamp projector reflector',cp,(s*.054,-.018,0),(0,-.016,.033),brake,.003,normal,16)
        oval('Headlamp projector lens',cp+normal*.005,(s*.042,-.014,0),(0,-.012,.027),optic,.006,normal,16)
    # Individual letters are real geometry, not a texture baked over the body.
    font=bpy.data.curves.new('GEOME badge','FONT');font.body='G E O M E';font.size=.045;font.align_x='CENTER';font.extrude=.0008
    obj=bpy.data.objects.new('GEOME front wordmark',font);bpy.context.collection.objects.link(obj);obj.location=(0,1.992,hoodz(0,1.992)+.008);obj.rotation_euler=(math.pi/3,0,math.pi);obj.data.materials.append(chrome)

# Front lower intake/recess, enclosing a real dark cavity with blade inserts.
fy=L/2+.003
intake=[(-.655,fy-.072,.277),(-.48,fy-.013,.372),(0,fy,.395),(.48,fy-.013,.372),(.655,fy-.072,.277),(.50,fy-.026,.247),(-.50,fy-.026,.247)]
if BINGO:intake=[(-.69,fy-.073,.259),(-.68,fy-.068,.347),(-.52,fy-.020,.372),(.52,fy-.020,.372),(.68,fy-.068,.347),(.69,fy-.073,.259),(.53,fy-.018,.247),(-.53,fy-.018,.247)]
panel('Lower cooling inlet shadow',intake,gap,.005,(0,1,0),24)
curve('Front lower chrome blade',[(-.61,fy-.06,.285),(0,fy+.011,.289),(.61,fy-.06,.285)],.010 if BINGO else .006,chrome)
for j in range(15):
    x=-.52+j*1.04/14
    tube('Cooling inlet inner vertical vane',[(x,fy+.006,.262),(x,fy+.006,.348)],.004,trim)
if not BINGO:
    for s in [-1,1]:
        points=[(s*.796,1.93,.34),(s*.824,1.905,.41),(s*.827,1.904,.61),(s*.81,1.915,.659),(s*.80,1.922,.57)]
        panel('Front corner air curtain recess',points,gap,.002,(s*.3,1,0))
        curve('Air curtain outer chrome',[points[0],points[1],points[2],points[3]],.005,chrome)
        curve('Sculpted front apron crease',[(s*.37,fy+.005,.39),(s*.59,fy-.024,.45),(s*.81,1.914,.514)],.003,paint)
roundbox('Front number plate surround',(0,fy+.018,.428),(.465,.015,.15),gap,.012)
roundbox('Front number plate',(0,fy+.029,.434),(.435,.008,.125),material('Registration plate neutral',(.08,.13,.10),.1,.43),.008)

# Rear lamp types are different meshes, mapped around the hatch corners.
if BINGO:
    for s in [-1,1]:
        c=Vector((s*.670,-1.892,.887));u=Vector((s*.102,.026,0));v=Vector((0,.031,.146));n=Vector((s*.28,-.94,.08)).normalized()
        pts=[]
        for i in range(32):
            a=2*math.pi*i/32
            pts.append(c+u*(math.copysign(abs(math.cos(a))**.64,math.cos(a)))+v*(math.copysign(abs(math.sin(a))**.64,math.sin(a))))
        panel('Matrix rear lamp perimeter',pts,gap,.015,n)
        panel('Ruby matrix rear lens',scale_outline(pts,c,.91,n*.012),darkred,.020,n)
        tube('Vertical matrix red light surround',[Vector(p)+n*.039 for p in scale_outline(pts,c,.72,(0,0,0))],.008,red,True)
        for z in [-.053,0,.053]:
            oval('Matrix rear optical cell',c+Vector((0,0,z))+n*.052,u*.48,v*.10,red,.002,n,16)
else:
    for s in [-1,1]:
        pts=[(s*.40,-2.02,.970),(s*.62,-1.993,.993),(s*.815,-1.76,1.004),(s*.805,-1.852,.973),(s*.748,-1.994,.902),(s*.677,-2.032,.852),(s*.567,-2.045,.896)]
        n=Vector((s*.28,-.94,.14)).normalized();c=sum([Vector(p) for p in pts],Vector())/len(pts)
        panel('Light feather rear black surround',pts,gap,.003,n)
        panel('Light feather red lens',scale_outline(pts,c,.91,n*.005),darkred,.004,n)
        curve('Rear upper feather LED',[(s*.431,-2.027,.968),(s*.615,-2.006,.984),(s*.795,-1.802,.991)],.009,red)
        curve('Rear lower feather LED',[(s*.47,-2.035,.960),(s*.63,-2.038,.932),(s*.688,-2.011,.869),(s*.735,-2.001,.910)],.010,red)
        for j in range(4):
            curve('Rear LED feather vane',[(s*(.55+j*.041),-2.04+j*.014,.966-j*.007),(s*(.62+j*.030),-2.038+j*.015,.936-j*.010)],.005,red)
rear_y=-L/2-.004
for s in [-1,1]:
    curve('Rear hatch outer gap',[(s*.71,-1.87,1.06),(s*.70,rear_y,.94),(s*.60,rear_y,.62),(s*.47,rear_y,.52)],.0026,gap)
    panel('Rear bumper red reflector',[(s*.59,rear_y-.006,.45),(s*.79,rear_y+.045,.45),(s*.785,rear_y+.044,.481),(s*.60,rear_y-.006,.479)],reflector,.003,(0,-1,0))
    tube('Rear parking sensor ring',arc_points((s*.51,rear_y-.008,.65),(.014,0,0),(0,0,.014),count=32),.0018,gap,True)
panel('Rear lower bumper black valance',[(-.8,-1.933,.180),(-.81,-1.951,.393),(-.63,rear_y,.431),(0,rear_y,.442),(.63,rear_y,.431),(.81,-1.951,.393),(.8,-1.933,.180)],trim,.009,(0,-1,0),32)
roundbox('Rear plate surround',(0,rear_y-.016,.52 if BINGO else .327),(.475,.022,.15),gap,.012)
roundbox('Rear registration plate',(0,rear_y-.031,.522 if BINGO else .329),(.44,.006,.119),trim,.005)
if BINGO:
    for cy in [-1,1]:
        curve('Bingo hatch glass bright wing',[(cy*.71,-1.70,canopy_z(cy*.71,-1.70)+.015),(cy*.61,-1.827,canopy_z(cy*.61,-1.827)+.015),(0,-1.835,canopy_z(0,-1.835)+.015)],.006,chrome)
else:
    font=bpy.data.curves.new('Rear brand letters','FONT');font.body='G E O M E';font.size=.058;font.align_x='CENTER';font.extrude=.001
    obj=bpy.data.objects.new('Rear brand badge',font);bpy.context.collection.objects.link(obj);obj.location=(0,rear_y-.011,.766);obj.rotation_euler=(math.pi/2,0,0);obj.data.materials.append(chrome)

# Roof spoiler is a shaped, tapered 2D aerofoil with a moulded lower edge.
surface('Hatch roof spoiler',lambda u,v:((2*v-1)*.695,-1.27-.22*u,canopy_z((2*v-1)*.695,-1.27)+.008-.10*u+.010*math.sin(math.pi*u)),24,48,black,True)
curve('High mounted stop lamp',[(-.28,-1.499,1.417),(0,-1.504,1.424),(.28,-1.499,1.417)],.009,red)

# Wuling's current silver emblem is two swept wings and a central diamond.
# These facets trace the archived manufacturer close-up; five isolated generic
# lozenges do not reproduce the badge. No reference pixels enter the runtime.
if BINGO:
    for is_front,cz in [(True,.805),(False,.845)]:
        normal_sign=1 if is_front else -1
        left=[(-.106,.052),(-.062,.052),(-.020,-.017),(-.062,-.016)]
        outlines=[left,[(-x,z) for x,z in left],[(-.021,-.017),(0,.019),(.022,-.017),(0,-.052)]]
        for part,outline in enumerate(outlines):
            boundary=rounded_boundary(outline,.0012,3);count=len(boundary);rings=12
            center=sum(boundary,Vector((0,0)))/count
            def emblem_point(p,t):
                x,z=p;z+=cz
                return Vector((x,fascia_y(x,z,is_front)+normal_sign*(.004+.0015*(1-t)**2),z))
            vertices=[emblem_point(center,0)]
            for ring in range(1,rings+1):
                t=ring/rings
                vertices.extend(emblem_point(center+(p-center)*t,t) for p in boundary)
            faces=[(0,1+i,1+(i+1)%count) for i in range(count)]
            for ring in range(rings-1):
                for i in range(count):
                    a=1+ring*count+i;b=1+ring*count+(i+1)%count;faces.append((a,a+count,b+count,b))
            ob=mesh('Wuling silver emblem '+('front' if is_front else 'rear')+' curved facet '+str(part),vertices,faces,chrome)
            if sum(p.normal.y*normal_sign for p in ob.data.polygons)<0:
                for p in ob.data.polygons:p.flip()
                ob.data.update()
            tube('Wuling emblem polished edge',[emblem_point(p,1) for p in boundary],.00065,silver,True,sides=6)

front_prefix=('Lower cooling','Front lower chrome','Cooling inlet inner','Front corner air','Air curtain outer','Sculpted front apron','Wuling emblem diamond','Feather headlamp','Feather smoked','Feather continuous','Headlamp projector','Oval headlamp','Oval glass headlamp','Flying ring daytime','Ellipsoidal LED projector','Projector optical lens')
rear_prefix=('Rear bumper red','Rear parking sensor','Rear lower bumper','Rear hatch outer','Light feather rear','Rear upper feather','Rear lower feather','Rear LED feather','Matrix rear lamp','Ruby matrix','Vertical matrix','Matrix rear optical','Wuling rear emblem diamond')
for ob in list(bpy.context.scene.objects):
    if ob.type!='MESH':continue
    is_front=ob.name.startswith(front_prefix)
    is_rear=ob.name.startswith(rear_prefix)
    if not (is_front or is_rear):continue
    mat=ob.data.materials[0] if ob.data.materials else None
    depth=.010 if mat in [red,led,silver,chrome] else .007 if mat in [darkred,lampglass,optic,reflector] else .004
    if ob.name.startswith('Rear lower bumper'):depth=.025
    if ob.name.startswith(('Headlamp projector reflector','Ellipsoidal LED projector')):depth=.016
    if ob.name.startswith(('Headlamp projector lens','Projector optical lens')):depth=.023
    source=np.array([tuple(v.co) for v in ob.data.vertices])
    optical=ob.name.startswith(('Feather','Headlamp','Oval headlamp','Oval glass','Flying ring','Ellipsoidal','Projector optical','Light feather','Rear upper feather','Rear lower feather','Rear LED feather','Matrix rear lamp','Ruby matrix','Vertical matrix','Matrix rear optical'))
    optical_tube=ob.name.startswith(('Feather continuous','Flying ring','Rear upper feather','Rear lower feather','Rear LED feather','Vertical matrix'))
    center_xz=source[0,[0,2]]
    span_xz=np.maximum(.008,np.max(np.abs(source[:,[0,2]]-center_xz),axis=0))
    for vi,v in enumerate(ob.data.vertices):
        if optical_tube:
            block=source[(vi//8)*8:(vi//8+1)*8]
            cp=block.mean(axis=0);dv=source[vi]-cp
            v.co.y=fascia_y(float(cp[0]),float(cp[2]),is_front)+(depth if is_front else -depth)+float(dv[1])
            continue
        # A front optical surface cannot migrate behind the front axle when its
        # small lens bulge exceeds the unmodified bonnet by a few millimetres.
        if is_front and ob.name.startswith(('Feather','Headlamp','Oval headlamp','Oval glass','Flying ring','Ellipsoidal','Projector optical')):
            v.co.z=min(v.co.z,hoodz(v.co.x,1.46)-.004)
        radius2=float(np.sum(((source[vi,[0,2]]-center_xz)/span_xz)**2))
        panel_relief=.0025*max(0,1-radius2)**2 if optical else 0
        v.co.y=fascia_y(v.co.x,v.co.z,is_front)+(depth+panel_relief if is_front else -depth-panel_relief)
    ob.data.update()

# Number plates sit on their actual curved mounting face, including the plastic
# rear valance. Fixed bounding-box Y coordinates would leave them floating.
for ob in bpy.context.scene.objects:
    if ob.name=='GEOME front wordmark':
        ob.location=(0,fascia_y(0,.862,True)+.008,.862);ob.rotation_euler=(math.pi/2,0,math.pi)
    elif ob.name=='Front number plate surround':ob.location.y=fascia_y(0,ob.location.z,True)+.010
    elif ob.name=='Front number plate':ob.location.y=fascia_y(0,ob.location.z,True)+.021
    elif ob.name=='Rear plate surround':ob.location.y=fascia_y(0,ob.location.z,False)-(.038 if not BINGO else .016)
    elif ob.name=='Rear registration plate':ob.location.y=fascia_y(0,ob.location.z,False)-(.052 if not BINGO else .030)

# Seams are generated in the full curved domain. Reproject their dense vertices
# to eliminate interpolation segments disappearing into the rounded shoulder.
for ob in list(bpy.context.scene.objects):
    if ob.type=='MESH' and ob.name.startswith(('Door panel gap','Charging flap outline')):
        for v in ob.data.vertices:
            sign=1 if v.co.x>=0 else -1
            point=sidept(v.co.y,v.co.z,sign,.0045)
            v.co.x=point[0];v.co.z=point[2]
        ob.data.update()

# Four independent wheels: measured upright origins, child-only rolling geometry.
wheel_stats={}
for s in [-1,1]:
    for cy in [FRONT,REAR]:
        name=('F' if cy==FRONT else 'R')+('L' if s<0 else 'R')
        track=.760 if BINGO and cy==REAR else TRACK
        pivot=bpy.data.objects.new('Wheel_'+name,None);bpy.context.collection.objects.link(pivot);pivot.location=(s*track,cy,R)
        pivot['wheelPosition']=name;pivot['frontWheel']=cy==FRONT;pivot['wheelRadius']=R
        roll=bpy.data.objects.new('WheelRoll_'+name,None);bpy.context.collection.objects.link(roll);roll.parent=pivot
        before=set(bpy.context.scene.objects)
        tire_width=.195 if BINGO else .205
        profile=[(-tire_width*.45,.197),(-tire_width*.53,.225),(-tire_width*.54,R-.05),(-tire_width*.43,R-.011),(-tire_width*.30,R),(.0,R+.001),(tire_width*.30,R),(tire_width*.43,R-.011),(tire_width*.54,R-.05),(tire_width*.53,.225),(tire_width*.45,.197)]
        tire=lathe_x('Tyre carcass '+name,profile,rubber,112)
        # Fine circumferential tread channels are actual recessed bands between
        # shoulder blocks. The source model never supplies a warped wheel.
        for x in [-.060,-.021,.021,.060]:
            lathe_x('Tread circumferential groove',[(x-.0025,R-.001),(x-.0015,R+.001),(x+.0015,R+.001),(x+.0025,R-.001)],gap,112)
        for k in range(64):
            a=k*math.tau/64
            for stripe in [-1,1]:
                pts=[]
                for j in range(4):
                    x=stripe*(.027+j*.018);angle=a+(x-.027*stripe)*stripe*.35
                    pts.append((x,(R-.002)*math.cos(angle),(R-.002)*math.sin(angle)))
                tube('Fine lateral tyre sipe',pts,.0017,gap,sides=4)
        outward=s*(tire_width*.51+.003)
        lathe_x('Alloy wheel barrel',[(outward-s*.16,.197),(outward,.197),(outward+s*.006,.202),(outward+s*.013,.196),(outward+s*.008,.182)],black,96)
        for radius in [.203,.213,.270,R-.045]:
            tube('Sidewall concentric moulding',arc_points((outward,0,0),(0,radius,0),(0,0,radius),count=96),.0018,rubber,True,sides=5)
        # Disc and drilled rotor are visible through the clover wheel apertures.
        oval('Brake disc '+name,(outward-s*.047,0,0),(0,.163,0),(0,0,.163),brake,0,(s,0,0),24)
        for k in range(20):
            a=k*math.tau/20
            oval('Rotor drill', (outward-s*.046,.133*math.cos(a),.133*math.sin(a)),(0,.004,0),(0,0,.004),gap,0,(s,0,0),4)
        oval('Dark wheel cover backing',(outward,0,0),(0,.190,0),(0,0,.190),black,.003,(s,0,0),32)
        if BINGO:
            # Six individually curved petal blades, matching SGMW's 双生花瓣轮毂.
            for k in range(6):
                a=k*math.tau/6
                yz=[(.045,-.013),(.082,-.070),(.153,-.074),(.182,-.022),(.158,.051),(.071,.041)]
                pts=[(outward+s*.013,r*math.cos(a)-t*math.sin(a),r*math.sin(a)+t*math.cos(a)) for r,t in yz]
                panel('Bingo petal wheel blade',pts,silver,.010,(s,0,0),5)
        else:
            # Four convex satin quadrants separated by four black cardinal lobes.
            for k in range(4):
                a=k*math.pi/2
                yz=[(.028,.103),(.037,.143),(.067,.183),(.112,.159),(.157,.116),(.183,.068),(.139,.039),(.102,.027),(.062,.060)]
                pts=[(outward+s*.012,r*math.cos(a)-t*math.sin(a),r*math.sin(a)+t*math.cos(a)) for r,t in yz]
                panel('Starwish clover alloy quadrant',pts,silver,.003,(s,0,0),4)
                tube('Starwish diagonal satin split',[(outward+s*.018,.091*math.cos(a+math.pi/4),.091*math.sin(a+math.pi/4)),(outward+s*.018,.197*math.cos(a+math.pi/4),.197*math.sin(a+math.pi/4))],.0013,gap,sides=4)
        oval('Wheel centre cap',(outward+s*.017,0,0),(0,.038,0),(0,0,.038),black,.004,(s,0,0),18)
        for k in range(5):
            a=k*math.tau/5
            oval('Wheel fixing bolt',(outward+s*.019,.054*math.cos(a),.054*math.sin(a)),(0,.006,0),(0,0,.006),silver,.001,(s,0,0),6)
        wheel_objects=[o for o in bpy.context.scene.objects if o not in before]
        for o in wheel_objects:o.parent=roll
        cal=roundbox('Brake caliper '+name,(outward-s*.043,.113,.028),(.047,.068,.115),brake,.014);cal.parent=pivot
        wheel_stats[name]={'centerBlender':[s*track,cy,R],'radius':R,'triangles':triangle_count(wheel_objects),'components':len(wheel_objects)}

# Weld only the four adjoining structural skin boundaries. Matching station
# counts make every shared edge vertex coincide, so the surface normals are
# continuous rather than hiding a crack with two overlapping painted sheets.
skins=[o for o in bpy.context.scene.objects if o.name.startswith(('Compound curved door and fender skin','Continuous crowned bonnet and shoulder','Full width compound bumper and hatch skin'))]
skin_triangles=triangle_count(skins)
bpy.ops.object.select_all(action='DESELECT')
for o in skins:o.select_set(True)
bpy.context.view_layer.objects.active=skins[0];bpy.ops.object.join()
welded=bpy.context.object;welded.name=('Bingo Pro' if BINGO else 'Starwish')+' continuous exterior body shell'
bm=bmesh.new();bm.from_mesh(welded.data)
bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(welded.data);bm.free();welded.data.update()
assert triangle_count([welded])==skin_triangles,'Body welding changed the face count'

# Convert badge curves to mesh for deterministic glTF export, retain individual
# wheel hierarchies and never perform cross-wheel material joining.
for o in list(bpy.context.scene.objects):
    if o.type=='FONT':
        bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o;bpy.ops.object.convert(target='MESH')
objects=list(bpy.context.scene.objects)
for o in objects:
    if o.type=='MESH':o['sourceCar']=CAR;o['usage']='Reference-traced exterior; photographic review pending'
triangles=triangle_count(objects)
editable=ROOT/'assets/blender/tourism'/(CAR+'-exterior.blend')
if editable.exists():
    archive=OUT/(CAR+'-prior-source.blend')
    if not archive.exists():shutil.copy2(editable,archive)
bpy.ops.wm.save_as_mainfile(filepath=str(editable))
# Reduce draw calls strictly within each static body / upright / roll group.
# The editable .blend above retains named individual panels. No cross-hierarchy
# merge is allowed, so wheel rolling and steering never capture body geometry.
groups={}
for o in objects:
    if o.type=='MESH':groups.setdefault((o.parent,tuple(m.name for m in o.data.materials)),[]).append(o)
for (parent,mats),parts in groups.items():
    if len(parts)<2:continue
    names=[o.name for o in parts]
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts:o.select_set(True)
    bpy.context.view_layer.objects.active=parts[0]
    bpy.ops.object.join()
    merged=bpy.context.object
    merged.name=(parent.name if parent else 'Body')+' / '+mats[0]
    merged['sourceComponents']=names
assert triangle_count(bpy.context.scene.objects)==triangles
bpy.context.view_layer.update()
points=[o.matrix_world@v.co for o in bpy.context.scene.objects if o.type=='MESH' for v in o.data.vertices]
measured=[max(p[i] for p in points)-min(p[i] for p in points) for i in [1,0,2]]
bpy.ops.object.select_all(action='SELECT')
dest=OUT/(CAR+'.glb')
bpy.ops.export_scene.gltf(filepath=str(dest),export_format='GLB',use_selection=True,export_apply=True,export_extras=True,export_draco_mesh_compression_enable=True,export_draco_mesh_compression_level=6,export_draco_position_quantization=24,export_draco_normal_quantization=14)
record={'car':CAR,'generatorRevision':'compound-surfaces-20260909-r13','generatorSha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'helperSha256':hashlib.sha256((ROOT/'scripts/compact_exterior_helpers.py').read_bytes()).hexdigest(),'sourceYear':2026 if BINGO else 2025,'sourceType':'Independent reference-traced mesh surfaces','license':'Project-authored geometry; manufacturer reference photos retained for comparison, not embedded or relicensed','dimensionsM':[L,W,H],'measuredEnvelopeIncludingMirrorsM':measured,'wheelbaseM':WB,'tyre':('195/60 R16' if BINGO else '205/60 R16'),'wheelRig':wheel_stats,'runtimeTriangles':triangles,'rigFacesBefore':triangles,'rigFacesAfter':triangles,'runtimeBytes':dest.stat().st_size,'runtimeSha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'runtimeMeshCount':sum(o.type=='MESH' for o in bpy.context.scene.objects),'budgetBytes':10000000,'editable':str(editable.relative_to(ROOT)),'file':str(dest.relative_to(ROOT)),'geometryCompression':'Draco 24 bit positions / 14 bit normals','textureCount':0,'status':'candidate-awaiting-photographic-review','highFidelityAccepted':False,'features':['Model-specific nose contours and crowned hood with tangent-continuous rounded shoulders','Open wheel arch body skins and curved door bellies','Individual curved front, rear and quarter glass','Model-specific layered headlights and tail lights','Independent steering uprights and rolling tyre/alloy groups','Hood/hatch/door/charge-port seams','Half-hidden door handles, mirrors and repeaters','Wheel tread channels, sidewall rings, alloy petals, brake rotors','Body-specific bumpers, bright strips and roof spoiler'],'unverified':['Manufacturer surface scan/CAD not available; body surfaces reconstructed from photographs','No interior by approved scope; glazing is opaque','Exact lens optical microstructure and underbody mechanics not represented','Photographic exterior fidelity and real-time scene review not yet passed']}
raw=dest.read_bytes();gltf=json.loads(raw[20:20+struct.unpack_from('<I',raw,12)[0]])
nodes=gltf['nodes'];pivots=[n for n in nodes if 'wheelPosition' in n.get('extras',{})]
assert len(pivots)==4
for node in pivots:
    pos=node['extras']['wheelPosition'];source=wheel_stats[pos]['centerBlender'];actual=node['translation']
    assert max(abs(a-b) for a,b in zip(actual,[source[0],source[2],-source[1]]))<.00001
    assert any(nodes[c]['name']=='WheelRoll_'+pos for c in node['children'])
record['rigValidation']={'fourWheelPivots':True,'glTFOriginsMatchMeasuredAxles':True,'faceCountPreserved':True,'materialMergingRestrictedToSameParent':True,'minimumWheelTriangles':min(x['triangles'] for x in wheel_stats.values()),'browserDrivingVerified':False}
(OUT/'quality.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
shutil.copy2(pathlib.Path(__file__),OUT/('generator-'+record['generatorSha256'][:12]+'.py'))
shutil.copy2(ROOT/'scripts/compact_exterior_helpers.py',OUT/('helpers-'+record['helperSha256'][:12]+'.py'))
print('COMPACT_GEOMETRY_EXPORTED',json.dumps(record),flush=True)
if '--no-render' in sys.argv:sys.exit(0)

# Validate and render the exported runtime file itself, including Draco decode,
# exported normals/materials and wheel hierarchy; never substitute source-only views.
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(dest))
imported=list(bpy.context.scene.objects)
imported_pivots=[o for o in imported if 'wheelPosition' in o]
assert len(imported_pivots)==4
for o in imported_pivots:
    expected=Vector(wheel_stats[o['wheelPosition']]['centerBlender'])
    assert (o.matrix_world.translation-expected).length<.0001
imported_triangles=triangle_count(imported)
assert imported_triangles==triangles,(imported_triangles,triangles)
record['rigValidation']['exportedGlbReimported']=True
record['rigValidation']['exportedGlbTriangleCount']=imported_triangles
record['renderSource']='Re-imported exported compressed runtime GLB'
# Transform validation uses actual world vertices after Blender updates. Imported
# glTF nodes commonly retain QUATERNION mode; Euler assignment alone is no test.
def world_vertices(parts):
    results=[]
    for ob in parts:
        if ob.type!='MESH':continue
        co=np.empty(len(ob.data.vertices)*3,dtype=np.float64)
        ob.data.vertices.foreach_get('co',co)
        co=co.reshape((-1,3));mat=np.array(ob.matrix_world)
        results.append(co@mat[:3,:3].T+mat[:3,3])
    return np.concatenate(results) if results else np.zeros((0,3))
rig_members=set()
for upright in imported_pivots:rig_members.update([upright,*upright.children_recursive])
body_parts=[o for o in imported if o.type=='MESH' and o not in rig_members]
body_before=world_vertices(body_parts)
rig_motion={}
for upright in imported_pivots:
    tag=upright['wheelPosition'];rolling=next(o for o in upright.children if o.name=='WheelRoll_'+tag)
    upright.rotation_mode='XYZ';rolling.rotation_mode='XYZ'
    original_upright=upright.rotation_euler.copy();original_roll=rolling.rotation_euler.copy()
    wheel_parts=[o for o in rolling.children_recursive if o.type=='MESH']
    bpy.context.view_layer.update();baseline=world_vertices(wheel_parts)
    rolling.rotation_euler.x+=.73;bpy.context.view_layer.update()
    moved=np.linalg.norm(world_vertices(wheel_parts)-baseline,axis=1)>1e-5
    roll_fraction=float(np.mean(moved));assert roll_fraction>.98,(tag,'wheel rolling failed',roll_fraction)
    body_max_delta=float(np.max(np.linalg.norm(world_vertices(body_parts)-body_before,axis=1)))
    assert body_max_delta<1e-8,(tag,'body moved during rolling',body_max_delta)
    rolling.rotation_euler=original_roll;bpy.context.view_layer.update()
    steering_fraction=None
    if tag.startswith('F'):
        upright.rotation_euler.z+=.32;bpy.context.view_layer.update()
        moved=np.linalg.norm(world_vertices(wheel_parts)-baseline,axis=1)>1e-5
        steering_fraction=float(np.mean(moved));assert steering_fraction>.98,(tag,'front steering failed',steering_fraction)
        body_max_delta=max(body_max_delta,float(np.max(np.linalg.norm(world_vertices(body_parts)-body_before,axis=1))))
        assert body_max_delta<1e-8,(tag,'body moved during steering',body_max_delta)
        upright.rotation_euler=original_upright;bpy.context.view_layer.update()
    assert np.max(np.linalg.norm(world_vertices(wheel_parts)-baseline,axis=1))<1e-6,(tag,'restoration failed')
    rig_motion[tag]={'rollingMovedVertexFraction':roll_fraction,'steeringMovedVertexFraction':steering_fraction,'sampledVertices':len(baseline),'bodyMaxDisplacementM':body_max_delta,'rotationMode':'XYZ'}
record['rigValidation']['actualWorldVertexMotion']=rig_motion
record['rigValidation']['frontSteeringAndAllWheelRollingVerified']=True


scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=12 if '--draft' in sys.argv else 24;scene.cycles.use_denoising=True
scene.render.resolution_x=900 if '--draft' in sys.argv else 1100;scene.render.resolution_y=600 if '--draft' in sys.argv else 720;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
scene.world.use_nodes=True
nt=scene.world.node_tree;nt.nodes.clear();bg=nt.nodes.new('ShaderNodeBackground');bg.inputs['Color'].default_value=(.30,.33,.38,1);bg.inputs['Strength'].default_value=.45;output=nt.nodes.new('ShaderNodeOutputWorld');nt.links.new(bg.outputs['Background'],output.inputs['Surface'])
for loc,power,size in [((2,4,6),850,5),((-5,0,4),900,4),((2,-4,5),750,4)]:
    data=bpy.data.lights.new('Exterior softbox','AREA');data.energy=power;data.shape='DISK';data.size=size
    o=bpy.data.objects.new('Exterior softbox',data);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.01));floor=bpy.context.object;floor.data.materials.append(material('Review ground',(.08,.10,.12),0,.8))
camdata=bpy.data.cameras.new('Exterior review');cam=bpy.data.objects.new('Exterior review',camdata);bpy.context.collection.objects.link(cam);scene.camera=cam;camdata.lens=65
render_dir=OUT/('render-'+datetime.datetime.now().strftime('%Y%m%dT%H%M%S'));render_dir.mkdir()
selected_views=next((a.split('=',1)[1].split(',') for a in sys.argv if a.startswith('--views=')),None)
record['renderOriginals']={}
for view,loc in [('front',(5.7,7.4,2.65)),('side',(8.8,0,1.75)),('rear',(-5.7,-7.4,2.65)),('front-straight',(0,8.2,1.9))]:
    if selected_views and view not in selected_views:continue
    cam.location=loc;cam.rotation_euler=(Vector((0,0,.77))-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(render_dir/(view+'.png'));bpy.ops.render.render(write_still=True)
    record['renderOriginals'][view]=str((render_dir/(view+'.png')).relative_to(ROOT))
    # Latest comparison copies are replaceable; the timestamped render original
    # is never overwritten or deleted when the next iteration is built.
    shutil.copy2(render_dir/(view+'.png'),OUT/(view+'.png'))
if '--diffuse-diagnostic' in sys.argv:
    # Diagnostic only: identify whether an apparent triangular patch comes from
    # geometry or a clearcoat reflection. The exported runtime stays untouched.
    for mat in bpy.data.materials:
        if not any(token in mat.name.lower() for token in ['tail lamp','red tail']):continue
        if not mat.use_nodes:continue
        for node in mat.node_tree.nodes:
            if node.type=='BSDF_PRINCIPLED':
                for key,value in [('Metallic',0),('Roughness',.95),('Specular IOR Level',0),('Coat Weight',0),('Emission Strength',0)]:
                    for link in list(node.inputs[key].links):mat.node_tree.links.remove(link)
                    node.inputs[key].default_value=value
    cam.location=(-5.7,-7.4,2.65);cam.rotation_euler=(Vector((0,0,.77))-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(render_dir/'rear-optics-diffuse-diagnostic.png');bpy.ops.render.render(write_still=True)
    record['diagnosticRenders']={'rearOpticsDiffuse':str((render_dir/'rear-optics-diffuse-diagnostic.png').relative_to(ROOT)),'note':'Same reimported runtime geometry; rear optical specular and coat disabled for diagnosis only'}
(OUT/'quality.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print('COMPACT_REVIEW_RENDERED',CAR,flush=True)
