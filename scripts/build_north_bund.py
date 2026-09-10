"""Photo-referenced North Bund additions; run with scripts/blender-local.sh.
Builds only north-bund outputs. Existing Bund models are audited reuse references.
Street photographs remain archive-only; GLBs carry PBR geometry, never billboards.
"""
import bpy, math, json, pathlib, sys, hashlib, datetime, argparse, tempfile, os, array
from mathutils import Vector, Matrix
from mathutils.geometry import tessellate_polygon
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from north_bund_helpers import Mesh, material, polygon_ccw, resample_polygon, transformed_box, band, facade, hipped_roof, curtain, ring_rail, air_conditioner, brick_courses
from street_glb import read_glb, write_glb
OUT=ROOT/'public/streets/districts/north-bund';ASSET=ROOT/'assets/streets/north-bund';EDIT=ROOT/'assets/blender/streets/north-bund-detailed.blend'
OUT.mkdir(parents=True,exist_ok=True);ASSET.mkdir(parents=True,exist_ok=True)
P=argparse.ArgumentParser();P.add_argument('--render',action='store_true');P.add_argument('--render-only',action='store_true');P.add_argument('--ids',nargs='*');P.add_argument('--review-ids',nargs='*');P.add_argument('--cycles-review',action='store_true');ARGS=P.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
CITY=json.loads((ROOT/'public/tour-city.json').read_text());BUILDINGS={b['id']:b for b in CITY['buildings']}
HYATT_OSM=ROOT/'references/tourism/north-bund-hyatt-osm.json'
if HYATT_OSM.exists():
 for way in json.loads(HYATT_OSM.read_text())['elements']:
  if way['id'] in [446937834,446937836]:
   BUILDINGS[way['id']]={'id':way['id'],'points':[((p['lon']-CITY['origin'][0])*111320*math.cos(math.radians(CITY['origin'][1])),-(p['lat']-CITY['origin'][1])*111320) for p in way['geometry']]}
SPECS=json.loads((ROOT/'references/tourism/north-bund-model-config.json').read_text())
if ARGS.ids and ARGS.review_ids and not ARGS.render_only and (OUT/'manifest.json').exists():
 previous={r['id']:r for r in json.loads((OUT/'manifest.json').read_text())['models']}
 # A reviewed ID with an explicitly revised geometry config must be rebuilt
 # before its review. Unchanged district models are never included implicitly.
 for spec in SPECS:
  if spec['id'] in ARGS.review_ids and spec.get('geometryRevision')!=previous.get(spec['id'],{}).get('geometryRevision') and spec['id'] not in ARGS.ids:
   ARGS.ids.append(spec['id'])
REFERENCES=json.loads((ROOT/'references/tourism/north-bund-photos.json').read_text())
REFS={x['id']:x for x in REFERENCES['photos']}
records=[];roots=[]
if not ARGS.render_only:
 if ARGS.ids and EDIT.exists():
  bpy.ops.wm.open_mainfile(filepath=str(EDIT))
  records=[x for x in json.loads((OUT/'manifest.json').read_text())['models'] if x['id'] not in ARGS.ids];roots=[bpy.data.objects[x['id']] for x in records]
  for key in ARGS.ids:
   obj=bpy.data.objects.get(key)
   if obj:
    for child in list(obj.children_recursive)+[obj]:bpy.data.objects.remove(child,do_unlink=True)
 else:bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
else:bpy.ops.wm.open_mainfile(filepath=str(EDIT))
stone=material('north-bund-fine-limestone',(.60,.59,.56),.79)
white=material('north-bund-cut-stone-trim',(.74,.72,.67),.70)
bronze=material('north-bund-dark-bronze',(.065,.071,.066),.35,.65)
steel=material('north-bund-satin-aluminium',(.46,.51,.53),.31,.74)
roof=material('north-bund-waterproof-roof',(.12,.15,.16),.89)
red=material('north-bund-consulate-terracotta-tile',(.40,.048,.029),.83)
copper=material('north-bund-consulate-aged-copper',(.145,.285,.18),.60,.52)
brick=material('north-bund-red-brown-brick',(.30,.12,.075),.91)
glass=[material('north-bund-blue-grey-glass-'+str(i),c,.19,.46) for i,c in enumerate([(.105,.19,.23),(.12,.22,.27),(.14,.24,.29),(.12,.205,.25),(.16,.26,.30)])]
oldglass=[material('north-bund-old-window-'+str(i),c,.27,.21) for i,c in enumerate([(.14,.22,.20),(.22,.30,.27),(.27,.32,.27)])]
spandrel=material('north-bund-blue-grey-spandrel',(.115,.18,.20),.4,.40)


def centre(way):
 p=BUILDINGS[way]['points'];return [(min(x for x,z in p)+max(x for x,z in p))/2,(min(z for x,z in p)+max(z for x,z in p))/2]

def local(way,c=None):
 c=c or centre(way);return polygon_ccw([(x-c[0],-(z-c[1])) for x,z in BUILDINGS[way]['points']])

def new(spec):
 root=bpy.data.objects.new(spec['id'],None);bpy.context.collection.objects.link(root);root['exteriorOnly']=True;root['basis']='Archived inspected real photos and OSM plan; explicit unobserved inference'
 return root,Mesh(root)

def catmull(points,n=8):
 p=[Vector(v) for v in points];out=[]
 for i in range(len(p)):
  a,b,c,d=p[i-1],p[i],p[(i+1)%len(p)],p[(i+2)%len(p)]
  for j in range(n):
   f=j/n;v=.5*((2*b)+(-a+c)*f+(2*a-5*b+4*c-d)*f*f+(-a+3*b-3*c+d)*f*f*f);out.append(tuple(v))
 return polygon_ccw(out)

def entrance(m,p,t,n,width=8,z=5.3):
 p=Vector((*p,0));t=Vector(t);n=Vector(n)
 transformed_box(m,p+Vector((0,0,z)),t,n,(width+3.5,4,.22),steel)
 for x in [-width/2,width/2]:m.rod(p+t*x+n*1.6,p+t*x+n*1.6+Vector((0,0,z)),.13,steel,12)
 for x in [-3,-1,1,3]:
  transformed_box(m,p+t*x+n*.20+Vector((0,0,2.2)),t,n,(1.8,.10,4.4),glass[1])
  for dx in [-.92,.92]:m.rod(p+t*(x+dx)+n*.32,p+t*(x+dx)+n*.32+Vector((0,0,4.4)),.04,steel,8)
  m.rod(p+t*(x+.5)+n*.44+Vector((0,0,1.4)),p+t*(x+.5)+n*.44+Vector((0,0,2.0)),.026,bronze,8)


def physical_label(root,label,origin,t,n,size,mat):
 data=bpy.data.curves.new(root.name+'-identity-lettering','FONT');data.body=label;data.size=size;data.extrude=.035;data.bevel_depth=.012;data.resolution_u=3
 obj=bpy.data.objects.new(data.name,data);bpy.context.collection.objects.link(obj);obj.parent=root
 obj.rotation_euler=Matrix((Vector(t),Vector((0,0,1)),Vector(n))).transposed().to_euler();obj.location=origin;data.materials.append(mat)
 bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj;bpy.ops.object.convert(target='MESH')


def offset_roof_outline(poly,distance):
 out=[]
 for i,b in enumerate(poly):
  a=Vector(poly[i-1]);b=Vector(b);c=Vector(poly[(i+1)%len(poly)]);u=(b-a).normalized();v=(c-b).normalized();na=Vector((-u.y,u.x));nb=Vector((-v.y,v.x));summed=na+nb
  offset=summed*(distance/max(.2,1+na.dot(nb)))
  if offset.length>distance*3:offset=offset.normalized()*distance*3
  out.append(tuple(b+offset))
 return out


def magnolia(spec):
 root,m=new(spec);pts=local(spec['ways'][0]);pts=catmull(pts,6);p=resample_polygon(pts,1.4);n=len(p);H=320;levels=66
 # Photo shows an outward bow around mid-height and curved, petal-like crown.
 # The OSM outline supplies the base plan. The crown curve is photograph inferred.
 def point(i,k):
  x,y=p[i%n];f=k/levels;s=1+.035*math.sin(math.pi*f)-.025*f;angle=math.atan2(y,x)
  wave=8.4*(.5+.5*math.cos(4*(angle-.23)));z=f*(H-8.4)+(f**12)*wave
  return Vector((x*s,y*s,z))
 for k in range(levels):
  for j in range(n):
   a,b,c,d=point(j,k),point(j+1,k),point(j+1,k+1),point(j,k+1);t=(b-a).normalized();out=Vector((t.y,-t.x,0));g=glass[(j*3+k*7)%len(glass)]
   aa=a.lerp(d,.10);bb=b.lerp(c,.10)
   m.face([a,b,bb,aa],spandrel);m.face([aa,bb,c,d],g)
   m.rod(a+out*.045,d+out*.045,.043,steel,6)
   m.face([a,b,b+out*.33,a+out*.33],steel)
   m.face([a+out*.33,b+out*.33,b+out*.33+Vector((0,0,.075)),a+out*.33+Vector((0,0,.075))],steel)
   if k in [22,43,61]:m.face([a,b,b+Vector((0,0,.45)),a+Vector((0,0,.45))],spandrel)
 m.face([point(i,levels) for i in range(n)],roof)
 for j in range(n):m.rod(point(j,levels),point(j+1,levels),.09,steel,8)
 # Visible high lobby piers and layered entrance canopy at road-facing edges.
 for a,b in zip(pts,pts[1:]+pts[:1]):
  av=Vector((*a,0));bv=Vector((*b,0))
  if (bv-av).length>5:
   t=(bv-av).normalized();nn=Vector((t.y,-t.x,0));m.rod(av+nn*.13,av+nn*.13+Vector((0,0,8.6)),.14,steel,10)
 av,bv=Vector((*local(spec['ways'][0])[0],0)),Vector((*local(spec['ways'][0])[1],0));t=(bv-av).normalized();nn=Vector((t.y,-t.x,0));entrance(m,tuple(((av+bv)/2)[:2]),t,nn,11,6.2)
 return root,m,dict(independentWindowPanels=n*levels,observedDetails='320 m curved glass office tower; per-floor projecting light shelves; 66 story curtain-wall grid; scalloped petal crown; ground lobby canopy and doors',heightSource='OSM height 320 m; SOM architect 319.5 m / 66 storeys',heightSourceUrl='https://www.som.com/projects/sinar-mas-centre-formerly-white-magnolia-plaza/')


