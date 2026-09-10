"""Metre-scale original reconstructions from the recorded vehicle/photo references.
Blender Z-up, front +Y. Run through blender-local.sh. No downloaded vehicle meshes.
"""
import bpy, math, pathlib, json, random
from mathutils import Vector
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'public/tour-models';OUT.mkdir(exist_ok=True)
SRC=ROOT/'assets/blender/tourism';SRC.mkdir(exist_ok=True)
THUMBS=ROOT/'public/cars';THUMBS.mkdir(exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
M={};parts={};roots=[];active=None;geo_offset=(0,0,0)
def material(name,color,metal=0,rough=.5,emission=0,coat=0):
    if isinstance(color,str):color=tuple((int(color[i:i+2],16)/255)**2.2 for i in [1,3,5])
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough;p.inputs['Coat Weight'].default_value=coat
    p.inputs['Coat Roughness'].default_value=.13
    if emission:p.inputs['Emission Color'].default_value=(*color,1);p.inputs['Emission Strength'].default_value=emission
    M[name]=m
for args in [('glass','#16232a',.10,.19,0,.7),('black','#181b1e',.15,.3),('rubber','#202122',0,.94),('chrome','#bac4c9',.9,.2),('rim','#697078',.85,.26),('white','#f5eee0',.15,.3,1.8),('red','#bb101c',.15,.28,1),('stone','#b6ac96',0,.88),('limestone','#d6cbbb',0,.81),('roof','#527e72',.6,.49),('bronze','#a56f7b',.45,.42),('towerglass','#6f939f',.55,.22),('blueglass','#819aa9',.6,.18),('window','#3b4749',.28,.23),('steel','#687573',.75,.38),('bark','#59483b',0,.92),('leaf','#416349',0,.94),('leaflight','#648059',0,.96),('plate','#80b88a',.1,.4)]:material(*args)
def start(name):
    global active,parts
    flush();active=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(active);roots.append(active);parts={}
def geo(vertices,faces,mat,smooth=False,group='static'):
    key=(mat,smooth,group);v,f=parts.setdefault(key,([],[]));n=len(v);v.extend(tuple(p[k]+geo_offset[k] for k in range(3)) for p in vertices);f.extend(tuple(n+i for i in face) for face in faces)
def flush():
    global parts
    if active is None:return
    for (mat,smooth,group),(vs,fs) in parts.items():
        data=bpy.data.meshes.new(active.name+'-'+mat);data.from_pydata(vs,[],fs);data.update()
        obj=bpy.data.objects.new(group+'-'+mat,data);bpy.context.collection.objects.link(obj);obj.parent=active;data.materials.append(M[mat])
        for p in data.polygons:p.use_smooth=smooth
    parts={}
def box(p,s,m,rotation=0):
    x,y,z=p;a,b,c=[v/2 for v in s];co=math.cos(rotation);si=math.sin(rotation)
    v=[(x+i*co-j*si,y+i*si+j*co,z+k) for i,j,k in [(-a,-b,-c),(a,-b,-c),(a,b,-c),(-a,b,-c),(-a,-b,c),(a,-b,c),(a,b,c),(-a,b,c)]]
    geo(v,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],m)
def rod(a,b,r,m,n=12,r2=None):
    a=Vector(a);b=Vector(b);q=(b-a).to_track_quat('Z','Y');v=[]
    for center,rad in [(a,r),(b,r if r2 is None else r2)]:
        for i in range(n):v.append(tuple(center+q@Vector((rad*math.cos(i*math.tau/n),rad*math.sin(i*math.tau/n),0))))
    geo(v,[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],m,True)
def sphere(p,r,m,scale=(1,1,1),segments=36,rings=18):
    v=[]
    for j in range(rings+1):
        a=math.pi*j/rings
        for i in range(segments):
            b=i*math.tau/segments;v.append(tuple(p[k]+r*scale[k]*c for k,c in enumerate((math.sin(a)*math.cos(b),math.sin(a)*math.sin(b),math.cos(a)))))
    geo(v,[(j*segments+i,j*segments+(i+1)%segments,(j+1)*segments+(i+1)%segments,(j+1)*segments+i) for j in range(rings) for i in range(segments)],m,True)
