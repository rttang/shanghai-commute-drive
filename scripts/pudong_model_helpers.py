"""Batched exterior geometry; all lengths in metres, Blender Z up.
No mesh subdivision is used to increase asset size. Repeated surfaces represent
individual facade panels, window reveals, mullions, coping or mechanical louvers.
"""
import bpy, math
from mathutils import Vector


def material(name, color, rough=.65, metal=0):
    m=bpy.data.materials.get('pd-'+name) or bpy.data.materials.new('pd-'+name)
    m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Roughness'].default_value=rough
    p.inputs['Metallic'].default_value=metal
    return m


class Mesh:
    def __init__(self, parent): self.parent=parent; self.groups={}
    def face(self, vertices, mat, smooth=False, uv=None):
        vs,fs,uvs=self.groups.setdefault((mat,smooth),([],[],[]))
        n=len(vs); vs.extend(vertices); fs.append(tuple(range(n,n+len(vertices))));uvs.append(uv)
    def box(self,p,s,mat,angle=0):
        x,y,z=p; a,b,c=[v/2 for v in s]; co,si=math.cos(angle),math.sin(angle)
        v=[(x+i*co-j*si,y+i*si+j*co,z+k) for i,j,k in [(-a,-b,-c),(a,-b,-c),(a,b,-c),(-a,b,-c),(-a,-b,c),(a,-b,c),(a,b,c),(-a,b,c)]]
        for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:self.face([v[i] for i in f],mat)
    def rod(self,a,b,r,mat,n=8,r2=None):
        a,b=Vector(a),Vector(b)
        if (b-a).length<1e-6:return
        q=(b-a).to_track_quat('Z','Y');v=[]
        for p,rad in [(a,r),(b,r if r2 is None else r2)]:
            v.extend(tuple(p+q@Vector((rad*math.cos(i*math.tau/n),rad*math.sin(i*math.tau/n),0))) for i in range(n))
        for i in range(n):self.face([v[i],v[(i+1)%n],v[(i+1)%n+n],v[i+n]],mat,True)
        self.face(v[:n][::-1],mat);self.face(v[n:],mat)
    def edge_box(self,a,b,z,height,depth,mat,offset=0):
        dx,dy=b[0]-a[0],b[1]-a[1];l=math.hypot(dx,dy)
        if l<.01:return
        self.box(((a[0]+b[0])/2+dy/l*offset,(a[1]+b[1])/2-dx/l*offset,z+height/2),(l,depth,height),mat,math.atan2(dy,dx))
    def edge_panel(self,a,b,z,height,mat,offset=0):
        dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        if length<.01:return
        ox,oy=dy/length*offset,-dx/length*offset
        self.face([(a[0]+ox,a[1]+oy,z),(b[0]+ox,b[1]+oy,z),(b[0]+ox,b[1]+oy,z+height),(a[0]+ox,a[1]+oy,z+height)],mat)
    def ring(self,z,r,thickness,mat,n=96,cx=0,cy=0):
        for i in range(n):
            a=math.tau*i/n;b=math.tau*(i+1)/n
            self.rod((cx+r*math.cos(a),cy+r*math.sin(a),z),(cx+r*math.cos(b),cy+r*math.sin(b),z),thickness,mat,6)
    def sphere(self,center,r,mat,n=64,rows=32):
        cx,cy,cz=center
        def p(i,j):
            a=math.tau*i/n;t=-math.pi/2+math.pi*j/rows
            return (cx+r*math.cos(t)*math.cos(a),cy+r*math.cos(t)*math.sin(a),cz+r*math.sin(t))
        for j in range(rows):
            for i in range(n):self.face([p(i,j),p(i+1,j),p(i+1,j+1),p(i,j+1)],mat,True)
    def polygon(self,pts,z,mat):
        # Blender triangulates this simple concave polygon during glTF export.
        self.face([(x,y,z) for x,y in pts],mat)
    def flush(self):
        for (mat,smooth),(vs,fs,uvs) in self.groups.items():
            mesh=bpy.data.meshes.new(self.parent.name+'-'+mat.name)
            mesh.from_pydata(vs,[],fs);mesh.update()
            # Empty or invalid geometries are fatal rather than silently published.
            if mesh.validate(verbose=False): raise ValueError('Invalid exterior geometry: '+mesh.name)
            mesh.materials.append(mat)
            for p in mesh.polygons:p.use_smooth=smooth
            if any(uvs):
                layer=mesh.uv_layers.new()
                for poly,coords in zip(mesh.polygons,uvs):
                    if coords:
                        for li,co in zip(poly.loop_indices,coords):layer.data[li].uv=co
            obj=bpy.data.objects.new(mesh.name,mesh);bpy.context.collection.objects.link(obj);obj.parent=self.parent
        self.groups.clear()


def polygon_ccw(points):
    q=list(points)
    if q and math.dist(q[0],q[-1])<.01:q=q[:-1]
    clean=[]
    for p in q:
        if not clean or math.dist(p,clean[-1])>.08:clean.append(tuple(p))
    if sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(clean,clean[1:]+clean[:1]))<0:clean.reverse()
    return clean


