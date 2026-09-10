"""Build a closed, directed OSM driving loop; preserve the old sightseeing paths.

Uses node-via no/only turn restrictions. Unresolved via-way restrictions fail
when they touch the route, rather than silently claiming full validation.
Tunnel height is a continuous game profile, not a surveyed elevation.
"""
import json, math, heapq, pathlib, hashlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
city_file = ROOT / 'public/tour-city.json'
city = json.loads(city_file.read_text())
raw = json.loads((ROOT / 'references/tourism/loop.osm.json').read_text())
elements = raw['elements']
origin = city['origin']
def xy(p):
    return [round((p['lon']-origin[0])*math.cos(math.radians(origin[1]))*111320, 3), round(-(p['lat']-origin[1])*111320, 3)]
def length(a, b): return math.dist(a, b)
def num(v, fallback):
    try: return float(str(v).split(';')[0].split(' ')[0])
    except (TypeError, ValueError): return fallback

allowed = {'primary','secondary','tertiary','residential','unclassified','trunk','primary_link','secondary_link','tertiary_link','trunk_link','living_street'}
ways = {e['id']: e for e in elements if e['type']=='way' and 'highway' in e.get('tags', {})}
coords, graph, restrictions, unresolved, via_rules = {}, {}, {}, [], []
for w in ways.values():
    t = w['tags']
    if t['highway'] not in allowed or any(t.get(k) in ('no','private') for k in ('access','vehicle','motor_vehicle','motorcar')): continue
    for n,p in zip(w.get('nodes', []), w.get('geometry', [])):
        if p: coords[n] = xy(p)
    for a,b in zip(w['nodes'], w['nodes'][1:]):
        if a not in coords or b not in coords: continue
        d = length(coords[a], coords[b])
        oneway = t.get('oneway', 'yes' if t.get('junction')=='roundabout' else 'no')
        if oneway != '-1': graph.setdefault(a, []).append((b, d, w['id']))
        if oneway not in ('yes','1','true'): graph.setdefault(b, []).append((a, d, w['id']))
for e in elements:
    if e['type'] != 'relation' or e.get('tags', {}).get('type') != 'restriction': continue
    t = e['tags']; rule = t.get('restriction:motorcar', t.get('restriction', ''))
    members = e.get('members', [])
    source = next((m['ref'] for m in members if m['role']=='from'), None)
    dest = next((m['ref'] for m in members if m['role']=='to'), None)
    via = next((m for m in members if m['role']=='via'), None)
    if 'motorcar' in t.get('except', '').split(';'): continue
    if via and via['type']=='node': restrictions.setdefault((via['ref'],source), []).append((dest,rule))
    elif via:
        vias = [m['ref'] for m in members if m['role']=='via' and m['type']=='way']
        if source and dest: via_rules.append((tuple([source]+vias),dest,rule,e['id']))
        else: unresolved.append({'id':e['id'],'from':source,'to':dest,'via':vias})

def nearest(names, point):
    candidates = {n for w in ways.values() if w['tags'].get('name') in names for n in w['nodes'] if n in graph}
    if not candidates: raise ValueError(f'No mapped anchor: {names}')
    return min(candidates, key=lambda n:length(coords[n],point))

def path(start, target, incoming=0, previous=0, history=()):
    initial = (start,incoming,previous,history)
    queue = [(0, initial)]; costs = {initial:0}; prev = {}
    while queue:
        cost,state = heapq.heappop(queue)
        if cost != costs[state]: continue
        node,way,last,history = state
        if node == target:
            states = [state]
            while states[-1] != initial: states.append(prev[states[-1]])
            return states[::-1]
        for dest,dist,source in graph.get(node, []):
            if dest == last: continue
            blocked = False
            for to,rule in restrictions.get((node,way), []):
                if rule.startswith('no_') and source == to: blocked = True
                if rule.startswith('only_') and source != to: blocked = True
            if source != way:
                for prefix,to,rule,_ in via_rules:
                    if history[-len(prefix):] == prefix:
                        if rule.startswith('no_') and source==to: blocked=True
                        if rule.startswith('only_') and source!=to: blocked=True
            if blocked: continue
            next_history = history if source==way else (*history,source)[-4:]
            nxt = (dest,source,node,next_history)
            newcost = cost + dist
            if newcost < costs.get(nxt,float('inf')):
                costs[nxt] = newcost;prev[nxt] = state;heapq.heappush(queue,(newcost,nxt))
    raise ValueError(f'No directed legal path: {start} -> {target}')

anchors = [
    ('外白渡桥', ['外白渡桥'], [-772,-755]),
    ('十六铺', ['中山东二路'], [-286,821]),
    ('人民路隧道浦东出口', ['人民路隧道'], [885,748]),
    ('陆家嘴三高', ['陆家嘴环路'], [1060,485]),
    ('东方明珠', ['陆家嘴环路'], [270,-390]),
    ('北外滩', ['东大名路'], [200,-1100]),
    ('大名路', ['大名路'], [-640,-955]),
    ('外白渡桥', ['外白渡桥'], [-772,-755]),
]
nodes = [nearest(names,p) for _,names,p in anchors]
states = [(nodes[0],0,0,())]; legs=[]
for i,(a,b) in enumerate(zip(nodes,nodes[1:])):
    chain = path(a,b,states[-1][1],states[-1][2],states[-1][3]);states.extend(chain[1:])
    legs.append({'from':anchors[i][0],'to':anchors[i+1][0], 'metres':round(sum(length(coords[s[0]],coords[t[0]]) for s,t in zip(chain,chain[1:])),1), 'roads':list(dict.fromkeys(ways[s[1]]['tags'].get('name','未命名连接道路') for s in chain[1:]))})
