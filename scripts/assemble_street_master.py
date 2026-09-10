"""Build one complete, useful street GLB and matching runtime tiles.

The master embeds the original district geometry/PNG data unchanged. Runtime
tiles reuse the same meshes and coordinates. No byte padding, hidden filler,
vehicles, source-photo archive, or backups count toward the approved 5 GB runtime package budget.
"""
import collections
import datetime
import hashlib
import json
import math
import pathlib
from street_glb import Assembly, read_glb, write_glb

ROOT = pathlib.Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'public'
OUT = PUBLIC / 'streets/master'
OUT.mkdir(parents=True, exist_ok=True)


def load(path):
    return json.loads(path.read_text())


def embed_context_maps():
    path = OUT / 'context.glb'
    doc, binary = read_glb(path)
    binary = bytearray(binary[:doc['buffers'][0]['byteLength']])
    textures = load(OUT / 'context.json')['materialTextures']
    doc['images'], doc['textures'] = [], []
    doc['samplers'] = [{'magFilter': 9729, 'minFilter': 9987, 'wrapS': 10497, 'wrapT': 10497}]
    cache = {}
    for material in doc['materials']:
        source = textures.get(material.get('name'))
        if not source:
            continue
        if source not in cache:
            data = (PUBLIC / source).read_bytes()
            binary.extend(b'\0' * (-len(binary) % 4))
            view = len(doc['bufferViews'])
            doc['bufferViews'].append({'buffer': 0, 'byteOffset': len(binary), 'byteLength': len(data)})
            binary.extend(data)
            image = len(doc['images'])
            doc['images'].append({'bufferView': view, 'mimeType': 'image/png' if source.endswith('.png') else 'image/jpeg', 'name': source})
            cache[source] = len(doc['textures'])
            doc['textures'].append({'source': image, 'sampler': 0})
        material.setdefault('pbrMetallicRoughness', {})['baseColorTexture'] = {'index': cache[source]}
    write_glb(OUT / 'context-textured.glb', doc, binary)


