#!/usr/bin/env python3
"""Many camera streams on one Jetson, on the boards (plan S6 / E3-E4; 14 Nov 2026): v4.1's sending rule against the
pull-one-ahead coordinator of brief 19.13 (overload_model.py / overload_handling.py), with real radios and a real GPU.

A "stream" is a light camera: it replays the VisDrone-VID clip at --fps, encodes the newest frame as JPEG (640, q90:
the jetson path's s640q90) and sends it to the server. Several streams can run on one board (each its own TCP
connection, so the board's radio queue is shared, as for cameras on one channel). The server (a Jetson) runs YOLOv8s
FP16 on one frame at a time and returns each result to its stream, which measures capture-to-result latency.
  v41    each stream sends its newest frame once its previous one has left its socket (TIOCOUTQ = 0); at the server a
         newer frame of the same stream replaces its waiting one (as edge_node.py / adaptive2.py)
  pull1  streams send only when granted; the server grants while at most one frame waits for the GPU and none is on
         its way beyond that (pull one ahead), the turn going to the stream whose newest delivered result is oldest
         (counting a granted frame from its grant), as overload_handling.py's pull1 / pull_age
  serve  --listen PORT --mode v41|pull1 (the Jetson)
  run    --to HOST:PORT --streams N --seconds S --mode v41|pull1 --label L  -> one JSON line per stream + a total line
Per stream: on-time results per second (latency <= --deadline-ms 300), latency p50/p90, mean age of the newest result
(AoI). The server's mode must match the streams'.
"""
import argparse
import fcntl
import glob
import json
import os
import socket
import struct
import termios
import threading
import time

import cv2
import numpy as np


def send_msg(s, hdr, payload=b"", lock=None):
    h = json.dumps(hdr).encode()
    b = struct.pack("<II", len(h), len(payload)) + h + payload
    if lock:
        with lock:
            s.sendall(b)
    else:
        s.sendall(b)


def recv_exact(s, n):
    b = bytearray()
    while len(b) < n:
        c = s.recv(n - len(b))
        if not c:
            raise ConnectionError("closed")
        b += c
    return bytes(b)


def recv_msg(s):
    lh, lp = struct.unpack("<II", recv_exact(s, 8))
    return json.loads(recv_exact(s, lh)), recv_exact(s, lp)


def outq(s):
    return struct.unpack("i", fcntl.ioctl(s.fileno(), termios.TIOCOUTQ, b"\0\0\0\0"))[0]


def letterbox(img, size=640):
    h, w = img.shape[:2]
    r = min(size / h, size / w)
    nh, nw = round(h * r), round(w * r)
    out = np.full((size, size, 3), 114, np.uint8)
    top, left = (size - nh) // 2, (size - nw) // 2
    out[top:top + nh, left:left + nw] = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    return out


# ------------------------------------------------------------------------------------------------ server (Jetson)
def cmd_serve(a):
    import torch
    from ultralytics import YOLO
    model = YOLO(a.weights)
    dummy = np.zeros((640, 640, 3), np.uint8)
    for _ in range(5):
        model.predict(dummy, imgsz=640, device=0, half=True, verbose=False, conf=0.01)
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", a.listen))
    srv.listen(64)
    cv = threading.Condition()
    st = {"conns": {}, "waiting": {}, "granted": {}, "newest_res": {}, "pending_grants": 0, "busy": False, "n": 0}

    def try_grant():
        # pull one ahead: at most one frame waiting for the GPU plus none further on its way
        if a.mode != "pull1":
            return
        while st["busy"] + len(st["waiting"]) + st["pending_grants"] < 2:
            cand = [c for c in st["conns"] if c not in st["granted"] and c not in st["waiting"]]
            if not cand:
                return
            def age(c):
                v = [x for x in (st["newest_res"].get(c), st["granted"].get(c)) if x is not None]
                return max(v) if v else -1e18
            c = min(cand, key=age)
            st["granted"][c] = time.time()
            st["pending_grants"] += 1
            try:
                send_msg(st["conns"][c][0], {"grant": True}, lock=st["conns"][c][1])
            except OSError:
                st["pending_grants"] -= 1
                st["granted"].pop(c, None)

    def reader(cid, s):
        try:
            while True:
                h, p = recv_msg(s)
                if h.get("bye"):
                    break
                with cv:
                    if a.mode == "pull1" and cid in st["granted"]:
                        st["granted"].pop(cid)
                        st["pending_grants"] -= 1
                    st["waiting"][cid] = (h, p, time.time())        # newest of this stream replaces its waiting one
                    cv.notify_all()
        except (ConnectionError, OSError, struct.error):
            pass
        with cv:
            st["conns"].pop(cid, None)
            st["waiting"].pop(cid, None)
            if st["granted"].pop(cid, None) is not None:
                st["pending_grants"] -= 1
            try_grant()

    def acceptor():
        while True:
            s, _ = srv.accept()
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            with cv:
                st["n"] += 1
                cid = st["n"]
                st["conns"][cid] = (s, threading.Lock())
                try_grant()
            threading.Thread(target=reader, args=(cid, s), daemon=True).start()
    threading.Thread(target=acceptor, daemon=True).start()
    print(f"serving {a.mode} on {a.listen}", flush=True)
    while True:
        with cv:
            while not st["waiting"]:
                cv.wait()
            cid = min(st["waiting"], key=lambda c: st["waiting"][c][2])   # first come among the waiting streams
            h, p, t_in = st["waiting"].pop(cid)
            st["busy"] = True
            try_grant()
        img = cv2.imdecode(np.frombuffer(p, np.uint8), cv2.IMREAD_COLOR)
        t0 = time.time()
        r = model.predict(img, imgsz=640, device=0, half=True, verbose=False, conf=0.01)
        torch.cuda.synchronize()
        srv_ms = (time.time() - t0) * 1e3
        with cv:
            st["busy"] = False
            st["newest_res"][cid] = max(st["newest_res"].get(cid, -1e18), h["t_cap"])
            conn = st["conns"].get(cid)
            if conn:
                try:
                    send_msg(conn[0], {"id": h["id"], "server_ms": srv_ms, "wait_ms": (t0 - t_in) * 1e3,
                                       "ndet": int(len(r[0].boxes))}, lock=conn[1])
                except OSError:
                    pass
            try_grant()


