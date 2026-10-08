#!/usr/bin/env python3
"""Link measurement between two devices over TCP: RTT, bulk goodput, and per-frame transfer time.

One side listens (serve), the other connects (connect); --role says which side sends the data,
so the data direction does not depend on who can open connections (the laptop is behind NAT).
All timing is done on the sending side, so clocks need not be synchronised:
  rtt_ms        1-byte ping-pong, n = 50
  frame[size]   time from the first byte of a message of `size` bytes to the receiver's 1-byte
                acknowledgement, minus half the median RTT; n = --reps per size
  bulk_mbps     goodput of one 20 MB stream, measured by the receiver and reported back
Output: JSON on stdout and in --out (sending side).
"""

import argparse
import json
import socket
import statistics
import struct
import time

SIZES = [2_048, 85_000, 315_000, 546_000, 820_000, 1_640_000]


def recv_exact(s, n):
    buf = bytearray(n)
    view, got = memoryview(buf), 0
    while got < n:
        r = s.recv_into(view[got:], min(n - got, 1 << 20))
        if r == 0:
            raise ConnectionError("closed")
        got += r
    return bytes(buf)


def sender(s, reps, out, label):
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    rtt = []
    for _ in range(50):
        t0 = time.perf_counter()
        s.sendall(b"P")
        recv_exact(s, 1)
        rtt.append((time.perf_counter() - t0) * 1e3)
    half = statistics.median(rtt) / 2
    frames = {}
    for size in SIZES:
        payload = b"\x5a" * size
        tt = []
        for _ in range(reps):
            t0 = time.perf_counter()
            s.sendall(b"F" + struct.pack("!I", size) + payload)
            recv_exact(s, 1)
            tt.append((time.perf_counter() - t0) * 1e3 - half)
            time.sleep(0.02)
        frames[size] = {"median_ms": statistics.median(tt), "p95_ms": sorted(tt)[int(0.95 * (len(tt) - 1))],
                        "mbps": size * 8 / (statistics.median(tt) * 1e3)}
    bulk = 20_000_000
    s.sendall(b"B" + struct.pack("!I", bulk))
    chunk = b"\x5a" * (1 << 20)
    left = bulk
    while left:
        n = min(left, len(chunk))
        s.sendall(chunk[:n])
        left -= n
    bulk_mbps = struct.unpack("!d", recv_exact(s, 8))[0]
    s.sendall(b"Q")
    res = {"label": label, "rtt_ms_median": statistics.median(rtt), "rtt_ms_p95": sorted(rtt)[47],
           "rtt_ms_min": min(rtt), "frame": frames, "bulk_mbps": bulk_mbps, "reps": reps,
           "time": time.strftime("%Y-%m-%d %H:%M:%S")}
    print(json.dumps(res))
    if out:
        json.dump(res, open(out, "w"), indent=1)


def receiver(s):
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    while True:
        op = recv_exact(s, 1)
        if op == b"P":
            s.sendall(b"p")
        elif op == b"F":
            n = struct.unpack("!I", recv_exact(s, 4))[0]
            recv_exact(s, n)
            s.sendall(b"a")
        elif op == b"B":
            n = struct.unpack("!I", recv_exact(s, 4))[0]
            t0 = time.perf_counter()
            got = 0
            while got < n:
                got += len(s.recv(min(n - got, 1 << 20)))
            s.sendall(struct.pack("!d", n * 8 / ((time.perf_counter() - t0) * 1e6)))
        elif op == b"Q":
            return


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["serve", "connect"])
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=47700)
    ap.add_argument("--role", choices=["send", "recv"], required=True)
    ap.add_argument("--reps", type=int, default=30)
    ap.add_argument("--label", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    if a.mode == "serve":
        ls = socket.socket()
        ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ls.bind((a.host, a.port))
        ls.listen(1)
        s, _ = ls.accept()
    else:
        s = socket.create_connection((a.host, a.port), timeout=60)
        s.settimeout(None)
    (sender(s, a.reps, a.out, a.label) if a.role == "send" else receiver(s))
    s.close()


if __name__ == "__main__":
    main()
