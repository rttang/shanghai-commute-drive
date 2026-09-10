"""North Bund metre-scale exterior helpers, batched per PBR material.
Coordinate basis: Blender X east, Y north, Z up; independent GLB roots local.
No image resampling, generic image planes, interior padding or decimation.
"""
import bpy, math
from mathutils import Vector
from bund_model_helpers import Mesh, material

UP=Vector((0,0,1))

def polygon_ccw(points):
    p=[tuple(v) for v in points]
    if p[0]==p[-1]:p=p[:-1]
    if sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(p,p[1:]+p[:1]))<0:p.reverse()
    return p

def resample_polygon(points,pitch=1.6):
    out=[]
    for a,b in zip(points,points[1:]+points[:1]):
        n=max(1,round(math.dist(a,b)/pitch))
        out.extend((a[0]+(b[0]-a[0])*i/n,a[1]+(b[1]-a[1])*i/n) for i in range(n))
    return out

def transformed_box(mesh,center,t,n,size,mat):
    c=Vector(center);t=Vector(t);n=Vector(n);w,d,h=size
    vertices=[c+t*(i*w/2)+n*(j*d/2)+UP*(k*h/2) for i,j,k in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
    for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:mesh.face([vertices[i] for i in f],mat)

def band(mesh,points,z,thick,projection,mat):
    for a,b in (list(zip(points,points[1:]+points[:1])) if len(points)>2 else [(points[0],points[1])]):
        av=Vector((*a,z));bv=Vector((*b,z));t=(bv-av).normalized();n=Vector((t.y,-t.x,0))
        transformed_box(mesh,(av+bv)/2+n*projection/2,t,n,((bv-av).length+.02,projection,thick),mat)

def facade(mesh,a,b,z0,z1,bays,wall,trim,glass,frame,window_fraction=.5,window_height=.60,arches=False,balcony=False):
    """Independent solid piers, recessed openings, physical mullions and sills."""
    a=Vector((*a,0));b=Vector((*b,0));length=(b-a).length;t=(b-a)/length;n=Vector((t.y,-t.x,0));h=z1-z0;pitch=length/bays
    for j in range(bays):
        c=a+t*((j+.5)*pitch)+UP*(z0+h*.52);w=pitch*window_fraction;wh=h*window_height
        def p(x,y,z):return c+t*x+n*y+UP*z
        for x0,x1,y0,y1 in [(-pitch/2,-w/2,-h*.52,h*.48),(w/2,pitch/2,-h*.52,h*.48),(-w/2,w/2,-h*.52,-wh/2),(-w/2,w/2,wh/2,h*.48)]:mesh.face([p(x0,0,y0),p(x1,0,y0),p(x1,0,y1),p(x0,0,y1)],wall)
        mesh.face([p(-w/2,-.22,-wh/2),p(w/2,-.22,-wh/2),p(w/2,-.22,wh/2),p(-w/2,-.22,wh/2)],glass[j%len(glass)] if isinstance(glass,list) else glass)
        for aa,bb in [((-w/2,-wh/2),(w/2,-wh/2)),((w/2,-wh/2),(w/2,wh/2)),((w/2,wh/2),(-w/2,wh/2)),((-w/2,wh/2),(-w/2,-wh/2))]:
            mesh.face([p(aa[0],0,aa[1]),p(bb[0],0,bb[1]),p(bb[0],-.24,bb[1]),p(aa[0],-.24,aa[1])],trim)
        for x in [-w/2,0,w/2]:transformed_box(mesh,p(x,-.10,0),t,n,(.06,.12,wh),frame)
        for z in [-wh/2,wh*.14,wh/2]:transformed_box(mesh,p(0,-.10,z),t,n,(w,.12,.07),frame)
        transformed_box(mesh,p(0,.10,-wh/2-.08),t,n,(w+.28,.38,.13),trim)
        if arches:
            spring=wh*.21;rx=w/2;rz=wh*.28
            # Fill the upper corners around each curved opening; arch voussoirs.
            for k in range(16):
                aa=k*math.pi/16;bb=(k+1)*math.pi/16
                coords=[(-rx*math.cos(aa),spring+rz*math.sin(aa)),(-rx*math.cos(bb),spring+rz*math.sin(bb))]
                mesh.face([p(coords[0][0],.01,coords[0][1]),p(coords[1][0],.01,coords[1][1]),p(coords[1][0],.01,wh/2+.03),p(coords[0][0],.01,wh/2+.03)],wall)
                mesh.rod(p(coords[0][0],.13,coords[0][1]),p(coords[1][0],.13,coords[1][1]),.10,trim,8)
        if balcony:
            transformed_box(mesh,p(0,.63,-wh/2),t,n,(w+.65,1.2,.20),trim)
            for k in range(max(3,round((w+.6)/.25))):
                x=-(w+.5)/2+k*.25
                mesh.rod(p(x,1.08,-wh/2+.12),p(x,1.08,-wh/2+1),.023,frame,6)
            mesh.rod(p(-(w+.5)/2,1.08,-wh/2+1),p((w+.5)/2,1.08,-wh/2+1),.034,frame,8)

def hipped_roof(mesh,points,z,height,mat,trim,inset=.74):
    cx=sum(x for x,y in points)/len(points);cy=sum(y for x,y in points)/len(points)
    top=[(cx+(x-cx)*inset,cy+(y-cy)*inset,z+height) for x,y in points]
    bottom=[(x,y,z) for x,y in points]
    for i in range(len(points)):
        j=(i+1)%len(points);mesh.face([bottom[i],bottom[j],top[j],top[i]],mat)
        mesh.rod(top[i],top[j],.08,trim,8)
    mesh.face(top,mat)
    return top

def curtain(mesh,points,height,levels,glass,metal,spandrel,profile=None,zbase=0,pitch=1.6):
    """Curtain panels with real ledges and segmented mullions, arbitrary plan/crown."""
    p=resample_polygon(polygon_ccw(points),pitch);count=len(p);floor=height/levels
    def pos(i,f):
        x,y=p[i%count];s=profile(f) if profile else 1
        return Vector((x*s,y*s,zbase+height*f))
    for k in range(levels):
        f0=k/levels;f1=(k+1)/levels
        for j in range(count):
            a,b,c,d=pos(j,f0),pos(j+1,f0),pos(j+1,f1),pos(j,f1)
            n=(b-a).cross(UP).normalized();g=glass[(j*7+k*3)%len(glass)]
            # Whole independent window, separate opaque spandrel and light shelf.
            lower=a.lerp(d,.11);lowerb=b.lerp(c,.11)
            mesh.face([a,b,lowerb,lower],spandrel)
            mesh.face([lower+n*.015,lowerb+n*.015,c+n*.015,d+n*.015],g)
            mesh.rod(a+n*.035,d+n*.035,.043,metal,6)
            # Repeated perforated light shelf silhouette, thin outward projection.
            mesh.face([a-n*.02,b-n*.02,b+n*.28,a+n*.28],metal)
            mesh.face([a+n*.28,b+n*.28,b+n*.28+UP*.075,a+n*.28+UP*.075],metal)
    mesh.face([tuple(pos(i,1)) for i in range(count)],spandrel)
    return count*levels

def ring_rail(mesh,points,z,iron):
    for a,b in zip(points,points[1:]+points[:1]):
        length=math.dist(a,b);n=max(1,round(length/.5))
        for j in range(n):
            p=(a[0]+(b[0]-a[0])*j/n,a[1]+(b[1]-a[1])*j/n,z)
            mesh.rod(p,(p[0],p[1],z+1.03),.024,iron,6)
        mesh.rod((*a,z+1.05),(*b,z+1.05),.034,iron,6)


def air_conditioner(mesh,center,t,n,case,metal):
    """Small exterior condenser, with separate casing, fan and mounting rails."""
    c=Vector(center);t=Vector(t);n=Vector(n)
    transformed_box(mesh,c,t,n,(.85,.43,.59),case)
    for x in [-.30,.30]:
        mesh.rod(c+t*x-n*.26-UP*.39,c+t*x+n*.28-UP*.39,.027,metal,6)
    cc=c+n*.224+t*.12
    for k in range(24):
        a=k*math.tau/24;b=(k+1)*math.tau/24
        mesh.rod(cc+t*(.21*math.cos(a))+UP*(.21*math.sin(a)),cc+t*(.21*math.cos(b))+UP*(.21*math.sin(b)),.014,metal,6)
    for j in [-2,-1,0,1,2]:
        zz=j*.07;half=math.sqrt(max(0,.21**2-zz**2))
        mesh.rod(cc-t*half+UP*zz,cc+t*half+UP*zz,.010,metal,6)


def brick_courses(mesh,a,b,z0,z1,bays,pitch_z,wall,trim,opening_fraction=.50,opening_height=.64):
    """Mortar courses stop at every recessed opening; no lines cross window glass."""
    av=Vector((*a,0));bv=Vector((*b,0));t=(bv-av).normalized();n=Vector((t.y,-t.x,0));length=(bv-av).length;bay=length/bays;h=z1-z0
    low=z0+h*(.52-opening_height/2);high=z0+h*(.52+opening_height/2)
    for row in range(max(1,math.ceil(h/pitch_z))):
        z=z0+(row+.5)*pitch_z
        if z>z1:continue
        for j in range(bays):
            spans=[(j*bay,(j+1)*bay)] if not low<z<high else [(j*bay,(j+.5-opening_fraction/2)*bay),((j+.5+opening_fraction/2)*bay,(j+1)*bay)]
            for l,r in spans:
                if r-l>.035:transformed_box(mesh,av+t*((l+r)/2)+n*.013+UP*z,t,n,(r-l,.016,.015),trim)
            # Short staggered vertical joints remain on solid masonry piers.
            for k in range(math.floor(bay/.47)):
                x=j*bay+(k+.5*(row%2))*.47
                if x>length:continue
                if low<z<high and abs(x-(j+.5)*bay)<bay*opening_fraction/2:continue
                transformed_box(mesh,av+t*x+n*.014+UP*(z+pitch_z/2),t,n,(.013,.016,pitch_z-.014),trim)