# ------------------------------------------------------------------------------------------------ streams (cameras)
def one_stream(a, k, imgs, out):
    host, port = a.to.rsplit(":", 1)
    s = socket.create_connection((host, int(port)), timeout=10)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    s.settimeout(None)
    lock, grant, sent, res = threading.Lock(), threading.Event(), {}, {}
    period = 1.0 / a.fps
    t_start = a.t0 + k * period / max(1, a.streams)      # cameras out of phase, as the model's
    newest = [None]
    stop = [False]

    def receiver():
        try:
            while True:
                h, _ = recv_msg(s)
                if h.get("grant"):
                    grant.set()
                else:
                    res[h["id"]] = (time.time(), h["server_ms"], h["wait_ms"])
        except (ConnectionError, OSError, struct.error):
            pass
    threading.Thread(target=receiver, daemon=True).start()

    def capture():
        while not stop[0]:
            el = time.time() - t_start
            if el < 0:
                time.sleep(-el)
                continue
            if el >= a.seconds:
                break
            tick = int(el / period)
            cap = t_start + tick * period
            ok, buf = cv2.imencode(".jpg", imgs[(tick + 37 * k) % len(imgs)], [cv2.IMWRITE_JPEG_QUALITY, 90])
            newest[0] = (tick, cap, buf.tobytes())
            nxt = t_start + (tick + 1) * period
            time.sleep(max(0.0, nxt - time.time()))
    ct = threading.Thread(target=capture, daemon=True)
    ct.start()
    last = -1
    while ct.is_alive():
        if a.mode == "pull1":
            if not grant.wait(0.05):
                continue
        else:
            while outq(s) > 0 and ct.is_alive():         # v4.1: the previous frame has not left the radio yet
                time.sleep(0.0005)
        item = newest[0]
        if item is None or item[0] <= last:
            time.sleep(0.001)
            continue
        tick, cap, p = item
        if a.mode == "pull1":
            grant.clear()
        send_msg(s, {"id": tick, "t_cap": cap}, p, lock)
        sent[tick] = cap
        last = tick
    time.sleep(2.0)
    stop[0] = True
    try:
        send_msg(s, {"bye": True}, lock=lock)
        s.close()
    except OSError:
        pass
    lat = sorted((res[i][0] - sent[i]) * 1e3 for i in sent if i in res)
    on = sum(1 for x in lat if x <= a.deadline_ms) / a.seconds
    # mean AoI: age of the newest delivered capture, over the run
    dl = sorted((res[i][0], sent[i]) for i in sent if i in res)
    aoi = None
    if dl:
        area, cur, t0 = 0.0, dl[0][1], dl[0][0]
        for t, tc in dl[1:]:
            area += ((t0 - cur) + (t - cur)) / 2 * (t - t0)
            cur, t0 = max(cur, tc), t
        aoi = area / max(1e-9, dl[-1][0] - dl[0][0]) * 1e3
    out[k] = {"stream": k, "sent": len(sent), "results": len(lat), "on_time_fps": on,
              "lat_p50_ms": lat[len(lat) // 2] if lat else None, "lat_p90_ms": lat[int(0.9 * len(lat))] if lat else None,
              "aoi_mean_ms": aoi, "server_ms_median": float(np.median([v[1] for v in res.values()])) if res else None}


def cmd_run(a):
    fs = sorted(glob.glob(os.path.join(a.frames, "**", "*.jpg"), recursive=True))[:300]
    imgs = [letterbox(cv2.imread(f)) for f in fs]
    a.t0 = time.time() + 2.0
    out, th = {}, []
    for k in range(a.streams):
        t = threading.Thread(target=one_stream, args=(a, k, imgs, out))
        t.start()
        th.append(t)
    for t in th:
        t.join()
    for k in sorted(out):
        print(json.dumps({"label": a.label, "mode": a.mode, **out[k]}))
    ok = [v for v in out.values()]
    print(json.dumps({"label": a.label, "mode": a.mode, "streams": a.streams, "fps": a.fps,
                      "on_time_total": sum(v["on_time_fps"] for v in ok),
                      "on_time_worst": min((v["on_time_fps"] for v in ok), default=None),
                      "aoi_mean_ms": float(np.mean([v["aoi_mean_ms"] for v in ok if v["aoi_mean_ms"] is not None]))
                      if ok else None}))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["serve", "run"])
    ap.add_argument("--mode", choices=["v41", "pull1"], default="v41")
    ap.add_argument("--weights", default="yolov8s_visdrone.pt")
    ap.add_argument("--listen", type=int, default=48200)
    ap.add_argument("--to", default="")
    ap.add_argument("--streams", type=int, default=1)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--frames", default="visdrone_vid_640")
    ap.add_argument("--deadline-ms", type=float, default=300.0)
    ap.add_argument("--label", default="")
    a = ap.parse_args()
    {"serve": cmd_serve, "run": cmd_run}[a.cmd](a)


if __name__ == "__main__":
    main()
