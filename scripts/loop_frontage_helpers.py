"""Exterior reconstruction helpers for the additional Puxi loop frontage.

Positions are metres in local Blender X east / Y north / Z up.  These helpers
never add a facade merely because an OSM polygon exists: the calling building
specification must supply observed elevations.  Unmatched footprints have a
separate, explicitly provisional builder.
"""
import bpy, math, pathlib, struct
from mathutils import Matrix, Vector
from bund_model_helpers import Mesh, material
from north_bund_helpers import polygon_ccw, transformed_box, band

UP = Vector((0, 0, 1))


def frame(a, b):
    a, b = Vector((*a[:2], 0)), Vector((*b[:2], 0))
    tangent = (b-a).normalized()
    return a, b, tangent, Vector((tangent.y, -tangent.x, 0)), (b-a).length


def wall_openings(m, a, b, bottom, top, openings, wall, trim, glazing, metal,
                  depth=.24, sill=True, crossbar=.1):
    """Solid wall cells surround separate recessed windows; no image planes.

    openings contain normalised horizontal centre, width in metres, bottom
    and top in metres. Irregular photo-counted bay positions are preserved.
    """
    av, bv, t, n, length = frame(a, b)
    def p(x, z, d=0): return av + t*x + n*d + UP*z
    cuts = {0., length}
    levels = {bottom, top}
    boxes = []
    for f, w, z0, z1 in openings:
        x0, x1 = max(.05, length*f-w/2), min(length-.05, length*f+w/2)
        z0, z1 = max(bottom+.03, z0), min(top-.03, z1)
        if x1 <= x0 or z1 <= z0: continue
        cuts.update([x0, x1]); levels.update([z0, z1]); boxes.append((x0,x1,z0,z1))
    xs, zs = sorted(cuts), sorted(levels)
    for x0,x1 in zip(xs,xs[1:]):
        for z0,z1 in zip(zs,zs[1:]):
            x,z=(x0+x1)/2,(z0+z1)/2
            if any(l<x<r and lo<z<hi for l,r,lo,hi in boxes): continue
            m.face([p(x0,z0),p(x1,z0),p(x1,z1),p(x0,z1)],wall)
    for index,(x0,x1,z0,z1) in enumerate(boxes):
        for aa,bb in [((x0,z0),(x1,z0)),((x1,z0),(x1,z1)),((x1,z1),(x0,z1)),((x0,z1),(x0,z0))]:
            m.face([p(*aa),p(*bb),p(*bb,-depth),p(*aa,-depth)],trim)
        g=glazing[index%len(glazing)] if isinstance(glazing,list) else glazing
        m.face([p(x0,z0,-depth),p(x1,z0,-depth),p(x1,z1,-depth),p(x0,z1,-depth)],g)
        for x in [x0,(x0+x1)/2,x1]:
            transformed_box(m,p(x,(z0+z1)/2,-depth*.45),t,n,(.055,.10,z1-z0),metal)
        for z in [z0,z1]+([z0+(z1-z0)*crossbar] if crossbar else []):
            transformed_box(m,p((x0+x1)/2,z,-depth*.45),t,n,(x1-x0,.10,.055),metal)
        if sill: transformed_box(m,p((x0+x1)/2,z0-.065,.10),t,n,(x1-x0+.18,.35,.12),trim)
    return len(boxes)


def shell(m, poly, bottom, top, wall, roof):
    for a,b in zip(poly,poly[1:]+poly[:1]):
        m.face([(*a,bottom),(*b,bottom),(*b,top),(*a,top)],wall)
    m.face([(*p,top) for p in poly],roof)
    m.face([(*p,bottom) for p in reversed(poly)],wall)


def inset(poly, x, y=None):
    """Photo-proportional rectangular setbacks about the polygon centroid."""
    cx=sum(p[0] for p in poly)/len(poly); cy=sum(p[1] for p in poly)/len(poly)
    y=x if y is None else y
    return [(cx+(px-cx)*x,cy+(py-cy)*y) for px,py in poly]


def roof_tiles(m, a, b, inward, base, rise, depth, tile, pitch=.34, curved=True):
    """A curved Chinese eave made of a roof sheet and actual tile ribs."""
    av,bv,t,n,length=frame(a,b);n=-n if inward else n
    def pos(u,f):return av+t*u+n*(depth*f)+UP*(base+(rise*f*f+.28*(abs(2*u/length-1)**6)*(1-f) if curved else rise*f))
    segments=max(3,min(16,math.ceil(depth/.55)))
    for k in range(segments):
        f0,f1=k/segments,(k+1)/segments
        m.face([pos(0,f0),pos(length,f0),pos(length,f1),pos(0,f1)],tile)
    for j in range(max(2,round(length/pitch))+1):
        u=min(length,j*pitch)
        for k in range(segments):m.rod(pos(u,k/segments),pos(u,(k+1)/segments),.034,tile,6)
    for f in [0,1]:m.rod(pos(0,f),pos(length,f),.07,tile,8)