def line(points,r,m,n=8):
    for a,b in zip(points,points[1:]):rod(a,b,r,m,n)
def torus(center,major,minor,m,axis='X',n=56,k=12,stretch=1):
    v=[]
    for i in range(n):
        a=i*math.tau/n
        for j in range(k):
            b=j*math.tau/k;rr=major+minor*math.cos(b)
            p=(minor*math.sin(b)*stretch,rr*math.sin(a),rr*math.cos(a)) if axis=='X' else (rr*math.cos(a),rr*math.sin(a),minor*math.sin(b))
            v.append(tuple(center[t]+p[t] for t in range(3)))
    geo(v,[(i*k+j,((i+1)%n)*k+j,((i+1)%n)*k+(j+1)%k,i*k+(j+1)%k) for i in range(n) for j in range(k)],m,True)
def patch(points,m):geo(points,[tuple(range(len(points)))],m)
def smooth_rect_front(cx,y,cz,w,h,m,slant=0,oval=False):
    pts=[]
    for i in range(32):
        a=i*math.tau/32;xx=math.cos(a);zz=math.sin(a)
        power=1 if oval else .42
        x=math.copysign(abs(xx)**power,xx)*w/2;z=math.copysign(abs(zz)**power,zz)*h/2
        pts.append((cx+x,y-abs(x)*.035,cz+z+slant*x))
    patch(pts,m);return pts

cars=json.loads((ROOT/'src/tour/cars.json').read_text())
profiles={
 'starwish':(.27,.36,.62,.86,'teardrop',5), 'leap-a10':(.24,.39,.60,.94,'kidney',10),
 'model-y':(.28,.38,.67,.91,'bar',7),'yuan-up':(.26,.40,.63,.97,'blade',5),
 'model-3':(.32,.33,.71,.80,'slit',10),'qiyuan-q05':(.25,.39,.63,.90,'split',5),
 'li-i6':(.25,.40,.68,.92,'li',10),'dolphin':(.24,.37,.63,.90,'dolphin',5),
 'su7':(.34,.33,.70,.80,'su7',5),'bingo-pro':(.25,.36,.61,.91,'round',6)}
