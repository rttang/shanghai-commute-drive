"""Evidence-only Commons originals and footprint-edge/visible-frontage inventory.
All outputs remain on this project's external volume; no source image is deleted.
"""
import urllib.request, urllib.parse, urllib.error, json, pathlib, hashlib, re, time, math, argparse, html
ROOT = pathlib.Path(__file__).resolve().parents[1]
DIR = ROOT/'assets/streets/reference-expansion'
REPORT = ROOT/'references/tourism/streets-expansion-photos.json'
UA = 'ShanghaiStreetReferenceStudy/1.0 (local architectural reference research)'

def api(params):
    url = 'https://commons.wikimedia.org/w/api.php?'+urllib.parse.urlencode({'action':'query','format':'json',**params})
    for retry in range(5):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':UA}),timeout=45))
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            if retry==4: raise
            time.sleep(3*(retry+1))

def clean(value): return html.unescape(re.sub('<[^>]+>','',value)).strip()

def download(selection):
    DIR.mkdir(parents=True,exist_ok=True)
    records = json.loads(REPORT.read_text()) if REPORT.exists() else []
    for spec in selection:
        key,title = spec['id'],spec['title']
        previous = next((r for r in records if r['id']==key),None)
        if previous and (ROOT/previous['file']).exists(): continue
        info = next(iter(api({'titles':'File:'+title,'prop':'imageinfo','iiprop':'url|size|extmetadata|metadata'} )['query']['pages'].values()))['imageinfo'][0]
        meta=info['extmetadata']; license=meta['LicenseShortName']['value']
        if license not in ['CC0','CC BY-SA 4.0','CC BY-SA 3.0','CC BY-SA 2.5','CC BY-SA 2.0','CC BY 4.0','CC BY 3.0','CC BY 2.0','Public domain']:
            print('UNSUPPORTED LICENSE',key,license,flush=True);continue
        # Prefer originals. For >10 MB, Commons' 1920px derivative avoids unbounded downloads.
        if info['size'] > 10_000_000 or spec.get('thumbnail'):
            info = next(iter(api({'titles':'File:'+title,'prop':'imageinfo','iiprop':'url|size|extmetadata|metadata','iiurlwidth':1920})['query']['pages'].values()))['imageinfo'][0]
            url=info['thumburl'].split('?')[0]
        else: url=info['url'].split('?')[0]
        ext='.png' if info.get('mime')=='image/png' or title.lower().endswith('.png') else '.jpg'
        dst=DIR/(key+ext)
        if not dst.exists():
            for attempt in range(5):
                try:
                    req=urllib.request.Request(url,headers={'User-Agent':UA})
                    data=urllib.request.urlopen(req,timeout=90).read(); assert data[:2]==b'\xff\xd8' or data[:8]==b'\x89PNG\r\n\x1a\n'
                    dst.write_bytes(data);break
                except Exception as error:
                    if attempt==4: raise
                    if isinstance(error, urllib.error.HTTPError) and error.code==429:
                        # Honor Wikimedia's explicit recommendation to request cached thumbnails.
                        time.sleep(60)
                        if url==info['url'].split('?')[0]:
                            info = next(iter(api({'titles':'File:'+title,'prop':'imageinfo','iiprop':'url|size|extmetadata|metadata','iiurlwidth':1920})['query']['pages'].values()))['imageinfo'][0]
                            url=info['thumburl'].split('?')[0]
                            print('Using Commons recommended cached thumbnail after 429:',key,flush=True)
                    else: time.sleep(5*(attempt+1))
        record = {**spec,'file':str(dst.relative_to(ROOT)),'source':info['descriptionurl'],'download':url,'author':clean(meta.get('Artist',{}).get('value','')),'license':license,'licenseUrl':meta.get('LicenseUrl',{}).get('value'),'date':clean(meta.get('DateTimeOriginal',{}).get('value','')),'description':clean(meta.get('ImageDescription',{}).get('value','')),'cameraCoordinates':{'latitude':meta.get('GPSLatitude',{}).get('value'),'longitude':meta.get('GPSLongitude',{}).get('value')},'originalWidth':info['width'],'originalHeight':info['height'],'isOriginal':url==info['url'].split('?')[0],'bytes':dst.stat().st_size,'sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),'usage':'pending-visual-inspection','visualInspection':None}
        records.append(record);REPORT.write_text(json.dumps(records,ensure_ascii=False,indent=2));print(key,license,dst.stat().st_size,flush=True)
        time.sleep(4)

def sub(a,b):return (a[0]-b[0],a[1]-b[1])
def cross(a,b):return a[0]*b[1]-a[1]*b[0]
def project(p,a,b):
    ab=sub(b,a); den=ab[0]**2+ab[1]**2
    t=max(0,min(1,((p[0]-a[0])*ab[0]+(p[1]-a[1])*ab[1])/den)) if den else 0
    q=(a[0]+t*ab[0],a[1]+t*ab[1]);return math.dist(p,q),q,t

def intersect(a,b,c,d):
    r=sub(b,a);s=sub(d,c);det=cross(r,s)
    if abs(det)<1e-9:return None
    t=cross(sub(c,a),s)/det;u=cross(sub(c,a),r)/det
    return (t,u,(a[0]+t*r[0],a[1]+t*r[1])) if -1e-9<=t<=1+1e-9 and -1e-9<=u<=1+1e-9 else None

def segdist(a,b,c,d):
    hit=intersect(a,b,c,d)
    if hit:return 0,hit[2],hit[2],hit[0],hit[1]
    vals=[]
    for p,t in [(a,0),(b,1)]:
        dist,q,u=project(p,c,d);vals.append((dist,p,q,t,u))
    for p,u in [(c,0),(d,1)]:
        dist,q,t=project(p,a,b);vals.append((dist,q,p,t,u))
    return min(vals,key=lambda x:x[0])

def frontage_chain(edges, index):
    """A facade can contain redundant OSM vertices; do not squash it to one subedge."""
    def aligned(i,j):
        u=sub(edges[i][1],edges[i][0]);v=sub(edges[j][1],edges[j][0])
        norm=math.hypot(*u)*math.hypot(*v)
        return norm>1e-8 and (u[0]*v[0]+u[1]*v[1])/norm>math.cos(math.radians(3))
    chain=[index];n=len(edges)
    while len(chain)<n:
        prev=(chain[0]-1)%n
        if prev in chain or not aligned(prev,chain[0]):break
        chain.insert(0,prev)
    while len(chain)<n:
        following=(chain[-1]+1)%n
        if following in chain or not aligned(chain[-1],following):break
        chain.append(following)
    return (edges[chain[0]][0],edges[chain[-1]][1]),chain

def coverage():
    city=json.loads((ROOT/'public/tour-city.json').read_text())
    photos=json.loads((ROOT/'src/tour/photo-architecture.json').read_text())
    existing={w:p for p in photos for w in p['ways']}
    imageRefs=json.loads(REPORT.read_text()) if REPORT.exists() else []
    mapping={}; all_refs={}
    for ref in imageRefs:
        if ref['usage']!='exterior-reference':continue
        for way in ref.get('wayIds',[]):
            mapping.setdefault(way,ref);all_refs.setdefault(way,[]).append(ref['id'])
    height_file=DIR/'height-facts.json'
    height_facts=json.loads(height_file.read_text()) if height_file.exists() else []
    heights={w:h for h in height_facts for w in h.get('heightAppliesToWayIds',h['wayIds'])}
    output=[]; summaries=[]
    for route in city['routes']:
        segments=[];dist=0
        for a,b in zip(route['points'],route['points'][1:]):
            length=math.dist(a,b)
            if length:segments.append((a,b,dist,length))
            dist+=length
        candidates=[]
        for building in city['buildings']:
            poly=building['points'][:]
            if poly and poly[0]==poly[-1]:poly.pop()
            edges=list(zip(poly,poly[1:]+poly[:1]));best=(1e30,)
            for a,b,along,length in segments:
                # bounding-box short circuit (does not change minimum if retained)
                xs=[p[0] for p in poly];zs=[p[1] for p in poly]
                if max(xs)<min(a[0],b[0])-100 or min(xs)>max(a[0],b[0])+100 or max(zs)<min(a[1],b[1])-100 or min(zs)>max(a[1],b[1])+100:continue
                for edge,(c,d) in enumerate(edges):
                    v=segdist(a,b,c,d)
                    if v[0]<best[0]:best=(*v,along+v[3]*length,edge,a,b)
            if best[0]>100:continue
            candidates.append((building,best,edges))
        rays=[]
        for a,b,along,length in segments:
            # Road normal ray sampling; account for both sides and take FIRST footprint hit.
            n=max(1,math.ceil(length/5))
            for i in range(n):
                t=(i+.5)/n;p=(a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1]))
                for side,sign in [('left',-1),('right',1)]:
                    q=(p[0]+sign*(b[1]-a[1])/length*100,p[1]-sign*(b[0]-a[0])/length*100)
                    hits=[]
                    for building,best,edges in candidates:
                        for ei,(c,d) in enumerate(edges):
                            h=intersect(p,q,c,d)
                            if h and h[0]>=0:hits.append((h[0],building['id'],ei))
                    if hits:
                        hit=min(hits);rays.append((hit[1],along+t*length,side,hit[0]*100,hit[2],length/n))
        for building,best,edges in candidates:
            bid=building['id'];visible=[r for r in rays if r[0]==bid];old=existing.get(bid);ref=mapping.get(bid)
            frontIndex=max(set(r[4] for r in visible),key=lambda ei:sum(r[5] for r in visible if r[4]==ei)) if visible else best[6]
            frontEdge,chain=frontage_chain(edges,frontIndex)
            inferred=not(old or ref)
            output.append({'wayId':bid,'name':building['name'] or f'OSM building {bid}','route':route['id'],'footprint':building['points'],'height':building['height'],'heightSource':building['heightSource'],'minFootprintEdgeToRouteM':round(best[0],2),'nearestRouteDistanceM':round(best[5],2),'frontage':{'classification':'first-row-sampled' if visible else 'near-route-occluded-or-not-normal-facing','edge':[list(p) for p in frontEdge],'side':max(set(r[2] for r in visible),key=lambda x:sum(r[5] for r in visible if r[2]==x)) if visible else None,'visibleRoadLengthM':round(sum(r[5] for r in visible),2),'routeStartM':round(min(r[1] for r in visible),2) if visible else None,'routeEndM':round(max(r[1] for r in visible),2) if visible else None,'minRaySetbackM':round(min(r[3] for r in visible),2) if visible else None},'photoRef':old['reference'] if old else ref['id'] if ref else None,'photoLibrary':'architecture-photos.json' if old else 'streets-expansion-photos.json' if ref else None,'existingPhotoModel':old['id'] if old else None,'confidence':'photo-referenced-osm-footprint' if not inferred else 'inferred-no-matched-exterior-photo','geometryAuthority':'OSM footprint; height supplied by '+building['heightSource']+'; facade detail is photograph observation or inferred, not surveyed','modelingStatus':'existing-photo-model' if old else 'new-photo-reference' if ref else 'needs-photo-or-honest-inference'})
            output[-1]['photoRefs']={'existing':[old['reference']] if old else [],'expansion':all_refs.get(bid,[])}
            output[-1]['frontage']['sourceEdgeIndices']=chain
            output[-1]['frontage']['facadeWidthM']=round(math.dist(*frontEdge),3)
            output[-1]['heightReference']=heights.get(bid)
        rows=[r for r in output if r['route']==route['id']];summaries.append({'route':route['id'],'routeLengthM':round(dist,2),'nearRouteBuildings':len(rows),'firstRowBuildings':sum(r['frontage']['classification']=='first-row-sampled' for r in rows),'firstRowWithExistingPhotoModel':sum(r['frontage']['classification']=='first-row-sampled' and bool(r['existingPhotoModel']) for r in rows),'firstRowWithNewPhotoReference':sum(r['frontage']['classification']=='first-row-sampled' and r['modelingStatus']=='new-photo-reference' for r in rows)})
    for summary in summaries:
        summary['firstRowWithoutMatchedExteriorPhoto']=sum(r['route']==summary['route'] and r['frontage']['classification']=='first-row-sampled' and not r['photoRef'] for r in output)
        summary['countUnit']='OSM way or building component; multiple ways can represent one physical building'
    result={'schemaVersion':1,'sourceMap':'public/tour-city.json','sourceMapSha256':hashlib.sha256((ROOT/'public/tour-city.json').read_bytes()).hexdigest(),'method':{'candidateDistance':'Exact segment-to-segment minimum between building footprint boundary and route polyline, <=100m; not centroid distance.','firstRow':'Sample route at <=5m spacing, cast left and right normal rays 100m; retain first footprint intersection. Curved corners, longitudinal facades and narrow glimpses can be missed. Candidate inventory retained for review.','frontage':'Dominant visible footprint edge selected by summed road sample length. Adjacent boundary segments aligned within 3 degrees are merged; sourceEdgeIndices retains indices after removing duplicate closing point. This is geometric visibility, not a real-world claim that vegetation/furniture is absent.','heights':'OSM height or levels estimate retained explicitly; independent heightReference is attached to its applicable main-tower way only. No photograph is silently promoted to measured height.','photoCoverage':'Only matched building-specific exterior photos count; district panoramas are context refs, not per-building surveyed evidence.'},'routes':summaries,'buildings':sorted(output,key=lambda r:(r['route'],r['nearestRouteDistanceM']))}
    (ROOT/'references/tourism/street-frontage-coverage.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(summaries,ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--selection');p.add_argument('--coverage',action='store_true');args=p.parse_args()
    if args.selection:download(json.loads(pathlib.Path(args.selection).read_text()))
    if args.coverage:coverage()
