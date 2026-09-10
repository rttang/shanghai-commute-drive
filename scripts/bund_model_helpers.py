"""Batched architectural detail geometry; dimensions in metres, facade +Y."""
import bpy, math
from mathutils import Vector


def material(name, color, roughness=.75, metallic=0):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Roughness'].default_value=roughness
    p.inputs['Metallic'].default_value=metallic
    return m

class Mesh:
    def __init__(self,parent): self.parent=parent; self.groups={}
    def face(self,vertices,mat,uv=None,smooth=False):
        vs,fs,uvs=self.groups.setdefault((mat,smooth),([],[],[])); start=len(vs)
        vs.extend(tuple(v) for v in vertices);fs.append(tuple(range(start,start+len(vertices))));uvs.append(uv)
    def box(self,center,size,mat):
        x,y,z=center;a,b,c=(d/2 for d in size)
        vs=[(x+i,y+j,z+k) for i,j,k in [(-a,-b,-c),(a,-b,-c),(a,b,-c),(-a,b,-c),(-a,-b,c),(a,-b,c),(a,b,c),(-a,b,c)]]
        for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]: self.face([vs[i] for i in f],mat)
    def rod(self,a,b,r,mat,n=12,r2=None):
        a,b=Vector(a),Vector(b);q=(b-a).to_track_quat('Z','Y');vs=[]
        for c,rad in [(a,r),(b,r if r2 is None else r2)]:
            vs.extend(tuple(c+q@Vector((rad*math.cos(i*math.tau/n),rad*math.sin(i*math.tau/n),0))) for i in range(n))
        for i in range(n):self.face([vs[i],vs[(i+1)%n],vs[(i+1)%n+n],vs[i+n]],mat,smooth=True)
        self.face(vs[:n][::-1],mat);self.face(vs[n:],mat)
    def lathe(self,center,rings,mat,n=64,flutes=0):
        cx,cy=center
        for (z0,r0),(z1,r1) in zip(rings,rings[1:]):
            for i in range(n):
                a=i*math.tau/n;b=(i+1)*math.tau/n
                def pt(z,r,t):
                    rr=r*(1+.038*math.cos(flutes*t)) if flutes else r
                    return (cx+rr*math.cos(t),cy+rr*math.sin(t),z)
                self.face([pt(z0,r0,a),pt(z0,r0,b),pt(z1,r1,b),pt(z1,r1,a)],mat,smooth=True)
    def bevel_box(self,center,size,mat,r=.025):
        # Eight-sided solid extrusion: real bevels retain highlight at a close camera.
        x,y,z=center;w,d,h=size;r=min(r,w/4,h/4)
        outline=[(-w/2+r,-h/2),(w/2-r,-h/2),(w/2,-h/2+r),(w/2,h/2-r),(w/2-r,h/2),(-w/2+r,h/2),(-w/2,h/2-r),(-w/2,-h/2+r)]
        rear=[(x+a,y-d/2,z+b) for a,b in outline];front=[(x+a,y+d/2,z+b) for a,b in outline]
        self.face(rear[::-1],mat);self.face(front,mat)
        for i in range(8):j=(i+1)%8;self.face([rear[i],rear[j],front[j],front[i]],mat)
    def arch(self,cx,y,z,width,rise,thickness,depth,mat,segments=24):
        # Elliptical archivolt with separate voussoirs and expressed joints.
        rx=width/2;rz=rise
        for i in range(segments):
            a=math.pi*i/segments+.006;b=math.pi*(i+1)/segments-.006
            outline=[(cx+rx*math.cos(a),z+rz*math.sin(a)),(cx+rx*math.cos(b),z+rz*math.sin(b)),(cx+(rx+thickness)*math.cos(b),z+(rz+thickness)*math.sin(b)),(cx+(rx+thickness)*math.cos(a),z+(rz+thickness)*math.sin(a))]
            vs=[[(x,yy,zz) for x,zz in outline] for yy in [y-depth/2,y+depth/2]]
            self.face(vs[0][::-1],mat);self.face(vs[1],mat)
            for j in range(4):k=(j+1)%4;self.face([vs[0][j],vs[0][k],vs[1][k],vs[1][j]],mat)
    def flush(self):
        out=[]
        for (mat,smooth),(vs,fs,uvs) in self.groups.items():
            data=bpy.data.meshes.new(self.parent.name+'-detail-'+mat.name);data.from_pydata(vs,[],fs);data.update();data.materials.append(mat)
            layer=data.uv_layers.new()
            for p,coords in zip(data.polygons,uvs):
                p.use_smooth=smooth
                for k,li in enumerate(p.loop_indices):
                    co=data.vertices[data.loops[li].vertex_index].co
                    layer.data[li].uv=coords[k] if coords else (co.x/3,co.z/3)
            obj=bpy.data.objects.new(data.name,data);bpy.context.collection.objects.link(obj);obj.parent=self.parent;out.append(obj)
        self.groups.clear();return out


