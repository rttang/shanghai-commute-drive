"""Restore the proven original Magnolia indices without reassembling the scene.

This one-time repair is deliberately pinned to the damaged delivery. It restores
the exact original source SHA from the assembly snapshot, preserves GLB JSON and
every byte outside the damaged index range, and backs up before publishing.
No district model, placement, texture, or other runtime tile is refreshed.
"""
import array
import datetime
import hashlib
import json
import os
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MASTER = ROOT / 'public/streets/master'
OLD = ROOT / 'assets/streets/north-bund/revision-before-corrupt-podium-repair/magnolia-podium.glb'
FIXED = ROOT / 'public/streets/districts/north-bund/magnolia-podium.glb'
EXPECTED_ORIGINAL = 'a63af81a3562fbba08d51170bf6ec10f86d8c39427708e2e427b9ae8a5692157'
EXPECTED_BAD = '086e694cf652f41cfc84a5d5d3ea361d8027efa7bb6aceee2aa662a10e7b7433'
EXPECTED_FIXED = '5315551bda244ea21ce30c9caafb1c1d2f2e4ad3282e66d3a5e2324d787ccf87'
BAD_MESH = 'magnolia-podium-detail-north-bund-satin-aluminium.003'
BLOCK = 4 * 1024 * 1024


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(BLOCK), b''):
            h.update(block)
    return h.hexdigest()


def header(path):
    with path.open('rb') as f:
        h = f.read(20)
        magic, version, size, length, kind = struct.unpack('<5I', h)
        assert (magic, version, size, kind) == (0x46546c67, 2, path.stat().st_size, 0x4e4f534a)
        raw = f.read(length)
        binary_length, binary_kind = struct.unpack('<2I', f.read(8))
        assert binary_kind == 0x004e4942 and 28 + length + binary_length == size
    return json.loads(raw), 28 + length, binary_length


def strip_names(value):
    if isinstance(value, dict):
        return {k: strip_names(v) for k, v in value.items() if k != 'name'}
    if isinstance(value, list):
        return [strip_names(v) for v in value]
    return value


def indices(doc, binary):
    checked, invalid = 0, []
    for mesh in doc.get('meshes', []):
        for primitive in mesh['primitives']:
            if 'indices' not in primitive:
                continue
            accessor = doc['accessors'][primitive['indices']]
            assert 'bufferView' in accessor, 'This repair source must have raw indices'
            view = doc['bufferViews'][accessor['bufferView']]
            assert not view.get('byteStride') and not accessor.get('sparse')
            values = array.array({5121: 'B', 5123: 'H', 5125: 'I'}[accessor['componentType']])
            start = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
            values.frombytes(binary[start:start + accessor['count'] * values.itemsize])
            assert len(values) == accessor['count']
            positions = doc['accessors'][primitive['attributes']['POSITION']]['count']
            bad = sum(v >= positions for v in values)
            checked += len(values)
            if bad:
                invalid.append({'mesh': mesh['name'], 'invalidIndices': bad,
                                'positionCount': positions, 'maximumIndex': max(values)})
    return {'indicesChecked': checked, 'invalid': invalid}


def verified_copy(source, target, expected):
    target.parent.mkdir(parents=True, exist_ok=True)
    assert not target.exists(), target
    with source.open('rb') as reader, target.open('xb') as writer:
        for block in iter(lambda: reader.read(BLOCK), b''):
            writer.write(block)
        writer.flush()
        os.fsync(writer.fileno())
    assert digest(target) == expected, f'Backup copy failed: {target}'


