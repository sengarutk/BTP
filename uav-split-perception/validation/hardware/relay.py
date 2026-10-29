#!/usr/bin/env python3
"""Edge-drone relay (runs on the Jetson): the camera's "relay" path, Pi -> Jetson -> laptop GPU and back.

Toward the camera (adaptive2.py, port 48103) it behaves like a worker: it connects and reconnects to the camera.
Toward the ground it behaves like a camera: a normal laptop worker (`adaptive.py worker --camera <jetson>:<listen>`)
connects to it. Every message (frames, probes, the final bye) is forwarded unchanged from the camera to the worker,
and every reply (detections, probe answers) unchanged back, so the camera scores relayed results exactly like direct
ones; its probe round trip covers both hops. The relay is connected to the camera only while a worker is connected
to it: a relay without a ground link closes its camera connection, so the camera sees the path as down instead of
sending frames that can never return.
usage: relay.py --camera PI_IP:48103 [--listen 48104] [--give-up-s 900]
"""
import argparse
import json
import socket
import threading
import time

from pipeline_node import recv_msg, send_msg

stats = {"up_msgs": 0, "down_msgs": 0, "connects": 0, "fwd_ms": []}


def pump(src, dst, dst_lock, key, stop, bye=None):
    """Forward messages src -> dst until either side fails; returns via the stop event."""
    try:
        if bye is None:                              # worker -> camera: keeps running after the camera's bye
            while True:
                h, blobs = recv_msg(src)
                if not stop.is_set():
                    send_msg(dst, h, blobs, dst_lock)
                    stats[key] += 1
        while not stop.is_set():
            h, blobs = recv_msg(src)
            t0 = time.perf_counter()
            send_msg(dst, h, blobs, dst_lock)
            stats[key] += 1
            if key == "up_msgs" and not h.get("probe") and len(stats["fwd_ms"]) < 100000:
                stats["fwd_ms"].append((time.perf_counter() - t0) * 1e3)
            if h.get("bye") and bye is not None:
                bye.set()
                break
    except (ConnectionError, OSError, ValueError):
        pass
    stop.set()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--camera", required=True, help="PI_IP:48103")
    ap.add_argument("--listen", type=int, default=48104, help="port the laptop worker connects to")
    ap.add_argument("--give-up-s", type=float, default=900.0, help="exit after this long without a camera link")
    a = ap.parse_args()
    host, port = a.camera.rsplit(":", 1)
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", a.listen))
    srv.listen(1)
    bye, t_ok = threading.Event(), time.time()
    print(f"relay listening on {a.listen}, camera {a.camera}", flush=True)
    while not bye.is_set():
        down, _ = srv.accept()                       # a ground worker first: no ground link, no camera link
        down.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        up = None
        while up is None:
            try:
                up = socket.create_connection((host, int(port)), timeout=1)
            except OSError:
                if time.time() - t_ok > a.give_up_s:
                    print(json.dumps({"relay": "gave up", **{k: v for k, v in stats.items() if k != "fwd_ms"}}))
                    return
                time.sleep(0.2)
        up.settimeout(None)
        up.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        stats["connects"] += 1
        stop = threading.Event()
        t1 = threading.Thread(target=pump, args=(up, down, threading.Lock(), "up_msgs", stop, bye), daemon=True)
        t2 = threading.Thread(target=pump, args=(down, up, threading.Lock(), "down_msgs", stop), daemon=True)
        t1.start()
        t2.start()
        stop.wait()
        if bye.is_set():
            # the bye was forwarded: let the WORKER close first. A worker keeps only the newest message, so closing
            # right away let the end-of-connection replace the unread bye; the worker then waited for its timeout
            t1.join(timeout=2.0)
            t_bye = time.time()
            while t2.is_alive() and time.time() - t_bye < 10.0:
                t2.join(timeout=0.2)
        for s in (up, down):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            s.close()
        t_ok = time.time()
    f = stats["fwd_ms"]
    print(json.dumps({"relay": "done", "up_msgs": stats["up_msgs"], "down_msgs": stats["down_msgs"],
                      "connects": stats["connects"],
                      "forward_ms_median": round(sorted(f)[len(f) // 2], 2) if f else None}), flush=True)


if __name__ == "__main__":
    main()
