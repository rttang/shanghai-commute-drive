"""Photo-referenced architecture, separate from the protected vehicle pipeline.

Coordinates: front +Y, image-left +X, up +Z; east facade anchors live in the
OSM-derived scene. Photographs are rectified with imagegen, then UV mapped onto
stepped masonry, recessed windows, round columns and actual silhouette volumes.
No source photograph is used as a roadside billboard. Hidden elevations remain
explicitly inferred; this is an exterior reconstruction, not a measured survey.
"""
import bpy, json, pathlib, math, hashlib, sys, shutil, datetime
from mathutils import Vector

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'public/streets/photo-models';OUT.mkdir(parents=True,exist_ok=True)
EDIT=ROOT/'assets/blender/streets';EDIT.mkdir(parents=True,exist_ok=True)
TEMP=ROOT/'assets/streets/photofacades/runtime';TEMP.mkdir(parents=True,exist_ok=True)
CONFIG=json.loads((ROOT/'src/tour/photo-architecture.json').read_text())
PHOTOREF={p['id']:p for p in json.loads((ROOT/'references/tourism/architecture-photos.json').read_text())}
sys.path.insert(0,str(ROOT/'scripts'))
from pearl_exterior import build as build_pearl
FREEZE=json.loads((ROOT/'docs/evidence/tourism/street-freeze.json').read_text())
SCOPE=json.loads((ROOT/'docs/evidence/tourism/driving-scope.json').read_text())
RELEASED=set(SCOPE['releasedFromStreetFreeze'])
assert RELEASED=={'src/tour/drive.ts','src/tour/ui.ts','src/main.ts','src/tour/vehicle-assets.json'},'Unexpected freeze release'
assert RELEASED.issubset(FREEZE),'Released path absent from original baseline'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
CURRENT_RELEASED={path:digest(ROOT/path) for path in RELEASED}
SOURCE_IMAGES={str(p.relative_to(ROOT)):digest(p) for p in (ROOT/'assets/streets/photofacades').glob('*.png')}
BUDGET=json.loads((ROOT/'public/streets/model-budget.json').read_text())
QUALITY=dict(jpegQuality=96,textureResize=False,meshDecimation=False,dracoCompressionLevel=6,dracoPositionBits=18,dracoNormalBits=14,dracoTexcoordBits=16)
def assert_frozen():
 for path,expected in FREEZE.items():
  if path not in RELEASED:assert digest(ROOT/path)==expected,'Protected asset changed: '+path
 for path,expected in CURRENT_RELEASED.items():
  assert digest(ROOT/path)==expected,'Approved driving file changed during scenery build: '+path
 for path,expected in SOURCE_IMAGES.items():
  assert digest(ROOT/path)==expected,'Generated source image changed: '+path
assert_frozen()

# Retain the previous runtime set and editable scene before creating any new asset.
# PNG sources are never overwritten or removed, including the originals in Codex.
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
backup=ROOT/'backups'/('street-quality-'+stamp);backup.mkdir(parents=True,exist_ok=False)
backup_records=[]
for source in sorted(OUT.glob('*.glb'))+[OUT/'manifest.json',EDIT/'photo-architecture.blend',EDIT/'photo-architecture-quality96.blend']+sorted(TEMP.glob('*.jpg')):
 if not source.exists():continue
 relative=source.relative_to(ROOT);target=backup/relative;target.parent.mkdir(parents=True,exist_ok=True)
 shutil.copy2(source,target)
 sha=digest(source);assert digest(target)==sha,'Backup verification failed: '+str(relative)
 backup_records.append(dict(path=str(relative),bytes=source.stat().st_size,sha256=sha))