def publish_patch(path, start, replacement, backup):
    # Preserve the original GLB header/JSON and all unrelated binary bytes.
    temporary = path.with_suffix('.index-repair-writing')
    original = backup/'before'/path.relative_to(ROOT)
    failures = backup/'failed-publications'
    failures.mkdir(exist_ok=True)
    for attempt in range(3):
        if temporary.exists():
            actual = digest(temporary)
            failed = failures/(temporary.name+'.'+actual)
            assert not failed.exists(), failed
            temporary.replace(failed)
            assert digest(failed) == actual
        intended = hashlib.sha256()
        with original.open('rb') as reader, temporary.open('xb') as writer:
            offset = 0
            for block in iter(lambda: reader.read(BLOCK), b''):
                lo, hi = max(offset, start), min(offset + len(block), start + len(replacement))
                if lo < hi:
                    block = bytearray(block)
                    block[lo-offset:hi-offset] = replacement[lo-start:hi-start]
                writer.write(block)
                intended.update(block)
                offset += len(block)
            writer.flush()
            os.fsync(writer.fileno())
        expected = intended.hexdigest()
        actual = digest(temporary)
        if actual == expected:
            temporary.replace(path)
            assert digest(path) == expected
            return expected
        print(json.dumps({'copyVerificationFailure':str(path),'attempt':attempt+1,
                          'expectedSha256':expected,'actualSha256':actual}),flush=True)
    raise RuntimeError('Copy failed after three attempts; previous published file retained')


