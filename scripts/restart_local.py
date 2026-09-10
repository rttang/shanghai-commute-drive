#!/usr/bin/env python3
"""Restart only this project's known Vite process; use the existing start/guard."""
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
VITE_ARGS = ['--host', '127.0.0.1', '--port', '8080', '--strictPort']


def output(argv):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=10)
    if result.returncode not in (0, 1):
        raise RuntimeError('无法核查进程：' + argv[0])
    return result.stdout.strip()


def decode_cwd(value):
    while '\\\\x' in value:
        value = value.replace('\\\\x', '\\x')
    return re.sub(r'(?:\\x[0-9a-fA-F]{2})+', lambda match:
                  bytes(int(x, 16) for x in re.findall(r'\\x([0-9a-fA-F]{2})', match[0])).decode('utf8'), value)


def identity(pid):
    status = output(['ps', '-p', str(pid), '-o', 'stat='])
    if not status or status.startswith('Z'):
        return None
    cwd = output(['lsof', '-a', '-p', str(pid), '-d', 'cwd', '-Fn'])
    directory = next((decode_cwd(line[1:]) for line in cwd.splitlines() if line.startswith('n')), '')
    return {'pid': pid, 'start': output(['ps', '-p', str(pid), '-o', 'lstart=']),
            'cwd': directory, 'command': output(['ps', '-p', str(pid), '-o', 'command='])}


def listeners():
    return sorted({int(pid) for pid in output(['lsof', '-nP', '-tiTCP:8080', '-sTCP:LISTEN']).splitlines()})


def owned_mode(proc):
    if not proc or not proc['cwd'] or Path(proc['cwd']).resolve() != ROOT:
        raise RuntimeError('8080归属不明或属于其他项目，未终止进程。')
    argv = shlex.split(proc['command'])
    if len(argv) < 2 or Path(argv[0]).name != 'node' or (ROOT / argv[1]).resolve() != (ROOT / 'node_modules/vite/bin/vite.js').resolve():
        raise RuntimeError('8080不是本项目已知的Vite入口，未终止进程。')
    if argv[2:] == VITE_ARGS:
        return []
    if argv[2:] == ['preview'] + VITE_ARGS:
        return ['--preview']
    raise RuntimeError('Vite启动参数与固定流程不符，未终止进程。')


def guard_for(proc):
    ppid = output(['ps', '-p', str(proc['pid']), '-o', 'ppid='])
    parent = identity(int(ppid)) if ppid else None
    if not parent or parent['cwd'] != proc['cwd']:
        return proc
    argv = shlex.split(parent['command'])
    if (len(argv) >= 4 and Path(argv[0]).name in ('python', 'python3', 'Python')
            and (ROOT / argv[1]).resolve() == ROOT / 'scripts/storage_guard.py'
            and argv[2:4] == ['run', '--'] and argv[4:] == shlex.split(proc['command'])):
        return parent
    return proc


def stop_existing():
    pids = listeners()
    if not pids:
        return []
    if len(pids) != 1:
        raise RuntimeError('8080有多个监听者，未终止任何进程。')
    proc = identity(pids[0])
    mode = owned_mode(proc)
    target = guard_for(proc)
    if identity(proc['pid']) != proc or identity(target['pid']) != target or listeners() != pids:
        raise RuntimeError('检查期间进程身份变化，取消重启。')
    print(f"停止本项目服务：PID {proc['pid']}（监督进程 {target['pid']}）", flush=True)
    os.kill(target['pid'], signal.SIGTERM)
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        if not listeners() and identity(target['pid']) != target:
            return mode
        time.sleep(.2)
    raise RuntimeError('原服务未正常退出；未强制终止或启动第二个服务。')


def main():
    if len(sys.argv) != 1:
        raise RuntimeError('固定入口不接受额外参数。')
    os.chdir(ROOT)
    if not shutil.which('node') or not (ROOT / 'node_modules/vite/bin/vite.js').is_file():
        raise RuntimeError('缺少已有Node/Vite依赖，未自动安装。')
    if not os.path.ismount(ROOT.parent) or any(shutil.disk_usage(p).free < 5 * 1024**3 for p in (ROOT, '/Applications')):
        raise RuntimeError('移动硬盘未挂载或剩余容量不足5 GiB，未改变服务。')
    mode = stop_existing()
    os.execv('/bin/bash', ['bash', str(ROOT / 'start.sh'), *mode])


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print('RESTART: ' + str(error), file=sys.stderr)
        sys.exit(1)
