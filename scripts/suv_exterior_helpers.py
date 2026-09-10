"""Continuous surface and manufactured-detail tools for the A10 exterior.

Independent authored geometry in metres; Blender +Y is forward and +Z is up.
No existing car body or interior is used by these functions.
"""
import math
import bpy
from mathutils import Vector

def mat(name, rgb, metal=0, rough=.3, coat=0, emission=0):
    m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*rgb,1)
    p=m.node_tree.nodes.get('Principled BSDF')
    for key,value in [('Base Color',(*rgb,1)),('Metallic',metal),('Roughness',rough),('Coat Weight',coat),('Coat Roughness',.14)]:p.inputs[key].default_value=value
    if emission:p.inputs['Emission Color'].default_value=(*rgb,1);p.inputs['Emission Strength'].default_value=emission
    return m

def mesh(name, verts, faces, material, smooth=True):
    data=bpy.data.meshes.new(name);data.from_pydata(verts,[],faces);data.update()
    obj=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(obj)
    if material:data.materials.append(material)
    for face in data.polygons:face.use_smooth=smooth
    return obj

def surface(name, fn, nu, nv, material, reverse=False):
    verts=[fn(i/nu,j/nv) for i in range(nu+1) for j in range(nv+1)];faces=[]
    for i in range(nu):
        for j in range(nv):
            a=i*(nv+1)+j;f=(a,a+nv+1,a+nv+2,a+1);faces.append(f[::-1] if reverse else f)
    return mesh(name,verts,faces,material)

def interp(keys,t):
    if t<=keys[0][0]:return keys[0][1]
    if t>=keys[-1][0]:return keys[-1][1]
    for i in range(len(keys)-1):
        x0,y0=keys[i];x1,y1=keys[i+1]
        if t>x1:continue
        d=(y1-y0)/(x1-x0);pr=keys[max(i-1,0)];nx=keys[min(i+2,len(keys)-1)]
        a=(y1-pr[1])/(x1-pr[0]);b=(nx[1]-y0)/(nx[0]-x0)
        if d==0:a=b=0
        else:
            a=math.copysign(min(abs(a),abs(3*d)),d) if a*d>0 else 0
            b=math.copysign(min(abs(b),abs(3*d)),d) if b*d>0 else 0
        u=(t-x0)/(x1-x0)
        return (2*u**3-3*u*u+1)*y0+(u**3-2*u*u+u)*(x1-x0)*a+(-2*u**3+3*u*u)*y1+(u**3-u*u)*(x1-x0)*b

def spline(points, steps=8, closed=False):
    p=[Vector(x) for x in points];n=len(p);out=[]
    for i in range(n if closed else n-1):
        a=p[(i-1)%n] if i or closed else p[0];b=p[i];c=p[(i+1)%n];d=p[(i+2)%n] if i+2<n or closed else p[-1]
        for j in range(steps):
            t=j/steps;out.append((2*b+(c-a)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t)*.5)
    if not closed:out.append(p[-1])
    return out

def tube(name,points,radius,material,closed=False,sides=8):
    p=[Vector(v) for v in points];verts=[];faces=[];previous_u=None
    for i,pt in enumerate(p):
        before=p[(i-1)%len(p)] if i or closed else p[0];after=p[(i+1)%len(p)] if i+1<len(p) or closed else p[-1]
        t=(after-before).normalized()
        if previous_u is None:
            ref=Vector((0,0,1)) if abs(t.z)<.95 else Vector((0,1,0));u=t.cross(ref).normalized()
        else:
            u=previous_u-t*previous_u.dot(t)
            if u.length<.00001:u=t.cross(Vector((1,0,0)) if abs(t.x)<.9 else Vector((0,1,0)))
            u.normalize()
        v=t.cross(u);previous_u=u
        verts.extend(pt+radius*(u*math.cos(k*2*math.pi/sides)+v*math.sin(k*2*math.pi/sides)) for k in range(sides))
    for i in range(len(p) if closed else len(p)-1):
        for j in range(sides):faces.append((i*sides+j,((i+1)%len(p))*sides+j,((i+1)%len(p))*sides+(j+1)%sides,i*sides+(j+1)%sides))
    if not closed:faces.extend([tuple(range(sides-1,-1,-1)),tuple((len(p)-1)*sides+j for j in range(sides))])
    return mesh(name,verts,faces,material)

