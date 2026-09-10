"""Independent loop frontage/photo catalog; never writes the old city or coverage files."""
from pathlib import Path
import argparse, collections, hashlib, importlib.util, json, math

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'assets/streets/loop-reference-catalog'
OUT=ROOT/'references/tourism/loop-frontage-catalog.json'
spec=importlib.util.spec_from_file_location('existing_reference_geometry',ROOT/'scripts/fetch_street_expansion_refs.py')
ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)

def load(path):return json.loads(Path(path).read_text())
def save(path,value):Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2))
def cells(box):
    a,b,c,d=box
    return [(x,z) for x in range(math.floor(a/100),math.floor(c/100)+1) for z in range(math.floor(b/100),math.floor(d/100)+1)]
def bounds(points,pad=0):
    return (min(p[0] for p in points)-pad,min(p[1] for p in points)-pad,max(p[0] for p in points)+pad,max(p[1] for p in points)+pad)

def catalog():
    city=load(ROOT/'public/tour-city.json');route=next(r for r in city['routes'] if r['id']=='shanghai-loop')
    old=load(ROOT/'references/tourism/street-frontage-coverage.json')
    old_first={b['wayId'] for b in old['buildings'] if b['frontage']['classification']=='first-row-sampled'}
    old_near={b['wayId'] for b in old['buildings']};old_photo={w:r for r in load(ROOT/'src/tour/photo-architecture.json') for w in r['ways']}
    photos=load(ROOT/'references/tourism/streets-expansion-photos.json')
    if (ASSETS/'photos.json').exists():photos+=load(ASSETS/'photos.json')
    photo_by_way=collections.defaultdict(list)
    for photo in photos:
        if photo.get('usage')=='exterior-reference':
            for way in photo.get('wayIds',[]):photo_by_way[way].append({'id':photo['id'],'file':photo['file'],'source':photo['source'],'scope':photo.get('photoRole','building exterior; observe limits in photo manifest')})
    index=collections.defaultdict(set);geometry={};road_by_id={r['id']:r for r in city['roads']}
    for b in city['buildings']:
        p=b['points'][:]
        if p[0]==p[-1]:p.pop()
        if len(p)<3:continue
        edges=list(zip(p,p[1:]+p[:1]));geometry[b['id']]={'source':b,'points':p,'edges':edges}
        for cell in cells(bounds(p)):index[cell].add(b['id'])
    def nearby(box):
        ids=set()
        for cell in cells(box):ids.update(index.get(cell,()))
        return ids
    nearest={};visible=collections.defaultdict(list);along=0;surface=0
    for si,(a,b) in enumerate(zip(route['points'],route['points'][1:])):
        length=math.dist(a,b)
        if not length:continue
        mid=along+length/2
        tunnel=next((t for t in route.get('tunnels',[]) if t['start']<=mid<=t['end']),None)
        if tunnel:along+=length;continue
        surface+=length;way=route.get('segmentWays',[None]*len(route['points']))[si]
        ids=nearby(bounds([a,b],100))
        for bid in ids:
            for ei,(c,d) in enumerate(geometry[bid]['edges']):
                hit=ref.segdist(a,b,c,d)
                if hit[0]<=100 and (bid not in nearest or hit[0]<nearest[bid]['distance']):nearest[bid]={'distance':hit[0],'routeDistance':along+hit[3]*length,'edgeIndex':ei,'roadWay':way,'roadName':road_by_id.get(way,{}).get('name','')}
        n=max(1,math.ceil(length/5))
        for i in range(n):
            t=(i+.5)/n;p=(a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1]))
            for side,sign in [('left',-1),('right',1)]:
                q=(p[0]+sign*(b[1]-a[1])/length*100,p[1]-sign*(b[0]-a[0])/length*100);hits=[]
                for bid in ids:
                    for ei,(c,d) in enumerate(geometry[bid]['edges']):
                        h=ref.intersect(p,q,c,d)
                        if h and h[0]>=0:hits.append((h[0],bid,ei))
                if hits:
                    distance,bid,ei=min(hits);visible[bid].append({'routeDistance':along+t*length,'side':side,'setback':distance*100,'edgeIndex':ei,'roadSampleLength':length/n,'roadWay':way})
        along+=length
    rows=[]
    for bid,near in nearest.items():
        g=geometry[bid];b=g['source'];hits=visible[bid]
        ei=max(set(h['edgeIndex'] for h in hits),key=lambda x:sum(h['roadSampleLength'] for h in hits if h['edgeIndex']==x)) if hits else near['edgeIndex']
        edge,chain=ref.frontage_chain(g['edges'],ei);refs=photo_by_way[bid];old_ref=old_photo.get(bid)
        rows.append({'wayId':bid,'name':b['name'] or f'OSM building {bid}','route':'shanghai-loop','nearestRoadWay':near['roadWay'],'nearestRoadName':near['roadName'],'routeDistanceM':round(near['routeDistance'],3),'minFootprintEdgeToSurfaceRouteM':round(near['distance'],3),'firstRow':bool(hits),'newFirstRow':bool(hits) and bid not in old_first,'previouslyNearLegacyRoutes':bid in old_near,'footprint':b['points'],'height':b['height'],'heightSource':b['heightSource'],'frontage':{'edge':edge,'sourceEdgeIndices':chain,'widthM':round(math.dist(*edge),3),'visibleRoadLengthM':round(sum(h['roadSampleLength'] for h in hits),3),'side':max(set(h['side'] for h in hits),key=lambda x:sum(h['roadSampleLength'] for h in hits if h['side']==x)) if hits else None,'routeStartM':round(min(h['routeDistance'] for h in hits),3) if hits else None,'routeEndM':round(max(h['routeDistance'] for h in hits),3) if hits else None},'photoReferences':refs,'existingPhotoArchitecture':old_ref['id'] if old_ref else None,'confidence':'photograph-reference-with-visible-limits' if refs or old_ref else 'inferred-no-matched-building-photo','modelingBoundary':'OSM footprint plus stated height source. Non-visible sides, obscured details and unreferenced facades remain inferred, never claimed surveyed.'})
    rows.sort(key=lambda b:b['routeDistanceM'])
    result={'schemaVersion':1,'sourceMap':'public/tour-city.json','sourceMapSha256':hashlib.sha256((ROOT/'public/tour-city.json').read_bytes()).hexdigest(),'expandedOsmSource':'references/tourism/loop.osm.json','legacyCoverageSource':'references/tourism/street-frontage-coverage.json','routeLengthM':round(along,3),'surfaceRouteLengthM':round(surface,3),'method':{'distance':'Exact minimum between footprint boundary edges and surface route segments, threshold 100m. Tunnels excluded using route.tunnels; not centroid distance.','firstRow':'Normal rays every <=5m, both sides, first footprint intersection within100m; corner glimpses and longitudinal facades may be missed.','facade':'Dominant seen edge merged with adjacent edges aligned within3 degrees to avoid half-width OSM vertex splits.','countUnit':'OSM ways/building components, not independently surveyed physical buildings.','newFirstRow':'First row in this loop but not first row in the immutable legacy coverage table.'},'summary':{'nearSurfaceRouteWays':len(rows),'firstRowWays':sum(b['firstRow'] for b in rows),'newFirstRowWays':sum(b['newFirstRow'] for b in rows),'newFirstRowWaysWithPhoto':sum(b['newFirstRow'] and bool(b['photoReferences'] or b['existingPhotoArchitecture']) for b in rows)},'buildings':rows,'tunnelPortalReferences':load(ASSETS/'portals.json') if (ASSETS/'portals.json').exists() else [],'landmarkIdentityFacts':load(ASSETS/'identity-facts.json') if (ASSETS/'identity-facts.json').exists() else []}
    save(OUT,result);print(json.dumps(result['summary'],ensure_ascii=False),flush=True)

def download(selection):
    ref.DIR=ASSETS;ref.REPORT=ASSETS/'photos.json'
    ref.download(load(selection))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--photos');p.add_argument('--catalog',action='store_true');args=p.parse_args()
    if args.photos:download(args.photos)
    if args.catalog:catalog()