assert states[0][0] == states[-1][0]
sourceways = [s[1] for s in states[1:]]
assert not any(any(w in sourceways for w in x['via']) for x in unresolved), 'Route touches an incomplete turn restriction'
first_way = sourceways[0];last_way = sourceways[-1]
for to,rule in restrictions.get((nodes[0], last_way), []):
    assert not (rule.startswith('no_') and to==first_way or rule.startswith('only_') and to!=first_way), 'Closure turn restriction'
points = [coords[s[0]] for s in states]
distances = [0]
for a,b in zip(points,points[1:]): distances.append(distances[-1]+length(a,b))
# Densify to <= 5 m so grades, collision walls and road meshes share samples.
dense=[]; edges=[]; heights=[]
for i,(a,b) in enumerate(zip(points,points[1:])):
    count=max(1,math.ceil(length(a,b)/5))
    for j in range(count):
        f=j/count;dense.append([round(a[0]+(b[0]-a[0])*f,3),round(a[1]+(b[1]-a[1])*f,3)]);edges.append(sourceways[i])
dense.append(dense[0]);edges.append(edges[0])
ds=[0]
for a,b in zip(dense,dense[1:]):ds.append(ds[-1]+length(a,b))
tunnels=[ways[w]['tags'].get('tunnel') in ('yes','building_passage') or ways[w]['tags'].get('name') in ('人民路隧道','新建路隧道') or '地道' in ways[w]['tags'].get('name','') for w in edges]
heights=[0.0]*len(dense);runs=[];i=0
while i<len(dense)-1:
    if not tunnels[i]:i+=1;continue
    start=i
    while i<len(dense)-1 and tunnels[i]:i+=1
    end=i;span=ds[end]-ds[start];depth=min(18,span*.025)
    ramp=min(350,span/2)
    ease=min(50,ramp/5)
    for j in range(start,end+1):
        x=min(ramp,ds[j]-ds[start],ds[end]-ds[j])
        integral=x*x/(2*ease) if x<ease else x-ease/2 if x<ramp-ease else ramp-ease-(ramp-x)**2/(2*ease)
        heights[j]=round(-depth*integral/(ramp-ease),4)
    runs.append({'start':round(ds[start],2),'end':round(ds[end],2),'depth':depth,'name':ways[edges[start]]['tags'].get('name','隧道')})
legacy=city.get('legacyRoutes', city['routes'])
route={'id':'shanghai-loop','name':'一江两岸 · 上海环游','subtitle':'外滩 · 陆家嘴 · 北外滩','description':'穿过浦江隧道，从百年外滩驶向摩天楼群，沿北外滩回望两岸。发现地标，停好车，留下自己的上海相册。','focus':'城市环游 · 地标收集','speed':35,'closed':True,'points':dense,'elevations':heights,'segmentWays':edges,'length':round(ds[-1],3),'sourceWays':list(dict.fromkeys(sourceways)),'directed':True,'tunnels':runs,'elevationSource':'continuous game grade, not surveyed'}
known={r['id']:r for r in city['roads']}
for wid,w in ways.items():
    t=w['tags'];pts=[xy(p) for p in w.get('geometry',[]) if p]
    if len(pts)<2:continue
    foot=t['highway'] in ('footway','pedestrian','path','steps','cycleway')
    known[wid]={'id':wid,'name':t.get('name',''),'kind':t['highway'],'points':pts,'width':num(t.get('width'),2.4 if foot else num(t.get('lanes'),2)*3.2),'foot':foot,'bridge':t.get('bridge')=='yes','tunnel':t.get('tunnel')=='yes' or '地道' in t.get('name',''),'layer':num(t.get('layer'),0),'oneway':t.get('oneway','no')}
buildings={b['id']:b for b in city['buildings']}
for w in elements:
    t=w.get('tags',{})
    if w['type']!='way' or 'building' not in t or w['id'] in buildings:continue
    pts=[xy(p) for p in w.get('geometry',[]) if p]
    if len(pts)<4:continue
    buildings[w['id']]={'id':w['id'],'name':t.get('name',''),'points':pts,'height':max(3,num(t.get('height'),num(t.get('building:levels'),5)*3.4)),'heightSource':'height' if 'height' in t else 'levels' if 'building:levels' in t else 'estimated','kind':t['building']}
city.update(routes=[route],legacyRoutes=legacy,roads=list(known.values()),buildings=list(buildings.values()))
temp=city_file.with_suffix('.tmp');temp.write_text(json.dumps(city,ensure_ascii=False,separators=(',',':')));temp.replace(city_file)
audit={'closed':True,'metres':ds[-1],'points':len(dense),'ways':len(route['sourceWays']),'legs':legs,'tunnels':runs,'nodeTurnRestrictions':sum(map(len,restrictions.values())),'viaWayRestrictions':len(via_rules),'unresolvedViaWayRestrictionsOutsideRoute':unresolved,'elevationSource':route['elevationSource'],'maximumGrade':max(abs(a-b)/max(.001,d-c) for a,b,c,d in zip(heights,heights[1:],ds,ds[1:])),'mapSha256':hashlib.sha256(city_file.read_bytes()).hexdigest()}
(ROOT/'docs/evidence/tourism/loop-road-network.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
print(json.dumps(audit,ensure_ascii=False,indent=2))