(backup/'manifest.json').write_text(json.dumps(dict(reason='Preserve pre-quality-upgrade assets',files=backup_records),ensure_ascii=False,indent=2))
print('PHOTO_BACKUP_VERIFIED',str(backup),len(backup_records),flush=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene;scene.render.image_settings.file_format='JPEG';scene.render.image_settings.quality=QUALITY['jpegQuality']
scene.view_settings.view_transform='Standard'

def material(name,color,rough=.82):
 m=bpy.data.materials.new(name);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF')
 p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough
 return m
stone=material('photo-side-stone',(.44,.405,.345));roof=material('photo-roof',(.20,.225,.20),.96)
glass=material('photo-glass',(.075,.12,.14),.24);iron=material('photo-iron',(.04,.048,.04),.34)
terracotta=material('photo-terracotta',(.36,.13,.065));copper=material('photo-copper',(.14,.255,.205),.62)
atlas={}
def photo_material(key):
 if key in atlas:return atlas[key]
 source=ROOT/'assets/streets/photofacades'/f'{key}.png'
 image=bpy.data.images.load(str(source),check_existing=True)
 # High-quality JPEG conversion; composition and native pixel dimensions retained.
 jpeg=TEMP/f'{key}.jpg';image.save_render(str(jpeg),scene=scene)
 img=bpy.data.images.load(str(jpeg),check_existing=True)
 assert tuple(image.size)==tuple(img.size),'Texture dimensions changed: '+key
 m=material('photo-'+key,(1,1,1),.88);nodes=m.node_tree.nodes;tex=nodes.new('ShaderNodeTexImage');tex.image=img
 m.node_tree.links.new(tex.outputs['Color'],nodes.get('Principled BSDF').inputs['Base Color'])
 atlas[key]=m;return m

class Mesh:
 def __init__(self,parent):self.parent=parent;self.groups={}
 def face(self,verts,mat,uv=None,smooth=False):
  vs,fs,uvs=self.groups.setdefault((mat,smooth),([],[],[]));n=len(vs);vs.extend(verts);fs.append(tuple(range(n,n+len(verts))));uvs.append(uv)
 def box(self,p,s,mat):
  x,y,z=p;a,b,c=[t/2 for t in s];v=[(x+i,y+j,z+k) for i,j,k in [(-a,-b,-c),(a,-b,-c),(a,b,-c),(-a,b,-c),(-a,-b,c),(a,-b,c),(a,b,c),(-a,b,c)]]
  for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:self.face([v[i] for i in f],mat)
 def rod(self,a,b,r,mat,n=12,r2=None):
  a,b=Vector(a),Vector(b);q=(b-a).to_track_quat('Z','Y');v=[]
  for c,rad in [(a,r),(b,r if r2 is None else r2)]:
   v.extend(tuple(c+q@Vector((rad*math.cos(i*math.tau/n),rad*math.sin(i*math.tau/n),0))) for i in range(n))
  for i in range(n):self.face([v[i],v[(i+1)%n],v[(i+1)%n+n],v[i+n]],mat,smooth=True)
  self.face(v[:n][::-1],mat);self.face(v[n:],mat)
 def lathe(self,center,rings,mat,n=48):
  cx,cy=center
  for (z0,r0),(z1,r1) in zip(rings,rings[1:]):
   for i in range(n):
    a=i*math.tau/n;b=(i+1)*math.tau/n
    self.face([(cx+r0*math.cos(a),cy+r0*math.sin(a),z0),(cx+r0*math.cos(b),cy+r0*math.sin(b),z0),(cx+r1*math.cos(b),cy+r1*math.sin(b),z1),(cx+r1*math.cos(a),cy+r1*math.sin(a),z1)],mat,smooth=True)
 def flush(self):
  for (mat,smooth),(vs,fs,uvs) in self.groups.items():
   if self.parent.get('backShift'):
    vs=[(x-min(0,y)/self.parent['depth']*self.parent['backShift'],y,z) for x,y,z in vs]
   mesh=bpy.data.meshes.new(self.parent.name+'-'+mat.name);mesh.from_pydata(vs,[],fs);mesh.update();mesh.materials.append(mat);uv=mesh.uv_layers.new()
   for p,coords in zip(mesh.polygons,uvs):
    p.use_smooth=smooth
    for i,li in enumerate(p.loop_indices):
     co=mesh.vertices[mesh.loops[li].vertex_index].co
     uv.data[li].uv=coords[i] if coords else (co.x/3,co.z/3)
   obj=bpy.data.objects.new(mesh.name,mesh);bpy.context.collection.objects.link(obj);obj.parent=self.parent
  self.groups.clear()

# Coordinates below are measured on each generated rectified elevation, not a
# shared facade tile. Features map to that building's own windows and moldings.
FEATURES={
 'bund-18':dict(profile=[(0,.17),(.25,.17),(.25,.054),(.5,.005),(.75,.054),(.75,.17),(1,.17)],bands=[(.163,.211,.55),(.315,.348,.38),(.791,.817,.43)],columns=[(.418,.401,.760,.024),(.57,.401,.76,.024)],windows=[(.303,.39,.43,.734),(.451,.548,.43,.734),(.605,.698,.43,.734),(.126,.174,.400,.489),(.827,.87,.40,.489),(.126,.174,.58,.677),(.826,.871,.58,.677)],pilasters=[(.218,.288,.337,.789,.18),(.704,.776,.337,.789,.18)]),
 'aia-building':dict(profile=[(.04,.234),(.06,.114),(.11,.108),(.11,.057),(.18,.01),(.25,.057),(.29,.11),(.71,.11),(.75,.057),(.82,.01),(.89,.057),(.89,.108),(.94,.114),(.96,.234)],bands=[(.227,.269,.58),(.709,.734,.48),(.111,.135,.25)],columns=[(.405,.765,.935,.019),(.585,.765,.935,.019),(.32,.143,.218,.008),(.39,.143,.218,.008),(.575,.143,.218,.008),(.685,.143,.218,.008)],windows=[(u-.03,u+.03,v,v+.042) for u in [.18,.35,.49,.63,.795] for v in [.30,.377,.446,.516,.587,.651]]),
 'russo-chinese-bank':dict(profile=[(.018,.12),(.018,.07),(.10,.07),(.10,.036),(.16,.008),(.22,.036),(.22,.08),(.44,.08),(.47,.028),(.53,.028),(.56,.08),(.78,.08),(.78,.036),(.84,.008),(.90,.036),(.90,.07),(.982,.07),(.982,.12)],bands=[(.12,.18,.48),(.25,.279,.32),(.75,.78,.43)],columns=[(.418,.294,.70,.014),(.575,.294,.70,.014)],windows=[(.291,.383,.303,.459),(.443,.535,.303,.459),(.598,.69,.303,.459),(.311,.373,.585,.72),(.465,.525,.585,.72),(.618,.68,.585,.72),(.122,.17,.336,.451),(.821,.867,.336,.451)]),
 'hsbc-bund':dict(profile=[(0,.47),(.018,.363),(.39,.363),(.4,.237),(.417,.222),(.425,.18),(.47,.131),(.49,.11),(.493,.02),(.507,.02),(.51,.11),(.53,.131),(.575,.18),(.583,.222),(.6,.237),(.61,.363),(.982,.363),(1,.47)],bands=[(.466,.49,.6),(.791,.815,.43)],columns=[(u,.55,.769,.009) for u in [.389,.444,.472,.532,.56,.612]],windows=[(u-.01,u+.01,v,v+.047) for u in [.057,.11,.15,.188,.223,.26,.324,.672,.724,.762,.799,.836,.89,.946] for v in [.527,.614,.704]]),
 'customs-house':dict(profile=[(.02,.53),(.04,.45),(.2,.45),(.2,.52),(.32,.52),(.32,.36),(.39,.36),(.39,.17),(.43,.17),(.43,.08),(.47,.04),(.53,.04),(.57,.08),(.57,.17),(.61,.17),(.61,.36),(.68,.36),(.68,.52),(.8,.52),(.8,.45),(.96,.45),(.98,.53)],bands=[(.50,.526,.5),(.80,.823,.35)],columns=[],windows=[]),
 'peace-hotel':dict(profile=[(.03,.38),(.12,.33),(.23,.33),(.23,.26),(.29,.26),(.31,.15),(.46,.025),(.46,.005),(.54,.005),(.54,.025),(.69,.15),(.71,.26),(.77,.26),(.77,.33),(.88,.33),(.97,.38)],bands=[(.28,.302,.4),(.824,.84,.38)],columns=[],windows=[]),
 'palace-hotel':dict(profile=[(.02,.205),(.09,.165),(.15,.165),(.15,.112),(.21,.086),(.27,.112),(.32,.165),(.69,.165),(.70,.07),(.76,.035),(.84,.035),(.9,.07),(.94,.20)],bands=[(.19,.22,.38),(.48,.50,.22),(.815,.835,.28)],columns=[],windows=[]),
 'bank-china':dict(profile=[(.015,.285),(.15,.285),(.15,.019),(.23,.025),(.77,.025),(.85,.019),(.85,.285),(.985,.285)],bands=[(.04,.055,.6),(.806,.824,.3)],columns=[],windows=[]),
}

# Trace the actual generated silhouettes; gray reference background is excluded
# from the mesh. Window recess locations are independently measured per image.
FEATURES['customs-house'].update(
 profile=[(.018,.354),(.052,.354),(.052,.275),(.079,.252),(.217,.252),(.246,.276),(.246,.321),(.331,.321),(.331,.266),(.339,.246),(.383,.246),(.405,.274),(.408,.198),(.431,.19),(.431,.107),(.45,.107),(.45,.075),(.466,.068),(.466,.043),(.475,.028),(.525,.028),(.534,.043),(.534,.068),(.55,.075),(.55,.107),(.569,.107),(.569,.19),(.592,.198),(.595,.274),(.617,.246),(.661,.246),(.669,.266),(.669,.321),(.754,.321),(.754,.276),(.783,.252),(.921,.252),(.948,.275),(.948,.354),(.982,.354)],
 bands=[(.354,.383,.55),(.702,.725,.34),(.792,.812,.4)],
 columns=[(u,.852,.985,.015) for u in [.337,.43,.524,.618]],
 windows=[(u-.022,u+.022,v,v+.037) for u in [.127,.287,.384,.48,.576,.672,.87] for v in [.441,.508,.578,.648]])
FEATURES['peace-hotel'].update(
 profile=[(.055,.35),(.196,.325),(.196,.258),(.263,.254),(.263,.211),(.275,.182),(.321,.182),(.321,.166),(.451,.064),(.463,.063),(.463,.025),(.474,.014),(.526,.014),(.537,.025),(.537,.063),(.549,.064),(.679,.166),(.679,.182),(.725,.182),(.737,.211),(.737,.254),(.804,.258),(.804,.325),(.945,.35)],
 bands=[(.202,.222,.48),(.254,.276,.42),(.332,.35,.35),(.831,.85,.3)],
 windows=[(u-.014,u+.014,v,v+.03) for u in [.265,.31,.355,.455,.5,.545,.645,.69,.735] for v in [.368,.428,.487,.546,.606,.669,.73,.794]])
FEATURES['palace-hotel'].update(
 profile=[(.03,.169),(.079,.133),(.086,.091),(.139,.071),(.24,.071),(.24,.036),(.278,.015),(.313,.036),(.313,.071),(.36,.071),(.396,.112),(.691,.112),(.715,.061),(.765,.026),(.829,.009),(.89,.034),(.936,.061),(.936,.161),(.97,.17)],
 bands=[(.162,.182,.40),(.435,.458,.3),(.562,.581,.26),(.693,.716,.31),(.823,.84,.35)],
 windows=[(u-r,u+r,v,v+.06) for u,r in [(.224,.052),(.51,.052),(.827,.021)] for v in [.23,.352,.474,.6,.727]],
 pilasters=[(.041,.093,.19,.817,.17),(.347,.409,.19,.817,.2),(.605,.667,.19,.817,.2),(.748,.91,.19,.817,.48)])
FEATURES['bank-china'].update(
 profile=[(.047,.848),(.079,.824),(.108,.255),(.148,.194),(.232,.194),(.232,.099),(.274,.099),(.27,.056),(.263,.021),(.287,.027),(.714,.027),(.738,.019),(.73,.055),(.727,.099),(.767,.099),(.767,.194),(.85,.194),(.89,.255),(.917,.824),(.954,.848)],
 bands=[(.036,.053,.45),(.74,.752,.18),(.783,.796,.25)],
 windows=[(u-.012,u+.012,v,v+.023) for u in [.197,.406,.448,.5,.549,.593,.8] for v in [.3,.35,.40,.449,.497,.55,.60,.65,.705]])

FEATURES.update({
 'ocean-aquarium':dict(profile=[(.009,.619),(.038,.619),(.038,.036),(.345,.476),(.377,.467),(.53,.466),(.547,.48),(.55,.539),(.605,.55),(.63,.554),(.809,.554),(.815,.164),(.989,.164)],bands=[(.619,.642,.35),(.809,.824,.3)],columns=[],windows=[(.375,.4,.602,.67),(.425,.45,.602,.67),(.475,.497,.611,.678),(.526,.547,.616,.68),(.57,.587,.627,.69)],pilasters=[(.06,.36,.64,.96,-.18)],loggias=[(.63,.702,.558,.82,3),(.343,.55,.83,.968,1.2)]),
 'hang-seng':dict(profile=[(.15,.939),(.15,.815),(.19,.815),(.19,.095),(.196,.066),(.242,.066),(.242,.036),(.33,.036),(.33,.025),(.39,.025),(.45,.012),(.50,.007),(.55,.012),(.61,.025),(.682,.025),(.682,.036),(.752,.036),(.752,.066),(.80,.066),(.812,.095),(.812,.815),(.85,.815),(.85,.939)],bands=[(.813,.821,.6),(.939,.947,.4)],columns=[],windows=[(u-.01,u+.01,v,v+.008) for u in [.28,.324,.37,.415,.578,.623,.668,.712] for v in [0.096+i*.0198 for i in range(36)]],pilasters=[(.444,.552,.042,.915,-.5)],roughness=.65,sideCrop=[.246,.428,.099,.81]),
 'bea-tower':dict(profile=[(.205,.041),(.247,.041),(.247,.019),(.369,.019),(.369,.041),(.395,.041),(.395,.047),(.422,.047),(.422,.018),(.548,.018),(.548,.18),(.708,.18)],bands=[(.18,.187,.35),(.275,.284,.25),(.622,.63,.28),(.93,.935,.2)],columns=[],windows=[],pilasters=[(.39,.418,.043,.93,-1),(.51,.532,.19,.99,.4)],roughness=.35,sideCrop=[.224,.374,.048,.929]),
 'bank-taiwan':dict(profile=[(.01,.235),(.065,.216),(.065,.082),(.083,.082),(.083,.046),(.18,.043),(.5,.004),(.82,.043),(.917,.046),(.917,.082),(.935,.082),(.935,.216),(.99,.235)],bands=[(.082,.10,.35),(.216,.269,.6),(.355,.40,.5),(.90,.93,.3)],columns=[(u,.43,.886,.04) for u in [.085,.35,.648,.911]],windows=[(a,b,c,e) for a,b in [(.176,.265),(.429,.571),(.729,.815)] for c,e in [(.285,.347),(.446,.532),(.756,.857)]]),
 'bank-communications':dict(profile=[(.005,.219),(.04,.183),(.079,.183),(.081,.149),(.10,.149),(.12,.179),(.16,.183),(.16,.227),(.22,.227),(.23,.201),(.24,.201),(.24,.228),(.30,.228),(.34,.204),(.37,.14),(.37,.09),(.405,.09),(.43,.06),(.473,.06),(.473,.025),(.487,.018),(.5,.004),(.513,.018),(.527,.025),(.527,.06),(.57,.06),(.595,.09),(.63,.09),(.63,.14),(.66,.204),(.70,.228),(.77,.228),(.77,.201),(.78,.201),(.79,.227),(.84,.227),(.84,.183),(.88,.179),(.90,.149),(.92,.149),(.921,.183),(.96,.183),(.995,.219)],bands=[(.885,.899,.25)],columns=[],windows=[(u-r,u+r,v,v+.046) for u,r in [(.085,.013),(.185,.025),(.267,.025),(.435,.025),(.553,.025),(.733,.025),(.811,.025),(.917,.013)] for v in [.338,.438,.531,.632,.775]],pilasters=[(u-.011,u+.011,.23,.882,.24) for u in [.047,.136,.226,.313,.378,.496,.62,.687,.775,.867,.955]]),
 'china-merchants':dict(profile=[(.01,.13),(.12,.034),(.239,.034),(.27,.015),(.313,.034),(.841,.034),(.88,.044),(.989,.13)],bands=[(.133,.205,.42),(.413,.46,.28),(.695,.743,.34)],columns=[(u,a,b,.007) for u in [.204,.336,.389,.493,.514,.619,.638,.774,.826,.932] for a,b in [(.237,.362),(.477,.644)]],windows=[(u-.025,u+.025,v,v+.155) for u in [.105,.276,.442,.70,.877] for v in [.28,.52,.787]],pilasters=[(.171,.198,.216,.976,.25),(.358,.384,.216,.742,.25),(.785,.814,.216,.976,.25)]),
 'asia-building':dict(profile=[(.015,.10),(.033,.053),(.058,.052),(.08,.032),(.087,.006),(.282,.006),(.294,.033),(.32,.039),(.328,.08),(.673,.08),(.677,.039),(.706,.033),(.718,.006),(.915,.006),(.934,.034),(.971,.053),(.985,.10)],bands=[(.1,.13,.43),(.373,.4,.44),(.741,.77,.38)],columns=[(u,.187,.364,.008) for u in [.322,.422,.45,.55,.578,.678]],windows=[(u-.021,u+.021,v,v+.063) for u in [.133,.225,.775,.867] for v in [.177,.287,.413,.523,.645,.805,.913]],pilasters=[(u-.013,u+.013,.138,.741,.18) for u in [.048,.297,.703,.952]],loggias=[(.335,.665,.182,.368,2.2),(.332,.432,.443,.735,1.6),(.467,.534,.443,.661,1.6),(.568,.668,.443,.735,1.6)]),
 'super-brand-mall':dict(profile=[(.008,.389),(.025,.331),(.12,.295),(.125,.169),(.167,.121),(.19,.088),(.224,.066),(.227,.024),(.236,.024),(.236,.064),(.29,.056),(.4,.056),(.42,.02),(.432,.02),(.432,.07),(.491,.108),(.51,.153),(.995,.157)],bands=[(.275,.305,.24),(.782,.821,.38)],columns=[(u,.72,.988,.0035) for u in [.492,.708,.809,.865,.954]],windows=[],roughness=.4),
})

def photo_build(spec):
 key=spec['id'];root=bpy.data.objects.new(key,None);bpy.context.collection.objects.link(root);mesh=Mesh(root)
 root['sourcePhoto']=spec['reference'];root['reconstruction']='photo-referenced exterior; non-surveyed depth'
 root['backShift']=spec.get('backShift',0);root['depth']=spec['depth']
 w=math.dist(*spec['front']);h=spec.get('facadeHeight',spec['height']);d=spec['depth'];mat=photo_material(key);f=FEATURES[key]
 mat.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=f.get('roughness',.88)
 profile=f['profile'];left,right=profile[0][0],profile[-1][0]
 # Exclude the reference's neutral margin from the metre scale; the actual
 # silhouette, not the full image rectangle, spans the mapped street frontage.
 w/=right-left;mid=(left+right)/2
 def top(u):
  for (a,b),(c,e) in zip(profile,profile[1:]):
   if a<=u<=c and c>a:
    v=b+(e-b)*(u-a)/(c-a)
    if key=='customs-house' and .32<u<.68:return max(v,.321)
    # These silhouettes continue into genuinely round/pyramidal roof geometry.
    return max(v,.215 if key=='hsbc-bund' else .163 if key=='peace-hotel' else 0)
  return .99
 def point(u,v,y=0):return ((mid-u)*w,y,(1-v)*h)
 def face(points,ys=None):
  ys=ys or [0]*len(points);mesh.face([point(u,v,y) for (u,v),y in zip(points,ys)],mat,[(u,1-v) for u,v in points])
 def depth(u,v):
  z=0
  for a,b,c,e in f['windows']:
   if a<u<b and c<v<e:z=-.34
  for a,b,c,e,offset in f.get('pilasters',[]):
   if a<u<b and c<v<e:z=offset
  for a,b,c,e,offset in f.get('loggias',[]):
   if a<u<b and c<v<e:z=-offset
  for a,b,e in f['bands']:
   if a<v<b:z=max(z,e)
  # Tall upper tower volume is set behind the main east elevation.
  if v<spec['bodyTop']:z-=1.3
  if spec.get('curve') and u<.51:
   # The shopping centre's circular atrium and bowed west wing have real
   # plan curvature. Keep their foremost points behind the street anchor.
   z+=spec['curve']*(math.sin(math.pi*u/.51)-1)
  return z
 us={left,right,*[u for u,v in profile]};vs={1.,spec['bodyTop'],*[v for u,v in profile]}
 us.update(left+(right-left)*i/90 for i in range(91));vs.update(i/100 for i in range(101))
 for a,b,c,e in f['windows']:us.update([a,b]);vs.update([c,e])
 for a,b,e in f['bands']:vs.update([a,b])
 for a,b,c,e,_ in f.get('pilasters',[]):us.update([a,b]);vs.update([c,e])
 for a,b,c,e,_ in f.get('loggias',[]):us.update([a,b]);vs.update([c,e])
 us=sorted(x for x in us if left<=x<=right);vs=sorted(x for x in vs if 0<=x<=1)
 for a,b in zip(us,us[1:]):
  for c,e in zip(vs,vs[1:]):
   ta,tb=top(a+1e-8),top(b-1e-8)
   if e<=min(ta,tb):continue
   pa,pb=max(c,ta),max(c,tb)
   if pa>=e or pb>=e:continue
   y=depth((a+b)/2,(pa+pb+2*e)/4)
   face([(a,e),(b,e),(b,pb),(a,pa)],[y]*4)
   # Recess jambs / raised molding returns are true surfaces with the same UV.
   for p,q,nu,nv in [((a,e),(b,e),(a+b)/2,e+1e-6),((b,e),(b,pb),b+1e-6,(e+pb)/2),((b,pb),(a,pa),(a+b)/2,c-1e-6),((a,pa),(a,e),a-1e-6,(pa+e)/2)]:
    ny=depth(nu,nv)
    if y>ny+1e-5:face([p,q,q,p],[y,y,ny,ny])
 # Perimeter silhouette with real depth and a closed back; upper volume depth is bounded.
 outline=[(left,1),*profile,(right,1)]
 for a,b in zip(outline,outline[1:]+outline[:1]):
  if a[0]==b[0] and a[0] in [left,right]:
   # Main side elevation is emitted below with its own texture. Do not place
   # a second coplanar stone wall behind it (visible moire / z-fighting).
   if min(a[1],b[1])>=spec['bodyTop']:continue
   a=(a[0],min(a[1],spec['bodyTop']));b=(b[0],min(b[1],spec['bodyTop']))
  if key in ['hsbc-bund','peace-hotel'] and max(a[1],b[1])<(.215 if key=='hsbc-bund' else .163):continue
  if key=='customs-house' and .32<a[0]<.68 and .32<b[0]<.68 and max(a[1],b[1])<.321:continue
  y1=depth(*a);y2=depth(*b);dep=d if (a[1]+b[1])/2>=spec['bodyTop'] else min(d,14)
  if key=='ocean-aquarium' and max(a[0],b[0])<.38 and max(a[1],b[1])<.62:dep=.65
  mesh.face([point(*a,y1),point(*b,y2),point(*b,-dep),point(*a,-dep)],roof if abs(a[1]-b[1])<.03 else stone)
 # Main volume side walls: actual long side photo where available; otherwise
 # infer secondary windows from the same building, never the shared city tile.
 ztop=(1-spec['bodyTop'])*h
 sidekey=spec.get('side');sidemat=photo_material(sidekey) if sidekey and (ROOT/'assets/streets/photofacades'/f'{sidekey}.png').exists() else mat
 for sign in [-1,1]:
  x=sign*w*(right-left)/2
  if sidemat!=mat:
   v=[(x,0,0),(x,-d,0),(x,-d,ztop),(x,0,ztop)];uv=[(0,0),(1,0),(1,1),(0,1)]
   if sign<0:v.reverse();uv.reverse()
   mesh.face(v,sidemat,uv)
  else:
   bays=max(2,round(d/4.0))
   for i in range(bays):
    y1=-d*i/bays;y2=-d*(i+1)/bays
    a,b,c,e=f.get('sideCrop',[.115,.206,spec['bodyTop'],1])
    v=[(x,y1,0),(x,y2,0),(x,y2,ztop),(x,y1,ztop)];uv=[(a,1-e),(b,1-e),(b,1-c),(a,1-c)]
    if sign<0:v.reverse();uv.reverse()
    mesh.face(v,mat,uv)
  # Projecting side cornices continue around corners, giving near oblique depth.
  for a,b,offset in f['bands']:
   z=(1-(a+b)/2)*h
   if z<ztop:mesh.box((x+sign*.13,-d/2,z),(.32,d+.2,max(.14,(b-a)*h)),terracotta if key=='palace-hotel' else stone)
 mesh.box((0,-d/2,ztop-.1),(w*(right-left),d,.2),roof)
 mesh.box((0,-d-.05,ztop/2),(w*(right-left),.1,ztop),stone)
 # Round columns: source-projected texture on an actual curved shaft, with
 # independent cylindrical bases. Capitals retain the photograph's relief.
 for u,v0,v1,rad in f['columns']:
  cx=(mid-u)*w;r=rad*w;z0=(1-v1)*h;z1=(1-v0)*h
  n=32
  for k in range(n):
   angles=[k*math.tau/n,(k+1)*math.tau/n];verts=[];uv=[]
   for z,v in [(z0,v1),(z1,v0)]:
    for theta in angles:
     x=cx+math.cos(theta)*r;y=math.sin(theta)*r+.02
     if spec.get('curve') and u<.51:y+=spec['curve']*(math.sin(math.pi*u/.51)-1)
     verts.append((x,y,z));uv.append((mid-x/w,1-v))
   mesh.face([verts[i] for i in [0,1,3,2]],mat,[uv[i] for i in [0,1,3,2]],True)
  for z,rr in [(z0-.09,r*1.2),(z0+.08,r*1.08),(z1,r*1.25)]:mesh.rod((cx,0,z-.08),(cx,0,z+.08),rr,stone,32)
 # Stone doorstep and entry landings in actual metre scale.
 for i in range(3):mesh.box((0,.25+i*.21,.06*(3-i)),(min(8,w*.35),.4,.12),stone)
 if key=='customs-house':
  # Four-sided clock tower, not a photograph on a single blade. The tower and
  # crown occupy the upper height; the flag mast is only the final 2.4 metres.
  masonry=material('customs-tower-limestone',(.57,.51,.40),.82)
  dial=material('customs-clock-opal',(.84,.86,.82),.5)
  gold=material('customs-crown-bronze',(.50,.36,.13),.4)
  cy=-5.5
  for z,size in [(44.5,(9,10,12)),(51,(9.8,10.8,.7)),(58.5,(7.6,7.6,14.4)),(66,(8.5,8.5,.65)),(69.6,(5.6,5.6,6.5)),(73,(6.3,6.3,.5))]:mesh.box((0,cy,z),size,masonry)
  mesh.box((0,cy,74.8),(4.8,4.8,3.1),gold)
  mesh.lathe((0,cy),[(76.4,3.4),(76.8,2.7)],gold,4)
  mesh.rod((0,cy,76.8),(0,cy,spec['height']),.055,iron,8)
  for nx,ny in [(0,1),(1,0),(0,-1),(-1,0)]:
   n=Vector((nx,ny,0));t=Vector((ny,-nx,0));up=Vector((0,0,1));c=Vector((0,cy,58.5))+n*3.84
   mesh.rod(c-n*.05,c+n*.02,2.78,iron,64)
   mesh.rod(c+n*.03,c+n*.05,2.58,dial,64)
   for i in range(60):
    a=i*math.tau/60;v=t*math.sin(a)+up*math.cos(a)
    mesh.rod(c+n*.09+v*(2.16 if i%5==0 else 2.37),c+n*.09+v*2.48,.06 if i%5==0 else .022,iron,5)
   for a,length in [(math.tau*10/12,1.5),(math.tau/6,2.13)]:
    mesh.rod(c+n*.14,c+n*.14+(t*math.sin(a)+up*math.cos(a))*length,.07,iron,8)
   # Three recessed upper-tower windows, referenced to the source's arrangement.
   for offset in [-2.2,0,2.2]:
    c0=Vector((0,cy,45))+n*5.06+t*offset
    mesh.face([tuple(c0+t*x+up*z) for x,z in [(-.55,-2.8),(.55,-2.8),(.55,2.8),(-.55,2.8)]],glass)
 if key=='hsbc-bund':
  z=(1-.215)*h;r=w*.092;cy=-r-1.3
  mesh.lathe((0,cy),[(z+.67*r*math.sin(i*math.pi/32),r*math.cos(i*math.pi/32)) for i in range(17)],stone,64)
  mesh.rod((0,cy,z+r*.66),(0,cy,z+r*.66+1.25),1.6,stone,24)
  mesh.lathe((0,cy),[(z+r*.66+1.25+i*.12,1.7*(1-i/10)) for i in range(11)],roof,32)
  mesh.rod((0,cy,z+r*.66+2.4),(0,cy,h),.10,iron,8)
 if key=='peace-hotel':
  z0=(1-.163)*h;z1=(1-.064)*h;a=w*.181;b=w*.048;cy=-a-1.3
  bottom=[(-a,cy-a,z0),(a,cy-a,z0),(a,cy+a,z0),(-a,cy+a,z0)]
  upper=[(-b,cy-b,z1),(b,cy-b,z1),(b,cy+b,z1),(-b,cy+b,z1)]
  for i in range(4):
   mesh.face([bottom[i],bottom[(i+1)%4],upper[(i+1)%4],upper[i]],copper)
   mesh.rod(bottom[i],upper[i],.095,terracotta,8)
   for j in range(1,24):
    t=j/24;lo=Vector(bottom[i]).lerp(Vector(bottom[(i+1)%4]),t);hi=Vector(upper[i]).lerp(Vector(upper[(i+1)%4]),t)
    mesh.rod(lo,hi,.024,iron,5)
  mesh.box((0,cy,z1+(h-z1)*.40),(b*1.8,b*1.8,(h-z1)*.7),terracotta)
  for x in [-b*.91,b*.91]:mesh.box((x,cy,z1+(h-z1)*.40),(.035,b*1.2,(h-z1)*.50),glass)
  mesh.box((0,cy,h-.8),(b*2.1,b*2.1,.32),copper)
 mesh.flush();return root

roots=[];manifest=[]
for spec in CONFIG+[dict(id='pearl',reference='pearl-base',height=468,front=[[0,0],[50,0]])]:
 if spec['id']=='pearl':root=build_pearl(bpy,Mesh,material)
 else:
  assert (ROOT/'assets/streets/photofacades'/f"{spec['id']}.png").exists(),spec['id']
  root=photo_build(spec)
 roots.append(root)
 bpy.ops.object.select_all(action='DESELECT');root.select_set(True)
 for o in root.children_recursive:o.select_set(True)
 bpy.context.view_layer.objects.active=root;p=OUT/f"{spec['id']}.glb"
 bpy.ops.export_scene.gltf(filepath=str(p),export_format='GLB',use_selection=True,export_apply=True,export_extras=True,export_draco_mesh_compression_enable=True,export_draco_mesh_compression_level=QUALITY['dracoCompressionLevel'],export_draco_position_quantization=QUALITY['dracoPositionBits'],export_draco_normal_quantization=QUALITY['dracoNormalBits'],export_draco_texcoord_quantization=QUALITY['dracoTexcoordBits'])
 meshes=[o for o in root.children_recursive if o.type=='MESH']
 source=PHOTOREF[spec['reference']]
 assert source['usage']=='exterior-reference',spec['id']
 textures={node.image.name:dict(width=node.image.size[0],height=node.image.size[1]) for o in meshes for mat in o.data.materials if mat and mat.use_nodes for node in mat.node_tree.nodes if node.type=='TEX_IMAGE' and node.image}
 budget_class='landmark-exception' if spec['id'] in BUDGET['landmarkExceptions'] else 'ordinary'
 manifest.append(dict(id=spec['id'],bytes=p.stat().st_size,triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes),meshes=len(meshes),reference=spec['reference'],source=source['source'],author=source['author'],license=source['license'],licenseUrl=source['licenseUrl'],modifications='Imagegen perspective/occlusion reconstruction, Blender exterior volumes, JPEG 96 at source dimensions and precision-preserving Draco; inferred unseen sides',frontWidth=math.dist(*spec['front']),height=spec['height'],sha256=digest(p),budgetClass=budget_class,quality=QUALITY,textures=textures))
 print('PHOTO_ARCHITECTURE',manifest[-1],flush=True)
