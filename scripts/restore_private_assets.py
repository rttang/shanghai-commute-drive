"""Verify and restore private backup parts without extracting arbitrary archive paths.

Download attachments with GitHub CLI first; credentials never enter this script.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import zipfile


def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parts', required=True, type=Path)
    parser.add_argument('--manifest', type=Path, default=Path(__file__).resolve().parents[1] / 'docs/private-backup/asset-manifest.json')
    parser.add_argument('--target', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--group', choices=['all', 'runtime', 'authoring', 'source-assets', 'design-references'], default='all')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args(); root = args.target.resolve()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    if manifest.get('schemaVersion') != 1 or manifest.get('visibility') != 'private': raise SystemExit('Unexpected manifest')
    selected = [f for f in manifest['files'] if args.group == 'all' or f['group'] == args.group]
    needed = {f['part'] for f in selected}; by_part = {p['file']: p for p in manifest['parts']}
    paths = set()
    for entry in selected:
        name = entry['file']
        if not isinstance(name, str) or not name.startswith(('public/', 'assets/', '.dream-loop/')) or re.search(r'[\\\x00:%]', name) or any(p in ['', '.', '..'] for p in name.split('/')): raise SystemExit('Unsafe destination')
        if name in paths: raise SystemExit('Duplicate destination')
        paths.add(name)
        if not re.fullmatch(r'[0-9a-f]{64}', entry['sha256']): raise SystemExit('Invalid SHA-256')
        target = root / name
        for parent in [target, *target.parents]:
            if parent == root.parent: break
            if parent.is_symlink(): raise SystemExit('Symlink destination refused')
        if target.exists() and (not target.is_file() or digest(target) != entry['sha256']): raise SystemExit('Different local file retained; use a clean destination: '+name)
    for name in sorted(needed):
        if Path(name).name != name or name not in by_part: raise SystemExit('Unsafe part name')
        p = args.parts / name; expected = by_part[name]
        if not p.is_file() or p.stat().st_size != expected['bytes'] or digest(p) != expected['sha256']: raise SystemExit('Missing or corrupt part: '+name)
    restored = 0
    for name in sorted(needed):
        with zipfile.ZipFile(args.parts/name) as z:
            entries = {i.filename: i for i in z.infolist()}
            if len(entries) != len(z.infolist()): raise SystemExit('Duplicate archive objects')
            for entry in (f for f in selected if f['part'] == name):
                member = 'objects/'+entry['sha256']; info = entries.get(member)
                if not info or info.file_size != entry['bytes'] or ((info.external_attr >> 16) & 0o170000) == 0o120000: raise SystemExit('Invalid archive object')
                target = root / entry['file']; h = hashlib.sha256(); count = 0
                write = not args.verify_only and not target.exists()
                if write:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    temp = target.with_name(target.name+'.restore-partial')
                    output = temp.open('xb')
                else: output = None
                try:
                    with z.open(member) as source:
                        for block in iter(lambda: source.read(4 * 1024 * 1024), b''):
                            count += len(block)
                            if count > entry['bytes']: raise SystemExit('Oversized object')
                            h.update(block)
                            if output: output.write(block)
                    if count != entry['bytes'] or h.hexdigest() != entry['sha256']: raise SystemExit('Object checksum mismatch')
                    if output:
                        output.flush(); os.fsync(output.fileno()); output.close(); output = None
                        temp.replace(target)
                    restored += 1
                finally:
                    if output: output.close()
        print(json.dumps({'verifiedPart': name, 'filesSoFar': restored}), flush=True)
    print(json.dumps({'passed': True, 'files': restored, 'group': args.group, 'verifyOnly': args.verify_only}), flush=True)


if __name__ == '__main__': main()
