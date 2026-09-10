"""Reference-driven 2026 Leapmotor A10 exterior reconstruction and review.

Run: scripts/blender-local.sh -b --threads 2 --python scripts/build_suv_exteriors.py -- leap-a10
The body is built as independent shaped exterior surfaces. Source photos stay in
assets/vehicles/suv-exteriors; there is no cabin geometry or substitute B10 body.
"""
import bpy, math, json, pathlib, sys, hashlib, struct
from mathutils import Vector, Matrix
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from suv_exterior_helpers import *
CAR=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'leap-a10'
ASSET=ROOT/'assets/vehicles/suv-exteriors'/CAR
OUT=ROOT/'public/vehicles/rigged';ASSET.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
REV=sys.argv[sys.argv.index('--revision')+1] if '--revision' in sys.argv else 'v1'
REVIEW=ASSET/REV;REVIEW.mkdir(exist_ok=True)
YUAN_META={}

def build_yuan():
    """Retain licensed Atto 2 exterior geometry and isolate its original wheels."""
    import bmesh
    from mathutils.bvhtree import BVHTree
    from rig_vehicle_wheels import rig_wheels
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    source=ASSET/'source/original/nested/Final_Model_Atto2.fbx'
    bpy.ops.import_scene.fbx(filepath=str(source),use_image_search=True,use_custom_normals=True)
    objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
    source_count=triangles(objects)
    for o in objects:
        transform=Matrix.Rotation(math.pi,4,'Z')@o.matrix_world.copy();o.data=o.data.copy();o.data.transform(transform);o.parent=None;o.matrix_world=Matrix.Identity(4);o.data.update()
    for o in list(bpy.context.scene.objects):
        if o not in objects:bpy.data.objects.remove(o,do_unlink=True)
    pts=[v.co for o in objects for v in o.data.vertices];lo=Vector(tuple(min(p[i] for p in pts) for i in range(3)));hi=Vector(tuple(max(p[i] for p in pts) for i in range(3)))
    scale=4.31/(hi.y-lo.y);center=Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z))
    for o in objects:
        for v in o.data.vertices:v.co=(v.co-center)*scale
        o.data.update()
    # All downloaded textures are retained at original resolution; only paths are repaired.
    texture_root=ASSET/'source/original/nested';tex={p.name.lower():p for p in texture_root.glob('*.png')}
    for im in bpy.data.images:
        base=pathlib.PureWindowsPath(im.filepath).name.lower()
        if base in tex:im.filepath=str(tex[base]);im.reload()
    inspection=[]
    for o in objects:
        ps=[v.co for v in o.data.vertices]
        inspection.append({'name':o.name,'triangles':triangles([o]),'materials':[m.name for m in o.data.materials],'bbox':[[min(v[i] for v in ps),max(v[i] for v in ps)] for i in range(3)]})
    (ASSET/'source/import-inspection.json').write_text(json.dumps(inspection,indent=2)+'\n')
    print('YUAN_SOURCE_INSPECTION',json.dumps(inspection),flush=True)
    removed=[]
    for o in list(objects):
        if any(k in o.name.lower() for k in ['mk_buttons','mk_carpet','mk_ceiling','mk_leather','mk_plastic_beige','mk_microphone','mk_emissive_blue','18070ecf']):
            removed.append({'name':o.name,'triangles':triangles([o])});objects.remove(o);bpy.data.objects.remove(o,do_unlink=True)
    paint=mat('Atto2_Breeze_Green_Paint',(.48,.58,.33),.38,.27,.65)
    pillar=mat('Atto2_Gloss_Black_Window_Pillars',(.007,.011,.014),.05,.25,.35)
    window=mat('Atto2_Opaque_Cabin_Glazing',(.008,.015,.021),.08,.20,.35)
    clear=mat('Atto2_Lamp_Clear_Covers',(.91,.95,.98),.0,.07,.25)
    p=clear.node_tree.nodes.get('Principled BSDF');p.inputs['Transmission Weight'].default_value=.94;p.inputs['IOR'].default_value=1.45
    for o in objects:
        if 'mk_Body' in o.name:
            o.data.materials.clear();o.data.materials.append(paint);o.data.materials.append(pillar)
            # The downloaded single-paint Body mesh includes the physical window
            # pillars. Their photographed black finish must be restored by face.
            for f in o.data.polygons:
                c=f.center
                if abs(c.x)>.62 and 1.123<c.z<1.58 and -1.47<c.y<1.22-1.65*(c.z-1.1):f.material_index=1
        elif o.name.endswith('mk_Glass'):
            o.data.materials.clear();o.data.materials.append(window);o.data.materials.append(clear)
            for f in o.data.polygons:
                c=f.center;f.material_index=0 if (-1.93<c.y<1.14 and c.z>.91) or abs(c.x)>.97 else 1
        if 'colorAtlas' in o.name:
            # Ray inspection of the exported GLB found the visible A-pillar
            # overlay in colorAtlas_3, above the correctly coloured Body mesh.
            # Restore the photographed finish on the actual outer trim faces.
            black_index=len(o.data.materials);o.data.materials.append(pillar)
            cap_index=len(o.data.materials);o.data.materials.append(paint)
            for f in o.data.polygons:
                c=f.center
                if .60<abs(c.x)<.92 and 1.123<c.z<1.58 and -1.47<c.y<1.22-1.65*(c.z-1.1):f.material_index=black_index
                if abs(c.x)>.92 and .2<c.y<.75 and 1.03<c.z<1.28 and f.normal.z>.18:f.material_index=cap_index
        for m in o.data.materials:
            if not m or not m.use_nodes:continue
            p=m.node_tree.nodes.get('Principled BSDF')
            if not p:continue
            if m not in [paint,pillar,window,clear]:
                p.inputs['Specular Tint'].default_value=(1,1,1,1)
                p.inputs['Specular IOR Level'].default_value=.24 if 'Tire' in m.name else .45
                p.inputs['Roughness'].default_value=.78 if 'Tire' in m.name else .34
                p.inputs['Metallic'].default_value=.03 if 'Tire' in m.name else .16
                if 'Glass_red' in m.name:
                    p.inputs['Base Color'].default_value=(.32,.006,.014,1);p.inputs['Transmission Weight'].default_value=.35;p.inputs['Roughness'].default_value=.16
                if 'Emissive' in m.name:
                    if p.inputs['Base Color'].is_linked:m.node_tree.links.new(p.inputs['Base Color'].links[0].from_socket,p.inputs['Emission Color'])
                    p.inputs['Emission Strength'].default_value=1.3
    # Conservative exterior visibility removal. Complete wheels remain protected,
    # including their inward faces exposed by steering and rolling.
    vv=[];ff=[]
    for o in objects:
        off=len(vv);vv.extend(v.co.copy() for v in o.data.vertices);ff.extend(tuple(off+i for i in f.vertices) for f in o.data.polygons)
    bvh=BVHTree.FromPolygons(vv,ff);directions=[Vector(x).normalized() for x in [(1,0,.4),(-1,0,.4),(0,1,.4),(0,-1,.4),(0,0,1),(0,0,-1)]]
    hidden=0
    for o in list(objects):
        if any(k in o.name for k in ['mk_Body','mk_Tires','mk_Glass','mk_Emissive','mk_Exterior_meshes']):continue
        keep=set()
        for f in o.data.polygons:
            c=f.center
            if abs(c.x)>.55 and 1.0<abs(c.y)<1.77 and c.z<.76:keep.add(f.index);continue
            # Visibility through transparent lamp covers is not represented by
            # an opaque BVH ray cast. Protect the complete optical assemblies.
            if (c.y>1.78 and .81<c.z<1.18 and abs(c.x)>.28) or (c.y<-1.78 and .85<c.z<1.27):keep.add(f.index);continue
            for d in [f.normal,-f.normal,*directions]:
                if bvh.ray_cast(c+d*.0003,d,10)[0] is None:keep.add(f.index);break
        bm=bmesh.new();bm.from_mesh(o.data);bm.faces.ensure_lookup_table();drop=[f for f in bm.faces if f.index not in keep];hidden+=sum(len(f.verts)-2 for f in drop);bmesh.ops.delete(bm,geom=drop,context='FACES');bm.to_mesh(o.data);bm.free()
        if not o.data.polygons:objects.remove(o);bpy.data.objects.remove(o,do_unlink=True)
    before=triangles(objects);rigged,rig=rig_wheels(objects);assert triangles(rigged)==before
    YUAN_META.update({'sourceTriangles':source_count,'sourceFile':str(source.relative_to(ROOT)),'removedInteriorMeshes':removed,'removedInteriorTriangles':sum(r['triangles'] for r in removed),'removedHiddenTriangles':hidden,'rigFacesBefore':before,'rigFacesAfter':before,'sourceLabeledYear':2024,'sourceModelTitle':'2024 BYD Atto 2','sourceYear':2025,'displayModel':'2025 ATTO 2 海外版同型外观 · 绿色','assetType':'licensed-exterior','author':'Ddiaz Design','license':'CC-BY-NC-SA-4.0','licenseUrl':'https://creativecommons.org/licenses/by-nc-sa/4.0/','source':'https://sketchfab.com/3d-models/2024-byd-atto-2-2e04b67017ed49e982a1f0737eb7f0ae','yearEvidence':'https://media.byd.com/byd-introduces-atto-2-compact-suv-in-europe/?lang=eng','dimensionsM':[4.31,1.83,1.675],'wheelbaseM':2.62,'features':['Licensed sculpted source body, lamp assemblies, 17 inch wheels and trim preserved','Opaque reflective cabin glazing; named cabin upholstery and controls removed','Original mesh topology/UV and original texture resolution preserved','Independent original tire/rim assemblies, four steering and rolling pivots'],'remainingDifferences':['Overseas ATTO 2 BYD badges and trim; same generation body as Yuan UP','Source titled 2024; displayed as 2025 overseas ATTO 2 because official Europe launch was February 2025','Mirror width excluded from nominal body width; existing source proportions retained'],'referencePolicy':'CC BY-NC-SA 4.0 applies to this adapted mesh; original archive, source FBX and textures are retained. BYD reference photographs are excluded from runtime.','sourcePhotos':'assets/vehicles/suv-exteriors/yuan-up/references'})
    return rig