def facade(mesh,pts,height,stone,glass,metal,style='curtain',floor=3.8,seed=0):
    """Build exact mapped footprint with individually recessed window modules.
    Detailing goes inward from the OSM boundary; coping projects only 0.12 m.
    Side/rear window arrangements remain a documented inference.
    """
    pts=polygon_ccw(pts);n=len(pts)
    mesh.polygon(pts,height,stone)
    rows=max(1,round(height/floor));floor=height/rows
    for ei,(a,b) in enumerate(zip(pts,pts[1:]+pts[:1])):
        length=math.dist(a,b)
        if length<.18:continue
        dx,dy=(b[0]-a[0])/length,(b[1]-a[1])/length
        # CCW outward=(dy,-dx); negative offset is inside the building.
        bays=max(1,round(length/(1.5 if style=='curtain' else 3.1)))
        bw=length/bays
        def edge(t):return (a[0]+dx*t,a[1]+dy*t)
        for j in range(rows):
            z=j*floor
            for k in range(bays):
                aa,bb=edge(k*bw),edge((k+1)*bw)
                if style=='curtain':
                    sill=.32 if j else .2;wh=floor-sill
                    gm=glass[(k+ei*3+j//3+seed)%len(glass)]
                    # Opaque pane thickness is 0.035 m and reveals are separate.
                    mesh.edge_panel(aa,bb,z+sill,wh,gm,offset=-.12)
                else:
                    margin=min(.46,bw*.20);sill=.8 if j else .25;wh=max(.8,floor-1.10 if j else floor-.65)
                    gm=glass[(k+ei+j+seed)%len(glass)]
                    mesh.edge_box(aa,bb,z,sill,.36,stone,offset=-.16)
                    mesh.edge_box(aa,bb,z+sill+wh,floor-sill-wh,.36,stone,offset=-.16)
                    mesh.edge_box(aa,edge(k*bw+margin),z+sill,wh,.36,stone,offset=-.16)
                    mesh.edge_box(edge((k+1)*bw-margin),bb,z+sill,wh,.36,stone,offset=-.16)
                    wa,wb=edge(k*bw+margin),edge((k+1)*bw-margin)
                    mesh.edge_panel(wa,wb,z+sill,wh,gm,offset=-.33)
                    mesh.edge_box(wa,wb,z+sill-.075,.075,.42,stone,offset=-.09)
                    mid=edge((k+.5)*bw)
                    mesh.box((mid[0]-dy*.22,mid[1]+dx*.22,z+sill+wh/2),(.055,.13,wh),metal,math.atan2(dy,dx))
                    for t in (k*bw+margin,(k+1)*bw-margin):
                        p=edge(t);mesh.box((p[0]-dy*.24,p[1]+dx*.24,z+sill+wh/2),(.075,.16,wh+.10),metal,math.atan2(dy,dx))
            if style=='curtain':
                # Continuous horizontal spandrels/transoms are emitted once per
                # edge, instead of closed boxes repeated for every glazing bay.
                # The visible profile and each vertical mullion are unchanged.
                sill=.32 if j else .2
                mesh.edge_panel(a,b,z,sill,metal,offset=-.07)
                mesh.edge_box(a,b,z+sill,.055,.19,metal,offset=-.03)
                mesh.edge_box(a,b,z+floor-.055,.055,.19,metal,offset=-.03)
            else:mesh.edge_box(a,b,z+floor-.14,.14,.42,stone,offset=-.08)
        if style=='curtain':
            for k in range(bays+1):
                p=edge(k*bw);mesh.box((p[0]-dy*.02,p[1]+dx*.02,height/2),(.065,.22,height),metal,math.atan2(dy,dx))
        # Roof parapet with two coping lips, physically distinct from facade.
        mesh.edge_box(a,b,height,.65,.28,stone,offset=-.14)
        mesh.edge_box(a,b,height+.65,.09,.44,metal,offset=-.10)
    # Rooftop service equipment is kept inside the footprint; no conjectural signs.


def roof_equipment(mesh,center,height,scale,stone,metal):
    x,y=center;s=max(1.5,min(scale,8))
    mesh.box((x,y,height+1.1),(s*1.6,s,2.2),stone)
    mesh.box((x,y,height+2.26),(s*1.7,s*1.1,.12),metal)
    for side in [-1,1]:
        for k in range(10):mesh.box((x, y+side*s*.502,height+.25+k*.17),(s*1.4,.055,.065),metal)
    for off in [-.34,.34]:
        mesh.rod((x+off*s,y,height+2.3),(x+off*s,y,height+2.8),s*.20,metal,24)
        mesh.ring(height+2.82,s*.19,.035,metal,24,x+off*s,y)
        for a in range(8):
            angle=math.tau*a/8
            mesh.rod((x+off*s,y,height+2.84),(x+off*s+s*.18*math.cos(angle),y+s*.18*math.sin(angle),height+2.84),.025,metal,5)
