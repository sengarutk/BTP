#!/usr/bin/env python3
"""Run a long job (e.g. GPU training) under a memory watchdog (10 Nov 2026).

WSL froze four times on 10 Nov when Windows ran out of memory (23.7 GB total, about 2 GB free with WSL running).
This wrapper starts the command in its own process group and every few seconds logs the memory left in WSL
(/proc/meminfo MemAvailable), the GPU's memory, and (every --win-every s) Windows' free physical memory. If either
falls below its floor, it stops the job (SIGTERM, then SIGKILL) before the machine locks up. The log is written with
fsync to a file on the Linux disk (not /tmp, which a WSL restart wipes).

usage: guarded_run.py --log FILE [--wsl-floor-mb 1500] [--win-floor-mb 1000] -- CMD ...
exit code: the job's, or 99 if the watchdog stopped it.
"""
import argparse
import os
import signal
import subprocess
import sys
import time


def wsl_avail_mb():
    for line in open("/proc/meminfo"):
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) // 1024
    return -1


def gpu_used_mb():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout.strip().split(",")
        return int(out[0]), int(out[1])
    except Exception:
        return -1, -1


def win_free_mb():
    try:
        out = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                              "[int](Get-Counter '\\Memory\\Available MBytes').CounterSamples[0].CookedValue"],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        return int(out)
    except Exception:
        return -1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--wsl-floor-mb", type=int, default=1500)
    ap.add_argument("--win-floor-mb", type=int, default=1000)
    ap.add_argument("--every", type=float, default=3.0)
    ap.add_argument("--win-every", type=float, default=15.0)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    log = open(a.log, "a")

    def w(msg):
        log.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
        log.flush()
        os.fsync(log.fileno())
    w("start: " + " ".join(cmd))
    p = subprocess.Popen(cmd, start_new_session=True)
    last_win, win, stopped = 0.0, -1, False
    while p.poll() is None:
        now = time.time()
        if now - last_win >= a.win_every:
            win, last_win = win_free_mb(), now
        wa = wsl_avail_mb()
        gm, gu = gpu_used_mb()
        w(f"wsl_avail_mb={wa} win_free_mb={win} gpu_mb={gm} gpu_util={gu}")
        if (0 <= wa < a.wsl_floor_mb) or (0 <= win < a.win_floor_mb):
            w(f"MEMORY FLOOR REACHED (wsl {wa} < {a.wsl_floor_mb} or windows {win} < {a.win_floor_mb}): stopping the job")
            stopped = True
            os.killpg(p.pid, signal.SIGTERM)
            for _ in range(20):
                if p.poll() is not None:
                    break
                time.sleep(0.5)
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGKILL)
            break
        time.sleep(a.every)
    rc = p.wait()
    w(f"end: exit {rc}" + (" (stopped by the watchdog)" if stopped else ""))
    sys.exit(99 if stopped else rc)


if __name__ == "__main__":
    main()