def rectified_front(mesh, spec, av, bv, facade_mat, trim, bronze):
    """Photographic pixels on the actual wall, jambs and recessed openings.

    Coordinates use the PNG (u right, v down); the visible silhouette defines
    metre scale. A denotes photo-left along a CCW footprint edge. The return
    contains explicitly geometric depth, not a floating facade photograph.
    """
    f=spec['rectifiedFacade'];profile=f['profile'];windows=f.get('windows',[])
    av,bv=Vector(av),Vector(bv);length=(bv-av).length;t=(bv-av).normalized();n=Vector((t.y,-t.x,0));up=Vector((0,0,1))
    left,right=profile[0][0],profile[-1][0];topv=min(v for u,v in profile);bottom=f.get('groundV',.98)
    scale=spec['height']/(bottom-topv)
    def point(u,v,depth=0):return tuple(av+t*((u-left)/(right-left)*length)+n*depth+up*((bottom-v)*scale))
    def top(u):
        for (a,b),(c,d) in zip(profile,profile[1:]):
            if a<=u<=c and c>a:return b+(d-b)*(u-a)/(c-a)
        return bottom
    def dep(u,v):
        value=0
        for a,b,c,d,offset in f.get('pilasters',[]):
            if a<u<b and c<v<d:value=offset
        for index,(a,b,c,d) in enumerate(windows):
            cutoff=c
            if index in f.get('archedWindows',[]):
                rx=max(-1,min(1,(u-(a+b)/2)/((b-a)/2)))
                cutoff=c+(d-c)*.24*(1-math.sqrt(max(0,1-rx*rx)))
            if a<u<b and cutoff<v<d:value-=f.get('windowDepth',.28)
        for c,d,offset in f.get('bands',[]):
            if c<v<d:value=max(value,offset)
        return value
    us={left,right,*[u for u,v in profile]};vs={bottom,*[v for u,v in profile]}
    us.update(left+(right-left)*i/36 for i in range(37));vs.update(topv+(bottom-topv)*i/40 for i in range(41))
    for a,b,c,d in windows:us.update([a,b]);vs.update([c,d])
    for i in f.get('archedWindows',[]):
        if i>=len(windows):continue
        a,b,c,d=windows[i]
        us.update(a+(b-a)*k/12 for k in range(13));vs.update(c+(d-c)*.24*k/6 for k in range(7))
    for a,b,c,d,_ in f.get('pilasters',[]):us.update([a,b]);vs.update([c,d])
    for c,d,_ in f.get('bands',[]):vs.update([c,d])
    us=sorted(us);vs=sorted(vs)
    def face(coords,depths):mesh.face([point(u,v,z) for (u,v),z in zip(coords,depths)],facade_mat,[(u,1-v) for u,v in coords])
    for a,b in zip(us,us[1:]):
        for c,d in zip(vs,vs[1:]):
            ta,tb=top(a+1e-8),top(b-1e-8)
            if d<=min(ta,tb):continue
            va,vb=max(c,ta),max(c,tb)
            if va>=d or vb>=d:continue
            depth=dep((a+b)/2,(va+vb+2*d)/4)
            face([(a,d),(b,d),(b,vb),(a,va)],[depth]*4)
            for p,q,nu,nv in [((a,d),(b,d),(a+b)/2,d+1e-6),((b,d),(b,vb),b+1e-6,(d+vb)/2),((b,vb),(a,va),(a+b)/2,c-1e-6),((a,va),(a,d),a-1e-6,(va+d)/2)]:
                nd=dep(nu,nv)
                if depth>nd+1e-5:face([p,q,q,p],[depth,depth,nd,nd])
    # Solid roof/parapet returns follow each unique photo silhouette.
    for a,b in zip(profile,profile[1:]):
        depth=f.get('upperVolumeDepth',4)
        if f.get('upperNarrowV') is not None and min(a[1],b[1])<f['upperNarrowV']:
            depth=f.get('upperNarrowDepth',.04)
        mesh.face([point(*a,0),point(*b,0),point(*b,-depth),point(*a,-depth)],trim)
        body=f.get('bodyTopV',topv)
        if max(a[1],b[1])>body:
            # The footprint roof behind a photograph-cropped end must meet a
            # closed return, never expose an unlit hole above the facade edge.
            mesh.face([point(a[0],body,-.015),point(b[0],body,-.015),point(b[0],max(b[1],body),-.015),point(a[0],max(a[1],body),-.015)],trim)
        if min(a[1],b[1])<body:
            mesh.face([point(a[0],body,-depth),point(b[0],body,-depth),point(b[0],min(b[1],body),-depth),point(a[0],min(a[1],body),-depth)],trim)
    for u in [left,right]:
        # Close the junction to the full footprint roof even when the source
        # image crops the last roof corner lower than the central cornice.
        endtop=min(top(u),f.get('bodyTopV',topv))
        mesh.face([point(u,bottom,0),point(u,endtop,0),point(u,endtop,-4),point(u,bottom,-4)],trim)
    for index,(a,b,c,d) in enumerate(windows):
        ww=(b-a)/(right-left)*length;hh=(d-c)*scale
        local_depth=dep((a+b)/2,(c+d)/2)+f.get('windowDepth',.28)
        if index in f.get('archedWindows',[]):
            spring=c+(d-c)*.24
            outline=[(a,d),(a,spring)]+[((a+b)/2-(b-a)/2*math.cos(math.pi*k/24),spring-(d-c)*.24*math.sin(math.pi*k/24)) for k in range(25)]+[(b,d),(a,d)]
        else:outline=[(a,c),(b,c),(b,d),(a,d),(a,c)]
        for (u0,v0),(u1,v1) in zip(outline,outline[1:]):mesh.rod(point(u0,v0,local_depth+.025),point(u1,v1,local_depth+.025),min(.045,ww*.035),trim,8)
        mesh.rod(point((a+b)/2,c,local_depth-.16),point((a+b)/2,d,local_depth-.16),min(.024,ww*.025),bronze,8)
        if hh>1.5:mesh.rod(point(a,c+(d-c)*.40,local_depth-.16),point(b,c+(d-c)*.40,local_depth-.16),min(.024,ww*.025),bronze,8)
        mesh.rod(point(a-.002,d+.003,local_depth+.08),point(b+.002,d+.003,local_depth+.08),.065,trim,8)
    for u,c,d,rfrac in f.get('columns',[]):
        p=Vector(point(u,0,.10));r=rfrac/(right-left)*length;z0=(bottom-d)*scale;z1=(bottom-c)*scale
        mesh.lathe((p.x,p.y),[(z0-.10,r*1.28),(z0+.05,r*1.28),(z0+.23,r),(z0+(z1-z0)*.35,r*1.01),(z1-.18,r*.91),(z1-.08,r*1.27),(z1+.11,r*1.27)],trim,64,flutes=20)
        # Two carved volutes at the visible capital, following the local facade.
        for sign in [-1,1]:
            centre=Vector((p.x,p.y,z1-.01))+t*(sign*r*1.01)+n*r*.91
            for k in range(24):
                theta=k*math.tau*1.3/24;theta2=(k+1)*math.tau*1.3/24
                radius=r*.35*(1-k/30);radius2=r*.35*(1-(k+1)/30)
                mesh.rod(centre+t*(math.cos(theta)*radius)+up*(math.sin(theta)*radius),centre+t*(math.cos(theta2)*radius2)+up*(math.sin(theta2)*radius2),max(.018,r*.055),trim,8)
    for a,b,c,d in f.get('railings',[]):
        span=(b-a)/(right-left)*length;count=max(2,round(span/.26))
        for k in range(count+1):
            u=a+(b-a)*k/count;mesh.rod(point(u,c,.28),point(u,d,.28),.025,bronze,8)
        for v in [c,d]:mesh.rod(point(a,v,.28),point(b,v,.28),.035,bronze,8)
    for a,b,c,d,depth in f.get('canopies',[]):
        coords=[(a,c),(b,c),(b,d),(a,d)]
        mesh.face([point(a,c,0),point(b,c,0),point(b,d,depth),point(a,d,depth)],facade_mat,[(u,1-v) for u,v in coords])
        mesh.face([point(a,d,depth),point(b,d,depth),point(b,d+.008,depth),point(a,d+.008,depth)],trim)
    for u,halfwidth,basev,topv in f.get('domes',[]):
        # Shallow elliptical copper/lead crown reconstructed from its observed
        # width and rise; a complete curved solid, with separate raised ribs.
        rx=halfwidth/(right-left)*length;ry=rx*.72;rise=(basev-topv)*scale
        centre=Vector(point(u,basev,-ry*.85));metal=material('bund-observed-dark-dome',(.10,.12,.13),.58,.48)
        def dome(theta,phi):return centre+t*(rx*math.cos(theta)*math.cos(phi))+n*(ry*math.sin(theta)*math.cos(phi))+up*(rise*math.sin(phi))
        for j in range(12):
            p0=j*math.pi/24;p1=(j+1)*math.pi/24
            for k in range(64):
                t0=k*math.tau/64;t1=(k+1)*math.tau/64
                mesh.face([dome(t0,p0),dome(t1,p0),dome(t1,p1),dome(t0,p1)],metal,smooth=True)
        for k in range(16):
            th=k*math.tau/16
            for j in range(12):mesh.rod(dome(th,j*math.pi/24),dome(th,(j+1)*math.pi/24),.028,trim,8)
        peak=centre+up*rise
        mesh.lathe((peak.x,peak.y),[(peak.z,.10),(peak.z+.12,.16),(peak.z+.25,.12),(peak.z+.39,0)],metal,32)
    return dict(windowCount=len(windows),photoGroundV=bottom,photoTopV=topv,frontWidth=length,facadeHeight=spec['height'])


