"""Download a bounded Shanghai road extract and record reference revisions."""
import json, urllib.request, urllib.parse, pathlib, datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'references'; OUT.mkdir(exist_ok=True)
def get(url,data=None):
    req=urllib.request.Request(url,data=data,headers={'User-Agent':'ShanghaiCommuteLocal/2.0'})
    with urllib.request.urlopen(req,timeout=55) as r:return r.read()
query='[out:json][timeout:40];way["highway"]["name"~"^(南京西路|常德路|延安中路|延安高架路|南北高架路|中山东一路|中山东二路|延安东路隧道|世纪大道|陆家嘴环路|银城中路)$"](31.19,121.43,31.26,121.515);out geom;'
for endpoint in ['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter']:
    try:
        raw=get(endpoint,urllib.parse.urlencode({'data':query}).encode())
        data=json.loads(raw)
        if not data.get('elements'):raise ValueError('Empty map')
        (OUT/'shanghai-roads.osm.json').write_bytes(raw)
        (OUT/'map-source.json').write_text(json.dumps({'endpoint':endpoint,'query':query,'retrievedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','ways':len(data['elements'])},ensure_ascii=False,indent=2))
        print('OSM',len(data['elements']),'ways',len(raw),'bytes',flush=True);break
    except Exception as e: print('MAP_FETCH',str(e),flush=True)
for repo in ['jakesgordon/javascript-racer','cconsta1/threejs_car_demo']:
    try:
        meta=json.loads(get('https://api.github.com/repos/'+repo))
        sha=json.loads(get('https://api.github.com/repos/'+repo+'/commits/'+meta['default_branch']))['sha']
        tree=json.loads(get(f'https://api.github.com/repos/{repo}/git/trees/{sha}?recursive=1'))
        paths=[x['path'] for x in tree['tree'] if x['type']=='blob']
        chosen=[p for p in paths if p.lower() in ['readme.md','license','license.md','src/main.js','src/experience/world/car.js','common.js']]
        dest=OUT/repo.split('/')[1];dest.mkdir(exist_ok=True)
        for p in chosen:
            (dest/p.replace('/','__')).write_bytes(get(f'https://raw.githubusercontent.com/{repo}/{sha}/{p}'))
        (dest/'revision.json').write_text(json.dumps({'repo':repo,'commit':sha,'files':paths,'read':chosen},indent=2))
        print('REFERENCE',repo,sha,chosen,flush=True)
    except Exception as e:print('REFERENCE_FETCH',repo,str(e),flush=True)