def roof_plant(m, centre, width, depth, base, metal, dark, count=2):
    """Visible exterior condenser housings, grilles and actual fan rings."""
    x,y=centre
    m.box((x,y,base+.55),(width,depth,1.1),metal)
    for i in range(count):
        xx=x-width/2+(i+.5)*width/count; r=min(depth*.34,width/count*.32)
        m.lathe((xx,y),[(base+1.11,r),(base+1.17,r)],dark,24)
        for j in range(4):
            th=j*math.tau/4
            m.rod((xx-r*math.cos(th),y-r*math.sin(th),base+1.19),
                  (xx+r*math.cos(th),y+r*math.sin(th),base+1.19),.025,metal,6)
    for i in range(10):m.box((x,y-depth/2-.015,base+.10+i*.095),(width-.16,.05,.025),dark)


def cornice(m, poly, height, trim):
    for dz,thick,proj in [(-.42,.12,.15),(-.21,.15,.28),(0,.22,.50),(.19,.13,.33)]:
        band(m,poly,height+dz,thick,proj,trim)


def front_edge(poly, target):
    tx,ty=target
    return min(enumerate(zip(poly,poly[1:]+poly[:1])),
               key=lambda item: math.dist(((item[1][0][0]+item[1][1][0])/2,
                                          (item[1][0][1]+item[1][1][1])/2),(tx,ty)))[0]


def lettering(parent, body, origin, tangent, normal, size, mat):
    """Short observed building identity in actual extruded mesh geometry."""
    curve=bpy.data.curves.new(parent.name+'-observed-sign','FONT')
    curve.body=body;curve.size=size;curve.align_x='CENTER';curve.align_y='CENTER'
    curve.extrude=.025;curve.bevel_depth=.007;curve.bevel_resolution=1;curve.resolution_u=3
    font_path='/System/Library/Fonts/Supplemental/Songti.ttc'
    if any(ch in body for ch in '業錢滬'):
        # Blender's TTC loader selects face0 (Songti SC Black), whose cmap
        # lacks these traditional plaque characters. Extract the installed
        # Songti SC Regular face6 for local mesh authoring only. No font or
        # reference photograph is copied to the public runtime directory.
        target=pathlib.Path(__file__).resolve().parents[1]/'assets/streets/loop-frontages/reference/fonts/SongtiSC-Regular-modeling.ttf'
        if not target.exists():
            raw=pathlib.Path(font_path).read_bytes();count=struct.unpack_from('>I',raw,8)[0]
            assert count>6,'Installed Songti collection changed; verify face identity before rebuilding'
            offset=struct.unpack_from('>I',raw,12+6*4)[0];num=struct.unpack_from('>H',raw,offset+4)[0];tables=[]
            for j in range(num):
                tag,checksum,pos,length=struct.unpack_from('>4sIII',raw,offset+12+j*16)
                if tag==b'DSIG':continue
                payload=bytearray(raw[pos:pos+length])
                if tag==b'head':payload[8:12]=b'\0'*4
                tables.append((tag,payload))
            tables.sort();num=len(tables);entry=int(math.log2(num));header=struct.pack('>4sHHHH',raw[offset:offset+4],num,16*(2**entry),entry,num*16-16*(2**entry));directory=bytearray();data=bytearray();position=12+16*num;head_offset=None
            def checksum(value):
                value=bytes(value)+b'\0'*((-len(value))%4)
                return sum(struct.unpack('>'+str(len(value)//4)+'I',value))&0xffffffff
            for tag,payload in tables:
                directory.extend(struct.pack('>4sIII',tag,checksum(payload),position,len(payload)))
                if tag==b'head':head_offset=position
                data.extend(payload);data.extend(b'\0'*((-len(payload))%4));position=12+16*num+len(data)
            result=bytearray(header)+directory+data;assert head_offset is not None
            struct.pack_into('>I',result,head_offset+8,(0xB1B0AFBA-checksum(result))&0xffffffff)
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(result)
        font_path=str(target)
    try:curve.font=bpy.data.fonts.load(font_path,check_existing=True)
    except RuntimeError:pass
    curve.materials.append(mat)
    obj=bpy.data.objects.new(curve.name,curve);bpy.context.collection.objects.link(obj)
    t,n=Vector(tangent),Vector(normal)
    # A manually supplied tangent/normal may form a reflected basis. Euler
    # decomposition cannot preserve that reflection and shows mirrored signs.
    # Keep the specified outward normal and choose its right-handed baseline.
    if t.cross(UP).dot(n)<0:t=-t
    obj.rotation_euler=Matrix((t,UP,n)).transposed().to_euler()
    obj.location=origin;obj.parent=parent
    bpy.context.view_layer.update()
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh=bpy.data.meshes.new_from_object(evaluated,preserve_all_data_layers=True,depsgraph=bpy.context.evaluated_depsgraph_get())
    result=bpy.data.objects.new(obj.name+'-mesh',mesh);bpy.context.collection.objects.link(result)
    result.parent=parent;result.matrix_local=obj.matrix_local.copy()
    bpy.data.objects.remove(obj,do_unlink=True);bpy.data.curves.remove(curve)
    return result