def observed_elevation(mesh, a, b, height, elevation, wall, trim, glass, metal):
    """Geometry-only elevation from individually inspected photograph observations.

    Openings are explicit normalized rectangles [u0,u1,z0,z1,kind]. 'arch' and
    'pointed' carve their actual silhouette; photographs are never embedded.
    """
    a=Vector((*a,0));b=Vector((*b,0));t=(b-a).normalized();n=Vector((t.y,-t.x,0));length=(b-a).length;up=Vector((0,0,1))
    def p(u,z,d=0):return a+t*(u*length)+up*z+n*(d+elevation.get('curveDepth',0)*math.sin(math.pi*u))
    def quad(u0,u1,z0,z1,d,mat):mesh.face([p(u0,z0,d),p(u1,z0,d),p(u1,z1,d),p(u0,z1,d)],mat)
    def bar(u0,u1,z,d,w,mat=trim):mesh.rod(p(u0,z,d),p(u1,z,d),w,mat,8)
    openings=elevation.get('openings',[]);us=sorted({0,1,*[u for w in openings for u in w[:2]]});zs=sorted({0,height,*[z for w in openings for z in w[2:4]]})
    for u0,u1 in zip(us,us[1:]):
        for z0,z1 in zip(zs,zs[1:]):
            if z0>=height or z1<=elevation.get('bottom',0):continue
            z0=max(z0,elevation.get('bottom',0))
            if any(w[0]<(u0+u1)/2<w[1] and w[2]<(z0+z1)/2<w[3] for w in openings):continue
            quad(u0,u1,z0,min(z1,height),0,wall)
    accent=material('bund-observed-grey-blue-spandrels',(.31,.38,.39),.55)
    for aa,bb,za,zb in elevation.get('spandrels',[]):
        for c0,c1 in zip(zs,zs[1:]):
            if c0<za or c1>zb:continue
            if any(w[0]<(aa+bb)/2<w[1] and w[2]<(c0+c1)/2<w[3] for w in openings):continue
            quad(aa,bb,c0,c1,.012,accent)
    depth=elevation.get('recess',.28)
    for index,w in enumerate(openings):
        depth=elevation.get('arcadeDepth',1.8) if index in elevation.get('arcades',[]) else elevation.get('recess',.28)
        u0,u1,z0,z1=w[:4];kind=w[4] if len(w)>4 else 'rect';ww=(u1-u0)*length;hh=z1-z0
        if kind in ['arch','pointed']:
            rise=min(hh*.30,ww*.50) if kind=='arch' else min(hh*.40,ww*.78);spring=z1-rise
            curve=[]
            for j in range(25):
                f=j/24;u=u0+(u1-u0)*f
                zz=spring+rise*(math.sqrt(max(0,1-(2*f-1)**2)) if kind=='arch' else (1-abs(2*f-1))**.70)
                curve.append((u,zz))
            outline=[(u0,z0),(u1,z0)]+curve[::-1]
            for (ua,za),(ub,zb) in zip(curve,curve[1:]):mesh.face([p(ua,za),p(ub,zb),p(ub,z1),p(ua,z1)],wall)
        else:outline=[(u0,z0),(u1,z0),(u1,z1),(u0,z1)]
        if index in elevation.get('arcades',[]):
            mesh.face([p(u,z,-depth) for u,z in outline],wall)
            mid=z0+(z1-z0)*.52
            if not elevation.get('arcadeMezzanine',True):
                quad(u0+.02,u1-.02,z0+.10,z1-.35,-depth+.014,glass)
            else:quad(u0+.012,u1-.012,z0+.08,mid-.35,-depth+.014,glass)
            for q in ([.24,.58] if elevation.get('arcadeMezzanine',True) else []):quad(u0+(u1-u0)*q,u0+(u1-u0)*(q+.19),mid+.38,z1-.60,-depth+.014,glass)
            if elevation.get('arcadeMezzanine',True):
                mesh.face([p(u0,mid,-depth),p(u1,mid,-depth),p(u1,mid,-depth+.8),p(u0,mid,-depth+.8)],trim)
                bar(u0,u1,mid,-depth+.8,.14)
        else:mesh.face([p(u,z,-depth) for u,z in outline],glass)
        for (ua,za),(ub,zb) in zip(outline,outline[1:]+outline[:1]):
            mesh.face([p(ua,za),p(ub,zb),p(ub,zb,-depth),p(ua,za,-depth)],trim)
            mesh.rod(p(ua,za,.025),p(ub,zb,.025),.065 if height<45 else .075,trim,8)
        divisions=1 if index in elevation.get('arcades',[]) else elevation.get('mullions',2)
        for j in range(1,divisions):mesh.rod(p(u0+(u1-u0)*j/divisions,z0,-depth+.025),p(u0+(u1-u0)*j/divisions,z1-(rise if kind in ['arch','pointed'] else 0),-depth+.025),.035,metal,8)
        for j in ([] if index in elevation.get('arcades',[]) else range(1,max(2,int(hh/elevation.get('horizontalSpacing',.7))))):bar(u0,u1,z0+hh*j/max(2,int(hh/elevation.get('horizontalSpacing',.7))),-depth+.035,.024,metal)
        bar(u0-.004,u1+.004,z0-.10,.12,.105)
        if index in elevation.get('balconies',[]):
            projection=elevation.get('balconyProjection',.85)
            mesh.face([p(u0-.01,z0-.08,0),p(u1+.01,z0-.08,0),p(u1+.01,z0-.08,projection),p(u0-.01,z0-.08,projection)],trim)
            for j in range(max(3,int(ww/.25))):
                u=u0+(u1-u0)*j/max(2,int(ww/.25)-1);mesh.rod(p(u,z0,projection-.04),p(u,z0+.88,projection-.04),.024,metal,8)
            bar(u0,u1,z0+.9,projection-.04,.04,metal)
            for left in [u0,u1]:mesh.rod(p(left,z0+.9,projection-.04),p(left,z0+.9,0),.03,metal,8)
    for row in elevation.get('bands',[]):
        z,projection,thickness=row;quad(0,1,z-thickness/2,z+thickness/2,projection,trim)
        mesh.face([p(0,z+thickness/2,0),p(1,z+thickness/2,0),p(1,z+thickness/2,projection),p(0,z+thickness/2,projection)],trim)
        bar(0,1,z-thickness/2,projection,.045)
    for u,z0,z1,width,projection in elevation.get('piers',[]):
        quad(u-width/2/length,u+width/2/length,z0,z1,projection,trim)
        for sign in [-1,1]:mesh.face([p(u+sign*width/2/length,z0),p(u+sign*width/2/length,z0,projection),p(u+sign*width/2/length,z1,projection),p(u+sign*width/2/length,z1)],trim)
    for u,width,zh in elevation.get('portals',[]):
        u0=u-width/2;u1=u+width/2
        quad(u0,u1,.05,zh,-.12,metal)
        for side in [u0,u1]:mesh.rod(p(side,0,.16),p(side,zh,.16),.14,trim,8)
        bar(u0-.01,u1+.01,zh,.20,.18);bar(u0-.02,u1+.02,zh+.34,.15,.11)
    for u,z0,z1,r in elevation.get('columns',[]):
        c=p(u,0,.42);mesh.lathe((c.x,c.y),[(z0,r*1.35),(z0+.20,r*1.35),(z0+.4,r),(z1-.40,r*.89),(z1-.18,r*1.18),(z1,r*1.38)],trim,40)
        for j in range(12):
            th=j*math.tau/12;mesh.rod((c.x+math.cos(th)*r,c.y+math.sin(th)*r,z1-.32),(c.x+math.cos(th)*r*1.3,c.y+math.sin(th)*r*1.3,z1-.04),.045,trim,8)
    for u0,u1,z0,peak in elevation.get('gables',[]):
        c=(u0+u1)/2
        upper=[w for w in elevation.get('upperOpenings',[]) if u0<=w[0]<w[1]<=u1]
        ux=sorted({u0,c,u1,*[v for w in upper for v in w[:2]]});zz=sorted({z0,peak,*[v for w in upper for v in w[2:4]]})
        def gtop(u):return z0+(peak-z0)*(1-abs(u-c)/max(.001,(u1-u0)/2))
        for ua,ub in zip(ux,ux[1:]):
            for za,zb in zip(zz,zz[1:]):
                if za>=min(gtop(ua),gtop(ub)) and za>=gtop((ua+ub)/2):continue
                if any(w[0]<(ua+ub)/2<w[1] and w[2]<(za+zb)/2<w[3] for w in upper):continue
                aa=min(zb,gtop(ua));bb=min(zb,gtop(ub))
                mesh.face([p(ua,min(za,aa)),p(ub,min(za,bb)),p(ub,bb),p(ua,aa)],wall)
        for aa,bb,za,zb,*kind in upper:
            rise=(zb-za)*.32;outline=[(aa,za),(bb,za),(bb,zb-rise),((aa+bb)/2,zb),(aa,zb-rise)]
            mesh.face([p(u,z,-.20) for u,z in outline],glass)
            for (ua,zz0),(ub,zz1) in zip(outline,outline[1:]+outline[:1]):
                mesh.face([p(ua,zz0),p(ub,zz1),p(ub,zz1,-.22),p(ua,zz0,-.22)],trim)
                mesh.rod(p(ua,zz0,.03),p(ub,zz1,.03),.05,trim,8)
            for coords in [[(aa,zb-rise),((aa+bb)/2,zb),(aa,zb)],[(bb,zb-rise),(bb,zb),((aa+bb)/2,zb)]]:mesh.face([p(u,z) for u,z in coords],wall)
            mesh.rod(p((aa+bb)/2,za,-.18),p((aa+bb)/2,zb,-.18),.025,metal,8)
        for d in [0,-2.5]:
            mesh.rod(p(u0,z0,d),p(c,peak,d),.12,trim,8);mesh.rod(p(c,peak,d),p(u1,z0,d),.12,trim,8)
        mesh.face([p(u0,z0),p(c,peak),p(c,peak,-2.5),p(u0,z0,-2.5)],trim)
        mesh.face([p(c,peak),p(u1,z0),p(u1,z0,-2.5),p(c,peak,-2.5)],trim)
        mesh.rod(p(c,peak),p(c,peak+.55),.055,trim,12)
    for u,z0,z1,r in elevation.get('pinnacles',[]):
        c=p(u,z0,.15);mesh.lathe((c.x,c.y),[(z0,r),(z1-.8,r),(z1-.7,r*1.25),(z1,.025)],trim,24)
    for z in elevation.get('rustication',[]):bar(0,1,z,.01,.012,metal)
    if elevation.get('dentils'):
        z=elevation['dentils'];count=max(3,int(length/.42))
        for j in range(count):
            c=p((j+.5)/count,z,.18);mesh.box(c,(.15,.26,.18),trim)
    return len(openings)


