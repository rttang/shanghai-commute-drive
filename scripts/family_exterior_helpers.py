"""Small geometry tools for the independently drawn i6 and 2026 Q05 exteriors.

All dimensions are metres. Blender +Y is forward and +Z is up. No existing
vehicle mesh or procedural vehicle prototype is imported by this module.
"""
import bpy, bmesh, math
from mathutils import Vector

def material(name, rgb, metallic=0, rough=.35, emission=0):
    mat=bpy.data.materials.new(name);mat.diffuse_color=(*rgb,1);mat.use_nodes=True
    p=mat.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*rgb,1)
    p.inputs['Metallic'].default_value=metallic;p.inputs['Roughness'].default_value=rough
    if metallic>.3:p.inputs['Coat Weight'].default_value=.32
    if emission:
        p.inputs['Emission Color'].default_value=(*rgb,1);p.inputs['Emission Strength'].default_value=emission
    return mat

def mesh(name,verts,faces,mat,smooth=True,parent=None):
    data=bpy.data.meshes.new(name);data.from_pydata(verts,[],faces);data.update()
    ob=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(ob)
    if mat:data.materials.append(mat)
    if parent:ob.parent=parent
    for poly in data.polygons:poly.use_smooth=smooth
    return ob

def grid(name,fn,nu,nv,mat,parent=None):
    vs=[fn(i/nu,j/nv) for i in range(nu+1) for j in range(nv+1)]
    fs=[]
    for i in range(nu):
        for j in range(nv):
            a=i*(nv+1)+j;fs.append((a,a+nv+1,a+nv+2,a+1))
    return mesh(name,vs,fs,mat,parent=parent)

def interp(knots,v):
    """Monotonic cubic interpolation of measured silhouette stations."""
    if v<=knots[0][0]:return knots[0][1]
    if v>=knots[-1][0]:return knots[-1][1]
    for i in range(len(knots)-1):
        x0,y0=knots[i];x1,y1=knots[i+1]
        if x0<=v<=x1:
            delta=(y1-y0)/(x1-x0)
            def slope(k):
                if k==0:return (knots[1][1]-knots[0][1])/(knots[1][0]-knots[0][0])
                if k==len(knots)-1:return (knots[-1][1]-knots[-2][1])/(knots[-1][0]-knots[-2][0])
                a=(knots[k][1]-knots[k-1][1])/(knots[k][0]-knots[k-1][0]);b=(knots[k+1][1]-knots[k][1])/(knots[k+1][0]-knots[k][0])
                return 0 if a*b<=0 else 2*a*b/(a+b)
            t=(v-x0)/(x1-x0);h=x1-x0
            return (2*t**3-3*t*t+1)*y0+(t**3-2*t*t+t)*h*slope(i)+(-2*t**3+3*t*t)*y1+(t**3-t*t)*h*slope(i+1)

def tube(name,points,radius,mat,closed=False,parent=None,segments=6):
    data=bpy.data.curves.new(name,'CURVE');data.dimensions='3D';data.resolution_u=1
    data.bevel_depth=radius;data.bevel_resolution=2;data.resolution_u=1
    spl=data.splines.new('POLY');spl.points.add(len(points)-1)
    for p,co in zip(spl.points,points):p.co=(*co,1)
    spl.use_cyclic_u=closed
    ob=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(ob);data.materials.append(mat)
    if parent:ob.parent=parent
    return ob

def smooth_path(points,n=8,closed=False):
    """Round corners inside the supplied polygon without spline overshoot.

    A uniform Catmull-Rom curve can overshoot a long bumper edge by 20 cm at
    a short corner. Bounded quadratic fillets and sampled straight sections
    preserve the independently drawn lamp/window/door outline instead.
    """
    ps=[Vector(p) for p in points];arcs=[]
    for i,p in enumerate(ps):
        if not closed and i in [0,len(ps)-1]:arcs.append([p]);continue
        prev=ps[(i-1)%len(ps)];nxt=ps[(i+1)%len(ps)]
        la=(prev-p).length;lb=(nxt-p).length;r=min(la,lb)*.18
        r=min(r,.040)
        a=p+(prev-p)*(r/max(la,1e-9));b=p+(nxt-p)*(r/max(lb,1e-9))
        arcs.append([(1-t)**2*a+2*t*(1-t)*p+t*t*b for t in [j/max(1,n) for j in range(n+1)]])
    result=[]
    for i,arc in enumerate(arcs):
        if result:
            a=Vector(result[-1]);b=arc[0];count=max(1,math.ceil((b-a).length/.035))
            result.extend(tuple(a+(b-a)*j/count) for j in range(1,count))
        result.extend(tuple(p) for p in arc)
    if closed:
        a=Vector(result[-1]);b=Vector(result[0]);count=max(1,math.ceil((b-a).length/.035))
        result.extend(tuple(a+(b-a)*j/count) for j in range(1,count))
    return result

