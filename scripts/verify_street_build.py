"""Verify static build copies; repair only dist copies from stable public files."""
import datetime
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC, DIST = ROOT / 'public', ROOT / 'dist'
REPORT = ROOT / 'docs/evidence/tourism/street-master-build-integrity.json'


def digest(file):
    h = hashlib.sha256()
    with file.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


result = {'startedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'method': 'All public files checked against dist by SHA256; any mismatched build copy replaced using streamed write, fsync and verified atomic rename. Source files never modified.',
          'pass': False, 'checkedFiles': 0, 'checkedBytes': 0, 'repairs': []}
try:
    for source in sorted(PUBLIC.rglob('*')):
        if not source.is_file() or source.name == '.DS_Store':
            continue
        relative = source.relative_to(PUBLIC)
        target = DIST / relative
        expected = digest(source)
        actual = digest(target) if target.is_file() else None
        size = source.stat().st_size
        if actual != expected:
            repair = {'file': str(relative), 'bytes': size, 'expected': expected,
                      'observedBuildCopy': actual, 'attempts': 0, 'verified': False}
            result['repairs'].append(repair)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + '.verified-copy')
            for attempt in range(3):
                repair['attempts'] = attempt + 1
                with source.open('rb') as reader, temporary.open('wb') as writer:
                    for block in iter(lambda: reader.read(4 * 1024 * 1024), b''):
                        writer.write(block)
                    writer.flush()
                    os.fsync(writer.fileno())
                if digest(source) != expected:
                    raise RuntimeError(f'Source changed during verification: {relative}')
                if digest(temporary) == expected:
                    temporary.replace(target)
                    repair['verified'] = digest(target) == expected
                    if repair['verified']:
                        break
            if not repair['verified']:
                raise RuntimeError(f'Persistent copy mismatch, build not ready: {relative}')
        result['checkedFiles'] += 1
        result['checkedBytes'] += size
    result['pass'] = True
except Exception as error:
    result['failure'] = str(error)
    raise
finally:
    result['finishedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    # Keep earlier failed-copy evidence across later successful builds.
    if REPORT.exists():
        previous = json.loads(REPORT.read_text())
        result['previousRepairs'] = previous.get('previousRepairs', []) + previous.get('repairs', [])
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False), flush=True)