def build_observed_building(root,spec):
    """An explicit per-building photo record chooses its elevations and roof."""
    m=Mesh(root);h=spec['height'];cfg=spec['observedModel'];pts=spec['localFootprint']
    wall=material('bund-observed-'+spec['id']+'-wall',spec['colors']['wall']);trim=material('bund-observed-'+spec['id']+'-trim',spec['colors']['trim']);metal=material('bund-observed-bronze',(.075,.063,.048),.35,.55);glass=material('bund-observed-blue-grey-glass',(.11,.19,.23),.23,.28);roof=material('bund-observed-slate',(.12,.135,.14),.8)
    nwin=0
    if cfg.get('shaftScale'):
        cx0=(min(p[0] for p in pts)+max(p[0] for p in pts))/2;cy0=(min(p[1] for p in pts)+max(p[1] for p in pts))/2;scale=cfg['shaftScale'];podium=cfg.get('podiumHeight',6.5)
        for a,b in zip(pts,pts[1:]+pts[:1]):m.face([(*a,0),(*b,0),(*b,podium),(*a,podium)],wall)
        m.face([(*p,podium) for p in pts],roof)
        pts=[(cx0+(p[0]-cx0)*scale,cy0+(p[1]-cy0)*scale) for p in pts]
    for i,(a,b) in enumerate(zip(pts,pts[1:]+pts[:1])):
        e=cfg['elevations'].get(str(i))
        if e is None:
            # No source photograph covers this elevation. Preserve massing only,
            # rather than copying the main elevation's bays onto an unseen side.
            m.face([(*a,0),(*b,0),(*b,h),(*a,h)],wall)
        else:
            if cfg.get('shaftScale'):e=dict(e,bottom=cfg.get('podiumHeight',6.5))
            nwin+=observed_elevation(m,a,b,h,e,wall,trim,glass,metal)
    m.face([(*p,h) for p in pts],roof)
    for a,b in zip(pts,pts[1:]+pts[:1]):m.rod((*a,h+.08),(*b,h+.08),.13,trim,8)
    roofcfg=cfg.get('roof',{});typ=roofcfg.get('type');minx=min(p[0] for p in pts);maxx=max(p[0] for p in pts);miny=min(p[1] for p in pts);maxy=max(p[1] for p in pts);cx=(minx+maxx)/2;cy=(miny+maxy)/2;w=maxx-minx;d=maxy-miny
    if typ=='balustraded-terrace':
        for a,b in zip(pts,pts[1:]+pts[:1]):
            le=math.dist(a,b);t=Vector((b[0]-a[0],b[1]-a[1],0)).normalized();count=max(2,int(le/.80))
            for j in range(count):
                p=Vector((*a,h))+t*((j+.5)*le/count)
                m.lathe((p.x,p.y),[(h+.10,.09),(h+.24,.13),(h+.40,.095),(h+.7,.07),(h+.95,.095),(h+1.05,.09)],trim,12)
            for z in [h+.10,h+1.12]:m.rod((*a,z),(*b,z),.12,trim,8)
    if typ=='platform-rail':
        for a,b in zip(pts,pts[1:]+pts[:1]):
            le=math.dist(a,b);t=Vector((b[0]-a[0],b[1]-a[1],0)).normalized()
            for j in range(max(2,int(le/1.4))):
                p=Vector((*a,h))+t*(j*1.4);m.rod(p,p+Vector((0,0,1.05)),.04,metal,8)
            for z in [h+.3,h+.65,h+1.05]:m.rod((*a,z),(*b,z),.04,metal,8)
    if typ=='open-ring':
        r=min(w,d)/2*.90;z1=h+roofcfg.get('height',3.2)
        for j in range(64):
            aa=j*math.tau/64;bb=(j+1)*math.tau/64
            def pt(a,z,r):return (cx+math.cos(a)*r,cy+math.sin(a)*r,z)
            m.face([pt(aa,h,r),pt(bb,h,r),pt(bb,z1,r),pt(aa,z1,r)],wall)
            m.face([pt(aa,h,r-.35),pt(aa,z1,r-.35),pt(bb,z1,r-.35),pt(bb,h,r-.35)],trim)
            m.face([pt(aa,z1,r),pt(bb,z1,r),pt(bb,z1,r-.35),pt(aa,z1,r-.35)],trim)
            if j%4==0:m.rod(pt(aa,h,r+.025),pt(aa,z1,r+.025),.035,metal,8)
    if typ=='kaishi-turret':
        aa,bb=[Vector((*v,h)) for v in spec['frontEdge']];center=(aa+bb)/2;cxx,cyy=center.x,center.y;r=3.2
        ring=[(cxx+r*math.cos(j*math.tau/8),cyy+r*math.sin(j*math.tau/8)) for j in range(8)]
        for a,b in zip(ring,ring[1:]+ring[:1]):
            e={'bottom':h,'openings':[[.27,.73,h+1.0,h+4.1,'rect']],'bands':[[h+.4,.2,.3],[h+4.6,.32,.36]],'mullions':2}
            observed_elevation(m,a,b,h+4.9,e,wall,trim,glass,metal)
        dome=material('bund-kaishi-patinated-brass-dome',(.42,.37,.20),.48,.45)
        m.lathe((cxx,cyy),[(h+4.9,r*1.1),(h+5.3,r*1.07),(h+5.9,r*.91),(h+6.8,r*.62),(h+7.3,.25)],dome,64)
        m.rod((cxx,cyy,h+7.2),(cxx,cyy,h+8.8),.07,metal,12)
    if typ=='pitched':
        edge=spec['frontEdge'];a=Vector((*edge[0],h));b=Vector((*edge[1],h));t=(b-a).normalized();n=Vector((-t.y,t.x,0));deep=roofcfg.get('depth',min(w,d)*.7);rise=roofcfg.get('rise',3)
        r0=a+n*deep/2+Vector((0,0,rise));r1=b+n*deep/2+Vector((0,0,rise));back0=a+n*deep;back1=b+n*deep
        for face in [[a,b,r1,r0],[r0,r1,back1,back0],[a,r0,back0],[b,back1,r1]]:m.face(face,roof)
        count=max(8,int((b-a).length/.6))
        for j in range(count+1):
            q=t*((b-a).length*j/count);m.rod(a+q,r0+q,.015,metal,6);m.rod(r0+q,back0+q,.015,metal,6)
    if typ=='icbc-crown':
        zh=roofcfg.get('height',29);radius=min(w,d)*.53
        for j,scale in enumerate([1,.81,.63,.46,.30]):
            z=h+j*zh*.165;hh=zh*.20;r=radius*scale;rt=r*.69
            # Octagonal tapered glass tier, not a stack of rectangular boxes.
            for k in range(8):
                a=k*math.tau/8+math.pi/8;b=(k+1)*math.tau/8+math.pi/8
                v0=Vector((cx+r*math.cos(a),cy+r*math.sin(a),z));v1=Vector((cx+r*math.cos(b),cy+r*math.sin(b),z));v2=Vector((cx+rt*math.cos(b),cy+rt*math.sin(b),z+hh));v3=Vector((cx+rt*math.cos(a),cy+rt*math.sin(a),z+hh))
                m.face([v0,v1,v2,v3],glass)
                for aa,bb in [(v0,v1),(v0,v3),(v1,v2)]:m.rod(aa,bb,.075,trim,8)
                # Repeating scalloped ribs conform to the inclined roof surface.
                count=3 if j<2 else 2
                for q in range(count):
                    prev=None
                    for f in range(25):
                        t0=(q+f/24)/count;rise=math.sin(math.pi*f/24)*.65+.10
                        low=v0.lerp(v1,t0);high=v3.lerp(v2,t0);vv=low.lerp(high,rise)
                        if prev is not None:m.rod(prev,vv,.09,trim,8)
                        prev=vv
                for f in range(1,5):m.rod(v0.lerp(v3,f/5),v1.lerp(v2,f/5),.026,metal,8)
        m.rod((cx,cy,h+zh*.86),(cx,cy,h+zh+10),.075,metal,16)
    if typ=='orient-lantern':
        scale=.92;top=h+roofcfg.get('height',6)
        pp=[(cx+(x-cx)*scale,cy+(y-cy)*scale) for x,y in pts]
        for a,b in zip(pp,pp[1:]+pp[:1]):
            leng=math.dist(a,b)
            if leng<4:continue
            count=max(1,round(leng/3));e={'bottom':h,'openings':[[ (j+.15)/count,(j+.85)/count,h+.7,top-.8,'pointed'] for j in range(count)],'mullions':2}
            observed_elevation(m,a,b,top,e,wall,trim,glass,metal)
        m.face([(*p,top) for p in pp],roof)
        for a,b in zip(pp,pp[1:]+pp[:1]):m.rod((*a,top+.2),(*b,top+.2),.65,trim,8)
    if typ=='pediment':
        edge=spec['frontEdge'];a=Vector((*edge[0],h));b=Vector((*edge[1],h));t=(b-a).normalized();n=Vector((t.y,-t.x,0));c=(a+b)/2
        rise=roofcfg.get('rise',1.6);width=roofcfg.get('width',4.6)
        outline=[tuple(c-Vector((0,0,.03)))];prev=None
        for j in range(33):
            theta=math.pi*j/32;v=c+t*(width/2*math.cos(theta))+Vector((0,0,rise*math.sin(theta)))
            if prev:m.rod(prev,v,.13,trim,8)
            outline.append(tuple(v));prev=v
        m.face(outline,trim)
        m.rod(c,c+Vector((0,0,rise+4)),.04,metal,8)
    for block in cfg.get('upperBlocks',[]):
        aa,bb=[Vector((*v,0)) for v in spec['frontEdge']];tt=(bb-aa).normalized();nn=Vector((-tt.y,tt.x,0));le=(bb-aa).length
        p0=aa+tt*(block['u0']*le)+nn*block['inset'];p1=aa+tt*(block['u1']*le)+nn*block['inset'];pp=[p0,p1,p1+nn*block['depth'],p0+nn*block['depth']];top=block['top'];base=block['base'];count=block['columns'];rows=block['rows']
        for a,b in zip(pp,pp[1:]+pp[:1]):
            e={'bottom':base,'openings':[],'bands':[[top-.2,.22,.22]],'mullions':1}
            if count:
                for k in range(rows):
                    pitch=(top-base)/rows
                    for j in range(count):e['openings'].append([(j+.26)/count,(j+.74)/count,base+k*pitch+.55,base+(k+1)*pitch-.55,'rect'])
            observed_elevation(m,a[:2],b[:2],top,e,wall,trim,glass,metal)
        m.face([(p.x,p.y,top) for p in pp],roof)
    m.flush();root['photoObservedOpeningCount']=nwin;root['sourcePhotographsEmbedded']=False;root['observedModel']=cfg['identity'];root['inferredDetails']=spec['inferredDetails']
    return dict(id=spec['id'],name=spec['name'],ways=spec['ways'],center=spec['center'],heading=0,height=h,referenceIds=spec['referenceIds'],photoVerified=spec['photoVerified'],detailDescription=spec['observedDetails'],inferredDetails=spec['inferredDetails'],heightSource=spec['heightSource'],photoObservedOpenings=nwin,referenceOnlyTextures=True,routeDistance=spec.get('routeDistance'),frontageClassification=spec.get('frontageClassification'),buildingGroup=spec.get('buildingGroup'),photoVerificationScope=spec.get('photoVerificationScope','Building identity and listed visible exterior features only; unobserved elevations remain inferred'),geometryConfidence=spec.get('geometryConfidence','Source-observed feature layout, estimated metric geometry'))
