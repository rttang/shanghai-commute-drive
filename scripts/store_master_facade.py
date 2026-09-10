"""Keep both generated originals and verified external-disk texture copies."""
import sys, json, pathlib, hashlib, shutil, datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]
key,source=sys.argv[1:3]
source=pathlib.Path(source).resolve()
assert source.is_file() and '/.codex/generated_images/' in str(source)
assert str(ROOT).startswith('/Volumes/')
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
target=ROOT/'assets/streets/photofacades-expansion'/f'{key}.png'
target.parent.mkdir(parents=True,exist_ok=True)
if target.exists() and digest(target)!=digest(source):
    target=target.with_name(f'{key}-{digest(source)[:12]}.png')
if not target.exists():shutil.copy2(source,target)
assert digest(source)==digest(target)
ledger=ROOT/'docs/evidence/tourism/street-master-generated-images.json'
items=json.loads(ledger.read_text()) if ledger.exists() else []
record={'id':key,'path':str(source),'retained':str(target),'bytes':target.stat().st_size,'sha256':digest(target),'tool':'built-in image_gen','sourceReferenceId':key,'sourcePhoto':f'assets/streets/reference-expansion/{key}.jpg','method':'Photographic perspective rectification and conservative occlusion completion; original image preserved; not a measured facade survey','requestSummary':'Orthographic front elevation of the real referenced building; retain stone joints, carved ornaments, actual windows/columns/roof silhouette; remove foreground people/trees/traffic/sky; neutral daylight; no labels or invented brands; fill occluded details conservatively','created':datetime.datetime.now(datetime.timezone.utc).isoformat()}
if not any(r['sha256']==record['sha256'] for r in items):items.append(record)
ledger.write_text(json.dumps(items,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(record,ensure_ascii=False))
