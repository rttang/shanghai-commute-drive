"""Original, reproducible game models. Blender Z-up, front +Y; glTF Y-up."""
import bpy, math, json, pathlib
from mathutils import Vector
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'public/models'; OUT.mkdir(parents=True,exist_ok=True)
SOURCE=ROOT/'assets/blender/commute'; SOURCE.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
M={}
def mat(name,color,metal=0,rough=.6,emission=0):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*color,1)
    bs.inputs['Metallic'].default_value=metal;bs.inputs['Roughness'].default_value=rough
    if emission:bs.inputs['Emission Color'].default_value=(*color,1);bs.inputs['Emission Strength'].default_value=emission
    M[name]=m;return m
for name,col,metal,rough,emit in [
 ('ink',(.055,.095,.12),.15,.55,0),('ivory',(.81,.77,.63),.25,.35,0),
 ('teal',(.12,.34,.33),.35,.32,0),('taxi',(.59,.72,.63),.3,.35,0),
 ('glass',(.13,.23,.26),.55,.23,0),('chrome',(.62,.67,.66),.7,.28,0),
 ('rubber',(.035,.045,.047),0,.9,0),('headlight',(1,.84,.52),.2,.2,1.5),
 ('taillight',(.7,.07,.035),.1,.3,.65),('paper',(.72,.69,.60),0,.8,0),
 ('wall',(.5,.53,.5),0,.85,0),('roof',(.26,.32,.29),.15,.65,0),
 ('window',(.18,.3,.31),.3,.4,0),('leaf',(.18,.31,.24),0,.9,0),
 ('bark',(.27,.2,.14),0,.9,0),('copper',(.62,.37,.25),.55,.4,0)]: mat(name,col,metal,rough,emit)
roots=[];active=None
def finish(o,name,material,bevel=0):
    o.name=name;o.data.materials.append(M[material]);o.parent=active
    if bevel:
        mod=o.modifiers.new('Manufactured edges','BEVEL');mod.width=bevel;mod.segments=2
        bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=mod.name)
    return o
def cube(n,p,s,m,b=0):
    bpy.ops.mesh.primitive_cube_add(size=1,location=p);o=bpy.context.object;o.scale=s
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return finish(o,n,m,b)
def cyl(n,p,r,depth,m,verts=20):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=depth,location=p)
    return finish(bpy.context.object,n,m)
def sphere(n,p,r,m,scale=(1,1,1)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20,ring_count=12,radius=r,location=p)
    o=finish(bpy.context.object,n,m);o.scale=scale
    for f in o.data.polygons:f.use_smooth=True
    return o
def beam(n,a,b,r,m):
    v=Vector(b)-Vector(a);o=cyl(n,(Vector(a)+Vector(b))/2,r,v.length,m,12)
    o.rotation_euler=v.to_track_quat('Z','Y').to_euler();return o
def mesh(n,verts,faces,m):
    data=bpy.data.meshes.new(n);data.from_pydata(verts,[],faces);data.update()
    o=bpy.data.objects.new(n,data);bpy.context.collection.objects.link(o);return finish(o,n,m)
def root(name):
    global active
    active=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(active);roots.append(active)
    return active
