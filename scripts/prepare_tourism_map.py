"""Prepare the saved WGS84 OSM extracts for two directed, metre-scale tours."""
import json, math, heapq, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
elements=json.loads((ROOT/'references/tourism/city.osm.json').read_text())['elements']
relations=ROOT/'references/tourism/building-relations.osm.json'
if relations.exists():
    for e in json.loads(relations.read_text())['elements']:
        for i,m in enumerate(e.get('members',[])):
            if m.get('role')=='outer' and len(m.get('geometry',[]))>3:
                elements.append({'type':'way','id':-e['id']*10-i,'tags':e.get('tags',{}),'geometry':m['geometry']})
origin=[121.494,31.239]
def xy(p):return [round((p['lon']-origin[0])*math.cos(math.radians(origin[1]))*111320,2),round(-(p['lat']-origin[1])*111320,2)]
def distance(a,b):return math.hypot(a[0]-b[0],a[1]-b[1])
def num(s,fallback):
    try:return float(str(s).split(';')[0].split(' ')[0])
    except (ValueError,TypeError):return fallback
ways=[e for e in elements if e['type']=='way' and len(e.get('geometry',[]))>1]
roads=[];buildings=[];water=[]
for w in ways:
    t=w.get('tags',{});pts=[xy(p) for p in w['geometry'] if p]
    if len(pts)<2:continue
    if 'highway' in t:
        kind=t['highway'];foot=kind in ['footway','pedestrian','path','steps','cycleway']
        roads.append({'id':w['id'],'name':t.get('name',''),'kind':kind,'points':pts,'width':num(t.get('width'),2.4 if foot else num(t.get('lanes'),2)*3.2),'foot':foot,'bridge':t.get('bridge')=='yes','tunnel':t.get('tunnel')=='yes' or '地道' in t.get('name','')})
    elif 'building' in t:
        height=num(t.get('height'),num(t.get('building:levels'),5)*3.4)
        buildings.append({'id':w['id'],'name':t.get('name',''),'points':pts,'height':round(max(3,height),1),'heightSource':'height' if 'height' in t else 'levels' if 'building:levels' in t else 'estimated','kind':t.get('building')})
    elif t.get('natural')=='water' and pts[0]==pts[-1]:water.append({'id':w['id'],'points':pts})
for e in elements:
    if e['type']=='relation' and e.get('tags',{}).get('natural')=='water':
        for m in e.get('members',[]):
            p=[xy(x) for x in m.get('geometry',[]) if x]
            if m.get('role')=='outer' and len(p)>3:water.append({'id':m.get('ref'),'points':p})
def tour(names,anchors):
    graph={};coords={};edgeway={}
    for w in ways:
        t=w.get('tags',{})
        if t.get('highway') not in ['primary','secondary','tertiary','residential','unclassified','primary_link','secondary_link','tertiary_link'] or t.get('tunnel')=='yes' or t.get('access')=='private':continue
        center=sum(p['lon'] for p in w['geometry'] if p)/sum(bool(p) for p in w['geometry'])
        if (anchors[0][0]<121.49)!=(center<121.491):continue
        for n,p in zip(w.get('nodes',[]),w['geometry']):
            if p:coords[n]=xy(p);graph.setdefault(n,{})
        for a,b in zip(w['nodes'],w['nodes'][1:]):
            if a not in coords or b not in coords:continue
            length=distance(coords[a],coords[b])
            if t.get('oneway')!='-1':graph[a][b]=length;edgeway[a,b]=w['id']
            if t.get('oneway') not in ['yes','1','true']:graph[b][a]=length;edgeway[b,a]=w['id']
    def path(a,b):
        queue=[(0,a)];cost={a:0};prev={}
        while queue:
            d,n=heapq.heappop(queue)
            if n==b:
                chain=[b]
                while chain[-1]!=a:chain.append(prev[chain[-1]])
                return chain[::-1]
            if d!=cost.get(n):continue
            for nxt,weight in graph[n].items():
                if d+weight<cost.get(nxt,float('inf')):
                    cost[nxt]=d+weight;prev[nxt]=n;heapq.heappush(queue,(d+weight,nxt))
        raise RuntimeError(f'No directed driving path: {a} -> {b}')
    points=[xy({'lon':p[0],'lat':p[1]}) for p in anchors]
    preferred={n for w in ways if w.get('tags',{}).get('name') in names for n in w.get('nodes',[]) if n in coords}
    nodes=[min(preferred,key=lambda n:distance(coords[n],p)) for p in points]
    chain=[]
    for a,b in zip(nodes,nodes[1:]):chain.extend(path(a,b)[:-1])
    chain.append(nodes[-1]);length=sum(distance(coords[a],coords[b]) for a,b in zip(chain,chain[1:]))
    simplified=[coords[chain[0]]]
    for n in chain[1:-1]:
        if distance(simplified[-1],coords[n])>2:simplified.append(coords[n])
    simplified.append(coords[chain[-1]])
    return {'points':simplified,'length':round(length),'sourceWays':list(dict.fromkeys(edgeway[a,b] for a,b in zip(chain,chain[1:]))),'directed':True}
routes=[
 {'id':'bund','name':'浦西滨江线','subtitle':'从外白渡桥，到十六铺','description':'沿苏州河口驶向外滩。铜绿屋顶、钟楼和石砌柱廊在右侧展开，左侧是黄浦江与浦东天际线。','focus':'历史建筑 · 浦江风光','speed':32,**tour(['外白渡桥','中山东一路','中山东二路'],[[121.4856,31.2457],[121.4877,31.2336],[121.4913,31.2291]])},
 {'id':'pudong','name':'浦东天际线','subtitle':'环行陆家嘴，抵达滨江','description':'沿环路走近东方明珠与三座摩天大楼，再向江边驶去。从街道仰望城市，也从高处回望外滩。','focus':'现代天际线 · 滨江街道','speed':35,**tour(['陆家嘴环路','陆家嘴西路','陆家嘴东路','世纪大道','世纪大道辅路','银城中路','富城路','花园石桥路'],[[121.4953,31.2431],[121.5033,31.2403],[121.5031,31.2354],[121.4981,31.2338],[121.4938,31.2393]])}
]
parks=[];parks_file=ROOT/'references/tourism/parks.osm.json'
if parks_file.exists():
    for e in json.loads(parks_file.read_text())['elements']:
        points=[xy(p) for p in e.get('geometry',[]) if p]
        if len(points)>3 and points[0]==points[-1]:parks.append({'id':e['id'],'name':e.get('tags',{}).get('name',''),'points':points})
data={'parks':parks,'origin':origin,'projection':'local equirectangular WGS84 metres','attribution':'© OpenStreetMap contributors','buildings':buildings,'roads':roads,'water':water,'routes':routes}
dest=ROOT/'public/tour-city.json';temp=dest.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')));temp.replace(dest)
print(json.dumps({'parks':len(parks),'buildings':len(buildings),'roads':len(roads),'routes':[(r['id'],r['length']) for r in routes]},ensure_ascii=False))
