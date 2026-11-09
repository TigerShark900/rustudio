#!/usr/bin/env python3
"""Catch the isolated rig Studio's SessionCrypto serializers.

Attaches only to a new Main process whose WINEPREFIX is the capture rig's.
The user's Studio is never selected. Writes binary diagnostic state under the
rig's 0600 keys directory; the GDB log contains addresses, not packet bodies.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

BASE = Path.home() / ".cache/rustudio-dev/tc"
PROJECT = Path(__file__).resolve().parents[3]
OUT = BASE / "keys" / "sessioncrypto-watch"
GDB = Path(os.environ.get(
    "SC_WATCH_GDB",
    str(PROJECT / "tools/tc/rig/sessioncrypto_watch.gdb"),
))


def is_rig_main(pid: int) -> bool:
    try:
        if Path(f"/proc/{pid}/comm").read_text().strip() != "Main":
            return False
        env = Path(f"/proc/{pid}/environ").read_bytes()
        maps = Path(f"/proc/{pid}/maps").read_text()
    except OSError:
        return False
    return f"WINEPREFIX={BASE}/prefix\0".encode() in env and "146000" in maps


def rig_mains() -> set[int]:
    return {int(p) for p in os.listdir("/proc") if p.isdigit() and is_rig_main(int(p))}


def main() -> int:
    old = rig_mains()
    print(f"watching for a new rig Studio; existing={sorted(old)}", flush=True)
    OUT.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name in ("a7-object.bin", "a7-stack.bin", "m8a-stack.bin", "m8a-data.bin", "m90-stack.bin", "m90-data.bin"):
        p = OUT / name
        p.touch(mode=0o600, exist_ok=True)
        p.chmod(0o600)
    pid = None
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        new = rig_mains() - old
        if new:
            pid = min(new)
            break
        time.sleep(0.05)
    if pid is None:
        print("no new rig Studio appeared", flush=True)
        return 1

    print(f"attaching to rig Studio pid {pid}", flush=True)
    env = os.environ.copy()
    env["SC_WATCH_OUT"] = str(OUT)
    proc = subprocess.Popen(
        ["gdb", "-q", "-batch", "-p", str(pid), "-x", str(GDB)],
        env=env,
    )
    try:
        return proc.wait(timeout=150)
    except subprocess.TimeoutExpired:
        # Never leave the capture Studio stopped under a dead debugger.
        proc.terminate()
        proc.wait(timeout=10)
        subprocess.run(
            ["gdb", "-q", "-batch", "-p", str(pid), "-ex", "detach", "-ex", "quit"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        print("GDB timed out; detached cleanly", flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