def cabin(width=1.55,length=2.1,z=.86,height=.75,m='ivory'):
    # Trapezoid cabin with proper windshield rake and window pillars.
    x=width/2; y=length/2
    vs=[(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z),(-x*.84,-y*.62,z+height),(x*.84,-y*.62,z+height),(x*.84,y*.62,z+height),(-x*.84,y*.62,z+height)]
    mesh('Glazing',vs,[(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],'glass')
    cube('Roof',(0,0,z+height),(width*.86,length*.66,.11),m,.07)
    for i,j in [(0,4),(1,5),(2,6),(3,7),(4,5),(6,7)]:beam('Window pillar',vs[i],vs[j],.038,m)
    for side in [-1,1]:beam('B pillar',(side*x,0,z),(side*x*.84,0,z+height),.044,m)
def wheel(x,y,z=.37,r=.36):
    tire=cyl('wheel_tire',(x,y,z),r,.22,'rubber',24);tire.rotation_euler[1]=math.pi/2
    rim=cyl('wheel_rim',(x+(.12 if x>0 else -.12),y,z),r*.67,.04,'chrome',16);rim.rotation_euler[1]=math.pi/2
    hub=cyl('wheel_hub',(x+(.15 if x>0 else -.15),y,z),r*.25,.045,'ink',12);hub.rotation_euler[1]=math.pi/2
def car(name,color):
    root(name)
    cube('Chassis',(0,0,.49),(1.8,4.4,.35),'ink',.13)
    cube('Sculpted body',(0,0,.72),(1.82,4.32,.56),color,.18)
    cube('Bonnet',(0,1.4,1.02),(1.7,1.22,.1),color,.09)
    cube('Boot',(0,-1.57,.99),(1.7,1,.12),color,.09)
    cabin(m=color)
    for x in [-.91,.91]:
        for y in [-1.38,1.37]:wheel(x,y)
        for y in [-.55,.48]:cube('Door handle',(x*1.015,y,1.05),(.045,.21,.04),'chrome',.01)
        cube('Mirror',(x*1.15,.75,1.25),(.25,.3,.16),color,.055)
        beam('Door seam',(x,-.03,.63),(x,-.03,1.09),.009,'ink')
        cube('Sill',(x,0,.43),(.04,2.2,.07),'chrome')
    for x in [-.61,.61]:
        cube('Headlamp',(x,2.16,.91),(.48,.07,.19),'headlight',.045)
        cube('Rear lamp',(x,-2.16,.89),(.46,.07,.15),'taillight',.025)
    cube('Grille',(0,2.19,.63),(.7,.04,.19),'ink',.025)
    for x in [-.24,-.12,0,.12,.24]:cube('Grille rib',(x,2.215,.63),(.022,.01,.14),'chrome')
    cube('Front plate',(0,2.22,.45),(.37,.02,.11),'teal')
    cube('Rear plate',(0,-2.2,.64),(.37,.02,.11),'teal')
    for x in [-.42,.42]:cube('Seat',(x,-.15,1.0),(.52,.5,.5),'ink',.09)
    cube('Dashboard',(0,.69,1.0),(1.4,.3,.16),'ink',.04)
    if name=='taxi':cube('Taxi roof sign',(0,0,1.83),(.72,.33,.19),'headlight',.055)
for n,c in [('sedan','ivory'),('taxi','taxi'),('hatchback','teal')]:car(n,c)
root('bus')
cube('Bus shell',(0,0,1.65),(2.45,8.8,2.9),'ivory',.18)
cube('Lower livery',(0,0,.91),(2.49,8.75,.59),'teal',.04)
cube('Windscreen',(0,4.42,2.05),(2.21,.04,1.27),'glass',.06)
for x in [-1.24,1.24]:
    for y in [-3,-1.5,0,1.5,3]:cube('Bus window',(x,y,2.15),(.04,1.25,1.14),'glass',.035)
    for y in [-2.75,2.7]:wheel(x,y,.48,.47)
for x in [-.85,.85]:cube('Bus lamp',(x,4.45,1),(.4,.06,.21),'headlight',.03)
cube('Air conditioning',(0,-.8,3.2),(1.2,2.6,.3),'roof',.1)
root('scooter')
cube('Foot board',(0,0,.3),(.45,1.4,.12),'teal',.06)
cube('Battery',(0,-.23,.55),(.42,.7,.4),'teal',.1)
cube('Seat',(0,-.18,.84),(.46,.65,.12),'ink',.06)
for y in [-.55,.65]:
    w=cyl('wheel',(0,y,.25),.25,.12,'rubber',16);w.rotation_euler[1]=math.pi/2
beam('Steering stem',(0,.5,.3),(0,.62,1.12),.045,'chrome')
beam('Handlebar',(-.35,.62,1.12),(.35,.62,1.12),.03,'ink')
cube('Delivery box',(0,-.53,1.0),(.5,.46,.43),'copper',.04)
sphere('Rider helmet',(0,.08,1.7),.19,'ivory')
cube('Rider torso',(0,-.04,1.29),(.37,.28,.55),'teal',.09)
for x in [-.16,.16]:beam('Rider arm',(x,.0,1.43),(x,.56,1.1),.055,'teal')

root('pearl')
for a in [0,2*math.pi/3,4*math.pi/3]:
    p=(math.cos(a)*9,math.sin(a)*9)
    beam('Tower leg',(p[0]*1.8,p[1]*1.8,0),(p[0],p[1],56),2.3,'paper')
    cyl('Tower column',(p[0],p[1],80),1.6,115,'paper')
sphere('Lower observation sphere',(0,0,57),17,'copper')
sphere('Upper observation sphere',(0,0,126),12,'copper')
cyl('Core',(0,0,100),4,76,'paper')
for z,r in [(51,16.3),(57,17.1),(63,16.3),(122,11.5),(127,12),(131,10.8)]:
    cyl('Observation glazing',(0,0,z),r,1.8,'glass',40)
cyl('Spire',(0,0,153),1.25,37,'paper',16)
sphere('Upper capsule',(0,0,145),4.2,'copper')
beam('Antenna',(0,0,167),(0,0,183),.35,'chrome')

root('shanghai-tower')
vs=[];n=16;floors=32
for j in range(floors+1):
    t=j/floors;angle=t*1.6;radius=14*(1-.56*t)
    for k in range(n):
        a=k/n*math.tau+angle;vs.append((math.cos(a)*radius,math.sin(a)*radius,220*t))
faces=[]
for j in range(floors):
    for k in range(n):a=j*n+k;b=j*n+(k+1)%n;faces.append((a,b,b+n,a+n))
faces.extend([tuple(range(n-1,-1,-1)),tuple(range(floors*n,(floors+1)*n))])
mesh('Twisted glazed skin',vs,faces,'glass')
for k in range(0,n,2):
    for j in range(floors):beam('Vertical mullion',vs[j*n+k],vs[(j+1)*n+k],.18,'chrome')
for j in range(0,floors+1,2):
    for k in range(n):beam('Floor band',vs[j*n+k],vs[j*n+(k+1)%n],.13,'paper')

root('financial-center')
cube('Tower base',(0,0,88),(22,15,176),'glass')
for side in [-1,1]:
    cube('Crown leg',(side*8.2,0,185),(5.6,15,18),'glass')
cube('Sky bridge',(0,0,196),(22,15,5),'chrome')
for z in range(5,177,6):cube('Floor line',(0,-7.55,z),(22,.15,.24),'chrome')
for x in [-11,-5.5,0,5.5,11]:cube('Facade mullion',(x,-7.65,88),(.25,.2,176),'paper')
root('jinmao')
for i in range(10):
    w=25-i*1.8;z=i*15
    cube('Stepped tower',(0,0,z+7.5),(w,w,15),'glass')
    cube('Crown ledge',(0,0,z+15),(w+1,w+1,1),'chrome')
    for x in [-w*.4,0,w*.4]:cube('Vertical rib',(x,-w*.51,z+7.5),(.45,.5,15),'paper')
beam('Spire',(0,0,150),(0,0,175),.7,'chrome')

root('bund-house')
cube('Stone facade',(0,0,10),(26,16,20),'paper',.3)
for z in [1,6,12,19.5]:cube('Stone cornice',(0,0,z),(27,17,.65),'ivory',.08)
for x in [-10,-5,0,5,10]:
    for z in [4,9,15]:cube('Recessed window',(x,8.08,z),(2.4,.13,3.5),'window',.2)
    cyl('Facade column',(x,8.6,3),.4,5,'paper',12)
cube('Parapet',(0,0,21),(24,14,2),'roof',.2)
cube('Clock base',(0,0,25),(7,7,7),'paper',.1)
cyl('Clock roof',(0,0,30),4,3,'roof',12)
for side in [-1,1]:
    o=cyl('Clock face',(0,side*3.55,26),1.8,.09,'ivory',24);o.rotation_euler[0]=math.pi/2
    cube('Clock hand',(0,side*3.63,26.6),(.13,.06,1.2),'ink')
    cube('Clock hand',(0.45,side*3.63,26),(.9,.06,.13),'ink')

for name,w,h,d in [('office',18,42,16),('apartment',14,25,13),('shikumen',11,9,10)]:
    root(name);cube('Building mass',(0,0,h/2),(w,d,h),'paper',.15)
    cube('Roof slab',(0,0,h+.3),(w+1,d+1,.6),'roof')
    for x in range(-int(w/2)+2,int(w/2),3):
        for z in range(3,h,4):
            for side in [-1,1]:cube('Window',(x,side*(d/2+.02),z),(1.6,.08,2),'window')
    if name=='shikumen':
        for x in [-3,3]:
            cube('Door surround',(x,d/2+.1,1.5),(2,.3,3),'roof')
            cube('Door',(x,d/2+.3,1.3),(1.25,.1,2.6),'copper')
        cube('Roof ridge',(0,0,h+.8),(w+1,.5,1),'roof',.1)
    else:
        cube('Roof equipment',(0,0,h+1.2),(3,4,2),'wall',.2)

root('tree');cyl('Trunk',(0,0,2),.26,4,'bark',8)
for p,r in [((0,0,5),2.5),((-1.3,0,4.1),1.8),((1.2,.4,4.6),1.7)]:
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=r,location=p);finish(bpy.context.object,'Canopy','leaf')
root('lamp');cyl('Pole',(0,0,4),.09,8,'roof',10)
beam('Lamp arm',(0,0,8),(2,0,8.5),.085,'roof')
cube('Lamp housing',(2,0,8.45),(1.1,.45,.14),'roof',.05)
cube('Light',(2,0,8.36),(.95,.35,.025),'headlight')
root('barrier');cube('Concrete block',(0,0,.4),(.45,4,.8),'wall',.08)
cube('Reflector',(0,.0,.85),(.08,.18,.14),'headlight')