for car in cars:
    name=car['id'];start(name);material('paint-'+name,car['color'],.5,.24,0,1)
    paint='paint-'+name;L,W,H=[n/1000 for n in car['dimensions']];WB=car['wheelbase']/1000
    front,back,belt,roofwide,lamp,spokes=profiles[name];tire=car['tire'].replace(' ','').split('R');twidth,aspect=[float(s) for s in tire[0].split('/')]
    R=int(tire[1])*.0254/2+twidth/1000*aspect/100;rimR=int(tire[1])*.0254/2;track=W/2-twidth/2200
    # A continuous 96-station compound curved shell, with true wheel openings.
    rows=96;cols=48;vs=[];faces=[];zlo=.22;ztop=H*belt
    for i in range(rows+1):
        t=i/rows;y=(t-.5)*L;end=abs(2*t-1);half=W/2*(1-.11*end**5)
        for j in range(cols):
            a=j*math.tau/cols;xx=math.copysign(abs(math.cos(a))**.36,math.cos(a));zz=math.copysign(abs(math.sin(a))**.62,math.sin(a))
            z=zlo+(ztop-zlo)*(zz+1)/2;z-=.13*end**5*(zz+1)/2
            vs.append((half*xx,y,z))
    for i in range(rows):
        for j in range(cols):faces.append((i*cols+j,i*cols+(j+1)%cols,(i+1)*cols+(j+1)%cols,(i+1)*cols+j))
    faces.extend([tuple(range(cols-1,-1,-1)),tuple(range(rows*cols,(rows+1)*cols))]);faces=[tuple(reversed(f)) for f in faces];geo(vs,faces,paint,True,'body');flush()
    body=next(o for o in active.children if o.name.startswith('body-'))
    for y in [-WB/2,WB/2]:
        bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=R+.052,depth=W+1,location=(0,y,R+.005),rotation=(0,math.pi/2,0));cut=bpy.context.object
        mod=body.modifiers.new('Wheel opening','BOOLEAN');mod.operation='DIFFERENCE';mod.object=cut;bpy.context.view_layer.objects.active=body
        bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cut,do_unlink=True)
    mod=body.modifiers.new('Panel edge radii','BEVEL');mod.width=.016;mod.segments=2;bpy.context.view_layer.objects.active=body;bpy.ops.object.modifier_apply(modifier=mod.name)
    # Cabin glass follows a per-model fastback or upright silhouette.
    rear=-L*back;frontbase=L*front;rearroof=-L*(.18 if name not in ['model-y','model-3','su7'] else .12);frontroof=L*.085
    points=[(rear,ztop-.03,.91),(rearroof,H*.96,.77),(0,H,.76),(frontroof,H*.97,.76),(frontbase,ztop,.88)]
    v=[]
    for y,z,w in points:
        for j in range(17):
            t=j/16*2-1;v.append((t*W/2*w,y,z-.10*abs(t)**2))
    geo(v,[(i*17+j,i*17+j+1,(i+1)*17+j+1,(i+1)*17+j) for i in range(4) for j in range(16)],'glass',True)
    for side in [-1,1]:
        lower=[(side*W*.46,rear,ztop-.04),(side*W*.46,frontbase,ztop-.025)]
        upper=[(side*W*.385,rearroof,H*.96-.10),(side*W*.38,frontroof,H*.97-.10)]
        patch([lower[0],lower[1],upper[1],upper[0]],'glass')
        patch([lower[0],(side*W*.462,rear+.20,ztop-.03),(side*W*.388,rearroof+.12,H*.96-.105),upper[0]],paint)
        line([lower[0],upper[0],upper[1],lower[1]],.026,paint)
        line(lower,.019,'chrome' if name in ['li-i6','dolphin'] else 'black')
        rod((side*W*.455,-L*.04,ztop),(side*W*.38,-L*.04,H-.1),.03,'black')
        # Door shut lines and sculpted flush/conventional handles.
        for y in [-L*.06,-L*.30,frontbase]:line([(side*W*.494,y,.35),(side*W*.501,y,ztop-.06)],.0045,'black',6)
        for y in [-L*.23,L*.09]:box((side*W*.504,y,ztop-.08),(.022,.15,.025),paint if name in ['su7','model-y','model-3','li-i6'] else 'chrome')
        sphere((side*(W/2+.055),frontbase-.14,ztop+.075),1,paint,(.12,.14,.065),24,12)
        rod((side*W*.43,frontbase-.12,ztop+.02),(side*(W/2+.04),frontbase-.14,ztop+.06),.025,'black')
        rod((side*W*.48,-WB*.37,.265),(side*W*.48,WB*.37,.265),.037,'black')
    # Panoramic roof or contrasting painted roof, central roof panel.
    if name not in ['model-y','model-3','su7','li-i6']:
        roof=[]
        for i in range(13):
            y=rearroof+(frontroof-rearroof)*i/12
            for j in range(13):
                x=(j/12*2-1)*W*.375;roof.append((x,y,H-.09*(abs(x)/(W*.375))**2+.008))
        geo(roof,[(i*13+j,i*13+j+1,(i+1)*13+j+1,(i+1)*13+j) for i in range(12) for j in range(12)],'black' if name in ['bingo-pro','starwish','yuan-up','leap-a10'] else paint,True)
    # Wheels: tread volume, sidewall, brake disc, individual alloy spokes.
    for side in [-1,1]:
        for y in [-WB/2,WB/2]:
            x=side*track;torus((x,y,R),R-twidth/2000,twidth/2000,'rubber',stretch=.9)
            rod((x-side*.035,y,R),(x+side*.09,y,R),rimR*.90,'rim',48)
            torus((x+side*.105,y,R),rimR*.94,.014,'chrome')
            for k in range(spokes):
                a=k*math.tau/spokes
                rod((x+side*.11,y+math.sin(a)*rimR*.16,R+math.cos(a)*rimR*.16),(x+side*.115,y+math.sin(a+.16)*rimR*.88,R+math.cos(a+.16)*rimR*.88),.031 if spokes<8 else .017,'chrome',6)
            rod((x+side*.10,y,R),(x+side*.13,y,R),.055,'black',24)
            for k in range(5):
                a=k*math.tau/5;sphere((x+side*.135,y+math.sin(a)*.033,R+math.cos(a)*.033),.009,'chrome',segments=8,rings=6)
    fy=L/2+.028;ry=-L/2-.028;hz=ztop-.29
    smooth_rect_front(0,fy,.34,W*.57,.14,'black')
    for side in [-1,1]:
        x=side*W*.31
        if lamp=='round':
            sphere((x,fy+.005,hz),1,'black',(.19,.03,.21));p=smooth_rect_front(x,fy+.008,hz,.32,.35,'glass',oval=True);line(p+[p[0]],.009,'white');sphere((x,fy+.014,hz),.067,'white',(1,.24,1))
        elif lamp in ['teardrop','su7']:
            pts=[(x-side*.17,fy+.005,hz-.04),(x+side*.17,fy+.005,hz+.16),(x+side*.19,fy+.005,hz-.06),(x+side*.06,fy+.009,hz-.115),(x-side*.17,fy+.005,hz-.04)]
            patch(pts,'black');line(pts,.008,'white');rod((x-side*.085,fy+.011,hz-.04),(x+side*.1,fy+.011,hz+.015),.023,'white')
            if lamp=='su7':rod((x,fy+.012,hz-.05),(x,fy+.012,hz+.08),.009,'white')
        else:
            w=.40 if lamp!='li' else .18;h=.10 if lamp in ['slit','blade','bar','dolphin'] else .16
            p=smooth_rect_front(x,fy+.005,hz,w,h,'black',side*.2,oval=lamp=='kidney');line(p+[p[0]],.006,'white')
            if lamp in ['split','li']:smooth_rect_front(side*W*.37,fy-.001,hz-.25,.18,.25,'black');smooth_rect_front(side*W*.37,fy+.006,hz-.26,.11,.08,'white')
        rearshape=smooth_rect_front(x,ry,ztop-.28,.30,.21 if name in ['leap-a10','bingo-pro'] else .09,'black',-side*.12,oval=name=='starwish')
        line(rearshape+[rearshape[0]],.015,'red')
    if lamp in ['bar','li','split','blade','dolphin']:
        smooth_rect_front(0,fy+.006,hz+.07,W*.82,.065,'black');rod((-W*.40,fy+.015,hz+.075),(W*.40,fy+.015,hz+.075),.010,'white')
    if name in ['model-y','yuan-up','qiyuan-q05','li-i6','dolphin','su7']:rod((-W*.39,ry-.012,ztop-.28),(W*.39,ry-.012,ztop-.28),.016,'red')
    box((0,fy+.012,.49),(.44,.018,.14),'plate');box((0,ry-.012,.53),(.44,.018,.14),'plate')
    # Dashboard, four seats and steering wheel are geometric, not texture decals.
    box((0,frontbase-.09,ztop-.10),(W*.72,.28,.17),'black')
    for x in [-W*.22,W*.22]:
        for y in [-L*.20,L*.01]:
            sphere((x,y,H*.40),1,'black',(.23,.25,.17),20,12);sphere((x,y-.11,H*.59),1,'black',(.21,.09,H*.16),20,12)
    torus((-W*.22,frontbase-.28,ztop),.145,.016,'black',axis='Z')
    if name in ['model-y','model-3','li-i6','su7']:box((0,frontbase-.18,ztop-.08),(.31,.025,.14),'black')