def hotel(spec):
 root,m=new(spec);pts=local(spec['ways'][0]);p=catmull(pts,4)
 count=curtain(m,p,172,39,glass,steel,spandrel,profile=lambda f:1-.055*f,pitch=1.65)
 # A pair of broad vertical seam bands distinguishes the curved hotel from tower.
 for frac in [.12,.65]:
  i=int(len(p)*frac);x,y=p[i]
  for z in range(0,172,4):m.rod((x*(1-.055*z/172),y*(1-.055*z/172),z),(x*(1-.055*(z+4)/172),y*(1-.055*(z+4)/172),min(172,z+4)),.15,steel,10)
 ring_rail(m,[(x*.945,y*.945) for x,y in p],172,bronze)
 av,bv=Vector((*p[0],0)),Vector((*p[len(p)//4],0));t=(bv-av).normalized();nn=Vector((t.y,-t.x,0));entrance(m,tuple(((av+bv)/2)[:2]),t,nn,8,5)
 # Source-observed W identity, geometric lettering without a billboard.
 xx,yy=p[len(p)//2];nn=Vector((xx,yy,0)).normalized();tt=Vector((-nn.y,nn.x,0));base=Vector((xx,yy,163))+nn*.4
 for a,b in zip([(-2,4),(-1,-.3),(0,2),(1,-.3),(2,4)],[(-1,-.3),(0,2),(1,-.3),(2,4)]):m.rod(base+tt*a[0]+Vector((0,0,a[1])),base+tt*b[0]+Vector((0,0,b[1])),.19,white,10)
 return root,m,dict(independentWindowPanels=count,observedDetails='172 m curved W hotel; kidney-shaped mapped plan; horizontal light shelves, vertical seam bands, rooftop railing, modeled W sign and entrance',heightSource='OSM height 172 m / 39 storeys')


def podium(spec):
 root,m=new(spec);c=spec['center'];parts=spec['ways'];count=0
 for way in parts:
  p=local(way,c);p=catmull(p,3);count+=curtain(m,p,17,3,glass,steel,spandrel,pitch=1.7)
  for z in [5.5,11.2,17]:band(m,p,z,1.20,.60,white)
  ring_rail(m,p,17,steel)
  # Roof gardens and stone perimeter coping are geometric, hidden construction inferred.
  for j in range(0,len(p),max(1,len(p)//20)):
   x,y=p[j];m.box((x*.92,y*.92,17.5),(2.6,1.0,.60),stone)
 # Shangqiu Road photograph: folded translucent roof canopy and large diagonal supports.
 # Place on the northeast retail wing, following its mapped street-side edge.
 north=local(parts[0],c);a,b=max(zip(north,north[1:]+north[:1]),key=lambda ab:math.dist(*ab));av,bv=Vector((*a,0)),Vector((*b,0));t=(bv-av).normalized();nn=Vector((t.y,-t.x,0));span=(bv-av).length
 for j in range(2):
  cp=av+t*(span*(.35+j*.30))+nn*.30
  m.rod(cp+Vector((0,0,1.4)),cp+t*4+Vector((0,0,10.4)),.43,white,12)
 for j in range(14):
  aa=av+t*(span*(.12+.045*j))-nn*2+Vector((0,0,17.3));bb=aa+t*(span*.045);peak=(aa+bb)/2-nn*2.3+Vector((0,0,1.8));backa=aa-nn*4.6;backb=bb-nn*4.6
  m.face([aa,bb,peak],white);m.face([bb,backb,peak],white);m.face([backb,backa,peak],white);m.face([backa,aa,peak],white)
 # Pebble-shaped glazed pavilion visible between hotel and office in street photos.
 # It occupies the mapped western podium; exact oblique shell curvature inferred.
 pc=Vector((-110-c[0],-(-1300-c[1]),17));rx,ry,rise=17,12,19
 for k in range(10):
  ph0=k*math.pi/22;ph1=(k+1)*math.pi/22
  for j in range(72):
   a=j*math.tau/72;b=(j+1)*math.tau/72
   def pp(t,f):return pc+Vector((rx*math.cos(t)*math.cos(f),ry*math.sin(t)*math.cos(f),rise*math.sin(f)))
   p0,p1,p2,p3=pp(a,ph0),pp(b,ph0),pp(b,ph1),pp(a,ph1);m.face([p0,p1,p2,p3],glass[(j+k)%5]);m.rod(p0,p1,.075,steel,8);m.rod(p0,p3,.045,steel,6)
 return root,m,dict(independentWindowPanels=count,observedDetails='Two interlocking curvilinear mapped podium wings, individual retail glazing, broad horizontal white bands, roof coping/railings and glazed pebble pavilion',heightSource='Main podium 17 m OSM estimate; pavilion rise 19 m photograph proportion estimate')


def consulate(spec):
 root,m=new(spec);p=local(spec['ways'][0]);body=15.8;levels=[0,1.8,6.5,11.2,15.8];count=0
 for a,b in zip(p,p[1:]+p[:1]):
  length=math.dist(a,b);bays=max(1,round(length/3.55));count+=bays*3
  for level in range(1,4):facade(m,a,b,levels[level],levels[level+1],bays,stone,white,oldglass,bronze,(.69 if level==2 else .53),.69,arches=level==2)
  # Plinth basement grille bays and expressed stone courses.
  facade(m,a,b,0,1.8,bays,stone,white,oldglass,bronze,.50,.50)
  for z in [1.8,6.5,11.2,15.8]:band(m,[a,b],z,.19,.32,white)
  av,bv=Vector((*a,0)),Vector((*b,0));t=(bv-av).normalized();nn=Vector((t.y,-t.x,0))
  for j in range(bays+1):
   cp=av+t*(length*j/bays)+nn*.07
   transformed_box(m,cp+Vector((0,0,9)),t,nn,(.33,.22,12.5),white)
  # Cornice dentils and rusticated corner quoin stones.
  for j in range(max(1,round(length/.60))):
   cp=av+t*(j*.60)+nn*.18;transformed_box(m,cp+Vector((0,0,15.35)),t,nn,(.20,.35,.26),white)
  for z in range(2,15):transformed_box(m,av+nn*.16+Vector((0,0,z+.23)),t,nn,(.68,.36,.44),white)
 band(m,p,16.02,.35,.6,white);m.face([(x,y,15.8) for x,y in p],roof)
 hipped_roof(m,p,16.25,5.4,red,red,.58)
 # Red-tile mansard seams: actual thin tile courses, modeled only on visible roof.
 cx=sum(x for x,y in p)/len(p);cy=sum(y for x,y in p)/len(p)
 for k in range(1,16):
  f=k/16;line=[(cx+(x-cx)*(1-.42*f),cy+(y-cy)*(1-.42*f)) for x,y in p]
  band(m,line,16.25+5.4*f,.025,.04,red)
 # White chimneys with red cap observed across the hip roof.
 for x,y in [(-10,-.5),(0,2),(11,1)]:
  m.bevel_box((x,y,22.1),(1.2,1.3,3.9),white,.06);m.box((x,y,24.1),(1.5,1.6,.20),red)
 # Landmark green copper turret toward the western gable, with octagonal lantern.
 tx,ty=-14,3;r=2.7
 m.lathe((tx,ty),[(19.2,r+.35),(19.6,r+.35),(19.9,r),(23.0,r),(23.3,r+.3)],white,8)
 for i in range(8):
  a=i*math.tau/8;x=tx+r*math.cos(a);y=ty+r*math.sin(a);m.rod((x,y,19.7),(x,y,23.2),.16,white,12)
  mid=a+math.pi/8;x1=tx+(r-.03)*math.cos(mid);y1=ty+(r-.03)*math.sin(mid)
  tangent=Vector((-math.sin(mid),math.cos(mid),0));normal=Vector((math.cos(mid),math.sin(mid),0));transformed_box(m,(x1,y1,21.4),tangent,normal,(1.15,.10,2),oldglass[1])
 m.lathe((tx,ty),[(23.3,3.15),(23.55,3.05),(24.3,2.50),(25.2,1.85),(26.0,1.30),(26.7,.56),(27.1,.27)],copper,64)
 for i in range(8):
  a=i*math.tau/8
  rings=[(23.35,3.15),(23.55,3.05),(24.3,2.5),(25.2,1.85),(26,1.3),(26.7,.56),(27.1,.27)]
  for (z0,r0),(z1,r1) in zip(rings,rings[1:]):m.rod((tx+r0*math.cos(a),ty+r0*math.sin(a),z0),(tx+r1*math.cos(a),ty+r1*math.sin(a),z1),.038,copper,8)
 m.rod((tx,ty,27.1),(tx,ty,34.5),.045,bronze,10)
 # River photo reveals one asymmetric Dutch gable above a columned balcony.
 x=-10;y=min(v[1] for v in p)-.18;z=16.15
 profile=[(-4.8,0),(-4.2,.65),(-3.7,1),(-3.2,1.25),(-2.35,2.55),(-1.55,3.65),(-.65,4.3),(0,4.55),(.65,4.3),(1.55,3.65),(2.35,2.55),(3.2,1.25),(3.7,1),(4.2,.65),(4.8,0)]
 m.face([(x+u,y,z+v) for u,v in profile],stone)
 for (u,v),(u1,v1) in zip(profile,profile[1:]):m.rod((x+u,y-.13,z+v),(x+u1,y-.13,z+v1),.15,white,10)
 for dx in [-1.5,0,1.5]:m.box((x+dx,y-.025,z+1.6),(1.0,.10,2),oldglass[0])
 # Two short Corinthian-like stone columns and gently bowed balcony rail.
 for dx in [-3,3]:m.lathe((x+dx,y-.70),[(11.2,.32),(11.4,.32),(11.55,.23),(14.9,.21),(15.15,.33),(15.35,.34)],white,32,flutes=12)
 for j in range(40):
  u=-4+j*8/39;yy=y-.7-.5*(1-(u/4)**2)
  m.rod((x+u,yy,10.95),(x+u,yy,11.87),.065,white,10)
  if j<39:
   un=-4+(j+1)*8/39;yyn=y-.7-.5*(1-(un/4)**2);m.rod((x+u,yy,11.92),(x+un,yyn,11.92),.11,white,10)
 m.box((x,y-.68,10.85),(8.5,1.5,.25),white)
 # Round dormers with green-roof copper portico and physical door handles.
 for x in [-14,-5,5,15]:
  y=min(v[1] for v in p)+1.7;m.box((x,y,18.0),(1.3,.3,1.8),oldglass[1]);m.arch(x,y-.23,18.3,1.4,.55,.12,.20,red)
 # The photographed river face has no modern glass entry canopy; none is invented.
 return root,m,dict(independentWindowPanels=count,observedDetails='Grey-white rusticated walls, two arched-window levels, physical timber/bronze mullions, multi-layer dentil cornice, red hipped/mansard roof with tile courses, green copper octagonal lantern, asymmetric curved Dutch gable with columned balcony, dormers and white chimneys',heightSource='OSM base 17 m; body/roof/lantern proportions estimated from archived front-side photograph; flagpole included separately',heightUncertaintyMetres=3.5)


def yesong(spec):
 root,m=new(spec);p=local(spec['ways'][0]);floor=4.4;count=0;green=material('north-bund-yesong-glazed-tiles',(.14,.28,.22),.32,.20);slate=material('north-bund-yesong-dark-slate',(.09,.115,.12),.70)
 c=Vector((sum(x for x,y in p)/len(p),sum(y for x,y in p)/len(p)))
 def scaled(f):return [(c.x+(x-c.x)*f,c.y+(y-c.y)*f) for x,y in p]
 # Three-storey base followed by two individually recessed upper storeys.
 for level,scale in enumerate([1,1,1,.82,.65]):
  poly=scaled(scale)
  for a,b in zip(poly,poly[1:]+poly[:1]):
   bays=max(2,round(math.dist(a,b)/3.9));count+=bays
   facade(m,a,b,level*floor,(level+1)*floor,bays,brick,white,oldglass,bronze,.50,.66,arches=level==0)
   av,bv=Vector((*a,0)),Vector((*b,0));t=(bv-av).normalized();nn=Vector((t.y,-t.x,0));length=(bv-av).length
   # Additional fine window grid of the restored steel windows.
   for j in range(bays):
    cp=av+t*((j+.5)*length/bays)+Vector((0,0,level*floor+floor*.52));ww=length/bays*.50;hh=floor*.66
    for f in [-.25,.25]:m.rod(cp+t*(ww*f)-nn*.1-Vector((0,0,hh/2)),cp+t*(ww*f)-nn*.1+Vector((0,0,hh/2)),.018,bronze,6)
    for f in [-.28,-.08,.30]:m.rod(cp-t*ww/2-nn*.1+Vector((0,0,hh*f)),cp+t*ww/2-nn*.1+Vector((0,0,hh*f)),.018,bronze,6)
   # Stretcher bond mortar is explicit light shallow linework between openings.
   for row in range(int(floor/.23)):
    z=level*floor+row*.23
    for j in range(bays):
     cp=av+t*(j*length/bays)+nn*.008+Vector((0,0,z));width=length/bays*.22
     m.rod(cp,cp+t*width,.009,stone,4)
  band(m,poly,(level+1)*floor,.12,.17,white)
  if level>=2:
   # Broad dark hipped eave extending over the next terrace below.
   lower=scaled(scale+(.025 if level==2 else .03));upper=scaled(scale-.08)
   z=(level+1)*floor
   for a,b,aa,bb in zip(lower,lower[1:]+lower[:1],upper,upper[1:]+upper[:1]):
    m.face([(*a,z),(*b,z),(*bb,z+1.0),(*aa,z+1.0)],slate)
    m.rod((*a,z),(*b,z),.055,slate,8)
   m.face([(*x,z+1) for x in upper],slate)
  if level==1:
   # Continuous pale stone balcony railing with actual openings.
   rail=scaled(1.025);band(m,rail,8.9,.22,.44,white)
   for a,b in zip(rail,rail[1:]+rail[:1]):
    av,bv=Vector((*a,9)),Vector((*b,9));t=(bv-av).normalized();nn=Vector((t.y,-t.x,0));length=(bv-av).length
    for j in range(max(1,round(length/.72))):transformed_box(m,av+t*(j*.72)+Vector((0,0,.46)),t,nn,(.27,.22,.92),white)
    m.rod(av+Vector((0,0,1)),bv+Vector((0,0,1)),.13,white,8)
 # West-side square tower integrated into the stepped body, below the green spire.
 # Map's long western edge has north/east components; use actual footprint frame.
 edges=[(a,b) for a,b in zip(p,p[1:]+p[:1])];a,b=min(edges,key=lambda e:(e[0][0]+e[1][0])/2);av,bv=Vector((*a,0)),Vector((*b,0));t=(bv-av).normalized();nn=Vector((t.y,-t.x,0));tower=(av+bv)/2-nn*1.6;tw=5.8;dep=5.8
 def square(z,w=tw):return [tower+t*x+nn*y+Vector((0,0,z)) for x,y in [(-w/2,-w/2),(w/2,-w/2),(w/2,w/2),(-w/2,w/2)]]
 for z0,z1 in [(0,4.4),(4.4,8.8),(8.8,13.2),(13.2,17.6),(17.6,22),(22,27)]:
  # t/right-normal is a reflected frame: explicitly restore counterclockwise
  # winding so reveals and steel mullions face outside rather than behind glass.
  pts=polygon_ccw([v[:2] for v in square(0)])
  for aa,bb in zip(pts,pts[1:]+pts[:1]):
   av0,bv0=Vector((*aa,0)),Vector((*bb,0));tt=(bv0-av0).normalized();nv=Vector((tt.y,-tt.x,0))
   if z0==0 and nv.dot(nn)>.95:continue # Real circular entrance constructed below.
   facade(m,aa,bb,z0,z1,1,brick if z1<=22 else stone,white,oldglass,bronze,.43,.70);count+=1
   hh=(z1-z0)*.70;ww=tw*.43;cp=(av0+bv0)/2+Vector((0,0,z0+(z1-z0)*.52))-nv*.08
   for fraction in [-.25,.25]:m.rod(cp+tt*(ww*fraction)-Vector((0,0,hh/2)),cp+tt*(ww*fraction)+Vector((0,0,hh/2)),.023,bronze,8)
   for fraction in [-.35,-.18,0,.31]:m.rod(cp-tt*ww/2+Vector((0,0,hh*fraction)),cp+tt*ww/2+Vector((0,0,hh*fraction)),.023,bronze,8)
   if z1<=22:brick_courses(m,aa,bb,z0,z1,1,.23,brick,stone,.43,.70)
 band(m,[v[:2] for v in square(0)],22,.28,.5,white)
 # Four-sided curved pavilion roof with upturned eaves and green rounded tiles.
 def roofpoint(side,u,f):
  corners=[t*(-4.3)+nn*(-4.3),t*4.3+nn*(-4.3),t*4.3+nn*4.3,t*(-4.3)+nn*4.3]
  edge=corners[side].lerp(corners[(side+1)%4],u);s=(1-f)**.82
  z=27+6.7*f+(.62*(2*u-1)**6)*(1-f)**5
  return tower+edge*s+Vector((0,0,z))
 for side in range(4):
  for j in range(24):
   u=j/24;un=(j+1)/24
   for k in range(16):
    f=k/16;fn=(k+1)/16;v0,v1,v2,v3=roofpoint(side,u,f),roofpoint(side,un,f),roofpoint(side,un,fn),roofpoint(side,u,fn);m.face([v0,v1,v2,v3],green)
    m.rod(v0,v3,.032,green,8)
   m.rod(roofpoint(side,u,0),roofpoint(side,un,0),.075,green,10)
  # Soffit brackets in three receding timber blocks.
  for j in range(7):
   cp=roofpoint(side,(j+.5)/7,0)
   for k in range(3):m.box(tuple(cp+Vector((0,0,-.25-k*.18))),(.32+.18*k,.32+.18*k,.15),red)
 m.rod(tuple(tower+Vector((0,0,33.7))),tuple(tower+Vector((0,0,35))),.055,bronze,10)
 # Moon gate: the photographed portal is an open circular masonry aperture,
 # with straight lower jambs. Do not cover it with the former rectangular pane.
 gate=tower+nn*(dep/2+.12)+Vector((0,0,2));r=1.65
 recess=material('north-bund-yesong-entry-shadow',(.045,.051,.047),.93)
 def half_opening(z):return math.sqrt(max(0,r*r-(max(z,.7)-2)**2)) if z<2+r else 0
 for row in range(88):
  z0=row*.05;z1=(row+1)*.05;h0=half_opening(z0);h1=half_opening(z1)
  for sign in [-1,1]:
   pp=lambda x,z:tower+t*x+nn*(dep/2+.12)+Vector((0,0,z))
   face=[pp(sign*h0,z0),pp(sign*tw/2,z0),pp(sign*tw/2,z1),pp(sign*h1,z1)]
   m.face(face if sign>0 else face[::-1],brick)
   if h0 or h1:m.face([pp(sign*h0,z0),pp(sign*h1,z1),pp(sign*h1,z1)-nn*.45,pp(sign*h0,z0)-nn*.45],stone)
 for k in range(72):
  aa=k*math.tau/72;bb=(k+1)*math.tau/72
  if math.sin((aa+bb)/2)<-.88:continue
  pp=lambda rr,th:gate+t*(rr*math.cos(th))+Vector((0,0,rr*math.sin(th)))
  m.face([pp(r,aa),pp(r,bb),pp(r+.20,bb),pp(r+.20,aa)][::-1],white)
 for sign in [-1,1]:
  x=sign*half_opening(.7);m.rod(tower+t*x+nn*(dep/2+.135),tower+t*x+nn*(dep/2+.135)+Vector((0,0,.7)),.09,white,10)
 outline=[tower+t*(-half_opening(.7))+Vector((0,0,0)),tower+t*half_opening(.7)+Vector((0,0,0))]
 outline += [gate+t*(r*math.cos(k*math.pi/72))+Vector((0,0,r*math.sin(k*math.pi/72)))-nn*(dep/2+.12) for k in range(73)]
 m.face([v+nn*(dep/2-.70) for v in outline],recess)
 # Continuous ceramic canopy surface and individual rounded tile courses,
 # with upturned ends and a red timber fascia visible beneath the green eaves.
 def canopy(x,f):return tower+t*x+nn*(dep/2+.12+f*2.0)+Vector((0,0,5.15+.70*(x/3.65)**4-.42*f+.10*f*f))
 for j in range(32):
  x=-3.65+j*7.30/32;xn=-3.65+(j+1)*7.30/32
  for k in range(9):
   f=k/9;fn=(k+1)/9;m.face([canopy(x,f),canopy(xn,f),canopy(xn,fn),canopy(x,fn)],green)
   m.rod(canopy((x+xn)/2,f)+Vector((0,0,.04)),canopy((x+xn)/2,fn)+Vector((0,0,.04)),.080,green,10)
  a0,b0=canopy(x,1),canopy(xn,1);m.face([a0,b0,b0-Vector((0,0,.25)),a0-Vector((0,0,.25))],red)
 for x in [-2.75,0,2.75]:
  for k in range(3):transformed_box(m,canopy(x,.45)-Vector((0,0,.35+k*.15)),t,nn,(.35+k*.15,1.05-k*.20,.14),red)
 return root,m,dict(independentWindowPanels=count,observedDetails='2024 restoration photographs: five-storey brick building, three distinct dark roof terraces, continuous pale-stone balcony, west square tower, green four-corner upturned tiled pavilion, dense metal window grids and moon gate entrance',heightSource='Five-storey OSM plan; 22 m main roof + 11.7 m turret inferred from observed floor spacing; not surveyed',heightUncertaintyMetres=3)


def sipg(spec):
 root,m=new(spec);poly=local(spec['ways'][0]);p=resample_polygon(catmull(poly,3),1.35);n=len(p);H=127.;levels=29
 x0=min(x for x,y in p);span=max(x for x,y in p)-x0
 dark=material('sipg-anthracite-diagrid',(.10,.13,.13),.31,.65)
 glazing=[material('sipg-warm-smoke-glass-'+str(i),c,.21,.48) for i,c in enumerate([(.16,.22,.21),(.18,.24,.22),(.21,.25,.22)])]
 def crown(x):return H-8+8*(x-x0)/span
 def pp(j,k):
  j=j%n;i=math.floor(j);f=j-i;x=p[i][0]*(1-f)+p[(i+1)%n][0]*f;y=p[i][1]*(1-f)+p[(i+1)%n][1]*f
  z=(H-11)*min(k,levels)/levels
  if k>levels:z=(H-11)+(crown(x)-(H-11))*min(1,k-levels)
  return Vector((x,y,z))
 for k in range(levels+1):
  for j in range(n):
   a,b,c,d=pp(j,k),pp(j+1,k),pp(j+1,k+1),pp(j,k+1);nn=(b-a).cross(Vector((0,0,1))).normalized()
   m.face([a,b,c,d],glazing[(j//4+k)%3]);m.rod(a+nn*.025,d+nn*.025,.028,dark,6)
   m.rod(a+nn*.04,b+nn*.04,.050,dark,6)
 # Three-floor X members form the photographed six-floor diamond rhythm.
 diagrid_bays=max(12,round(n/5));step=n/diagrid_bays
 for j in range(diagrid_bays):
  for k in range(0,levels,3):
   for sign in [-1,1]:
    for seg in range(6):
     kk=k+seg*.5;kn=min(levels,kk+.5)
     if kn<=kk:continue
     shift=(k//3%2)*step/2
     a=pp(j*step+shift+sign*step*(kk-k)/6,kk);b=pp(j*step+shift+sign*step*(kn-k)/6,kn)
     nn=Vector((a.x,a.y,0)).normalized();m.rod(a+nn*.18,b+nn*.18,.145,dark,8)
 for j in range(n):m.rod(pp(j,levels+1),pp(j+1,levels+1),.11,dark,8)
 m.face([pp(j,levels+1) for j in range(n)],roof)
 # Thin vertical crown louvers follow the sloping roof rather than a flat cap.
 for j in range(0,n,2):m.rod(pp(j,levels),pp(j,levels+1),.07,dark,8)
 j=min(range(n),key=lambda j:p[j][1]);aa,bb=pp(j,levels),pp(j+1,levels);tt=(bb-aa).normalized();nv=Vector((tt.y,-tt.x,0));cp=Vector((aa.x,aa.y,H-13))-tt*5+nv*.45
 physical_label(root,'SIPG',cp,tt,nv,3.5,white)
 return root,m,dict(independentWindowPanels=n*(levels+1),observedDetails='Photograph: rounded triangular plan, warm grey glass, six-floor diamond exoskeleton, narrow horizontal transoms and inclined curved crown. The street-level entry is obscured in the source and has not been invented.',heightSource='CVU/Skyscraper Center 127 m estimate, 29 floors; replaces OSM 22-floor estimate',heightSourceUrl='https://www.skyscrapercenter.com/shanghai/sipg-tower/15150',heightUncertaintyMetres=10,photoVerified=True,realPhotoAcceptance=False,confidence='Source-matched silhouette and envelope; entry and crown orientation require additional views')


def ocean(spec):
 root,m=new(spec);raw=local(spec['ways'][0]);av,bv=Vector((*raw[0],0)),Vector((*raw[1],0));t=(bv-av).normalized();nn=Vector((t.y,-t.x,0));c=Vector((0,0,0));w=(bv-av).length;d=math.dist(raw[1],raw[2]);H=102
 sand=material('ocean-pink-granite-ribs',(.47,.38,.31),.73);light=material('ocean-pale-stone-inlay',(.65,.59,.50),.65)
 blue=[material('ocean-cobalt-curtain-'+str(i),c,.22,.45) for i,c in enumerate([(.10,.23,.31),(.12,.26,.35),(.15,.27,.35)])]
 def p(x,y,z=0):return t*x+nn*y+Vector((0,0,z))
 # Model a mapped rectilinear base and rounded glazing crown seen from the street.
 poly=[tuple(p(x,y)[:2]) for x,y in [(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]];poly=polygon_ccw(poly)
 count=curtain(m,poly,89,25,blue,steel,spandrel,pitch=1.45)
 for edge,(a,b) in enumerate(zip(poly,poly[1:]+poly[:1])):
  aa,bb=Vector((*a,0)),Vector((*b,0));tt=(bb-aa).normalized();nv=Vector((tt.y,-tt.x,0));le=(bb-aa).length
  # Paired wide stone strips enclose the narrow punched-window columns.
  for u in [.08,.29,.71,.92]:
   cp=aa+tt*le*u+nv*.18
   transformed_box(m,cp+Vector((0,0,43.5)),tt,nv,(.88,.40,87),sand)
   transformed_box(m,cp+nv*.24+Vector((0,0,43.5)),tt,nv,(.14,.08,87),light)
  # The reference has broad pink masonry strips with two narrow punched
  # windows, not just a generic glass curtain wall behind slender trim rods.
  for lo,hi in [(.085,.285),(.715,.915)]:
   a2=tuple((aa+tt*(le*lo)+nv*.24)[:2]);b2=tuple((aa+tt*(le*hi)+nv*.24)[:2])
   for k in range(4,25):facade(m,a2,b2,k*89/25,(k+1)*89/25,2,sand,light,blue,steel,.57,.67)
  for z in [0,12.3,86.5,89]:band(m,[a,b],z,.55,.55,sand)
 # Six upper glazed levels become a shallow elliptical crown, with a stone
 # rear service fin; exact roof equipment is unobserved and is omitted.
 ellipse=[tuple(p(w*.48*math.cos(i*math.tau/80),d*.48*math.sin(i*math.tau/80))[:2]) for i in range(80)]
 count+=curtain(m,ellipse,12,3,blue,steel,spandrel,zbase=89,pitch=1.0)
 band(m,ellipse,101,.52,.32,light)
 for j in range(0,80,8):
  x,y=ellipse[j];m.rod((x,y,89),(x,y,101),.13,sand,10)
 # Source-observed rear crown fin, distinct from the rounded glazing.
 transformed_box(m,p(-w*.30,-d*.31,97),t,nn,(w*.26,2.0,13),sand)
 transformed_box(m,p(-w*.30,-d*.31,103.5),t,nn,(w*.26,2.0,.32),light)
 a,b=poly[0],poly[1];aa,bb=Vector((*a,0)),Vector((*b,0));tt=(bb-aa).normalized();nv=Vector((tt.y,-tt.x,0));entrance(m,tuple(((aa+bb)/2)[:2]),tt,nv,6,4.8)
 return root,m,dict(independentWindowPanels=count,observedDetails='Photographed blue-grey window strips, paired pink stone vertical ribs, lower entrance frame, rounded upper glass crown and asymmetric stone service fin. OSM map rectangle retained for the main footprint.',heightSource='Existing OSM 30-floor/102 m estimate; crown and 25 main bands adjusted to visible street photograph',heightUncertaintyMetres=5,photoVerified=True,realPhotoAcceptance=False,confidence='Building identity and main envelope matched; low-resolution source limits entrance and crown detail')


def jinshan(spec):
 root,m=new(spec);p=local(spec['ways'][0]);main=20.5;floor=main/5;count=0
 greybrick=material('jinshan-restored-grey-brick',(.27,.29,.27),.90);salmon=material('jinshan-salmon-brick-trim',(.52,.27,.16),.88);mortar=material('jinshan-grey-mortar',(.33,.34,.31),.92);sill=material('jinshan-weathered-stone-sill',(.49,.48,.43),.86)
 metalroof=material('jinshan-standing-seam-blue-metal',(.19,.27,.30),.53,.50);frames=material('jinshan-deep-green-frames',(.046,.093,.060),.52,.30);aqua=[material('jinshan-window-glass-'+str(i),c,.29,.25) for i,c in enumerate([(.10,.18,.14),(.13,.23,.16),(.22,.28,.20)])]
 for a,b in zip(p,p[1:]+p[:1]):
  length=math.dist(a,b)
  if length<.7:continue
  bays=max(1,round(length/3.25));count+=bays*6;av,bv=Vector((*a,0)),Vector((*b,0));tt=(bv-av).normalized();nv=Vector((tt.y,-tt.x,0));pitch=length/bays
  for k in range(5):
   facade(m,a,b,k*floor,(k+1)*floor,bays,greybrick,sill,aqua,frames,.44 if k else .72,.72 if k else .68)
   brick_courses(m,a,b,k*floor,(k+1)*floor,bays,.20,greybrick,mortar,.44 if k else .72,.72 if k else .68)
   if k:
    for j in range(bays):
     cp=av+tt*((j+.5)*pitch)+Vector((0,0,k*floor+floor*.52));ww=pitch*.44;wh=floor*.72
     # Distinct shallow salmon segmental window heads and two-by-four sashes.
     for seg in range(16):
      aa=math.pi*seg/16;bb=math.pi*(seg+1)/16
      def pp(ang,r):return cp+tt*(r*math.cos(ang))+nv*.035+Vector((0,0,wh/2+.10+.22*math.sin(ang)))
      m.rod(pp(aa,ww*.59),pp(bb,ww*.59),.10,salmon,6)
     for zf in [-.25,.0,.25]:m.rod(cp-tt*ww/2-nv*.10+Vector((0,0,wh*zf)),cp+tt*ww/2-nv*.10+Vector((0,0,wh*zf)),.022,frames,6)
     if j%2==0:air_conditioner(m,cp+tt*(ww*.55)+nv*.45-Vector((0,0,wh*.55)),tt,nv,white,bronze)
   for zz in [(k+1)*floor-.15]:band(m,[a,b],zz,.13,.24,sill)
   if k==1:band(m,[a,b],floor+.23,.60,.035,salmon)
  # Blue sheet-metal sixth floor and long slim rectangular windows, matching
  # the 2023 published repair photograph rather than the old red tiled roof.
  facade(m,a,b,main,main+3.7,bays,metalroof,metalroof,aqua,frames,.40,.70)
  for j in range(bays*5+1):
   cp=av+tt*(length*j/(bays*5));u=(j/5)%1
   segments=[(0,.62),(3.23,3.7)] if .30<u<.70 else [(0,3.7)]
   for za,zb in segments:m.rod(cp+Vector((0,0,main+za)),cp+Vector((0,0,main+zb)),.012,metalroof,6)
  # Eaves with a sloping blue flashing on the old cornice, continuous drain.
  for z,th,pr,mat in [(main,.20,.45,salmon),(main+.18,.18,.60,metalroof),(main+3.72,.18,.35,white)]:band(m,[a,b],z,th,pr,mat)
  m.rod(av+nv*.28+Vector((0,0,.1)),av+nv*.28+Vector((0,0,main+3.9)),.065,metalroof,8)
 # Offset the V-shaped outline along its walls. Scaling around a courtyard
 # centroid made crossing roof faces and holes in the first exported GLB.
 top=offset_roof_outline(p,1.1);z0=main+3.8;z1=z0+1.9
 for i in range(len(p)):
  j=(i+1)%len(p);m.face([(*p[i],z0),(*p[j],z0),(*top[j],z1),(*top[i],z1)],metalroof)
 roof_vertices=[Vector((*xy,z1)) for xy in top]
 for triangle in tessellate_polygon([roof_vertices]):
  # Blender 5.2 returns corner indices; older versions returned the vectors.
  m.face([roof_vertices[v] if isinstance(v,int) else v for v in triangle],metalroof)
 return root,m,dict(independentWindowPanels=count,observedDetails='2023 government photograph: mapped V-shaped building, five grey-brick lower floors, salmon segmental heads and brick bands, slender green 2x4 sash windows, white horizontal stringcourses, individual condensers, blue metal sixth floor and shallow metal hipped roof.',heightSource='Five original storeys plus photographed metal sixth floor; 26.2 m photo proportion estimate replaces untagged 17 m default',heightUncertaintyMetres=3,photoVerified=True,realPhotoAcceptance=False,confidence='Two street wings and material/roof family source-matched; courtyard and exact bay survey unverified')


def hailun(spec):
 root,m=new(spec);p=local(spec['ways'][0]);H=54.;levels=18;floor=3.;count=0
 cream=material('hailun-beige-stucco',(.59,.52,.43),.88);pale=material('hailun-window-sill',(.65,.62,.56),.80);frame=material('hailun-aluminium-window',(.40,.45,.43),.45,.50)
 for a,b in zip(p,p[1:]+p[:1]):
  le=math.dist(a,b)
  if le<.65:continue
  bays=max(1,round(le/3.3));av,bv=Vector((*a,0)),Vector((*b,0));tt=(bv-av).normalized();nv=Vector((tt.y,-tt.x,0));pitch=le/bays;count+=bays*levels
  for k in range(levels):
   facade(m,a,b,k*floor,(k+1)*floor,bays,cream,pale,oldglass,frame,.64,.56)
   for j in range(bays):
    cp=av+tt*((j+.5)*pitch)+Vector((0,0,k*floor+1.6))
    # The photographed projecting stacked glazed balconies occupy broad
    # primary faces above the lower three floors. Small returns stay plain.
    if le>18 and k>=3 and j%3!=1:
     ww=pitch*.90;dep=.85
     transformed_box(m,cp+nv*dep-Vector((0,0,.82)),tt,nv,(ww,dep*2,.40),cream)
     transformed_box(m,cp+nv*dep+Vector((0,0,.82)),tt,nv,(ww,dep*2,.30),cream)
     transformed_box(m,cp+nv*(dep*2-.08),tt,nv,(ww,.08,1.42),oldglass[j%3])
     for jj in range(5):m.rod(cp+tt*(ww*(jj/4-.5))+nv*(dep*2)-Vector((0,0,.7)),cp+tt*(ww*(jj/4-.5))+nv*(dep*2)+Vector((0,0,.7)),.025,frame,6)
    if k>0 and j%3==0:air_conditioner(m,cp+tt*pitch*.36+nv*.36-Vector((0,0,.65)),tt,nv,pale,bronze)
   # Lower window safety rails visible in the building's 2017 close views.
   if k in [0,1,2]:
    for j in range(bays):
     cp=av+tt*((j+.5)*pitch)+nv*.32+Vector((0,0,k*floor+.8));ww=pitch*.68
     for z in [0,.22,.44]:m.rod(cp-tt*ww/2+Vector((0,0,z)),cp+tt*ww/2+Vector((0,0,z)),.024,frame,6)
  for a0 in [av,bv]:m.rod(a0+nv*.18+Vector((0,0,.2)),a0+nv*.18+Vector((0,0,H)),.06,pale,8)
  band(m,[a,b],H,.22,.3,pale)
 m.face([(*xy,H) for xy in p],roof)
 return root,m,dict(independentWindowPanels=count,observedDetails='2017 address-matched photographs at Hailun Road 75: beige plaster, stacked projecting glazed balconies, aluminium window divisions, exterior condensers, white drainpipes and lower window security rails. Upper roof is absent in the source.',heightSource='OSM 54 m / 18 floors retained; photographed balcony depths estimated',photoVerified=True,realPhotoAcceptance=False,confidence='Address and partial facade observed; upper-floor repetition and roof remain inferred')


def jiantang(spec):
 root,m=new(spec);p=local(spec['ways'][0]);count=0
 plaster=material('jiantang-pale-pink-stucco',(.60,.53,.46),.88);darkstone=material('jiantang-shop-grey-brick',(.19,.20,.19),.86)
 signs=[material('jiantang-shop-green',(.025,.24,.10),.65),material('jiantang-shop-red',(.46,.06,.035),.65),material('jiantang-shop-yellow',(.60,.43,.02),.65)]
 matched_edge=[(x-spec['center'][0],-(z-spec['center'][1])) for x,z in spec['components'][0]['frontage']['edge']]
 for i,(a,b) in enumerate(zip(p,p[1:]+p[:1])):
  le=math.dist(a,b)
  if le<.7:continue
  av,bv=Vector((*a,0)),Vector((*b,0));tt=(bv-av).normalized();nv=Vector((tt.y,-tt.x,0));bays=max(1,round(le/4.4));pitch=le/bays;count+=bays*2
  facade(m,a,b,0,3.8,bays,darkstone,steel,oldglass,steel,.85,.82)
  facade(m,a,b,3.8,6.8,bays,plaster,white,oldglass,steel,.83,.52)
  photo_edge=min(math.dist(a,matched_edge[0])+math.dist(b,matched_edge[1]),math.dist(a,matched_edge[1])+math.dist(b,matched_edge[0]))<.5
  for j in range(bays):
   cp=av+tt*((j+.5)*pitch)
   fascia=signs[min(2,int(j*3/bays))] if photo_edge else darkstone
   transformed_box(m,cp+nv*.30+Vector((0,0,3.5)),tt,nv,(pitch-.07,.48,1.12),fascia)
   # Physical ribbed fascia, recessed door glazing and tall safety grilles.
   for k in range(9):m.rod(cp-tt*(pitch/2-.12)+nv*.56+Vector((0,0,3.04+k*.115)),cp+tt*(pitch/2-.12)+nv*.56+Vector((0,0,3.04+k*.115)),.012,fascia,6)
   for k in range(12):m.rod(cp+tt*((k/11-.5)*pitch*.83)+nv*.18+Vector((0,0,4.5)),cp+tt*((k/11-.5)*pitch*.83)+nv*.18+Vector((0,0,6.4)),.016,steel,6)
   if j%2==0:air_conditioner(m,cp+nv*.40+Vector((0,0,6.45)),tt,nv,white,bronze)
  band(m,[a,b],6.8,.18,.26,white)
 m.face([(*xy,6.8) for xy in p],roof)
 return root,m,dict(independentWindowPanels=count,observedDetails='2017 Jiantang street photographs: low commercial podium, grey brick piers, green/red/yellow ribbed shop fascia, metal doors and upper security grilles. Only the mapped two-floor podium is modeled; the taller apartment tower is outside this way.',heightSource='OSM two-floor podium 6.8 m retained; 14-floor estate description explicitly not applied to the podium',photoVerified=True,realPhotoAcceptance=False,confidence='Street-level commercial treatment matched; 2017 tenant colours and upper podium/roof are not current survey data')


def frontage(spec):
 root,m=new(spec);total=0;components=[]
 neutral=[(.49,.48,.43),(.51,.50,.45),(.45,.46,.45),(.55,.52,.45)]
 for component in spec['components']:
  way=component['wayId'];p=local(way,spec['center']);height=component['height'];tags=component['rawTags'];kind=tags.get('building','yes')
  obj=bpy.data.objects.new('north-bund-mapped-way-'+str(way),None);bpy.context.collection.objects.link(obj);obj.parent=root;obj['osmWay']=way;obj['photoStatus']=component['photoStatus'];sub=Mesh(obj)
  levels=int(tags.get('building:levels',max(1,round(height/3.4))));levels=max(1,min(45,levels));floor=height/levels
  wall=material('north-bund-inferred-wall-'+str(way),neutral[way%len(neutral)],.85)
  trim=material('north-bund-inferred-trim-'+str(way),tuple(min(.8,x+.10) for x in neutral[way%len(neutral)]),.77)
  frames=bronze;style='mapped-neutral-masonry'
  if kind in ['apartments','residential']:style='mapped-residential-recessed-windows'
  if height>70:style='mapped-highrise-frame';wall=stone;trim=steel
  floor_bays=0
  for a,b in zip(p,p[1:]+p[:1]):
   length=math.dist(a,b)
   if length<.3:continue
   bays=max(1,round(length/(3.7 if height<45 else 3.4)));floor_bays+=bays
   for level in range(levels):
    # No photo is attached to these windows: their arrangement is an explicit,
    # replaceable inference on the exact mapped perimeter, not visual acceptance.
    facade(sub,a,b,level*floor,(level+1)*floor,bays,wall,trim,oldglass if height<45 else glass,frames,.52 if kind in ['apartments','residential'] else .57,.58)
   av,bv=Vector((*a,0)),Vector((*b,0));t=(bv-av).normalized();nn=Vector((t.y,-t.x,0))
   for z in [0,.65,height]:band(sub,[a,b],z,.17,.24,trim)
   for level in range(1,levels):band(sub,[a,b],level*floor,.065,.04,trim)
   # Parapet coping and one correctly placed rainwater pipe at perimeter corners.
   band(sub,[a,b],height+.42,.13,.42,trim)
   sub.rod(av+nn*.16+Vector((0,0,.25)),av+nn*.16+Vector((0,0,height-.2)),.045,bronze,8)
  sub.face([(*xy,height) for xy in p],roof)
  # Exact floor count and roof outline, no unverified tower crowns/ornament/signs.
  sub.flush();total+=floor_bays*levels;components.append({'wayId':way,'levels':levels,'height':height,'heightSource':component['heightSource'],'frontageWidthM':component['frontage']['widthM'],'visibleRoadLengthM':component['frontage']['visibleRoadLengthM'],'appearanceBasis':style,'matchedExteriorPhoto':False})
 return root,m,dict(independentWindowPanels=total,observedDetails='OSM perimeter, map position and tagged floor/height data only; separate building components, recessed window geometry, coping and drainage. All facade rhythms/material colours remain inferred pending photographs.',heightSource='Per-component OSM tags or explicit catalogue estimate',componentTreatment=components,photoVerified=False,realPhotoAcceptance=False,confidence='geometry complete but facade appearance unverified')


def hyatt_tower(spec):
 root,m=new(spec);poly=local(spec['ways'][0]);H=133.;base=13.6;body_top=127.;levels=30;count=0
 pale=material('hyatt-honed-sandstone',(.58,.49,.36),.80);joint=material('hyatt-sandstone-joint',(.43,.39,.30),.89)
 turquoise=[material('hyatt-pale-turquoise-glass-'+str(i),c,.21,.45) for i,c in enumerate([(.14,.31,.34),(.18,.35,.37),(.23,.39,.39),(.18,.33,.34)])]
 frame=material('hyatt-silver-grey-window-frame',(.46,.50,.47),.40,.65);crown=material('hyatt-bronze-open-roof-frame',(.28,.17,.095),.50,.65)
 # Source photographs show a broad curved glass river facade and a sandstone
 # sawtooth rear facade. Keep the true independent tower plan, elevate it from
 # the existing podium, and treat the unresolved corner radii explicitly.
 perimeter=[];roles=[]
 edges=list(zip(poly,poly[1:]+poly[:1]));longest=max(math.dist(*edge) for edge in edges)
 for edge,(a,b) in enumerate(edges):
  av,bv=Vector((*a,0)),Vector((*b,0));tt=(bv-av).normalized();nv=Vector((tt.y,-tt.x,0));le=(bv-av).length
  # Each mapped wedge has one long straight rear edge and a multi-edge glass
  # front; the two towers mirror one another, so a global compass test would
  # incorrectly omit the sandstone rear on the east tower.
  is_stone=le>longest*.90
  nb=max(1,round(le/3.6))
  if is_stone:
   # Alternating projecting returns create the distinctive five-tooth profile.
   teeth=5
   for j in range(teeth):
    aa=av+tt*le*j/teeth;bb=av+tt*le*(j+1)/teeth;peak=aa+tt*le/teeth*.20+nv*3.2
    # Each photographed tooth has one broad recessed horizontal window stack
    # on its short return and a long opaque stone face. Repeating small window
    # bays across both faces erased the building's characteristic five stacks.
    a2,b2=tuple(aa[:2]),tuple(peak[:2])
    for k in range(levels-5):
     z0=base+k*(body_top-base)/levels;z1=base+(k+1)*(body_top-base)/levels
     facade(m,a2,b2,z0,z1,1,pale,pale,turquoise,frame,.90,.49);count+=1
     m.face([peak+Vector((0,0,z0)),bb+Vector((0,0,z0)),bb+Vector((0,0,z1)),peak+Vector((0,0,z1))],pale)
     band(m,[tuple(peak[:2]),tuple(bb[:2])],z0+.15,.016,.025,joint)
     for frac in [.33,.66]:
      a3=peak.lerp(bb,frac);m.rod(a3+nv*.018+Vector((0,0,z0)),a3+nv*.018+Vector((0,0,z1)),.013,joint,6)
   # Top five floors revert to the continuous glazed crown.
   topbase=base+(levels-5)*(body_top-base)/levels
   for k in range(5):facade(m,a,b,topbase+k*(body_top-topbase)/5,topbase+(k+1)*(body_top-topbase)/5,nb*2,frame,frame,turquoise,frame,.93,.88)
   count+=5*nb*2
  else:
   # Bow long glazing edges softly, avoiding rounded off map corners in plan.
   seg=max(1,round(le/2.0));count+=seg*levels
   for j in range(seg):
    f0=j/seg;f1=(j+1)/seg;aa=av+tt*le*f0+nv*(.70*math.sin(math.pi*f0) if le>10 else 0);bb=av+tt*le*f1+nv*(.70*math.sin(math.pi*f1) if le>10 else 0)
    for k in range(levels):
     z0=base+k*(body_top-base)/levels;z1=base+(k+1)*(body_top-base)/levels;a0=aa+Vector((0,0,z0));b0=bb+Vector((0,0,z0));a1=aa+Vector((0,0,z1));b1=bb+Vector((0,0,z1))
     m.face([a0,b0,b1,a1],turquoise[(j+k)%4]);m.rod(a0,b0,.04,frame,6);m.rod(a0,a1,.026,frame,6)
     # Narrow opaque mid-height service band, visible in both photos.
     if k==18:m.face([a0+nv*.035,b0+nv*.035,b0+nv*.035+Vector((0,0,.8)),a0+nv*.035+Vector((0,0,.8))],crown)
  # Open bronze crown rail and thin horizontal slats seen above the roofline.
  for j in range(nb+1):
   cp=av+tt*le*j/nb;m.rod(cp+Vector((0,0,body_top)),cp+Vector((0,0,H)),.10,crown,8)
  for z in [H-2,H-1.45,H-.90,H-.35,H]:m.rod(av+Vector((0,0,z)),bv+Vector((0,0,z)),.075,crown,8)
  perimeter.append((a,b));roles.append({'edgeIndex':edge,'appearance':'sandstone sawtooth rear' if is_stone else 'pale curved curtain glazing','basis':'photographed envelope family; exact compass matching inferred'})
 m.face([(*p,body_top) for p in poly],roof)
 label_edge=max(edges,key=lambda edge:math.dist(*edge));aa,bb=Vector((*label_edge[0],0)),Vector((*label_edge[1],0));tt=(bb-aa).normalized();nv=Vector((tt.y,-tt.x,0));physical_label(root,'HYATT',(aa+bb)/2-tt*6+nv*.20+Vector((0,0,129)),tt,nv,3.2,white)
 return root,m,dict(independentWindowPanels=count,observedDetails='Two licensed photographs: separate mapped tower, pale turquoise curtain wall, narrow mid-height dark band, five strong sandstone sawtooth returns with individual large horizontal window stacks and opaque stone flanks, upper glass crown, physical HYATT letters and open bronze rooftop slat frame. Elevated tower begins at the 13.6 m podium roof.',heightSource='133 m twin-tower published height; 32 mapped floors includes podium relationship; exact roof datum inferred',heightUncertaintyMetres=4,facadeRoles=roles,photoVerified=True,realPhotoAcceptance=False,confidence='Specific tower identity, facade families and crown modeled; exact corner radii and unseen elevations remain inferred')


def hyatt_podium(spec):
 root,m=new(spec);p=local(spec['ways'][0]);h=13.6;count=0
 pale=material('hyatt-podium-grey-stone',(.50,.52,.49),.79);frame=material('hyatt-podium-silver-frame',(.49,.53,.51),.36,.67);blue=[material('hyatt-podium-glass-'+str(i),c,.19,.4) for i,c in enumerate([(.17,.28,.29),(.20,.32,.33),(.24,.34,.34)])]
 for a,b in zip(p,p[1:]+p[:1]):
  le=math.dist(a,b)
  if le<.5:continue
  bays=max(1,round(le/2.8));count+=bays*3
  for k in range(3):facade(m,a,b,k*h/3,(k+1)*h/3,bays,pale,frame,blue,frame,.86,.78)
  for z in [0,h/3,2*h/3,h]:band(m,[a,b],z,.32,.12,pale)
 m.face([(*xy,h) for xy in p],roof)
 # Entrance photo shows the two towers linked by a steel-and-glass canopy.
 # Use their true mapped centers to establish the gap and canopy alignment.
 centers=[Vector((centre(way)[0]-spec['center'][0],-(centre(way)[1]-spec['center'][1]),0)) for way in [446937834,446937836]]
 tt=(centers[1]-centers[0]).normalized();nv=Vector((tt.y,-tt.x,0));mid=(centers[0]+centers[1])/2+nv*10.8;gap=max(10,(centers[1]-centers[0]).length-25);depth=13.;z=10.9
 for u in [-gap/2,gap/2]:
  for v in [-depth/2,depth/2]:
   cp=mid+tt*u+nv*v;m.rod(cp+Vector((0,0,.1)),cp+Vector((0,0,z)),.24,pale,16)
 for i in range(13):
  u=-gap/2+gap*i/12;m.rod(mid+tt*u-nv*depth/2+Vector((0,0,z)),mid+tt*u+nv*depth/2+Vector((0,0,z)),.13,frame,10)
 for j in range(6):
  v=-depth/2+depth*j/5;m.rod(mid-tt*gap/2+nv*v+Vector((0,0,z)),mid+tt*gap/2+nv*v+Vector((0,0,z)),.13,frame,10)
 for i in range(12):
  for j in range(5):
   u0=-gap/2+gap*i/12;u1=-gap/2+gap*(i+1)/12;v0=-depth/2+depth*j/5;v1=-depth/2+depth*(j+1)/5
   m.face([mid+tt*u+nv*v+Vector((0,0,z+.15)) for u,v in [(u0,v0),(u1,v0),(u1,v1),(u0,v1)]],blue[(i+j)%3])
 return root,m,dict(independentWindowPanels=count+60,observedDetails='James Yu 2007 exterior photograph: separate four-floor mapped podium, grey stone frames with broad glazing, large rectangular steel-and-glass canopy and massive paired supports between real tower positions.',heightSource='OSM four-floor podium 13.6 m retained',photoVerified=True,realPhotoAcceptance=False,confidence='Photo matched central entry/canopy; side street podium not fully exposed, roof and lateral bay rhythm remain inferred')


def validate_indices(document,binary):
 for mesh in document.get('meshes',[]):
  for primitive in mesh['primitives']:
   index=document['accessors'][primitive['indices']];view=document['bufferViews'][index['bufferView']]
   values=array.array({5121:'B',5123:'H',5125:'I'}[index['componentType']]);offset=view.get('byteOffset',0)+index.get('byteOffset',0)
   assert not view.get('byteStride'),'Interleaved indices are not expected in these static exports'
   values.frombytes(binary[offset:offset+index['count']*values.itemsize]);vertices=document['accessors'][primitive['attributes']['POSITION']]['count']
   assert len(values)==index['count'] and max(values)<vertices,(mesh['name'],max(values),vertices)


def verified_editable_save():
 # Preserve the intended Blender bytes on the local system volume before the
 # ExFAT copy. A readback hash of a direct corrupted export is not evidence.
 with tempfile.TemporaryDirectory(prefix='north-bund-blend-',dir='/tmp') as tmp:
  source=pathlib.Path(tmp)/'north-bund-detailed.blend';bpy.ops.wm.save_as_mainfile(filepath=str(source),compress=True)
  expected=hashlib.sha256(source.read_bytes()).hexdigest();pending=EDIT.with_suffix('.blend.writing')
  for attempt in range(3):
   with source.open('rb') as reader,pending.open('wb') as writer:
    for block in iter(lambda:reader.read(4*1024*1024),b''):writer.write(block)
    writer.flush();os.fsync(writer.fileno())
   if hashlib.sha256(pending.read_bytes()).hexdigest()==expected:
    pending.replace(EDIT)
    assert hashlib.sha256(EDIT.read_bytes()).hexdigest()==expected
    (ASSET/'editable-source-verification.json').write_text(json.dumps({'sha256':expected,'bytes':EDIT.stat().st_size,'method':'Local Blender source then 4 MiB block copy, fsync, independent SHA and atomic replace','file':str(EDIT.relative_to(ROOT))},indent=2)+'\n');return
  raise RuntimeError('Editable Blender source failed external-volume byte verification')


def save_one(spec,root,m,extra):
 m.flush();bpy.context.view_layer.update();bpy.ops.object.select_all(action='DESELECT');root.select_set(True)
 for child in root.children_recursive:child.select_set(True)
 bpy.context.view_layer.objects.active=root;path=OUT/(spec['id']+'.glb')
 with tempfile.TemporaryDirectory(prefix='north-bund-glb-',dir='/tmp') as tmp:
  staging=pathlib.Path(tmp)/(spec['id']+'.glb')
  bpy.ops.export_scene.gltf(filepath=str(staging),export_format='GLB',use_selection=True,export_apply=True,export_extras=True,export_draco_mesh_compression_enable=False)
  document,binary=read_glb(staging);validate_indices(document,binary);receipt=write_glb(path,document,binary)
  published,payload=read_glb(path);validate_indices(published,payload)
 meshes=[o for o in root.children_recursive if o.type=='MESH'];vs=[o.matrix_world@Vector(v) for o in meshes for v in o.bound_box];mins=[min(v[i] for v in vs) for i in range(3)];maxs=[max(v[i] for v in vs) for i in range(3)]
 record={**spec,**extra,'file':str(path.relative_to(ROOT/'public')),'y':0,'heading':0,'bytes':path.stat().st_size,'triangles':sum(len(p.vertices)-2 for o in meshes for p in o.data.polygons),'meshes':len(meshes),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'localBlenderBounds':{'min':mins,'max':maxs},'actualModelHeight':maxs[2]-mins[2],'photoReferenceFiles':[REFS[x]['file'] for x in spec['referenceIds'] if x in REFS],'unobservedSurfaces':'Hidden elevations, roof plant positions, exact mullion sections and unsurveyed secondary geometry inferred; dimensions follow OSM/photo proportions, not a survey.','quality':{'imageBillboards':False,'textureUpsampling':False,'decimation':False,'interiors':False,'compression':'none'}}
 record['publishVerification']={'method':'Local Blender export, validated indices, 4 MiB fsync copy and independent SHA atomic publication','expectedSha256':receipt['sha256'],'binaryAccessorRangesValid':True}
 assert record['sha256']==receipt['sha256']
 records.append(record);roots.append(root);print('NORTH_BUND_MODEL',spec['id'],record['bytes'],record['triangles'],flush=True)


if not ARGS.render_only:
 for spec in SPECS:
  if ARGS.ids and spec['id'] not in ARGS.ids:continue
  func={'magnolia':magnolia,'hotel':hotel,'podium':podium,'consulate':consulate,'yesong':yesong,'frontage':frontage,'sipg':sipg,'ocean':ocean,'jinshan':jinshan,'hailun':hailun,'jiantang':jiantang,'hyatt_tower':hyatt_tower,'hyatt_podium':hyatt_podium}[spec['builder']]
  root,m,extra=func(spec);save_one(spec,root,m,extra)
 verified_editable_save()
 reused=[]
 old=json.loads((ROOT/'public/streets/districts/bund/manifest.json').read_text())['models']
 for key in ['astor-front','shanghai-mansions']:
  r=next(x for x in old if x['id']==key);reused.append({'id':key,'name':r['name'],'sourceManifest':'streets/districts/bund/manifest.json','ways':r['ways'],'file':r['file'],'sha256':r['sha256'],'reason':'Existing source-aligned facade geometry verified against preserved exterior photos; no duplicate geometry export.','newModel':False,'referenceIds':r['referenceIds']})
 manifest={'version':1,'generator':'scripts/build_north_bund.py','createdAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'coordinateSystem':'Individual GLBs local; manifest center world X east, Z south; heading Three Y = Blender Z','models':records,'reuse':reused,'totals':{'newModels':len(records),'reuse':len(reused),'bytes':sum(x['bytes'] for x in records),'triangles':sum(x['triangles'] for x in records)},'sourceCatalog':'references/tourism/north-bund-photos.json'}
 (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
else:
 records=json.loads((OUT/'manifest.json').read_text())['models'];roots=[bpy.data.objects.get(x['id']) for x in records]

if ARGS.render or ARGS.render_only:
 # Round-trip the exported runtime GLBs; validation never relies on source meshes.
 for root in roots:
  for obj in list(root.children_recursive)+[root]:bpy.data.objects.remove(obj,do_unlink=True)
 roots=[];roundtrip=[]
 for record in records:
  path=ROOT/'public'/record['file'].lstrip('/');before=set(bpy.data.objects)
  assert hashlib.sha256(path.read_bytes()).hexdigest()==record['sha256'],('Runtime GLB bytes changed since expected manifest hash',record['id'])
  document,binary=read_glb(path);validate_indices(document,binary)
  bpy.ops.import_scene.gltf(filepath=str(path));imported=[o for o in bpy.data.objects if o not in before]
  top=[o for o in imported if o.parent not in imported];root=bpy.data.objects.new('review-runtime-'+record['id'],None);bpy.context.collection.objects.link(root)
  for child in top:child.parent=root
  bpy.context.view_layer.update();vs=[o.matrix_world@Vector(v) for o in imported if o.type=='MESH' for v in o.bound_box]
  bounds={'min':[min(v[i] for v in vs) for i in range(3)],'max':[max(v[i] for v in vs) for i in range(3)]}
  err=max(abs(bounds[k][i]-record['localBlenderBounds'][k][i]) for k in ['min','max'] for i in range(3));assert err<.02,(record['id'],err)
  roots.append(root);roundtrip.append({'id':record['id'],'file':record['file'],'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'boundsMaxDeviationMetres':err,'importedMeshes':sum(o.type=='MESH' for o in imported),'runtimeGlbImported':True})
 # Validate source-backed reuse by rendering the exact unchanged GLBs too.
 reuse_manifest=json.loads((ROOT/'public/streets/districts/bund/manifest.json').read_text())['models']
 for key in ['astor-front','shanghai-mansions']:
  prior=next(x for x in reuse_manifest if x['id']==key);before=set(bpy.data.objects)
  bpy.ops.import_scene.gltf(filepath=str(ROOT/'public'/prior['file'].lstrip('/')))
  imported=[o for o in bpy.data.objects if o not in before];top=[o for o in imported if o.parent not in imported]
  reuse_root=bpy.data.objects.new('review-reuse-'+key,None);bpy.context.collection.objects.link(reuse_root)
  for child in top:child.parent=reuse_root
  bpy.context.view_layer.update();vs=[o.matrix_world@Vector(v) for o in imported if o.type=='MESH' for v in o.bound_box]
  bounds={'min':[min(v[i] for v in vs) for i in range(3)],'max':[max(v[i] for v in vs) for i in range(3)]}
  records.append({'id':key,'localBlenderBounds':bounds});roots.append(reuse_root)
 scene=bpy.context.scene;scene.render.engine='CYCLES' if ARGS.cycles_review else 'BLENDER_EEVEE'
 scene.eevee.taa_render_samples=8
 # Installed Blender 5.2 uses BLENDER_EEVEE. Final PBR ray tracing remains
 # available through --cycles-review without changing geometry or textures.
 scene.cycles.device='CPU';scene.cycles.samples=8;scene.cycles.use_denoising=True;scene.render.resolution_x=1100;scene.render.resolution_y=900;scene.render.resolution_percentage=100
 scene.world.color=(.30,.30,.30);scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.65,.73,.80,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.65
 scene.view_settings.view_transform='AgX'
 light=bpy.data.lights.new('north-bund-review-sun','SUN');light.energy=2.1;light.angle=.18;o=bpy.data.objects.new(light.name,light);bpy.context.collection.objects.link(o);o.rotation_euler=(.48,-.42,-.50)
 camera_data=bpy.data.cameras.new('north-bund-review-camera');camera=bpy.data.objects.new(camera_data.name,camera_data);bpy.context.collection.objects.link(camera);scene.camera=camera;camera_data.type='PERSP';camera_data.lens=48
 rendered_images=[];pbr_rendered=[]
 for record,root in zip(records,roots):
  review_ids=ARGS.review_ids or ARGS.ids
  if review_ids and record['id'] not in review_ids:continue
  for other in roots:
   for o in [other]+list(other.children_recursive):o.hide_render=other!=root
  bounds=record['localBlenderBounds'];mi,ma=bounds['min'],bounds['max'];w=max(ma[0]-mi[0],ma[1]-mi[1]);h=ma[2];target=Vector(((mi[0]+ma[0])/2,(mi[1]+ma[1])/2,h*.48));distance=max(w*1.70,h*2.15)
  directions=[('front',Vector((.22,-1,.17))),('side',Vector((1,.25,.21)))]
  if record['id'].startswith('hyatt-'):directions.append(('rear',Vector((-1 if record['id']=='hyatt-west-tower' else 1,0,.12))))
  if record['id']=='yesong-shipyard':directions=[('front',Vector((-1,.18,.16))),('side',Vector((.22,1,.18)))]
  for view,direction in directions:
   camera.location=target+direction.normalized()*distance;camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera_data.lens=48
   path=ASSET/'review'/f"{record['id']}-{view}.png";path.parent.mkdir(parents=True,exist_ok=True);scene.render.filepath=str(path);bpy.ops.render.render(write_still=True);print('NORTH_BUND_RENDER',path,flush=True)
   rendered_images.append({'id':record['id'],'view':view,'file':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
   if not ARGS.cycles_review and (record['id'],view) in [('north-bund-frontage-292818817','side'),('hyatt-east-tower','front'),('yesong-shipyard','front')]:
    scene.render.engine='CYCLES';scene.cycles.samples=16
    pbr_path=ASSET/'review-pbr'/f"{record['id']}-{view}.png";pbr_path.parent.mkdir(parents=True,exist_ok=True);scene.render.filepath=str(pbr_path);bpy.ops.render.render(write_still=True);print('NORTH_BUND_PBR_RENDER',pbr_path,flush=True)
    pbr_rendered.append({'id':record['id'],'view':view,'file':str(pbr_path.relative_to(ROOT)),'sha256':hashlib.sha256(pbr_path.read_bytes()).hexdigest()})
    scene.render.engine='BLENDER_EEVEE'
 (ASSET/'review/runtime-glb-roundtrip.json').write_text(json.dumps({'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'models':roundtrip,'renderEngine':'Cycles CPU 8 samples' if ARGS.cycles_review else 'EEVEE Blender 5.2','renderedImages':rendered_images,'additionalPbrViews':pbr_rendered,'views':['front','side'],'reusedGlbsAlsoImported':['astor-front','shanghai-mansions']},ensure_ascii=False,indent=2)+'\n')
 print('NORTH_BUND_REVIEW_COMPLETE',flush=True)