def plaque(name,points,mat,depth=.008,parent=None):
    """A curved boundary with a shallow back; useful for lenses and trim."""
    if parent and parent.name.startswith('WheelRoll_'):
        side=-1 if parent.name.endswith('L') else 1
        normal=sum((Vector(points[i]).cross(Vector(points[(i+1)%len(points)])) for i in range(len(points))),Vector())
        if normal.x*side<0:points=list(reversed(points))
    ob=mesh(name,points,[tuple(range(len(points)))],mat,smooth=False,parent=parent)
    if depth:
        m=ob.modifiers.new('Lens thickness','SOLIDIFY');m.thickness=depth
    return ob

def box(name,location,scale,mat,bevel=.02,parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1,location=location);ob=bpy.context.object;ob.name=name
    ob.scale=scale;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if mat:ob.data.materials.append(mat)
    if bevel:
        m=ob.modifiers.new('Manufactured edge','BEVEL');m.width=bevel;m.segments=4
        m=ob.modifiers.new('Weighted surface normals','WEIGHTED_NORMAL')
    if parent:ob.parent=parent
    return ob

def sphere(name,location,scale,mat,parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=40,ring_count=24,location=location)
    ob=bpy.context.object;ob.name=name;ob.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);ob.data.materials.append(mat)
    for p in ob.data.polygons:p.use_smooth=True
    if parent:ob.parent=parent
    return ob

def lathe_x(name,profile,mat,parent=None,n=128):
    vs=[];fs=[]
    for x,r in profile:
        vs.extend([(x,r*math.sin(i*math.tau/n),r*math.cos(i*math.tau/n)) for i in range(n)])
    for j in range(len(profile)-1):
        for i in range(n):
            a=j*n+i;b=j*n+(i+1)%n;fs.append((a,b,b+n,a+n))
    return mesh(name,vs,fs,mat,parent=parent)