def main():
    assert digest(OLD) == EXPECTED_BAD and digest(FIXED) == EXPECTED_FIXED
    old_doc, old_start, old_length = header(OLD)
    fixed_doc, fixed_start, fixed_length = header(FIXED)
    assert strip_names(old_doc) == strip_names(fixed_doc) and old_length == fixed_length
    old_bytes, fixed_bytes = OLD.read_bytes(), FIXED.read_bytes()
    old_bin, fixed_bin = old_bytes[old_start:], fixed_bytes[fixed_start:]
    restored = old_bytes[:old_start] + fixed_bin
    assert hashlib.sha256(restored).hexdigest() == EXPECTED_ORIGINAL
    old_check, fixed_check = indices(old_doc, old_bin), indices(fixed_doc, fixed_bin)
    assert len(old_check['invalid']) == 1 and old_check['invalid'][0]['mesh'] == BAD_MESH
    assert not fixed_check['invalid']
    changes = [i for i, (a, b) in enumerate(zip(old_bin, fixed_bin)) if a != b]
    assert len(changes) == 5145
    lo, hi = changes[0], changes[-1] + 1
    target_primitive = next(m for m in old_doc['meshes'] if m['name'] == BAD_MESH)['primitives'][0]
    target_index = old_doc['accessors'][target_primitive['indices']]
    target_view = old_doc['bufferViews'][target_index['bufferView']]
    assert target_view['byteOffset'] <= lo < hi <= target_view['byteOffset'] + target_view['byteLength']

    manifest_path, assembly_path = MASTER/'manifest.json', MASTER/'assembly.json'
    manifest = json.loads(manifest_path.read_text())
    assembly = json.loads(assembly_path.read_text())
    asset = next(m for m in assembly['models'] if m['id'] == 'magnolia-podium')
    assert asset['sha256'] == EXPECTED_ORIGINAL
    chunk = next(c for c in manifest['chunks'] if c['id'] == '-1_-5')
    assert chunk['objects'] == 1
    backup = ROOT/sys.argv[1] if len(sys.argv)>1 else None
    previous = json.loads((backup/'repair.json').read_text()) if backup else None
    before = previous['beforeMasterFiles'] if previous else {str(p.relative_to(ROOT)): digest(p) for p in MASTER.rglob('*') if p.is_file()}
    targets = []
    for record in [chunk, manifest['master']]:
        path = ROOT / 'public' / record['file'].lstrip('/')
        assert before[str(path.relative_to(ROOT))] == record['sha256']
        original = backup/'before'/path.relative_to(ROOT) if backup else path
        doc, binary_start, _ = header(original)
        p = next(m for m in doc['meshes'] if m.get('name') == BAD_MESH)['primitives'][0]
        a = doc['accessors'][p['indices']]
        view = doc['bufferViews'][a['bufferView']]
        assert {k:v for k,v in a.items() if k != 'bufferView'} == {k:v for k,v in target_index.items() if k != 'bufferView'}
        base = view['byteOffset'] - target_view['byteOffset']
        with original.open('rb') as f:
            f.seek(binary_start + base)
            assert f.read(old_length) == old_bin, 'Embedded source is not exactly the proven damaged source'
        targets.append((record, path, binary_start + base + lo))

    if not backup:
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup = ROOT / 'assets/streets/master-index-repair' / stamp
        backup.mkdir(parents=True, exist_ok=False)
    preserve = [OLD, FIXED, manifest_path, assembly_path] + [p for _,p,_ in targets]
    for p in [ROOT/'.tooling/street-assets-index-validation.log', ROOT/'docs/evidence/tourism/street-master-assets.json']:
        if p.exists():
            preserve.append(p)
    copies = previous['backups'] if previous else []
    for path in preserve:
        destination = backup/'before'/path.relative_to(ROOT)
        expected = digest(path)
        if previous:
            saved = next(x for x in copies if x['path']==str(path.relative_to(ROOT)))
            assert digest(destination) == saved['sha256']
        else:
            verified_copy(path, destination, expected)
            copies.append({'path':str(path.relative_to(ROOT)), 'backup':str(destination.relative_to(ROOT)), 'sha256':expected})
    restored_path = backup/'restored-original-magnolia-podium.glb'
    if not previous:
        with restored_path.open('xb') as f:
            f.write(restored)
            f.flush()
            os.fsync(f.fileno())
    assert digest(restored_path) == EXPECTED_ORIGINAL
    receipt = {'boundary':'Exact source-byte restoration only; no visual quality changes or full assembly rebuild',
               'backupDirectory':str(backup.relative_to(ROOT)), 'backups':copies,
               'source':{'damagedSha256':EXPECTED_BAD,'fixedSourceSha256':EXPECTED_FIXED,
                         'restoredOriginalSha256':EXPECTED_ORIGINAL,'beforeIndices':old_check,'restoredIndices':fixed_check},
               'binaryDifference':{'changedBytes':len(changes),'start':lo,'endExclusive':hi,'bufferView':42},
               'beforeMasterFiles':before,'repaired':[]}
    receipt_path = backup/'repair.json'
    receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    for record, path, start in targets:
        new_sha = publish_patch(path, start, fixed_bin[lo:hi], backup)
        original = backup/'before'/path.relative_to(ROOT)
        difference_count = 0
        with original.open('rb') as a, path.open('rb') as b:
            offset = 0
            for aa in iter(lambda: a.read(BLOCK), b''):
                bb = b.read(len(aa))
                assert len(aa) == len(bb)
                if aa != bb:
                    changed = [i for i,(x,y) in enumerate(zip(aa,bb)) if x != y]
                    assert all(start <= offset+i < start+hi-lo for i in changed)
                    difference_count += len(changed)
                offset += len(aa)
            assert not b.read(1)
        assert difference_count == len(changes)
        record['sha256'] = new_sha
        receipt['repaired'].append({'file':str(path.relative_to(ROOT)),'bytes':path.stat().st_size,
                                    'sha256':new_sha,'changedBytes':difference_count,'absolutePatchStart':start,
                                    'jsonAndUnrelatedBinaryBytesUnchanged':True})
        receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    # Only the two SHA strings change; preserve formatting and all other metadata.
    original_manifest = manifest_path.read_text()
    updated = original_manifest
    for record,path,_ in targets:
        updated = updated.replace(before[str(path.relative_to(ROOT))], record['sha256'])
    assert json.loads(updated) == manifest
    temporary = manifest_path.with_suffix('.index-repair-writing')
    with temporary.open('x') as f:
        f.write(updated)
        f.flush()
        os.fsync(f.fileno())
    assert hashlib.sha256(updated.encode()).hexdigest() == digest(temporary)
    temporary.replace(manifest_path)
    changed_files = {str(p.relative_to(ROOT)) for _,p,_ in targets} | {str(manifest_path.relative_to(ROOT))}
    unchanged = []
    for name, expected in before.items():
        if name not in changed_files:
            assert digest(ROOT/name) == expected, f'Unrelated master file changed: {name}'
            unchanged.append(name)
    receipt['unrelatedMasterFilesUnchanged'] = unchanged
    receipt['manifestSha256'] = digest(manifest_path)
    receipt['assemblyUnchanged'] = digest(assembly_path) == before[str(assembly_path.relative_to(ROOT))]
    receipt['status'] = 'binary-restoration-complete-awaiting-full-runtime-validator'
    receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'receipt':str(receipt_path.relative_to(ROOT)), 'repaired':receipt['repaired'],
                      'unrelatedFilesUnchanged':len(unchanged), 'manifestSha256':receipt['manifestSha256']},indent=2),flush=True)


if __name__ == '__main__':
    main()