for image in bpy.data.images:
 if image.source=='FILE':image.pack()
for i,r in enumerate(roots):r.location.x=i*180
editable=EDIT/'photo-architecture-quality96.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(editable))
ordinary=[m for m in manifest if m['budgetClass']=='ordinary']
ordinary_average=sum(m['bytes'] for m in ordinary)/len(ordinary)
assert ordinary_average<BUDGET['ordinaryAverageBytes'],'Ordinary model average exceeds approved 10 MB budget'
assert_frozen()
(OUT/'manifest.json').write_text(json.dumps(dict(generator='scripts/build_photo_architecture.py',models=manifest,method='photo-referenced UV relief and exterior volumes; inferred unseen sides',totalBytes=sum(m['bytes'] for m in manifest),averageBytes=sum(m['bytes'] for m in manifest)/len(manifest),ordinaryAverageBytes=ordinary_average,budget=BUDGET,quality=QUALITY,editableSource=str(editable.relative_to(ROOT)),previousAssetsBackup=str(backup.relative_to(ROOT)),protectedFilesUnchanged=True,protectedFileCount=len(FREEZE)-len(RELEASED),approvedDrivingFilesUnchangedDuringBuild=CURRENT_RELEASED,generatedSourceImagesUnchanged=SOURCE_IMAGES),ensure_ascii=False,indent=2))
print('PHOTO_ARCHITECTURE_COMPLETE',len(roots),sum(r['bytes'] for r in manifest),flush=True)
assert_frozen()
