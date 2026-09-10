"""Serialize project Blender jobs; the OS releases the lock when the owner exits."""
import fcntl
import os
from pathlib import Path
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    command = sys.argv[1:]
    if command[:1] == ['--']:
        command = command[1:]
    if not command:
        raise SystemExit('A Blender command is required')
    lock = ROOT / '.tooling/blender/build.lock'
    lock.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    signal.signal(signal.SIGHUP, lambda *_: sys.exit(129))
    print(f'BLENDER_QUEUE waiting pid={os.getpid()}', flush=True)
    fcntl.flock(fd, fcntl.LOCK_EX)
    os.ftruncate(fd, 0)
    os.write(fd, f'{os.getpid()}\n'.encode())
    os.set_inheritable(fd, True)
    print(f'BLENDER_QUEUE acquired pid={os.getpid()}', flush=True)
    # Replace this waiter with the existing storage monitor. The inherited file
    # descriptor remains held for the monitor's complete child lifetime.
    os.execvp(command[0], command)


if __name__ == '__main__':
    main()