def curve(name,points,radius,material,closed=False,steps=8,sides=8):
    return tube(name,spline(points,steps,closed),radius,material,closed,sides)

def rounded_polygon(points,fraction=.085,count=6):
    """Small local corner radii without Catmull-Rom polygon overshoot."""
    p=[Vector(v) for v in points];out=[]
    for i,q in enumerate(p):
        start=q+(p[i-1]-q)*fraction;end=q+(p[(i+1)%len(p)]-q)*fraction
        for j in range(count+1):
            t=j/count;out.append(start*(1-t)**2+q*(2*t*(1-t))+end*t*t)
    return out

def patch(name,outline,material,bulge=.005,normal=(0,0,1),rings=5,steps=5):
    b=rounded_polygon(outline) if steps==0 else spline(outline,steps,True);c=sum(b,Vector())/len(b);normal=Vector(normal)
    verts=[c+normal*bulge];n=len(b);faces=[]
    for k in range(1,rings+1):
        t=k/rings;verts.extend(c+(p-c)*t+normal*bulge*(1-t*t) for p in b)
    for j in range(n):faces.append((0,1+j,1+(j+1)%n))
    for k in range(rings-1):
        for j in range(n):a=1+k*n+j;bb=1+k*n+(j+1)%n;faces.append((a,a+n,bb+n,bb))
    if (b[0]-c).cross(b[1]-c).dot(normal)<0:faces=[f[::-1] for f in faces]
    return mesh(name,verts,faces,material)

def rounded_outline(cx,cy,width,height,radius=.03,n=10):
    pts=[]
    for x,y,a in [(cx+width/2-radius,cy+height/2-radius,0),(cx-width/2+radius,cy+height/2-radius,90),(cx-width/2+radius,cy-height/2+radius,180),(cx+width/2-radius,cy-height/2+radius,270)]:
        for i in range(n):q=math.radians(a+90*i/n);pts.append((x+radius*math.cos(q),y+radius*math.sin(q)))
    return pts

def lathe_x(name,profile,material,n=96):
    verts=[(x,r*math.cos(j*2*math.pi/n),r*math.sin(j*2*math.pi/n)) for x,r in profile for j in range(n)];faces=[]
    for i in range(len(profile)-1):
        for j in range(n):faces.append((i*n+j,(i+1)*n+j,(i+1)*n+(j+1)%n,i*n+(j+1)%n))
    return mesh(name,verts,faces,material)

def roundbox(name,center,dims,material,bevel=.008):
    bpy.ops.mesh.primitive_cube_add(size=1,location=center);o=bpy.context.object;o.name=name;o.dimensions=dims
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    b=o.modifiers.new('Manufactured edge radius','BEVEL');b.width=bevel;b.segments=4;bpy.ops.object.modifier_apply(modifier=b.name)
    o.data.materials.append(material)
    for f in o.data.polygons:f.use_smooth=True
    m=o.modifiers.new('Weighted normals','WEIGHTED_NORMAL');bpy.ops.object.modifier_apply(modifier=m.name)
    return o

def text_obj(name,body,loc,size,material,rotation=(math.pi/2,0,math.pi),spacing=1):
    d=bpy.data.curves.new(name,'FONT');d.body=body;d.size=size;d.align_x='CENTER';d.align_y='CENTER';d.extrude=.0008;d.space_character=spacing
    o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=rotation;d.materials.append(material)
    bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.object.convert(target='MESH');o.select_set(False);return o

def triangles(objects):return sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objects if o.type=='MESH')

def join_by_material(objects,name):
    buckets={}
    for o in objects:
        if o.type=='MESH':buckets.setdefault(tuple(m.name for m in o.data.materials),[]).append(o)
    out=[]
    for materials,parts in buckets.items():
        bpy.ops.object.select_all(action='DESELECT')
        for o in parts:o.select_set(True)
        bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join();o=bpy.context.object;o.name=name+'_'+materials[0];out.append(o)
    return out
