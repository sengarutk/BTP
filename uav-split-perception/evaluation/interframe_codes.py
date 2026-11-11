#!/usr/bin/env python3
"""Inter-frame coding of the split codes (paper 1, roadmap P1-10, 12 Nov 2026).

Why. With low-delay video as the image family (evaluation/video_codecs.py, P1-1), the image side uses the previous
frame and the split codes did not. Here the codes are also coded against the previous frame: video against video.

Method. On the scored frames of the VisDrone-VID validation sequences (video_codecs.py's frames), for the frozen
learned codes (k4, width 128, 2 decoder layers) and the jointly trained codes. The uint8 code of every frame is
recorded in the validator's own run (the same run as video_codecs.py codes), keyed by the file the validator loaded,
then put in sequence order. Each frame is coded losslessly as the smallest of
  intra      zstd level 1 of the code (video_codecs.py's coding)
  residual   zstd of the byte-wise difference from the previous frame's code (mod 256)
  reference  zstd with the previous frame's code as a raw-content dictionary
plus a 1-byte mode flag (and the quantiser's 8-byte scale, as for intra). Every KEYINT-th coded frame of a sequence is
intra (the video encoders' keyint 60). The unscored frame in ten is not coded, so those references are two frames back
(conservative for the split). Every mode is decoded and checked bit-exact, so the accuracy is the intra code's. The
added CPU time (all three candidates, median per frame, this laptop) is kept for the analysis
(video_codecs.py analyse --inter). The stream is assumed error-free, as for the video options.
usage: interframe_codes.py extract [--tag TAG ...] -> experiments/results/interframe_codes/
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
OUT = REPO / "experiments" / "results" / "interframe_codes"
VC = REPO / "experiments" / "results" / "video_codecs"
KEYINT = 60


def code_tags():
    lb = REPO / "experiments" / "results" / "learned_bottleneck"
    frozen = [json.load(open(f))["config"] for f in sorted(lb.glob("eval_k4_*.json"))
              if json.load(open(f)).get("width") == 128 and json.load(open(f)).get("dec_layers") == 2]
    joints = [json.load(open(f))["config"] for f in sorted((REPO / "experiments" / "results" / "joint_bottleneck")
                                                           .glob("eval_joint_*.json"))]
    return [("learned", t) for t in frozen] + [("joint", t) for t in joints]


def record_codes(kind, tag):
    """Runs video_codecs' evaluation of one code and returns ({file: uint8 code}, mAP result)."""
    import torch
    import ultralytics.models.yolo.detect.val as dv
    from evaluation import learned_bottleneck as L
    from evaluation import video_codecs as V
    files, codes = [], []
    orig = dv.DetectionValidator.preprocess

    def pre(self, batch):
        files.extend(batch["im_file"])
        return orig(self, batch)
    dv.DetectionValidator.preprocess = pre
    try:
        if kind == "joint":
            from evaluation import joint_bottleneck as J
            import __main__
            __main__.CutWithBottleneck = J.CutWithBottleneck   # pickled as __main__.CutWithBottleneck

            def prep(yolo):
                w = [m for m in yolo.model.model if isinstance(m, J.CutWithBottleneck)]
                assert len(w) == 1
                w[0].bn.register_forward_hook(lambda m, i, o: codes.append(o[1].cpu().numpy().copy()))
            res = V.evaluate("raw", f"if_code_{tag}", weights=J.JCKPT / f"{tag[len('joint_'):]}.pt", prep=prep)
        else:
            bn, ck = L.load_bottleneck(L.CKPT / f"{tag}.pt", "cuda")

            def hook(m, i, out):
                with torch.no_grad():
                    rec = []
                    for b in range(out.shape[0]):
                        r, q = bn(out[b:b + 1].float())
                        codes.append(q.cpu().numpy().copy())
                        rec.append(r.to(out.dtype))
                    return torch.cat(rec)
            res = V.evaluate("raw", f"if_code_{tag}", hook=hook, layer=ck["cut"])
    finally:
        dv.DetectionValidator.preprocess = orig
    codes = L.drop_warmup(codes, res["num_images"])
    assert len(files) == len(codes) == res["num_images"], (len(files), len(codes), res["num_images"])
    return {Path(f).stem: q for f, q in zip(files, codes)}, res