# Recognisable architecture uses the recorded WGS84 positions in city.ts.
def facade(w,d,h,floors,mat='limestone',columns=False):
    box((0,0,h/2),(w,d,h),mat)
    for z in [1,h*.19,h*.9,h]:box((0,0,z),(w+1,d+1,.65),'stone')
    spacing=4.2
    for side in [-1,1]:
        for i in range(max(2,int(w/spacing))):
            x=-w/2+spacing/2+i*(w-spacing)/max(1,int(w/spacing)-1)
            for j in range(floors):
                z=3+(h-6)*j/max(1,floors-1);box((x,side*(d/2+.04),z),(1.7,.12,2.4),'window')
                box((x,side*(d/2+.13),z-1.25),(2.0,.26,.15),'stone')
        if columns:
            for i in range(8):
                x=-w*.39+i*w*.78/7;rod((x,side*(d/2+1.2),2),(x,side*(d/2+1.2),11),.65,'limestone',20)
                box((x,side*(d/2+1.2),11),(1.55,1.55,.5),'limestone')

    for side in [-1,1]:
        count=max(2,int(d/4.2))
        for i in range(count):
            y=-d/2+2.1+i*(d-4.2)/max(1,count-1)
            for j in range(floors):
                z=3+(h-6)*j/max(1,floors-1);box((side*(w/2+.04),y,z),(.12,1.7,2.4),'window')
                box((side*(w/2+.13),y,z-1.25),(.26,2,.15),'stone')
        for j in range(1,floors):
            z=3+(h-6)*j/max(1,floors-1)-1.6
            box((side*(w/2+.11),0,z),(.22,d,.15),'limestone')
    # Roof parapets, cornices and shallow window framing preserve facade depth.
    for side in [-1,1]:
        box((0,side*(d/2-.18),h+.5),(w,.36,1),'stone')
        box((side*(w/2-.18),0,h+.5),(.36,d,1),'stone')

