#!/usr/bin/env python3
"""Tunnel overhead micro-benchmark (16 Nov 2026; replaces plan A8's full bridge re-run).
server (on the camera, port 48101 while no campaign runs): reads <8-byte length><payload>, replies 1 byte when the
whole payload has arrived. client: N round trips per payload size to HOST:PORT; prints median / p90 round-trip ms
and the payload goodput (Mbit/s). Run the client from the laptop through the SSH tunnel (127.0.0.1:48101) and from
pi-sender directly over the mesh (camera:48101); the difference is the tunnel + cable cost of the laptop path."""
import argparse, json, socket, struct, time
import statistics as st


def recv_exact(s, n):
    b = bytearray()
    while len(b) < n:
        c = s.recv(min(1 << 20, n - len(b)))
        if not c:
            raise ConnectionError
        b += c
    return bytes(b)


def server(port, once):
    srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); srv.bind(("0.0.0.0", port)); srv.listen(2)
    print("serving", port, flush=True)
    while True:
        s, _ = srv.accept(); s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        try:
            while True:
                n, = struct.unpack("<Q", recv_exact(s, 8))
                if n == 0:
                    break
                recv_exact(s, n); s.sendall(b"k")
        except ConnectionError:
            pass
        s.close()
        if once:
            break


def client(host, port, n, sizes, label):
    s = socket.create_connection((host, port), timeout=20); s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    out = {"label": label, "target": f"{host}:{port}", "rounds": n, "sizes": {}}
    for size in sizes:
        p = b"\0" * size; ts = []
        for i in range(n + 3):
            t0 = time.perf_counter(); s.sendall(struct.pack("<Q", size) + p); recv_exact(s, 1); dt = time.perf_counter() - t0
            if i >= 3:
                ts.append(dt)
            time.sleep(0.03)
        ts.sort()
        out["sizes"][str(size)] = {"rtt_ms_median": 1e3 * st.median(ts), "rtt_ms_p90": 1e3 * ts[int(0.9 * len(ts))],
                                   "goodput_mbps_median": size * 8 / st.median(ts) / 1e6}
    s.sendall(struct.pack("<Q", 0)); s.close()
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["server", "client"])
    ap.add_argument("--port", type=int, default=48101); ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--n", type=int, default=100); ap.add_argument("--sizes", default="1024,83000")
    ap.add_argument("--label", default=""); ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    server(a.port, a.once) if a.cmd == "server" else client(a.host, a.port, a.n, [int(x) for x in a.sizes.split(",")], a.label)