def main():
    embed_context_maps()
    districts = []
    for name in ('bund', 'pudong', 'north-bund', 'loop-frontages'):
        if not (PUBLIC / f'streets/districts/{name}/manifest.json').exists():
            continue
        districts.extend(load(PUBLIC / f'streets/districts/{name}/manifest.json')['models'])
    ids=[m['id'] for m in districts]
    if len(ids)!=len(set(ids)):
        raise RuntimeError('Duplicate district model IDs')
    furniture = load(PUBLIC / 'streets/districts/furniture/manifest.json')
    furniture = {m['id']: m for m in furniture['models']}
    placements = load(OUT / 'placements.json')
    city = load(PUBLIC / 'tour-city.json')
    footprints = {b['id']: b for b in city['buildings']}
    master = Assembly()
    tiles = collections.defaultdict(list)
    records = []

    def include(asset, category, always=False):
        x, z = asset.get('center', [0, 0])
        key = 'context' if category == 'context' else ('skyline' if always else f'{math.floor(x / 320)}_{math.floor(z / 320)}')
        asset = dict(asset, category=category)
        tiles[key].append(asset)
        records.append(asset)

    include({'id': 'terrain-roads-far-buildings', 'file': 'streets/master/context-textured.glb', 'center': [0, 0], 'heading': 0, 'y': 0, 'ways': [], 'bounds': [-5000, -5000, 5000, 5000]}, 'context', True)
    for model in districts:
        points = [p for way in model.get('ways', []) for p in footprints.get(way, {}).get('points', [])]
        x, z = model['center']
        bounds = [min(p[0] for p in points)-12, min(p[1] for p in points)-12, max(p[0] for p in points)+12, max(p[1] for p in points)+12] if points else [x-100,z-100,x+100,z+100]
        include(dict(model, bounds=bounds, y=.12), 'architecture', model.get('height', 0) > 130)
    for i, item in enumerate(placements['streetObjects']):
        prototype = furniture[item['id']]
        x, z = item['x'], item['z']
        include({'id': f"{item['id']}-{i}", 'file': prototype['file'], 'center': [x,z], 'heading': item.get('heading',0), 'y': .14, 'ways': [], 'bounds': [x-9,z-9,x+9,z+9], 'prototype': item['id']}, 'furniture')
    for i, item in enumerate(placements['railings']):
        x, z = item['x'], item['z']
        include({'id': f'river-railing-{i}', 'file': furniture['river-railing']['file'], 'center': [x,z], 'heading': item['heading']-math.pi/2, 'y': .14, 'scale': [item['length']/3,1,1], 'ways': [], 'bounds': [x-3,z-3,x+3,z+3], 'prototype': 'river-railing'}, 'furniture')
    bridge = placements['bridge']
    x,z = bridge['center']
    include({'id': 'waibaidu-bridge', 'file': furniture['waibaidu-bridge']['file'], 'center': [x,z], 'heading': bridge['heading'], 'y': 0, 'ways': [], 'bounds': [x-65,z-65,x+65,z+65], 'netClearance': {'halfCarriageway':4.8,'lowStructureMinX':5.3,'beamBottom':5.2}}, 'bridge')

    def place(assembly, asset):
        return assembly.place(PUBLIC / asset['file'].lstrip('/'), asset['id'], asset['center'], asset.get('heading',0), asset.get('y',0), asset.get('scale',[1,1,1]), {'category':asset['category'],'ways':asset.get('ways',[]),'referenceIds':asset.get('referenceIds',[]),'inferredDetails':asset.get('inferredDetails','')})

    chunks = []
    rendered_triangles = 0
    for key, assets in sorted(tiles.items()):
        tile = Assembly()
        triangles = 0
        for asset in assets:
            triangles += place(tile, asset)
            rendered_triangles += place(master, asset)
        bounds = [min(a['bounds'][0] for a in assets),min(a['bounds'][1] for a in assets),max(a['bounds'][2] for a in assets),max(a['bounds'][3] for a in assets)]
        file = f'streets/master/chunks/{key}.glb'
        detail = tile.write(PUBLIC / file)
        chunks.append({'id':key,'file':'/'+file,'bounds':bounds,'triangles':triangles,'coveredWays':sorted(set(w for a in assets for w in a.get('ways',[]))), 'always':key in ('context','skyline'),'objects':len(assets),**detail})
        print(json.dumps({'chunk':key,**detail}),flush=True)
    master.doc['asset']['copyright'] = 'OpenStreetMap contributors ODbL; source-photo authors and derived asset licenses listed in credits and references.'
    master.doc['scenes'][0]['extras'] = {'worldAxes':'X east, Y up, Z south; metres','sourceMapSha256':hashlib.sha256((PUBLIC/'tour-city.json').read_bytes()).hexdigest(),'noVehicles':True,'budget':'runtime street package <= 5000000000 bytes; single GLB within uint32 limit'}
    detail = master.write(OUT / 'shanghai-streets.glb')
    covered = sorted(set(w for m in districts for w in m.get('ways',[])))
    coverage = load(ROOT / 'references/tourism/street-frontage-coverage.json')
    first = [b for b in coverage['buildings'] if b.get('frontage',{}).get('classification') == 'first-row-sampled']
    if not first:
        raise RuntimeError('First-row coverage inventory is missing or has an unknown schema')
    missing = [{'wayId':b['wayId'],'name':b['name'],'route':b['route']} for b in first if b['wayId'] not in covered]
    result = {'version':1,'generated':datetime.datetime.now(datetime.timezone.utc).isoformat(),'generator':'scripts/assemble_street_master.py','master':{'file':'/streets/master/shanghai-streets.glb',**detail,'triangles':rendered_triangles,'uniqueTriangles':Assembly.triangles(master.doc),'architectureModels':len(districts),'objects':len(records),'budgetSatisfied':sum(c['bytes'] for c in chunks)<=5_000_000_000,'runtimeBytes':sum(c['bytes'] for c in chunks)},'chunks':chunks,'coveredWays':covered,'firstRowCoverage':{'total':len(first),'covered':len(first)-len(missing),'missing':missing},'referenceCatalog':'/streets/master/reference-catalog.json','texturePolicy':'Original PNGs and geometric data preserved; no filler or car assets; shared props are mesh instances','runtime':{'loadRadiusM':850,'unloadRadiusM':1400,'maxConcurrent':2}}
    loop_file=ROOT/'references/tourism/loop-frontage-catalog.json'
    if loop_file.exists():
        loop=load(loop_file)
        selected=[b for b in loop['buildings'] if b.get('firstRow')]
        result['loopFrontageCatalog']=str(loop_file.relative_to(ROOT))
        result['loopFrontageSummary']=loop.get('summary',{})
        loop_missing=[{'wayId':b['wayId'],'name':b['name'],'routeDistanceM':b['routeDistanceM']} for b in selected if b['wayId'] not in covered]
        result['loopFirstRowGeometryCoverage']={
            'total':len(selected),'modeledWays':len(selected)-len(loop_missing),
            'missing':loop_missing,
            'meaning':'Mapped building-way geometry coverage only; this is not a photo-fidelity acceptance result.'}
    (OUT/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    (OUT/'assembly.json').write_text(json.dumps({'models':records},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'master':detail,'chunks':len(chunks),'missing':len(missing)},ensure_ascii=False),flush=True)
    if not result['master']['budgetSatisfied']:
        raise RuntimeError('Runtime street package exceeds approved 5 GB budget')


if __name__ == '__main__':
    main()
