"""Move a task-selected browser download to this external project, with hash verification."""
from pathlib import Path
import argparse, hashlib, json, shutil, zipfile

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('filename'); p.add_argument('car'); p.add_argument('url'); p.add_argument('author')
args = p.parse_args()
assert Path(args.filename).name == args.filename
assert args.car in ['su7','dolphin','model-3','model-y','starwish','yuan-up','leap-a10','qiyuan-q05','li-i6','bingo-pro']
source = Path('/Users/maiziheng/Downloads') / args.filename
assert source.is_file() and not source.is_symlink()
destination = ROOT / 'assets/vehicles/source' / args.car
destination.mkdir(parents=True,exist_ok=True)
target = destination / ('original' + source.suffix.lower())
assert not target.exists(), 'Never overwrite an earlier source asset'
digest = hashlib.sha256(source.read_bytes()).hexdigest()
shutil.copy2(source,target)
assert hashlib.sha256(target.read_bytes()).hexdigest() == digest
size = source.stat().st_size
source.unlink()
record = {'source':args.url,'author':args.author,'license':'CC-BY-4.0','file':target.name,'bytes':size,'sha256':digest,'mainDiskTemporary':str(source),'verifiedBeforeUnlink':True,'mainDiskCopyRemoved':not source.exists()}
(destination/'provenance.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
if target.suffix == '.zip':
    with zipfile.ZipFile(target) as archive:
        assert sum(i.file_size for i in archive.infolist()) < 400_000_000
        for name in archive.namelist():
            assert not Path(name).is_absolute() and '..' not in Path(name).parts
        archive.extractall(destination/'source')
        record['extracted'] = archive.namelist()
print(json.dumps(record,ensure_ascii=False))
