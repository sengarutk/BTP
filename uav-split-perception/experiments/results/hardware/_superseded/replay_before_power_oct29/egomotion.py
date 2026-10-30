#!/usr/bin/env python3
"""Camera ego-motion between consecutive video frames, for aligning stale detections (forecast.py).

Per frame pair (k-1, k): Shi-Tomasi corners on the grey frame downscaled to 320 px wide, pyramidal
Lucas-Kanade tracking into frame k, and a RANSAC similarity transform (rotation, scale, translation;
cv2.estimateAffinePartial2D) that maps frame k-1 pixel coordinates to frame k. Moving objects are outliers
to RANSAC. On failure (too few tracks) the step is the identity. Chaining the steps gives the transform
between any two frames of a sequence: T(c -> t) = C[t] @ inv(C[c]) with C[k] = S[k] @ ... @ S[1].

This is what a drone can compute live: one tracking step per camera frame on its own images.
usage: egomotion.py DATASET_DIR   -> DATASET_DIR/egomotion.npz  {seq: (n, 3, 3) cumulative transforms}
"""
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

W_SMALL = 320


def step(prev_small, cur_small, scale):
    """3x3 transform mapping full-resolution coordinates of the previous frame to the current one."""
    pts = cv2.goodFeaturesToTrack(prev_small, maxCorners=200, qualityLevel=0.01, minDistance=8, blockSize=7)
    if pts is None or len(pts) < 12:
        return np.eye(3)
    nxt, st, _ = cv2.calcOpticalFlowPyrLK(prev_small, cur_small, pts, None, winSize=(21, 21), maxLevel=3)
    ok = st.ravel() == 1
    if ok.sum() < 12:
        return np.eye(3)
    A, inl = cv2.estimateAffinePartial2D(pts[ok], nxt[ok], method=cv2.RANSAC, ransacReprojThreshold=1.0,
                                         maxIters=500, confidence=0.99)
    if A is None or inl is None or inl.sum() < 10:
        return np.eye(3)
    S = np.eye(3)
    S[:2] = A
    D = np.diag([scale, scale, 1.0])          # small-image transform -> full-resolution transform
    return D @ S @ np.linalg.inv(D)


def small_grey(img):
    s = W_SMALL / img.shape[1]
    return cv2.cvtColor(cv2.resize(img, (W_SMALL, round(img.shape[0] * s)), interpolation=cv2.INTER_AREA),
                        cv2.COLOR_BGR2GRAY), 1.0 / s


def chain_sequence(folder, n):
    C = np.zeros((n + 1, 3, 3))
    C[1] = np.eye(3)
    prev, scale = small_grey(cv2.imread(str(folder / ("%07d.jpg" % 1))))
    for k in range(2, n + 1):
        cur, _ = small_grey(cv2.imread(str(folder / ("%07d.jpg" % k))))
        C[k] = step(prev, cur, scale) @ C[k - 1]
        prev = cur
    return C                                   # index = frame number (1-based); C[0] unused


def transform(C, c, t):
    """3x3 map from frame c coordinates to frame t coordinates (same sequence)."""
    return C[t] @ np.linalg.inv(C[c])


def warp_boxes(boxes, T, wh=None):
    """Move xyxy boxes by T: the centre is mapped exactly, the size scaled by T's scale factor."""
    if not len(boxes):
        return boxes
    out = boxes.copy()
    cx, cy = (boxes[:, 0] + boxes[:, 2]) / 2, (boxes[:, 1] + boxes[:, 3]) / 2
    p = T @ np.stack([cx, cy, np.ones_like(cx)])
    s = float(np.sqrt(abs(np.linalg.det(T[:2, :2]))))
    hw, hh = (boxes[:, 2] - boxes[:, 0]) * s / 2, (boxes[:, 3] - boxes[:, 1]) * s / 2
    out[:, 0], out[:, 2], out[:, 1], out[:, 3] = p[0] - hw, p[0] + hw, p[1] - hh, p[1] + hh
    if wh is not None:
        out[:, [0, 2]] = out[:, [0, 2]].clip(0, wh[0])
        out[:, [1, 3]] = out[:, [1, 3]].clip(0, wh[1])
    return out


def main(ds):
    ds = Path(ds)
    seqs = json.load(open(ds / "sequences.json"))
    out, t0 = {}, time.time()
    for sq, n in seqs:
        n = min(n, int(sys.argv[2])) if len(sys.argv) > 2 else n
        out[sq] = chain_sequence(ds / sq, n)
        print(sq, n, f"{time.time() - t0:.0f}s", flush=True)
    np.savez_compressed(ds / "egomotion.npz", **out)


if __name__ == "__main__":
    main(sys.argv[1])