start('peace-hotel');geo_offset=(0,-63,0);facade(52,100,40,9,'limestone');geo_offset=(0,0,0);facade(55,53,43,9,'limestone');facade(25,27,61,12,'limestone')
box((0,0,63),(21,22,4),'stone')
geo([(-11,-11,65),(11,-11,65),(11,11,65),(-11,11,65),(0,0,82)],[(0,1,4),(1,2,4),(2,3,4),(3,0,4)],'roof');rod((0,0,82),(0,0,87),.15,'bronze')
start('customs-house');facade(66,47,34,7,'stone',True);box((0,0,46),(15,15,26),'limestone');box((0,0,63),(12,12,14),'stone')
for side in [-1,1]:
    smooth_rect_front(0,side*7.57,57,8,8,'limestone',oval=True)
    for a in range(12):
        t=a*math.tau/12;rod((math.sin(t)*2.9,side*7.67,57+math.cos(t)*2.9),(math.sin(t)*3.25,side*7.67,57+math.cos(t)*3.25),.08,'black')
    rod((0,side*7.70,57),(0,side*7.70,59.5),.10,'black');rod((0,side*7.70,57),(2.0,side*7.70,56),.11,'black')
box((0,0,72),(14,14,2),'stone');rod((0,0,73),(0,0,79),4,'roof',8,r2=2);rod((0,0,79),(0,0,86),.14,'bronze')
start('hsbc-bund');facade(82,50,30,6,'limestone',True);rod((0,0,30),(0,0,40),11,'stone',36)
sphere((0,0,40),12,'roof',(1,1,.65),48,20);rod((0,0,46),(0,0,52),2,'stone');sphere((0,0,52),2.5,'roof');rod((0,0,54),(0,0,60),.13,'bronze')
start('bank-china');facade(45,42,64,15,'stone');box((0,0,66),(39,36,3),'stone');box((0,0,69),(34,32,2),'roof')
start('palace-hotel');facade(50,45,32,7,'limestone',True)
for x in [-19,19]:sphere((x,14,35),4,'roof',(1,1,1.1));rod((x,14,38),(x,14,42),.13,'bronze')
start('bund-heritage');facade(34,28,30,7,'stone',True)
start('pearl');
for a in [0,math.tau/3,math.tau*2/3]:
    x=math.cos(a)*9;y=math.sin(a)*9;rod((x*3,y*3,0),(x,y,98),3.5,'limestone',28);rod((x,y,35),(x,y,290),2.6,'limestone',28)