def code_stream(seq_codes):
    """Lossless inter coding of one sequence's codes (in frame order). Returns per-frame (bytes, mode, ms)."""
    import zstandard
    cz, dz = zstandard.ZstdCompressor(level=1), zstandard.ZstdDecompressor()
    out, prev = [], None
    for i, q in enumerate(seq_codes):
        raw = q.tobytes()
        t0 = time.perf_counter()
        cand = {"intra": cz.compress(raw)}
        if prev is not None and i % KEYINT != 0 and prev.shape == q.shape:
            cand["residual"] = cz.compress((q.astype(np.int16) - prev.astype(np.int16)).astype(np.uint8).tobytes())
            d = zstandard.ZstdCompressionDict(prev.tobytes(), dict_type=zstandard.DICT_TYPE_RAWCONTENT)
            cand["reference"] = zstandard.ZstdCompressor(level=1, dict_data=d).compress(raw)
        mode = min(cand, key=lambda k: len(cand[k]))
        ms = (time.perf_counter() - t0) * 1e3
        data = cand[mode]
        if mode == "intra":                   # the decoder's check: bit-exact for every mode
            dec = dz.decompress(data)
        elif mode == "residual":
            dec = ((np.frombuffer(dz.decompress(data), np.uint8).astype(np.int16)
                    + prev.reshape(-1).astype(np.int16)) % 256).astype(np.uint8).tobytes()
        else:
            dec = zstandard.ZstdDecompressor(dict_data=d).decompress(data)
        assert dec == raw, mode
        out.append((len(data) + 8 + 1, mode, ms, len(cand["intra"]) + 8))
        prev = q
    return out


def cmd_extract(a):
    OUT.mkdir(parents=True, exist_ok=True)
    from evaluation import video_codecs as V
    for kind, tag in code_tags():
        if a.tag and tag not in a.tag:
            continue
        f_out = OUT / f"inter_{tag}.json"
        if f_out.exists():
            continue
        ref = json.load(open(VC / f"code_{tag}.json"))
        codes, res = record_codes(kind, tag)
        rows, modes = [], {}
        for seq, nf in V.sequences():
            stems = [f"{seq}_{f:07d}" for f in range(1, nf + 1) if V.scored(f)]
            rows += code_stream([codes[s] for s in stems])
        assert len(rows) == len(codes)
        b_int = [r[0] for r in rows]
        b_intra = [r[3] for r in rows]
        for r in rows:
            modes[r[1]] = modes.get(r[1], 0) + 1
        row = {"option": ref["option"], "family": kind, "frames": len(rows), "keyint": KEYINT,
               "payload_bytes_mean": float(np.mean(b_int)), "payload_bytes_p95": float(np.percentile(b_int, 95)),
               "payload_bytes_max": int(np.max(b_int)),
               "intra_payload_bytes_mean": float(np.mean(b_intra)),
               "p1_intra_payload_bytes_mean": ref["payload_bytes_mean"],
               "saving_vs_intra": 1 - float(np.mean(b_int)) / float(np.mean(b_intra)),
               "modes": modes, "code_ms_median": float(np.median([r[2] for r in rows])),
               "map50_95": res["map50_95"], "map50": res["map50"], "p1_map50_95": ref["map50_95"],
               "num_images": res["num_images"]}
        # check 1: the recorded codes are those of the P1-1 run
        assert abs(row["intra_payload_bytes_mean"] - ref["payload_bytes_mean"]) < 1e-9 * ref["payload_bytes_mean"], \
            (row["intra_payload_bytes_mean"], ref["payload_bytes_mean"])
        assert abs(row["map50_95"] - ref["map50_95"]) < 1e-9, (row["map50_95"], ref["map50_95"])
        json.dump(row, open(f_out, "w"), indent=1)
        print(json.dumps(row), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("--tag", nargs="+")
    a = ap.parse_args()
    {"extract": cmd_extract}[a.cmd](a)


if __name__ == "__main__":
    main()
