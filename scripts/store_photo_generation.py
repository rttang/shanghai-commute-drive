"""Copy generated images to external storage; always preserve their originals."""
import sys,json,pathlib,hashlib,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1]
key,src,prompt=sys.argv[1:4]
src=pathlib.Path(src); dst=ROOT/'assets/streets/photofacades'/f'{key}.png';dst.parent.mkdir(exist_ok=True,parents=True)
assert str(ROOT).startswith('/Volumes/')
assert src.parent==pathlib.Path('/Users/maiziheng/.codex/generated_images/01a0806f-f664-74d1-97a7-11b3fcbd1dc7')
hash=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
if dst.exists() and hash(dst)!=hash(src):
 dst=dst.with_name(f'{key}-{hash(src)[:12]}.png')
if not dst.exists():shutil.copyfile(src,dst)
assert hash(src)==hash(dst)
p=ROOT/'.dream-loop/photo-prompts.json';records=json.loads(p.read_text());records.append(dict(id=key,prompt=prompt,reference=f'assets/streets/references/{key}.jpg',output=str(dst.relative_to(ROOT)),original=str(src),originalPreserved=True,sha256=hash(dst)));p.write_text(json.dumps(records,ensure_ascii=False,indent=2))
print(key,dst.stat().st_size,hash(dst))