rod((0,0,25),(0,0,350),5,'limestone',36)
for z,r in [(95,25),(263,22.5),(350,7.5)]:
    sphere((0,0,z),r,'bronze',segments=56,rings=28)
    for dz in [-.65,-.35,0,.35,.65]:torus((0,0,z+dz*r),r*math.sqrt(1-dz*dz)+.07,.65,'towerglass',axis='Z',n=64,k=8)
rod((0,0,355),(0,0,410),1.6,'limestone',20,r2=.6);rod((0,0,410),(0,0,468),.42,'steel',12,r2=.12)
start('shanghai-tower');n=72;floors=128;v=[]
for j in range(floors+1):
    t=j/floors
    for k in range(n):
        a=k*math.tau/n+t*math.pi*2/3;r=(55*(1-.61*t))*(1+.12*math.cos(3*k*math.tau/n));v.append((r*math.cos(a),r*math.sin(a),t*632))
geo(v,[(j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k) for j in range(floors) for k in range(n)],'towerglass',True)
for k in range(0,n,3):line([v[j*n+k] for j in range(0,floors+1,4)],.14,'chrome',6)
for j in range(0,floors+1,2):line([v[j*n+k] for k in range(n)]+[v[j*n]],.13,'chrome',6)
start('financial-center');
v=[]
for z,w,d in [(0,58,48),(430,38,39)]:v.extend([(-w/2,-d/2,z),(w/2,-d/2,z),(w/2,d/2,z),(-w/2,d/2,z)])
geo(v,[(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],'blueglass')
for side in [-1,1]:box((side*15.5,0,455),(7,39,50),'blueglass')
box((0,0,486),(38,39,12),'blueglass')
for z in range(4,431,4):
    w=58-20*z/430;d=48-9*z/430;box((0,-d/2-.02,z),(w,.12,.10),'chrome')
for side in [-1,1]:rod((side*29,-24,0),(side*19,-19.5,492),.20,'chrome')
start('jinmao');h=0
for i in range(15):
    height=32 if i<5 else 18;w=52-i*2.25;box((0,0,h+height/2),(w,w,height),'blueglass')
    for z in range(0,height,3):box((0,0,h+z),(w+.6,w+.6,.26),'chrome')
    for side in [-1,1]:
        for x in [-w*.39,0,w*.39]:box((x,side*w/2,h+height/2),(.5,.75,height),'chrome')
    h+=height;box((0,0,h),(w+1.8,w+1.8,.85),'chrome')
rod((0,0,h),(0,0,406),5,'steel',8,r2=1);rod((0,0,406),(0,0,420.5),.45,'chrome',12,r2=.1)
start('waibaidu-bridge');geo_offset=(0,0,-2.8)
for side in [-1,1]:
    for segment in [-1,1]:
        center=segment*26
        pts=[(side*10.5,center+y,5+5*(1-(y/26)**2)) for y in range(-26,27,2)]
        line(pts,.27,'steel');line([(side*10.5,center-26,3),(side*10.5,center+26,3)],.23,'steel')
        for y in range(-26,26,6):
            z=5+5*(1-(y/26)**2);rod((side*10.5,center+y,3),(side*10.5,center+y,z),.17,'steel');rod((side*10.5,center+y,3),(side*10.5,center+y+6,5+5*(1-((y+6)/26)**2)),.14,'steel')
for y in range(-50,51,12):rod((-10.5,y,7),(10.5,y,7),.16,'steel')
geo_offset=(0,0,0)
start('plane-tree');rod((0,0,0),(0,0,5.8),.25,'bark',16,r2=.11)
rng=random.Random(121)
# Branching leaf sprays with folded, pointed leaf surfaces. No spherical crowns.
for i in range(28):
    a=i*2.399;r=rng.uniform(1.3,3.5);end=Vector((math.cos(a)*r,math.sin(a)*r,rng.uniform(6.0,9.5)))
    base=Vector((0,0,rng.uniform(3.5,5.7)));rod(base,end,.065,'bark',8,r2=.017)
    for spray in range(5):
        tip=end+Vector((rng.uniform(-1.1,1.1),rng.uniform(-1.1,1.1),rng.uniform(-.5,.7)))
        rod(end,tip,.016,'bark',5,r2=.005)
        for leaf in range(16):
            center=tip+Vector((rng.uniform(-.65,.65),rng.uniform(-.65,.65),rng.uniform(-.45,.45)))
            angle=rng.random()*math.tau;length=rng.uniform(.15,.31);width=length*.6
            tangent=Vector((math.cos(angle),math.sin(angle),rng.uniform(-.65,.65)));across=Vector((-math.sin(angle),math.cos(angle),.10))
            verts=[tuple(center-tangent*length),tuple(center-across*width),tuple(center+Vector((0,0,.05))),tuple(center+across*width),tuple(center+tangent*length)]
            geo(verts,[(0,1,2),(0,2,3),(1,4,2),(2,4,3)],'leaf' if rng.random()<.65 else 'leaflight')
start('streetlamp');rod((0,0,0),(0,0,9),.10,'steel',12,r2=.055);rod((0,0,9),(0,2,9.3),.065,'steel');box((0,2.25,9.3),(.40,1,.10),'steel');box((0,2.25,9.24),(.32,.7,.03),'white')
start('river-railing');
for y in [-1.5,1.5]:rod((0,y,0),(0,y,1.12),.065,'stone')
for z in [.30,.66,1.1]:rod((0,-1.5,z),(0,1.5,z),.035,'steel')
flush()

# Export independent, material-batched GLBs. Every mesh remains editable in the blend.
manifest=[]
for root in roots:
    bpy.ops.object.select_all(action='DESELECT');root.select_set(True)
    for o in root.children_recursive:o.select_set(True)
    path=OUT/(root.name+'.glb');bpy.context.view_layer.objects.active=root
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_apply=True,export_extras=True)
    meshes=[o for o in root.children_recursive if o.type=='MESH'];tri=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes)
    manifest.append({'id':root.name,'bytes':path.stat().st_size,'triangles':tri,'meshes':len(meshes),'source':'scripts/build_tourism_models.py'})
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
for i,r in enumerate(roots):
    r.location=(i*100,0,0)
    for o in [r,*r.children_recursive]:o.hide_render=True
