"""Geometry tools for individually traced compact-car exterior surfaces.

Blender coordinates: +Y forward, +Z up; dimensions are metres. These are
independent meshes, not edits or subdivision of the rejected downloaded asset.
"""
import math
import bpy
from mathutils import Vector


def material(name, rgb, metal=0, rough=.35, coat=0, emission=0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*rgb, 1)
    p.inputs['Metallic'].default_value = metal
    p.inputs['Roughness'].default_value = rough
    p.inputs['Coat Weight'].default_value = coat
    p.inputs['Coat Roughness'].default_value = .16
    if emission:
        p.inputs['Emission Color'].default_value = (*rgb, 1)
        p.inputs['Emission Strength'].default_value = emission
    return m


def mesh(name, vertices, faces, mat, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata(vertices, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    if mat:
        me.materials.append(mat)
    for f in me.polygons:
        f.use_smooth = smooth
    return ob


def surface(name, fn, nu, nv, mat, reverse=False):
    verts = [fn(i/nu,j/nv) for i in range(nu+1) for j in range(nv+1)]
    faces=[]
    for i in range(nu):
        for j in range(nv):
            a=i*(nv+1)+j
            f=(a,a+nv+1,a+nv+2,a+1)
            faces.append(tuple(reversed(f)) if reverse else f)
    return mesh(name,verts,faces,mat)


def spline(points, steps=10, closed=False):
    p=[Vector(x) for x in points]
    out=[]
    n=len(p)
    for i in range(n if closed else n-1):
        a=p[(i-1)%n] if i or closed else p[0]
        b=p[i];c=p[(i+1)%n];d=p[(i+2)%n] if i+2<n or closed else p[-1]
        for j in range(steps):
            t=j/steps
            out.append((b*2+(c-a)*t+(a*2-b*5+c*4-d)*t*t+(-a+b*3-c*3+d)*t*t*t)*.5)
    if not closed:out.append(p[-1])
    return out


def rounded_boundary(points, radius=.035, samples=8):
    """Round polygon corners without Catmull overshoot across straight mullions."""
    p=[Vector(x) for x in points];out=[]
    for i,corner in enumerate(p):
        before=p[(i-1)%len(p)];after=p[(i+1)%len(p)]
        distance=min(radius,(before-corner).length*.28,(after-corner).length*.28)
        a=corner+(before-corner).normalized()*distance
        b=corner+(after-corner).normalized()*distance
        for j in range(samples+1):
            t=j/samples
            out.append((1-t)**2*a+2*(1-t)*t*corner+t*t*b)
        next_corner=p[(i+1)%len(p)];next_after=p[(i+2)%len(p)]
        next_distance=min(radius,(corner-next_corner).length*.28,(next_after-next_corner).length*.28)
        next_a=next_corner+(corner-next_corner).normalized()*next_distance
        count=max(2,int((next_a-b).length/.02))
        out.extend(b.lerp(next_a,j/count) for j in range(1,count))
    return out


def tube(name, points, radius, mat, closed=False, sides=8):
    p=[Vector(v) for v in points]
    vertices=[]
    for i,pt in enumerate(p):
        before=p[(i-1)%len(p)] if i or closed else p[0]
        after=p[(i+1)%len(p)] if i<len(p)-1 or closed else p[-1]
        tangent=(after-before).normalized()
        ref=Vector((0,0,1)) if abs(tangent.z)<.95 else Vector((0,1,0))
        u=tangent.cross(ref).normalized();v=tangent.cross(u).normalized()
        vertices.extend(pt+radius*(u*math.cos(k*2*math.pi/sides)+v*math.sin(k*2*math.pi/sides)) for k in range(sides))
    faces=[]
    for i in range(len(p) if closed else len(p)-1):
        for j in range(sides):faces.append((i*sides+j,((i+1)%len(p))*sides+j,((i+1)%len(p))*sides+(j+1)%sides,i*sides+(j+1)%sides))
    if not closed:
        faces.extend([tuple(reversed(range(sides))),tuple((len(p)-1)*sides+j for j in range(sides))])
    return mesh(name,vertices,[tuple(reversed(f)) for f in faces],mat)


def curve(name, points, radius, mat, closed=False, steps=8):
    return tube(name,spline(points,steps,closed),radius,mat,closed)


def panel(name, outline, mat, bulge=.005, normal=(0,0,1), rings=6):
    """Radially sampled curved panel from a traced 3D perimeter."""
    optical_panel=rings==6 and any(token in name.lower() for token in ['headlamp','feather','rear lamp','rear lens','ruby matrix'])
    if optical_panel:rings=20
    boundary=spline(outline,12 if optical_panel else 8,True)
    center=sum(boundary,Vector())/len(boundary)
    norm=Vector(normal)
    verts=[center+norm*bulge]
    for k in range(1,rings+1):
        t=k/rings
        verts.extend(center+(p-center)*t+norm*bulge*(1-t*t) for p in boundary)
    n=len(boundary);faces=[]
    for j in range(n):faces.append((0,1+j,1+(j+1)%n))
    for k in range(rings-1):
        for j in range(n):
            a=1+k*n+j;b=1+k*n+(j+1)%n
            faces.append((a,a+n,b+n,b))
    ob=mesh(name,verts,faces,mat)
    if sum((p.normal.dot(norm) for p in ob.data.polygons))<0:
        for p in ob.data.polygons:p.flip()
        ob.data.update()
    return ob


def oval(name, center, u, v, mat, bulge=.004, normal=None, n=48):
    c=Vector(center);u=Vector(u);v=Vector(v)
    norm=Vector(normal) if normal else u.cross(v).normalized()
    return panel(name,[c+u*math.cos(2*math.pi*i/n)+v*math.sin(2*math.pi*i/n) for i in range(n)],mat,bulge,norm,rings=3)


def roundbox(name, center, dims, mat, bevel=.015):
    bpy.ops.mesh.primitive_cube_add(size=1,location=center)
    o=bpy.context.object;o.name=name;o.dimensions=dims
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    b=o.modifiers.new('Manufactured edge radius','BEVEL');b.width=bevel;b.segments=4
    bpy.ops.object.modifier_apply(modifier=b.name)
    o.data.materials.append(mat)
    for f in o.data.polygons:f.use_smooth=True
    n=o.modifiers.new('Panel normals','WEIGHTED_NORMAL')
    bpy.ops.object.modifier_apply(modifier=n.name)
    return o


def lathe_x(name, profile, mat, n=96):
    verts=[(x,r*math.cos(j*2*math.pi/n),r*math.sin(j*2*math.pi/n)) for x,r in profile for j in range(n)]
    faces=[]
    for i in range(len(profile)-1):
        for j in range(n):faces.append((i*n+j,(i+1)*n+j,(i+1)*n+(j+1)%n,i*n+(j+1)%n))
    return mesh(name,verts,[tuple(reversed(f)) for f in faces],mat)


def arc_points(center, u, v, start=0, end=2*math.pi, count=80):
    c=Vector(center);u=Vector(u);v=Vector(v)
    return [c+u*math.cos(start+(end-start)*i/count)+v*math.sin(start+(end-start)*i/count) for i in range(count+1)]


def interp(keys,t):
    """Slope-limited cubic Hermite interpolation for measured longitudinal stations."""
    if t<=keys[0][0]:return keys[0][1]
    if t>=keys[-1][0]:return keys[-1][1]
    for i in range(len(keys)-1):
        x0,y0=keys[i];x1,y1=keys[i+1]
        if t>x1:continue
        slope=(y1-y0)/(x1-x0)
        s0=(y1-keys[max(0,i-1)][1])/(x1-keys[max(0,i-1)][0])
        s1=(keys[min(len(keys)-1,i+2)][1]-y0)/(keys[min(len(keys)-1,i+2)][0]-x0)
        if not slope:s0=s1=0
        else:
            s0=max(0,min(abs(s0),abs(slope)*3))*(1 if slope>0 else -1) if s0*slope>0 else 0
            s1=max(0,min(abs(s1),abs(slope)*3))*(1 if slope>0 else -1) if s1*slope>0 else 0
        u=(t-x0)/(x1-x0)
        return (2*u**3-3*u*u+1)*y0+(u**3-2*u*u+u)*(x1-x0)*s0+(-2*u**3+3*u*u)*y1+(u**3-u*u)*(x1-x0)*s1


def parent_keep(objects,parent):
    for ob in objects:
        mat=ob.matrix_world.copy();ob.parent=parent;ob.matrix_world=mat


def triangle_count(objects):
    return sum(sum(len(f.vertices)-2 for f in o.data.polygons) for o in objects if o.type=='MESH')
