#!/usr/bin/env python3
"""Check both disks and supervise only the command started by this script."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
VOLUME = Path('/Volumes/mzh的固体移动硬盘')
GIB = 1024 ** 3
WARN = 10 * GIB
STOP = 5 * GIB
STATE = ROOT / '.tooling/blender'


def snapshot(reserve_system=0, reserve_external=0):
    if not os.path.ismount(VOLUME):
        raise RuntimeError('移动硬盘未挂载；停止写入，不转存系统盘。')
    if ROOT.stat().st_dev != VOLUME.stat().st_dev:
        raise RuntimeError('项目目录不在预期的移动硬盘上。')
    disks = []
    for name, path, reserve in [('系统盘', Path('/Applications'), reserve_system),
                                ('移动硬盘', VOLUME, reserve_external)]:
        free = shutil.disk_usage(path).free
        disks.append({'name': name, 'path': str(path), 'free_bytes': free,
                      'free_gib': round(free / GIB, 3),
                      'reserved_bytes': reserve,
                      'status': 'stop' if free - reserve < STOP else
                                'warning' if free < WARN else 'ok'})
    return {'timestamp': datetime.datetime.now().astimezone().isoformat(),
            'disks': disks}


def record(data):
    # Recheck the mount before touching the external log directory.
    if not os.path.ismount(VOLUME):
        raise RuntimeError('移动硬盘已断开；停止记录。')
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'storage.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(data, ensure_ascii=False) + '\n')


def report(data):
    print(json.dumps(data, ensure_ascii=False), flush=True)
    for disk in data['disks']:
        if disk['status'] != 'ok':
            print(f"{disk['status'].upper()}: {disk['name']}剩余 "
                  f"{disk['free_gib']:.2f} GiB", file=sys.stderr, flush=True)


def healthy(data):
    return all(disk['status'] != 'stop' for disk in data['disks'])


def stop_child(child):
    if child.poll() is not None:
        return
    os.killpg(child.pid, signal.SIGCONT)
    os.killpg(child.pid, signal.SIGTERM)
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        child.wait()


def interrupted(signum, frame):
    raise KeyboardInterrupt(f'Received signal {signum}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reserve-system-mib', type=int, default=0)
    parser.add_argument('--reserve-external-mib', type=int, default=0)
    parser.add_argument('action', choices=['check', 'run'])
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.reserve_system_mib < 0 or args.reserve_external_mib < 0:
        parser.error('Reserved space must be non-negative.')
    data = snapshot(args.reserve_system_mib * 1024**2,
                    args.reserve_external_mib * 1024**2)
    record(data)
    report(data)
    if not healthy(data):
        return 75
    if args.action == 'check':
        return 0
    command = args.command
    if command and command[0] == '--':
        command = command[1:]
    if not command:
        parser.error('run requires a command after --')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    child = subprocess.Popen(command, cwd=ROOT, start_new_session=True)
    previous = [disk['status'] for disk in data['disks']]
    last_record = time.monotonic()
    paused = False
    try:
        while child.poll() is None:
            try:
                data = snapshot()
            except (OSError, RuntimeError) as error:
                if not paused:
                    os.killpg(child.pid, signal.SIGSTOP)
                    paused = True
                    print(f'PAUSED: {error} 进程已暂停，内存内容保留。',
                          file=sys.stderr, flush=True)
                time.sleep(5)
                continue
            current = [disk['status'] for disk in data['disks']]
            if current != previous or time.monotonic() - last_record >= 60:
                record(data)
                report(data)
                previous = current
                last_record = time.monotonic()
            if not healthy(data):
                if not paused:
                    os.killpg(child.pid, signal.SIGSTOP)
                    paused = True
                    print('PAUSED: 容量不足，进程已暂停，内存内容保留。',
                          file=sys.stderr, flush=True)
            elif paused and all(disk['status'] == 'ok' for disk in data['disks']):
                os.killpg(child.pid, signal.SIGCONT)
                paused = False
                print('RESUMED: 移动硬盘已挂载且两块盘均恢复至 10 GiB 以上。',
                      flush=True)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        final = snapshot()
        record(final)
        report(final)
        return child.returncode if healthy(final) else 75
    finally:
        stop_child(child)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, RuntimeError, KeyboardInterrupt) as error:
        print(f'STORAGE_GUARD: {error}', file=sys.stderr, flush=True)
        sys.exit(75)