bpy.ops.wm.save_as_mainfile(filepath=str(SRC/'shanghai-tours.blend'))
# A uniform studio render exposes the geometry of all ten selectable cars.
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
scene.render.resolution_x=720;scene.render.resolution_y=440;scene.render.resolution_percentage=100
scene.world.color=(.35,.35,.35);scene.render.image_settings.file_format='PNG';scene.render.film_transparent=True
for location,power,size in [((1,3,7),1800,5),((-5,-2,4),1400,4),((4,-3,5),1800,3)]:
    data=bpy.data.lights.new('Studio softbox','AREA');data.energy=power;data.shape='DISK';data.size=size
    o=bpy.data.objects.new('Studio softbox',data);bpy.context.collection.objects.link(o);o.location=location;o.rotation_euler=(-o.location).to_track_quat('-Z','Y').to_euler()
camdata=bpy.data.cameras.new('Car portrait');cam=bpy.data.objects.new('Car portrait',camdata);bpy.context.collection.objects.link(cam);scene.camera=cam;cam.location=(6.3,8,4.0);cam.rotation_euler=(Vector((0,0,.8))-cam.location).to_track_quat('-Z','Y').to_euler();camdata.lens=54
for i,car in enumerate(cars):
    root=roots[i];root.location=(0,0,0)
    for o in [root,*root.children_recursive]:o.hide_render=False
    scene.render.filepath=str(THUMBS/(car['id']+'.png'));bpy.ops.render.render(write_still=True)
    for o in [root,*root.children_recursive]:o.hide_render=True
    root.location=(i*100,0,0)
print('TOURISM_MODELS_COMPLETE',len(manifest),sum(m['bytes'] for m in manifest),flush=True)
