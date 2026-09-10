"""Package only the verified static release; preserve any existing archive."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'dist-release/release-manifest.json'


def digest(stream):
    checksum = hashlib.sha256()
    for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
        checksum.update(block)
    return checksum.hexdigest()


def main():
    raw = MANIFEST.read_bytes()
    manifest_hash = hashlib.sha256(raw).hexdigest()
    manifest = json.loads(raw)
    destination = ROOT / 'release'
    destination.mkdir(exist_ok=True)
    archive = destination / f'shanghai-commute-drive-{manifest_hash[:16]}.tar.gz'
    temporary = archive if archive.exists() else archive.with_name(archive.name + f'.partial-{time.time_ns()}')
    if temporary != archive:
        environment = dict(os.environ, LC_ALL='C', COPYFILE_DISABLE='1')
        subprocess.run(['tar', '-czf', str(temporary), '--exclude', '._*',
                        '--exclude', '.DS_Store', '--exclude', '.deployment-owned',
                        'dist-release'], cwd=ROOT, env=environment, check=True)
    expected = {'dist-release/release-manifest.json': manifest_hash}
    for entry in manifest['files']:
        name = 'dist-release/' + entry['file']
        expected[name] = entry['sha256']
        for extension, field in [('br', 'brotli'), ('gz', 'gzip')]:
            if field + 'Sha256' in entry:
                expected[name + '.' + extension] = entry[field + 'Sha256']
    seen = set()
    with tarfile.open(temporary, 'r:gz') as bundle:
        for member in bundle:
            if member.isdir():
                continue
            if not member.isfile() or member.name not in expected or member.name in seen:
                raise RuntimeError('Unexpected archive member: ' + member.name)
            with bundle.extractfile(member) as stream:
                if digest(stream) != expected[member.name]:
                    raise RuntimeError('Archive hash mismatch: ' + member.name)
            seen.add(member.name)
    if seen != set(expected):
        raise RuntimeError('Incomplete archive')
    if MANIFEST.read_bytes() != raw:
        raise RuntimeError('Release changed while packaging; temporary archive preserved')
    if temporary != archive:
        if archive.exists():
            raise RuntimeError('Another archive appeared; temporary archive preserved')
        temporary.rename(archive)
    with archive.open('rb') as stream:
        checksum = digest(stream)
    archive.with_name(archive.name + '.sha256').write_text(checksum + '  ' + archive.name + '\n')
    result = {'archive': str(archive.relative_to(ROOT)), 'bytes': archive.stat().st_size,
              'sha256': checksum, 'verifiedFiles': len(seen), 'buildManifestSha256': manifest_hash}
    (ROOT / 'docs/evidence/deployment-optimization/archive.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
