"""Bounded OSM snapshot for two Shanghai waterfront tours; no account required."""
import json, pathlib, urllib.request, urllib.parse, datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'references/tourism'
OUT.mkdir(exist_ok=True)
BBOX='31.224,121.482,31.249,121.514'
query=f'[out:json][timeout:45];(way[building]({BBOX});way["building:part"]({BBOX});way[highway]({BBOX});way[natural=water]({BBOX});way[waterway=riverbank]({BBOX});relation[natural=water]({BBOX}););out geom;'
dest=OUT/'city.osm.json'
if dest.exists():
    print('Using existing snapshot',dest)
else:
    for endpoint in ['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter']:
        try:
            req=urllib.request.Request(endpoint,data=urllib.parse.urlencode({'data':query}).encode(),headers={'User-Agent':'ShanghaiTourismLocal/3.0'})
            with urllib.request.urlopen(req,timeout=55) as r: raw=r.read()
            data=json.loads(raw)
            assert len(data.get('elements',[]))>100
            dest.write_bytes(raw)
            (OUT/'map-source.json').write_text(json.dumps({'endpoint':endpoint,'query':query,'bbox':BBOX,'retrievedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'license':'ODbL-1.0','elements':len(data['elements'])},indent=2))
            print(len(data['elements']),len(raw),'bytes',flush=True)
            break
        except Exception as e: print(type(e).__name__,str(e),flush=True)
    else: raise RuntimeError('OSM snapshot unavailable')
