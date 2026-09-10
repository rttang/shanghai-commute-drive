"""Select connected OSM corridors. Simplify geometry; keep source way IDs."""
import pathlib,json,math,heapq
ROOT=pathlib.Path(__file__).resolve().parents[1]
ways=json.loads((ROOT/'references/shanghai-roads.osm.json').read_text())['elements']
def dist(a,b):return math.hypot((a[0]-b[0])*95000,(a[1]-b[1])*111320)
def route(names,start,end):
    graph={};pts={};ids=[]
    for w in ways:
        if w['tags']['name'] not in names:continue
        ids.append(w['id'])
        for n,p in zip(w['nodes'],w['geometry']):pts[n]=(p['lon'],p['lat']);graph.setdefault(n,{})
        for a,b in zip(w['nodes'],w['nodes'][1:]):graph[a][b]=graph[b][a]=dist(pts[a],pts[b])
    seen=set();components=[]
    for n in graph:
        if n in seen:continue
        todo=[n];comp=[];seen.add(n)
        while todo:
            a=todo.pop();comp.append(a)
            for b in graph[a]:
                if b not in seen:seen.add(b);todo.append(b)
        if len(comp)>4:components.append(comp)
    comp=min(components,key=lambda c:min(dist(pts[n],start) for n in c)+min(dist(pts[n],end) for n in c))
    a=min(comp,key=lambda n:dist(pts[n],start));b=min(comp,key=lambda n:dist(pts[n],end))
    queue=[(0,a)];cost={a:0};prev={}
    while queue:
        d,n=heapq.heappop(queue)
        if n==b:break
        if d>cost[n]:continue
        for nxt,w in graph[n].items():
            if d+w<cost.get(nxt,float('inf')):cost[nxt]=d+w;prev[nxt]=n;heapq.heappush(queue,(d+w,nxt))
    chain=[b]
    while chain[-1]!=a:chain.append(prev[chain[-1]])
    chain.reverse();coords=[pts[n] for n in chain]
    selected=[coords[0]]
    for p in coords[1:-1]:
        if dist(selected[-1],p)>12:selected.append(p)
    selected.append(coords[-1])
    used=[w['id'] for w in ways if w['id'] in ids and any(n in set(chain) for n in w['nodes'])]
    return {'coordinates':[[round(x,7),round(y,7)] for x,y in selected],'sourceWays':used,'sourceLength':round(cost[b])}
spec=[
 ('jingan',['南京西路'],(121.4445,31.223),(121.4637,31.232)),
 ('yanan',['延安高架路'],(121.4455,31.222),(121.4777,31.229)),
 ('northsouth',['南北高架路'],(121.4737,31.213),(121.469,31.247)),
 ('bund',['中山东一路'],(121.4874,31.2353),(121.486,31.2445)),
 ('tunnel',['延安东路隧道'],(121.480,31.2338),(121.4965,31.2398)),
 ('lujiazui',['陆家嘴环路'],(121.496,31.2393),(121.5048,31.2373))]
data={}
for id,n,a,b in spec:
    data[id]=route(n,a,b)
    assert data[id]['sourceLength']>250,(id,data[id])
    print(id,len(data[id]['coordinates']),data[id]['sourceLength'])
(ROOT/'src/data/routes.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
base=[{'name':w['tags']['name'],'points':[[round(p['lon'],5),round(p['lat'],5)] for p in w['geometry'][::max(1,len(w['geometry'])//18)]]} for w in ways]
(ROOT/'src/data/map.json').write_text(json.dumps(base,ensure_ascii=False,separators=(',',':')))