def build_a10():
    from a10_surface_helpers import parametric_patch
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    paint=mat('A10_Metallic_Forest_Green',(.022,.091,.032),.48,.235,.75)
    black=mat('A10_Black_Gloss',(.008,.011,.015),.08,.25,.45)
    glass=mat('A10_Reflective_Glazing',(.008,.015,.022),.03,.15,.7)
    rubber=mat('A10_Tire_Rubber',(.016,.018,.020),.02,.72)
    cladding=mat('A10_Arch_Cladding',(.027,.030,.033),.05,.5)
    gap=mat('A10_Panel_Gaps',(.004,.005,.007),0,.66)
    chrome=mat('A10_Diamond_Cut_Aluminium',(.66,.7,.73),.86,.2)
    graphite=mat('A10_Rim_Graphite',(.045,.052,.06),.72,.26)
    brake=mat('A10_Brake_Steel',(.19,.20,.21),.8,.4)
    white=mat('A10_LED_White',(.82,.91,1),.1,.2,0,2.4)
    red=mat('A10_LED_Red',(.47,.003,.009),.15,.24,0,2)
    smoked=mat('A10_Lamp_Smoked',(.009,.013,.016),.45,.15,.9)
    cyan=mat('A10_Indicator_Cyan',(.01,.54,.65),.12,.25,0,1.7)
    W=.905;R=.3361;CY=[-1.3425,1.2625];TRACK=.7625

    FRONT=1.74;REAR=-1.83
    def top(y):
        if y>=.97:
            v=1-max(0,(FRONT-y)/(FRONT-.97))**(1/1.6)
            return (1-v)**3*1.17+3*(1-v)**2*v*1.178+3*(1-v)*v*v*1.164+v**3*1.10
        return interp([(REAR,1.145),(-1.5,1.16),(-.5,1.159),(.35,1.163),(.97,1.17)],y)
    def sx(y,z):
        base=interp([(REAR,.872),(-1.65,.883),(-1.34,.895),(-.7,.865),(.15,.859),(.75,.882),(1.26,.897),(1.64,.887),(FRONT,.885)],y)
        waist=-.039*math.exp(-((z-.59)/.19)**2)*math.exp(-(y/.99)**6)
        shoulder=.017*math.exp(-((z-1.02)/.115)**2)
        lower=-.044*math.exp(-((z-.245)/.10)**2)
        roundtop=-.018*max(0,(z-(top(y)-.08))/.08)**2
        return base+waist+shoulder+lower+roundtop
    def bottom(y,r=.396):
        z=.265
        for yc in CY:
            if abs(y-yc)<r:z=max(z,R+math.sqrt(max(0,r*r-(y-yc)**2)))
        return z
    def sidept(s,y,z,off=0):return(s*(sx(y,z)+off),y,z)
    for s in [-1,1]:
        # Longitudinally sampled double-curvature side skin has actual wheel openings.
        ys=sorted(set([REAR+i*(FRONT-REAR)/220 for i in range(221)]+[yc+.396*math.cos(math.pi*i/96) for yc in CY for i in range(97)]))
        verts=[];faces=[];nz=22
        for y in ys:
            lo=bottom(y);hi=top(y)
            for k in range(nz+1):
                z=lo+(hi-lo)*k/nz;verts.append(sidept(s,y,z))
        for i in range(len(ys)-1):
            for j in range(nz):a=i*(nz+1)+j;f=(a,a+nz+1,a+nz+2,a+1);faces.append(f if s>0 else f[::-1])
        mesh('A10_Continuous_Side_Pressed_Steel_'+str(s),verts,faces,paint)
        for yc in CY:
            # Moulded, variable-width arch lip and dark wheel well; no filled arch discs.
            def arch(u,v):
                q=math.radians(-9)+u*math.radians(198);rr=.375+.070*v
                y=yc+rr*math.cos(q);z=R+rr*math.sin(q)
                x=sx(y,z)+.012+.012*math.sin(v*math.pi)
                return(s*x,y,z)
            surface('A10_Arch_Moulding',arch,104,5,cladding,s<0)
            surface('A10_Inner_Wheelhouse',lambda u,v:(s*(.70+.18*v),yc+.378*math.cos(-.16+u*3.46),R+.378*math.sin(-.16+u*3.46)),96,3,gap,s>0)
        # Sculpted rocker moulding follows the door scallop.
        surface('A10_Rocker',lambda u,v:sidept(s,-.91+1.75*u,.245+.105*v+.021*math.sin(u*math.pi),.007),90,6,cladding,s<0)
        curve('A10_Sill_Polished_Edge',[sidept(s,y,.352+.012*math.sin((y+.9)/1.75*math.pi),.012) for y in [-.91,-.7,-.2,.3,.7,.84]],.0038,chrome)
        # Door boundaries, including the curved rear wheel cut-out.
        front=[(.91,1.153),(.978,1.07),(.974,.89),(.843,.66),(.786,.42),(.755,.352),(.55,.325),(-.29,.322),(-.345,.43),(-.345,1.11)]
        back=[(-.353,1.111),(-.363,.78),(-.358,.40),(-.46,.337),(-.87,.34),(-.966,.47),(-1.009,.644),(-1.151,.81),(-1.23,.957),(-1.242,1.14)]
        for label,outline in [('Front',front),('Rear',back)]:
            yz=spline([(y,z,0) for y,z in outline],12,True)
            tube('A10_'+label+'_Door_Seam',[sidept(s,p.x,p.y,.003) for p in yz],.0023,gap,True)
        for y,z in [(-.20,1.008),(-1.11,1.039)]:
            outline=[sidept(s,yy,zz,.006) for yy,zz in rounded_outline(y,z,.184,.059,.021,5)]
            patch('A10_Handle_Recess',outline,gap,.002,(s,0,0),3,2)
            outline=[sidept(s,yy,zz,.013) for yy,zz in rounded_outline(y,z+.007,.171,.041,.016,5)]
            patch('A10_Semi_Flush_Handle',outline,paint,.006,(s,0,0),4,2)
        if s==-1:
            q=[sidept(s,y,z,.003) for y,z in rounded_outline(1.075,1.02,.204,.178,.037,8)]
            curve('A10_Charging_Flap',q,.0023,gap,True,1)
        # Small side badge behind the front wheel.
        p=[sidept(s,y,z,.009) for y,z in [(.983,.877),(.867,.887),(.846,.861),(.903,.846)]]
        patch('A10_Fender_Identity_Badge',p,chrome,.002,(s,0,0),3)

    def nose_depth(z):return .395-.050*math.exp(-((z-1.13)/.102)**2)-.041*math.exp(-((z-.235)/.115)**2)
    def fy(x,z):return FRONT+nose_depth(z)*math.sqrt(max(0,1-(abs(x)/sx(FRONT,z))**4.1))
    def ry(x,z):return REAR-(.305-.040*math.exp(-((z-.25)/.13)**2)-.019*math.exp(-((z-1.15)/.1)**2))*math.sqrt(max(0,1-(abs(x)/sx(REAR,z))**4.2))
    # Front and rear fascias are rounded in both axes, independently shaped.
    def nose(u,v):
        t=2*u-1;k=math.copysign(math.sin(abs(t)*math.pi/2)**(2/4.1),t)
        z=.265+(.780+.055*k*k)*v;x=k*sx(FRONT,z);return(x,fy(x,z),z)
    surface('A10_Rounded_Front_Fascia',nose,100,42,paint,True)
    def rear_fascia(u,v):
        t=2*u-1;k=math.copysign(math.sin(abs(t)*math.pi/2)**(2/4.2),t)
        z=.265+.88*v;x=k*sx(REAR,z);return(x,ry(x,z),z)
    surface('A10_Rounded_Rear_Quarter_Fascia',rear_fascia,100,38,paint)
    def hood(u,v):
        k=-1+2*u;tip=1.045+.055*k*k
        end=FRONT+nose_depth(tip)*math.sqrt(max(0,1-abs(k)**4.1))
        # A half-ellipse curls the hood's last 90 mm into the nose instead of
        # meeting a vertical fascia as a flat sheet with a knife edge.
        t=1-(1-v)**1.6;y=.97+(end-.97)*t
        z=(1-v)**3*1.17+3*(1-v)**2*v*1.178+3*(1-v)*v*v*1.164+v**3*tip
        z+=.024*(1-k*k)*math.sin(math.pi*v)
        x=k*sx(min(y,FRONT),z)
        return(x,y,z)
    surface('A10_Clamshell_Hood',hood,76,74,paint)
    curve('A10_Hood_Leading_Gap',[hood(u/100,1) for u in range(101)],.0025,gap)
    for s in [-1,1]:
        pts=[hood(.035 if s<0 else .965,t) for t in [0,.15,.3,.5,.7,.9,1]]
        curve('A10_Hood_Pressed_Crease',pts,.0014,paint)
    # Front lower intake with vertical vanes and two formed horizontal lips.
    front=lambda x,z,d=.007:(x,fy(x,z)+d,z)
    rear=lambda x,z,d=.009:(x,ry(x,z)-d,z)
    inlet=[(-.63,.293),(-.577,.419),(-.49,.468),(.49,.468),(.577,.419),(.63,.293)]
    patch('A10_Lower_Intake_Recess',[front(x,z) for x,z in inlet],gap,-.009,(0,1,0),7)
    for x in [-.57+i*.0285 for i in range(41)]:
        h=.105*(1-(abs(x)/.65)**4)
        curve('A10_Intake_Vane',[front(x,.313,.012),front(x-.014,.313+h,.012)],.0033,cladding,steps=2)
    for z,w in [(.312,.609),(.362,.583)]:curve('A10_Intake_Horizontal_Lip',[front(x,z,.020) for x in [-w,-w*.6,0,w*.6,w]],.010,cladding)
    curve('A10_Front_Lower_Splitter',[front(x,.263,.004) for x in [-.856,-.70,-.4,0,.4,.7,.856]],.021,cladding)
    for s in [-1,1]:
        q=[(s*x,z) for x,z in [(.553,.768),(.718,.778),(.777,.723),(.774,.543),(.724,.508),(.581,.530),(.526,.597)]]
        curve('A10_Front_Cheek_Sculpted_Seam',[front(x,z,.006) for x,z in q],.0032,gap,True)
        curve('A10_Cheek_Stamped_Horizontal',[front(s*x,z,.009) for x,z in [(.541,.679),(.602,.681),(.699,.681)]],.005,paint)
    plate=roundbox('A10_Front_Plate',(0,2.15,.592),(.365,.020,.116),black,.007)
    text_obj('A10_Front_Plate_Text','A10',(0,2.162,.593),.072,white)
    text_obj('A10_Intake_Embossed_Mark','L E A P M O T O R',(0,2.138,.481),.0135,cladding)
    # Short smiling headlamps, internal projector and separate upper DRL blades.
    for s in [-1,1]:
        outline=[(s*x,z) for x,z in [(.344,1.049),(.4,1.070),(.717,1.083),(.817,1.061),(.801,1.025),(.711,1.011),(.661,.976),(.410,.977),(.361,1.005)]]
        curve('A10_Headlamp_Seal',[front(x,z,.018) for x,z in outline],.004,gap,True)
        patch('A10_Headlamp_Smoked_Housing',[front(x,z,.019) for x,z in outline],smoked,.003,(0,1,0),7)
        for seg in [[(.378,1.042),(.435,1.045),(.46,1.037)],[ (.687,1.053),(.755,1.055),(.783,1.045)]]:
            curve('A10_Headlamp_Upper_DRL',[front(s*x,z,.027) for x,z in seg],.0055,white,steps=8)
        curve('A10_Headlamp_Lower_Smile',[front(s*x,z,.027) for x,z in [(.422,.990),(.475,.987),(.617,.990)]],.0043,white)
        center=Vector(front(s*.576,1.028,.031))
        p=[center+Vector((.020*math.cos(i*2*math.pi/32),0,.022*math.sin(i*2*math.pi/32))) for i in range(32)]
        patch('A10_Projector_Optic',p,chrome,.002,(0,1,0),4,1)
        for j in range(4):curve('A10_Lamp_Reflector_Ribs',[front(s*x,.998+j*.008,.022) for x in [.375,.399,.427]],.0015,graphite,steps=3)
    # Stylised Leapmotor emblem traced as two open angular loops.
    for d in [-.018,.018]:
        p=[(d-.013,1.048),(d-.009,1.071),(d+.014,1.092),(d+.012,1.065),(d-.013,1.048)]
        curve('A10_Nose_Brand_Emblem',[front(x,z,.010) for x,z in p],.0022,chrome,steps=2)

    # One shared cabin parameterization closes all glass/roof/A/D-pillar edges.
    # Thin opaque exterior glazing hides the unmodelled cabin.
    def cx(y,z):
        t=max(0,min(1,(z-1.135)/.47))
        return .878-.157*t+.025*math.sin(math.pi*t)+.010*math.exp(-((y+.4)/1.4)**2)
    def cp(s,y,z,off=0):return(s*(cx(y,z)+off),y,z)
    def roof_edge(t):
        return(.317-1.957*t,interp([(0,1.600),(.13,1.620),(.5,1.615),(.75,1.595),(1,1.540)],t))
    def cabin(s,u,v,off=0):
        yt,zt=roof_edge(u);yb=1.005-2.918*u;zb=1.153+.007*u
        y=yb*(1-v)+yt*v+.075*math.sin(math.pi*v)*(1-u)**4
        z=zb*(1-v)+zt*v+.012*math.sin(math.pi*v)*(1-u)**4
        return cp(s,y,z,off)
    def wind(u,v):
        k=2*u-1;edge=cabin(1,0,v)
        return(k*edge[0],edge[1]+.045*(1-k*k)*(1-.4*v),edge[2]+.024*(1-k*k)*v)
    def backwind(u,v):
        k=2*u-1;edge=cabin(1,1,v)
        return(k*edge[0],edge[1]-.087*(1-k*k)*(1-.55*v),edge[2]+.024*(1-k*k)*v)
    def roof(u,v):
        k=2*u-1;y,z=roof_edge(v)
        return(k*cx(y,z),y+(.027*(1-v)**8-.03915*v**8)*(1-k*k),z+.024*(1-k*k))
    surface('A10_Crowned_Panoramic_Roof',roof,80,96,black,True)
    surface('A10_Bowed_Windscreen',wind,80,64,glass,True)
    surface('A10_Rear_Windscreen',backwind,80,56,glass)
    # Roof border rolls from the side into the roof, rather than rising as a pipe.
    for s in [-1,1]:
        surface('A10_Cabin_Side_Black_Surround',lambda u,v:cabin(s,u,v),112,40,black,s>0)
        def roof_border(u,v):
            a=Vector(cabin(s,u,.951,.003));b=Vector(roof(.043 if s<0 else .957,u));c=Vector(cabin(s,u,1,.010))
            return a*(1-v)**2+c*(2*v*(1-v))+b*v*v
        surface('A10_Rolled_Cantrail',roof_border,112,12,paint,s>0)
        def pillar_border(u,v):
            a=Vector(cabin(s,.019,u,.005));b=Vector(wind(.024 if s<0 else .976,u));c=Vector(cabin(s,0,u,.010))
            return a*(1-v)**2+c*(2*v*(1-v))+b*v*v
        surface('A10_A_Pillar_Stamped_Sheet',pillar_border,80,12,paint,s>0)
        windows=[
            ('Front',[(.897,1.176),(.811,1.303),(.49,1.539),(.305,1.574),(.115,1.591),(-.292,1.584),(-.323,1.177)]),
            ('Rear',[(-.374,1.178),(-.344,1.585),(-.840,1.578),(-1.125,1.557),(-1.205,1.527),(-1.274,1.179)]),
            ('Quarter',[(-1.330,1.181),(-1.274,1.522),(-1.385,1.516),(-1.571,1.408),(-1.710,1.195)])]
        for label,outline in windows:
            parametric_patch('A10_'+label+'_Side_Glass',outline,lambda y,z:cp(s,y,z,.0035),glass,36)
            edge=rounded_polygon([(y,z,0) for y,z in outline],.13,8)
            tube('A10_'+label+'_Window_Rubber',[cp(s,p.x,p.y,.0055) for p in edge],.0023,gap,True)
        curve('A10_Beltline_Window_Trim',[cabin(s,u,0,.004) for u in [i/40 for i in range(41)]],.004,black,steps=1)
        for v,u in [(.52,.943),(.68,.939)]:
            parametric_patch('A10_D_Pillar_Twin_Bar',[(u-.062,v-.024),(u+.050,v-.024),(u+.05,v+.024),(u-.062,v+.024)],lambda a,b:cabin(s,a,b,.010),cladding,8)
        curve('A10_Mirror_Upright',[cp(s,.762,1.162),(s*.919,.781,1.164),(s*.978,.754,1.238)],.024,black)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=40,ring_count=20,location=(s*.997,.751,1.286));o=bpy.context.object;o.name='A10_Aerodynamic_Mirror_Shell';o.scale=(.140,.104,.062);o.data.materials.append(black)
        for f in o.data.polygons:f.use_smooth=True
        pts=[(s*(.997+.125*math.cos(a)),.683,1.287+.045*math.sin(a)) for a in [i*2*math.pi/48 for i in range(48)]]
        patch('A10_Mirror_Reflective_Insert',pts,chrome,.003,(0,-1,0),4,1)
        curve('A10_Mirror_Turn_Signal',[(s*.911,.832,1.277),(s*1.00,.851,1.277),(s*1.09,.802,1.276)],.0035,white)
    curve('A10_Windscreen_Lower_Seal',[wind(i/80,0) for i in range(81)],.005,gap)
    surface('A10_Sculpted_Cowl',lambda u,v:Vector(hood(u,0))*(1-v)+Vector(wind(u,0))*v,80,8,black,True)
    for x in [-.31,.32]:
        q=[Vector(wind((xx/.88+1)/2,.02))+Vector((0,.002,.003)) for xx in [x-.25,x,x+.26]]
        curve('A10_Front_Wiper',q,.0048,black)
    surface('A10_Rear_Glass_Lower_Shoulder',lambda u,v:Vector((x:=-.86+1.72*u,ry(x,1.14),1.14))*(1-v)+Vector(backwind(u,0))*v,80,10,paint)
    for i in range(9):
        v=.1+i*.072;curve('A10_Rear_Defroster',[backwind(u/40,v) for u in range(4,37)],.0006,graphite,steps=1,sides=4)
    def spoiler(u,v):
        k=2*u-1;start=Vector(roof(u,.90));end=Vector((k*.79,-1.845+.095*k*k,1.559+.02*(1-k*k)))
        p=start*(1-v)+end*v;p.z+=.008*math.sin(math.pi*v);return p
    surface('A10_Roof_Spoiler',spoiler,80,16,paint,True)
    curve('A10_High_Mount_Brake_Light',[(-.21,-1.850,1.543),(0,-1.859,1.542),(.21,-1.850,1.543)],.008,red)
    roundbox('A10_Lidar_Roof_Module',(0,.285,1.650),(.215,.159,.054),black,.023)
    # Tailgate sculpture and face-specific smiling rear lamp modules.
    curve('A10_Tailgate_Opening',[rear(x,z,.004) for x,z in [(-.711,1.153),(-.695,.96),(-.687,.734),(-.622,.657),(0,.649),(.622,.657),(.687,.734),(.695,.96),(.711,1.153)]],.0032,gap)
    for s in [-1,1]:
        lens=[rear(s*x,z,.017) for x,z in rounded_outline(.723,1.005,.241,.250,.048,7)]
        patch('A10_Smile_Taillamp_Housing',lens,smoked,.009,(0,-1,0),8,2)
        curve('A10_Taillamp_Rubber_Seal',lens,.0047,gap,True,1)
        for x in [.668,.773]:
            q=[(x-.036,1.050),(x-.031,1.068),(x-.014,1.074),(x+.018,1.073),(x+.033,1.057),(x+.035,1.049)]
            curve('A10_Taillamp_Smiling_Eye',[rear(s*xx,z,.033) for xx,z in q],.009,red,steps=7)
        q=[rear(s*x,z,.034) for x,z in rounded_outline(.72,.97,.169,.061,.019,6)]
        curve('A10_Taillamp_Smiling_Mouth',q,.009,red,True,1)
        curve('A10_Taillamp_Clear_Separator',[rear(s*x,1.024,.032) for x in [.633,.72,.813]],.0045,chrome)
        for j in range(3):curve('A10_Taillamp_Lower_Prism',[rear(s*x,.916+j*.006,.026) for x in [.647,.72,.794]],.0018,graphite)
        # Official rear-quarter photo shows a horizontal clear return lens
        # continuing around the curved shoulder, beside the two red eyes.
        def tailreturn(u,v,clear=False):
            theta=(1.12+.405*u) if not clear else (1.20+.25*u)
            z=(.949+.161*v) if not clear else (1.020+.040*v)
            x=s*sx(REAR,z)*math.sin(theta)**(2/4.2)
            return(x+s*.004,ry(x,z)-(.010 if not clear else .018),z)
        surface('A10_Taillamp_Quarter_Return_Housing',lambda u,v:tailreturn(u,v),28,14,smoked,s<0)
        surface('A10_Taillamp_Clear_Quarter_Return',lambda u,v:tailreturn(u,v,True),28,8,chrome,s<0)
    text_obj('A10_Tailgate_Lettering','L E A P M O T O R',(0,-2.148,1.063),.036,chrome,rotation=(math.pi/2,0,0),spacing=1.1)
    text_obj('A10_Model_Badge','A10',(.578,-2.12,.737),.033,chrome,rotation=(math.pi/2,0,0))
    # Rear plate recess, lower bumper and reflector strip are distinct surfaces.
    q=[rear(x,z,.008) for x,z in rounded_outline(0,.45,.96,.207,.034,8)];patch('A10_Rear_Plate_Recess',q,gap,.012,(0,-1,0),7,2)
    roundbox('A10_Rear_License_Plate',(0,-2.155,.454),(.395,.022,.122),black,.006)
    text_obj('A10_Rear_Plate_Text','A10',(0,-2.169,.455),.076,white,rotation=(math.pi/2,0,0))
    surface('A10_Rear_Lower_Cladding',lambda u,v:(x:=-.85+1.7*u,ry(x,z:=.231+.115*v)-.009,z),80,10,cladding)
    for s in [-1,1]:
        curve('A10_Rear_Bumper_Reflector',[rear(s*x,.326,.027) for x in [.565,.657,.74]],.010,red)
        for x in [.415,.784]:
            c=Vector(rear(s*x,.479,.009));p=[c+Vector((.007*math.cos(a),0,.007*math.sin(a))) for a in [i*2*math.pi/24 for i in range(24)]];tube('A10_Rear_Parking_Sensor',p,.0015,gap,True,6)
    # Flat concealed underside keeps opaque glazing/cabin exterior-only.
    roundbox('A10_Underbody',(0,0,.238),(1.47,3.42,.068),gap,.022)
    # Trim patches follow the underlying curved panel at every sampled vertex,
    # rather than approximating its bowed surface with a planar polygon chord.
    for o in list(bpy.context.scene.objects):
        if o.type!='MESH':continue
        if 'Headlamp_Smoked_Housing' in o.name or 'Lower_Intake_Recess' in o.name:
            for v in o.data.vertices:v.co.y=fy(v.co.x,v.co.z)+(.016 if 'Headlamp' in o.name else .009)
        elif 'Smile_Taillamp_Housing' in o.name or 'Rear_Plate_Recess' in o.name:
            for v in o.data.vertices:v.co.y=ry(v.co.x,v.co.z)-(.023 if 'Taillamp' in o.name else .011)
        elif any(k in o.name for k in ['_Side_Glass','Cabin_Side_Black']):
            s=1 if sum(v.co.x for v in o.data.vertices)>0 else -1
            for v in o.data.vertices:v.co.x=s*(cx(v.co.y,v.co.z)+(.0035 if '_Side_Glass' in o.name else 0))
        o.data.update()
    for o in list(bpy.context.scene.objects):
        if o.type=='MESH' and any(k in o.name for k in ['Crowned_Panoramic','Roof_Spoiler']):
            bpy.context.view_layer.objects.active=o
            m=o.modifiers.new('Physical outer-panel thickness','SOLIDIFY');m.thickness=.006;m.offset=-1
            bpy.ops.object.modifier_apply(modifier=m.name)
    body=[o for o in bpy.context.scene.objects if o.type=='MESH']
    body=join_by_material(body,'A10_Body')

    rig={}
    for s in [-1,1]:
        for yc in CY:
            pos=('F' if yc>0 else 'R')+('L' if s<0 else 'R');center=Vector((s*TRACK,yc,R))
            before=set(bpy.context.scene.objects)
            # Lathed tire retains sidewalls, crown, bead and embossed circumferential ribs.
            tireprofile=[(-.100,.226),(-.111,.250),(-.109,.291),(-.099,.321),(-.077,.334),(-.049,.3361),(.049,.3361),(.077,.334),(.099,.321),(.109,.291),(.111,.250),(.100,.226)]
            lathe_x('A10_Tire_Carcass',tireprofile,rubber,128)
            for side in [-1,1]:
                for rr in [.267,.301]:lathe_x('A10_Tire_Sidewall_Rib',[(side*.108,rr-.0009),(side*.1094,rr),(side*.108,rr+.0009)],rubber,128)
            # Fine actual tread grooves follow the crowned profile.
            for i in range(72):
                a=i*2*math.pi/72
                for side in [-1,1]:
                    points=[]
                    for k in range(6):
                        xx=side*(.008+.083*k/5);aa=a+.055*k/5;rr=.3362-.008*(abs(xx)/.095)**4
                        points.append((xx,rr*math.cos(aa),rr*math.sin(aa)))
                    tube('A10_Tread_Lateral_Groove',points,.00125,gap,sides=4)
            for xx in [-.042,.042]:lathe_x('A10_Tread_Circumferential_Groove',[(xx-.0012,.336),(xx,.3348),(xx+.0012,.336)],gap,128)
            lathe_x('A10_Alloy_Rim_Barrel',[(-.097,.207),(-.091,.226),(.091,.226),(.103,.234),(.108,.235),(.111,.230),(.108,.220),(.098,.216)],graphite,96)
            for face in [-1,1]:
                x=face*.108
                lathe_x('A10_Diamond_Cut_Rim_Lip',[(x-face*.004,.230),(x,.235),(x+face*.003,.233),(x+face*.003,.226)],chrome,128)
                # Five paired Y spokes, traced from the official 18 inch design.
                for n in range(5):
                    angle=2*math.pi*n/5+.15
                    for branch in [-1,1]:
                        polar=[(.054,angle+branch*.18),(.114,angle+branch*.08),(.149,angle+branch*.26),(.225,angle+branch*.31),(.229,angle+branch*.39),(.146,angle+branch*.40),(.101,angle+branch*.21),(.052,angle+branch*.36)]
                        outline=[(x+face*.003,rr*math.cos(a),rr*math.sin(a)) for rr,a in polar]
                        patch('A10_Diamond_Cut_Split_Spoke',outline,chrome,.002,(face,0,0),3,2)
                        inner=[(x-face*.004,rr*math.cos(a),rr*math.sin(a)) for rr,a in polar];patch('A10_Spoke_Black_Side',inner,graphite,.001,(face,0,0),3,2)
                lathe_x('A10_Wheel_Hub',[(x,.004),(x,.042),(x+face*.004,.045),(x+face*.008,.039),(x+face*.008,0)],graphite,64)
                for n in range(5):
                    a=n*2*math.pi/5;loc=(x+face*.006,.031*math.cos(a),.031*math.sin(a));bpy.ops.mesh.primitive_uv_sphere_add(segments=10,ring_count=6,radius=.005,location=loc);o=bpy.context.object;o.name='A10_Wheel_Lug';o.scale.x=.6;o.data.materials.append(chrome)
                # Small central marque; two slanted raised strokes.
                for d in [-.007,.007]:curve('A10_Hub_Logo',[(x+face*.010,d-.006,-.012),(x+face*.010,d+.006,.012)],.0022,chrome,steps=1)
            lathe_x('A10_Brake_Disc',[(-.061,0),(-.061,.167),(-.046,.169),(-.043,.165),(-.043,0)],brake,96)
            for n in range(24):
                a=n*2*math.pi/24;curve('A10_Brake_Disc_Machining',[(.039,.128*math.cos(a),.128*math.sin(a)),(.039,.157*math.cos(a+.08),.157*math.sin(a+.08))],.0009,graphite,steps=1,sides=4)
            parts=[o for o in bpy.context.scene.objects if o not in before and o.type=='MESH'];parts=join_by_material(parts,'A10_'+pos)
            pivot=bpy.data.objects.new('Wheel_'+pos,None);bpy.context.collection.objects.link(pivot);pivot.location=center;pivot['wheelPosition']=pos;pivot['wheelRadius']=R;pivot['frontWheel']=pos.startswith('F')
            roll=bpy.data.objects.new('WheelRoll_'+pos,None);bpy.context.collection.objects.link(roll);roll.parent=pivot
            for o in parts:o.parent=roll
            rig[pos]={'centerBlender':list(center),'radius':R,'triangles':triangles(parts),'components':len(parts)}
    bpy.context.view_layer.update()
    return rig