# Merge static pieces by material; retain moving wheel meshes as separate nodes.
manifest=[]
for r in roots:
    children=list(r.children)
    buckets={}
    for o in children:
        if o.type=='MESH' and not o.name.startswith('wheel'):
            buckets.setdefault(o.data.materials[0].name,[]).append(o)
    for material,obs in buckets.items():
        bpy.ops.object.select_all(action='DESELECT')
        for o in obs:o.select_set(True)
        bpy.context.view_layer.objects.active=obs[0];bpy.ops.object.join();obs[0].name=r.name+'_'+material
    bpy.ops.object.select_all(action='DESELECT');r.select_set(True)
    for o in r.children:o.select_set(True)
    path=OUT/(r.name+'.glb')
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_apply=True)
    meshes=[o for o in r.children if o.type=='MESH']
    triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes)
    manifest.append({'id':r.name,'file':path.name,'bytes':path.stat().st_size,'triangles':triangles,'meshes':len(meshes),'source':'scripts/build_models.py','license':'original-project-asset'})
    print('MODEL',r.name,triangles,path.stat().st_size,flush=True)

# Save all models in an editable catalogue, then render the sample vehicle.
for i,r in enumerate(roots):r.location.x=(i%5)*60;r.location.y=(i//5)*70
bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE/'shanghai-assets.blend'))
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
for r in roots:
    for o in r.children:o.hide_render=True
r=roots[0];r.location=(0,0,0)
for o in r.children:o.hide_render=False
bpy.context.scene.world.color=(.35,.35,.35)
cube('Preview ground',(0,0,-.08),(200,200,.1),'paper')
bpy.ops.object.light_add(type='AREA',location=(3,4,8));bpy.context.object.data.energy=1300;bpy.context.object.data.shape='DISK';bpy.context.object.data.size=6
bpy.ops.object.camera_add(location=(6.5,8,4.7));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,.6))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=48
scene=bpy.context.scene;scene.camera=cam;scene.render.engine='CYCLES';scene.cycles.samples=24
scene.render.resolution_x=1000;scene.render.resolution_y=750;scene.render.resolution_percentage=100
scene.render.filepath=str(SOURCE/'sedan-preview.png');bpy.ops.render.render(write_still=True)
print('DONE',len(manifest),'assets',flush=True)
