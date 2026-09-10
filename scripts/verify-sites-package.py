from pathlib import Path
import tarfile, hashlib, json, subprocess, zlib, gzip, sys
ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'release/sites'
archive=Path(sys.argv[1]).resolve()
limit=256*1024*1024
index=json.loads((SITE/'source/asset-index.json').read_text())
parts={p if isinstance(p,str) else p['path'] for e in index.values() for p in e['parts']}
expected={'dist/server/index.js','dist/server/wrangler.json','dist/.openai/hosting.json'}|{'dist/client'+p for p in parts}
def digest(stream):
 h=hashlib.sha256()
 while True:
  b=stream.read(1024*1024)
  if not b:break
  h.update(b)
 return h.hexdigest()
actual=set();file_bytes=0
with tarfile.open(archive,'r:gz') as tar:
 for item in tar:
  assert item.isdir() or item.isfile(),item.name
  assert not item.name.startswith('/') and '..' not in Path(item.name).parts,item.name
  if not item.isfile():continue
  actual.add(item.name);file_bytes+=item.size
  local=SITE/('.openai/hosting.json' if item.name=='dist/.openai/hosting.json' else item.name)
  with local.open('rb') as f:assert digest(tar.extractfile(item))==digest(f),item.name
  if item.name.startswith('dist/client/'):assert item.size<=8*1024*1024,item.name
assert actual==expected,(actual-expected,expected-actual)
expanded=0
with gzip.open(archive,'rb') as f:
 while True:
  b=f.read(1024*1024)
  if not b:break
  expanded+=len(b)
p=subprocess.Popen(['git','archive','--format=tar','HEAD'],cwd=SITE,stdout=subprocess.PIPE)
c=zlib.compressobj(6,zlib.DEFLATED,31);source_gzip=0;source_tar=0
while True:
 b=p.stdout.read(1024*1024)
 if not b:break
 source_tar+=len(b);source_gzip+=len(c.compress(b))
source_gzip+=len(c.flush());assert p.wait()==0
assert max(archive.stat().st_size,expanded,source_gzip,source_tar)<limit,{'buildGzip':archive.stat().st_size,'buildTar':expanded,'sourceGzip':source_gzip,'sourceTar':source_tar,'limit':limit}
assert not subprocess.check_output(['git','status','--porcelain'],cwd=SITE).strip()
with archive.open('rb') as f:archive_hash=digest(f)
record={'file':archive.name,'bytes':archive.stat().st_size,'sha256':archive_hash,'files':len(actual),'expandedArchiveBytes':expanded,'expandedFilesBytes':file_bytes,'sourceTarGzipBytes':source_gzip,'sourceTarBytes':source_tar,'compressedAndExpandedLimitBytes':limit,'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=SITE).decode().strip(),'allFilesVerified':True}
(ROOT/'docs/evidence/deployment-optimization/sites-archive-final.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