def export_and_render(rig):
    objects=[o for o in bpy.context.scene.objects if o.type in ['MESH','EMPTY']]
    count=triangles(objects)
    for o in objects:
        if o.type=='MESH' and CAR=='leap-a10':
            # Correct winding consistently on surface-built components.
            import bmesh
            bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free()
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    dest=OUT/(CAR+'.glb')
    bpy.ops.export_scene.gltf(filepath=str(dest),export_format='GLB',use_selection=True,export_apply=True,export_extras=True,export_draco_mesh_compression_enable=True,export_draco_mesh_compression_level=6,export_draco_position_quantization=18,export_draco_normal_quantization=14,export_draco_texcoord_quantization=16)
    raw=dest.read_bytes();gltf=json.loads(raw[20:20+struct.unpack_from('<I',raw,12)[0]])
    nodes=gltf['nodes'];wheel_nodes=[n for n in nodes if n.get('extras',{}).get('wheelPosition')]
    assert len(wheel_nodes)==4
    for n in wheel_nodes:
        p=n['extras']['wheelPosition'];assert n['extras']['frontWheel']==p.startswith('F');assert any(nodes[i].get('name')=='WheelRoll_'+p for i in n.get('children',[]))
    record={'car':CAR,'sourceYear':2026,'displayModel':'2026款 505激光雷达版外观 · 岩灰','assetType':'reference-reconstruction','author':'Original exterior reconstruction for this project','license':'Project-authored geometry; reference photos excluded from runtime','source':'https://www.leapmotor.uz/en/models/a10','dimensionsM':[4.27,1.81,1.635],'wheelbaseM':2.605,'runtimeTriangles':count,'runtimeMeshes':sum(o.type=='MESH' for o in objects),'runtimeBytes':dest.stat().st_size,'budgetBytes':10000000,'wheelRig':rig,'rigFacesBefore':count,'rigFacesAfter':count,'geometryCompression':'Draco position 18 bits, normal 14 bits, UV 16 bits; no decimation','scope':'Exterior only; continuous shaped body surfaces, separate glazing and lamp internals, four complete steering/rolling wheel assemblies','referencePolicy':'Official photographs archived unchanged; used as visual reference only. No photo textures included.','features':['Individually shaped continuous side skins with open wheel arches','Sloping clamshell hood and bowed glazing','Five paired diamond-cut Y spokes with tire tread geometry','Distinct short front lamps and smiling separate rear lamps','D-pillar twin bars, semi-flush handles, door/hood/tailgate seams','Mirrors, spoiler, LiDAR, fascia vane grille and badges'],'remainingDifferences':['Reconstruction from perspective photographs, not manufacturer CAD or a measured scan','Fine stamped crease radii and optical lens microstructure are approximations','Window contours and body highlights require actual multi-angle visual review'],'qualityStatus':'pending-visual-review','sourcePhotos':'assets/vehicles/suv-exteriors/leap-a10/references','sha256':hashlib.sha256(raw).hexdigest()}
    if CAR=='yuan-up':record.update(YUAN_META)
    else:record['displayModel']='2026款 505激光雷达版外观 · 绿色'
    record['revision']=REV
    (OUT/(CAR+'-quality.json')).write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(REVIEW/(CAR+'-authored.blend')))
    import shutil
    shutil.copy2(REVIEW/(CAR+'-authored.blend'),ROOT/'assets/blender/tourism'/(CAR+'-exterior.blend'))
    # Preview and hierarchy tests use a fresh import of the exact delivered GLB.
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(dest));objects=list(bpy.context.scene.objects)
    pivots=[o for o in objects if o.get('wheelPosition')]
    assert len(pivots)==4 and all(o.get('wheelRadius')>.3 for o in pivots)
    rolls=[o for o in objects if o.name.startswith('WheelRoll_')]
    for o in pivots+rolls:o.rotation_mode='XYZ'
    def wheel_points(pivot):
        return [(o.matrix_world@v.co).copy() for o in pivot.children_recursive if o.type=='MESH' for v in o.data.vertices]
    wheel_before={p.get('wheelPosition'):wheel_points(p) for p in pivots}
    fixed=[o for o in objects if o.type=='MESH' and not o.parent]
    fixed_before={o.name:[tuple(o.matrix_world@v.co) for v in o.data.vertices] for o in fixed}
    for p in pivots:
        if p.get('frontWheel'):p.rotation_euler.z=math.radians(25)
    for o in objects:
        if o.name.startswith('WheelRoll_'):o.rotation_euler.x=math.radians(45)
    bpy.context.view_layer.update()
    assert all(fixed_before[o.name]==[tuple(o.matrix_world@v.co) for v in o.data.vertices] for o in fixed)
    wheel_motion={}
    for p in pivots:
        key=p.get('wheelPosition');after=wheel_points(p);before=wheel_before[key]
        ratio=sum((a-b).length>1e-6 for a,b in zip(after,before))/max(1,len(before))
        assert ratio>.98,(key,'Wheel vertices did not move',ratio)
        wheel_motion[key]={'vertices':len(before),'movedFraction':ratio}
    for p in pivots:p.rotation_euler.z=0
    for o in objects:
        if o.name.startswith('WheelRoll_'):o.rotation_euler.x=0
    record['rigValidation']={'fourWheelPivots':True,'bodyStationaryWhenWheelsMove':True,'frontSteeringDegrees':25,'rollingDegrees':45,'actualWheelVertexMotion':wheel_motion,'previewUsesExportedGlb':True,'runtimeSha256':hashlib.sha256(raw).hexdigest()}
    (OUT/(CAR+'-quality.json')).write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n')
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
    scene.render.resolution_x=1200;scene.render.resolution_y=800;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
    scene.world.use_nodes=True;bg=scene.world.node_tree.nodes.get('Background');bg.inputs['Color'].default_value=(.32,.36,.40,1);bg.inputs['Strength'].default_value=.45
    for loc,power,size in [((-3,5,7),950,3.5),((4,1,6),600,5),((3,-4,6),1050,4)]:
        data=bpy.data.lights.new('Studio softbox','AREA');data.energy=power;data.shape='DISK';data.size=size;o=bpy.data.objects.new('Studio softbox',data);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(-o.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.006));o=bpy.context.object;o.name='Review floor';o.data.materials.append(mat('Review_Floor',(.08,.095,.115),0,.75))
    camera=bpy.data.cameras.new('Exterior review');cam=bpy.data.objects.new('Exterior review',camera);bpy.context.collection.objects.link(cam);scene.camera=cam;camera.lens=58
    bpy.ops.wm.save_as_mainfile(filepath=str(REVIEW/(CAR+'-render-review.blend')))
    views=[('front',(6.4,8.3,3.2)),('rear',(-6.4,-8.3,3.1)),('side',(9,0,2.05)),('front-ortho',(0,10,1.03)),('rear-ortho',(0,-10,1.1)),('steered',(7,4.8,2.15))]
    if '--draft' in sys.argv:views=views[:3];scene.cycles.samples=12;scene.render.resolution_percentage=75
    for label,loc in views:
        cam.location=loc;cam.rotation_euler=(Vector((0,0,.8))-cam.location).to_track_quat('-Z','Y').to_euler()
        camera.type='ORTHO' if label.endswith('ortho') or label=='side' else 'PERSP';camera.ortho_scale=5.2 if label=='side' else 3.2
        for o in objects:
            if o.get('frontWheel'):o.rotation_euler.z=math.radians(25) if label=='steered' else 0
            if o.name.startswith('WheelRoll_'):o.rotation_euler.x=math.radians(45) if label=='steered' else 0
        scene.render.filepath=str(REVIEW/(CAR+'-'+label+'.png'));bpy.ops.render.render(write_still=True)
    print('SUV_EXTERIOR_READY',json.dumps(record,ensure_ascii=False),flush=True)

if __name__=='__main__':
    assert CAR in ['leap-a10','yuan-up']
    export_and_render(build_a10() if CAR=='leap-a10' else build_yuan())