def wheel(name,center,radius,width,rim_radius,mats,design):
    pivot=bpy.data.objects.new('Wheel_'+name,None);bpy.context.collection.objects.link(pivot);pivot.location=center
    pivot['wheelPosition']=name;pivot['wheelRadius']=radius;pivot['frontWheel']=name.startswith('F')
    roll=bpy.data.objects.new('WheelRoll_'+name,None);bpy.context.collection.objects.link(roll);roll.parent=pivot
    side=-1 if name.endswith('L') else 1
    # Turned radial profile includes tread crown, rounded shoulders and two beads.
    profile=[(-width*.46,rim_radius*.99),(-width*.50,rim_radius*1.13),(-width*.51,radius*.92),(-width*.44,radius*.986),(-width*.30,radius),(-width*.15,radius*1.001),(0,radius*1.002),(width*.15,radius*1.001),(width*.30,radius),(width*.44,radius*.986),(width*.51,radius*.92),(width*.50,rim_radius*1.13),(width*.46,rim_radius*.99)]
    lathe_x(name+' tyre curved sidewall',profile,mats['rubber'],roll)
    # Raised and recessed bands plus diagonal tread sipes visible at steering angle.
    for offset in [-.28,-.10,.10,.28]:
        x=width*offset
        lathe_x(name+' circumferential tread channel',[(x-.0017,radius*1.002),(x,radius*1.004),(x+.0017,radius*1.002)],mats['groove'],roll)
    for i in range(80):
        a=i*math.tau/80
        for sg in [-1,1]:
            pts=[]
            for k in range(5):
                x=sg*width*(.05+.30*k/4);ang=a+sg*(k/4)*.030
                pts.append((x,(radius+.0008)*math.sin(ang),(radius+.0008)*math.cos(ang)))
            tube(name+' tread sipe',pts,.0012,mats['groove'],parent=roll)
    for sidewall in [-1,1]:
        for rr in [rim_radius*1.04,radius*.88,radius*.935]:
            lathe_x(name+' sidewall moulding',[(sidewall*width*.506,rr-.0015),(sidewall*width*.511,rr),(sidewall*width*.506,rr+.0015)],mats['rubber'],roll,n=96)
    outer=side*width*.51
    lathe_x(name+' alloy outer lip',[(outer-side*.024,rim_radius*.94),(outer,rim_radius),(outer+side*.004,rim_radius),(outer+side*.006,rim_radius*.96),(outer,rim_radius*.935)],mats['alloy'],roll)
    lathe_x(name+' graphite rim barrel',[(-width*.4,rim_radius*.95),(width*.4,rim_radius*.95)],mats['black'],roll)
    lathe_x(name+' brake rotor',[(outer-side*.05,.055),(outer-side*.05,rim_radius*.80),(outer-side*.065,rim_radius*.80),(outer-side*.065,.055)],mats['rotor'],roll,n=96)
    count=10 if design=='i6' else 5
    for i in range(count):
        a=i*math.tau/count
        def polar(r,da,x=outer):return (x,r*math.sin(a+da),r*math.cos(a+da))
        if design=='i6':
            pts=[polar(rim_radius*.22,-.15),polar(rim_radius*.87,-.10),polar(rim_radius*.95,.05),polar(rim_radius*.87,.22),polar(rim_radius*.31,.14)]
            plaque(name+' swept aero blade',pts,mats['alloy'],.012,roll)
            pts=[polar(rim_radius*.33,.24,outer-side*.004),polar(rim_radius*.85,.39,outer-side*.004),polar(rim_radius*.93,.45,outer-side*.004),polar(rim_radius*.28,.39,outer-side*.004)]
            plaque(name+' aero spoke graphite return',pts,mats['black'],.009,roll)
        else:
            # Five paired black spoke groups, narrow diamond-cut edges and
            # broad outer triangular facets, traced from q05-04 side photograph.
            for offset in [-.23,.23]:
                petal=[polar(rim_radius*.22,offset-.10,outer-side*.004),polar(rim_radius*.83,offset-.16,outer-side*.004),polar(rim_radius*.95,offset-.12,outer-side*.004),polar(rim_radius*.95,offset+.12,outer-side*.004),polar(rim_radius*.83,offset+.16,outer-side*.004),polar(rim_radius*.22,offset+.10,outer-side*.004)]
                plaque(name+' gloss black structural spoke',petal,mats['black'],.014,roll)
                for edge in [-1,1]:
                    pts=[polar(rim_radius*.27,offset+edge*.066-.016),polar(rim_radius*.84,offset+edge*.102-.018),polar(rim_radius*.94,offset+edge*.073-.018),polar(rim_radius*.94,offset+edge*.073+.018),polar(rim_radius*.84,offset+edge*.102+.018),polar(rim_radius*.27,offset+edge*.066+.016)]
                    plaque(name+' diamond cut spoke edge',pts,mats['alloy'],.006,roll)
                pts=[polar(rim_radius*.78,offset+.14),polar(rim_radius*.955,offset+.095),polar(rim_radius*.955,offset+.30),polar(rim_radius*.91,offset+.31)]
                plaque(name+' machined outer aero facet',pts,mats['alloy'],.008,roll)
    lathe_x(name+' center cap',[(outer+side*.006,0),(outer+side*.006,.044),(outer,.05),(outer-side*.008,.05)],mats['black'],roll,n=64)
    for i in range(5):
        a=i*math.tau/5;y=.064*math.sin(a);z=.064*math.cos(a)
        ob=sphere(name+' lug bolt',(outer+side*.002,y,z),(.008,.008,.008),mats['alloy'],roll)
    # Pivots have identity basis on glTF export, matching src/tour/wheels.ts.
    return pivot,roll

def apply_meshes():
    objects=[o for o in bpy.context.scene.objects if o.type in {'MESH','CURVE','FONT'}]
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    bpy.ops.object.convert(target='MESH')
    for o in objects:
        for mod in list(o.modifiers):
            try:
                bpy.context.view_layer.objects.active=o
                bpy.ops.object.modifier_apply(modifier=mod.name)
            except RuntimeError:pass

def join_by_parent_material():
    groups={}
    for o in list(bpy.context.scene.objects):
        if o.type=='MESH':groups.setdefault((o.parent,o.data.materials[0].name if o.data.materials else ''),[]).append(o)
    for (parent,mat),objects in groups.items():
        if len(objects)<2:continue
        bpy.ops.object.select_all(action='DESELECT')
        for ob in objects:ob.select_set(True)
        bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join();objects[0].name=('Body' if not parent else parent.name)+' '+mat
    # Panels share their sampled boundary rows. Welding those positions allows
    # a single continuous normal across a hood/shoulder instead of a hard crease.
    for ob in [o for o in bpy.context.scene.objects if o.type=='MESH']:
        bm=bmesh.new();bm.from_mesh(ob.data)
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00002)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        bm.to_mesh(ob.data);bm.free();ob.data.update()
