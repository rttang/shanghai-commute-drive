"""Create content-addressed private backup parts. Originals are never changed."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / '.tooling/private-backup'
MANIFEST = ROOT / 'docs/private-backup/asset-manifest.json'
MAX_RAW_PART = 1_500_000_000


def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def excluded(rel):
    name = rel.name
    if name.startswith('._') or name == '.DS_Store': return 'filesystem metadata'
    if name.endswith(('.log', '.lock', '.pyc')) or '__pycache__' in rel.parts: return 'runtime log or cache'
    if re.search(r'\.blend\d+$|\.previous(?:\.|$)|\.verified-copy$', name): return 'previous or temporary export'
    if any(re.search(r'^(before(?:-|$)|preserved-before|revision-before|candidate-|v\d+-|failed-publications$)', p) for p in rel.parts): return 'historical revision'
    if any('backup' in p.lower() or p == 'master-index-repair' for p in rel.parts): return 'historical backup or repair archive'
    if 'luxury-prepared' in rel.parts: return 'intermediate vehicle conversion; source and runtime retained'
    if name.lower().endswith(('.pem', '.key', '.p12', '.pfx', '.sqlite', '.sqlite3', '.db')): return 'sensitive or database file requires explicit review'
    return None


def group(rel):
    if rel.parts[0] == 'public': return 'runtime'
    if rel.parts[:2] == ('assets', 'blender'): return 'authoring'
    if rel.parts[0] == 'assets': return 'source-assets'
    return 'design-references'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    parser.add_argument('--scan-only', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]+', args.tag): raise SystemExit('Unsafe release tag')
    files, omissions, objects = [], [], {}
    for prefix in ('public', 'assets', '.dream-loop'):
        for p in sorted((ROOT / prefix).rglob('*')):
            if not p.is_file(): continue
            rel = p.relative_to(ROOT)
            reason = 'symlink' if p.is_symlink() else excluded(rel)
            if reason:
                omissions.append({'file': rel.as_posix(), 'reason': reason, 'bytes': p.stat().st_size})
                continue
            sha = digest(p)
            entry = {'file': rel.as_posix(), 'bytes': p.stat().st_size, 'sha256': sha, 'group': group(rel)}
            files.append(entry)
            objects.setdefault(sha, entry)
    parts = []
    for family in ('runtime', 'authoring', 'source-assets', 'design-references'):
        batch, size = [], 0
        for sha, record in sorted(objects.items()):
            if record['group'] != family: continue
            if batch and size + record['bytes'] > MAX_RAW_PART:
                parts.append((family, batch)); batch, size = [], 0
            batch.append(sha); size += record['bytes']
        if batch: parts.append((family, batch))
    report = {'schemaVersion': 1, 'repository': 'rttang/shanghai-commute-drive', 'visibility': 'private',
              'releaseTag': args.tag, 'createdAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'files': files, 'excluded': omissions, 'parts': [],
              'summary': {'paths': len(files), 'bytes': sum(e['bytes'] for e in files), 'uniqueObjects': len(objects),
                          'uniqueBytes': sum(e['bytes'] for e in objects.values()), 'parts': len(parts),
                          'excludedPaths': len(omissions), 'excludedBytes': sum(e['bytes'] for e in omissions)}}
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    if args.scan_only:
        (MANIFEST.parent / 'asset-selection.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(report['summary'])); return
    DEST.mkdir(parents=True, exist_ok=True)
    counters = {}
    object_parts = {}
    for family, shas in parts:
        counters[family] = counters.get(family, 0) + 1
        name = '{}-{}-{:02}.zip'.format(args.tag, family, counters[family])
        output = DEST / name
        if output.exists(): raise SystemExit('Refusing to overwrite an existing backup part: '+name)
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as z:
            for sha in shas:
                record = objects[sha]; source = ROOT / record['file']; h = hashlib.sha256(); count = 0
                info = zipfile.ZipInfo('objects/'+sha, (2026, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                with source.open('rb') as inp, z.open(info, 'w', force_zip64=True) as target:
                    for block in iter(lambda: inp.read(4 * 1024 * 1024), b''):
                        target.write(block); h.update(block); count += len(block)
                if h.hexdigest() != sha or count != record['bytes']: raise SystemExit('Source changed while packing: '+record['file'])
                object_parts[sha] = name
        if output.stat().st_size >= 2 * 1024**3: raise SystemExit('Part exceeds GitHub attachment limit')
        part = {'file': name, 'group': family, 'bytes': output.stat().st_size, 'sha256': digest(output), 'objects': shas}
        report['parts'].append(part)
        print(json.dumps({'packed': name, 'bytes': part['bytes'], 'objects': len(shas)}), flush=True)
    for entry in report['files']: entry['part'] = object_parts[entry['sha256']]
    MANIFEST.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (DEST / 'SHA256SUMS.txt').write_text(''.join(p['sha256']+'  '+p['file']+'\n' for p in report['parts']), encoding='utf-8')
    print(json.dumps({'done': True, **report['summary'], 'compressedBytes': sum(p['bytes'] for p in report['parts'])}), flush=True)


if __name__ == '__main__': main()
