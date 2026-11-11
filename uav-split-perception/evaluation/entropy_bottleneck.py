#!/usr/bin/env python3
"""The strongest frozen-detector split we can build: a learned bottleneck with a learned entropy model, trained for
rate and accuracy together, and coded with a real range coder (hardening, paper 1, 11 Nov 2026).

Why. The learned codes of learned_bottleneck.py quantise each image's code to uint8 with a min-max scale and compress
it with zstd, a generic byte coder that knows nothing of the code's statistics. Supervised-compression work codes the
latent with a learned entropy model instead (Singh et al., ICIP 2020; Matsubara et al., "Entropic Student", WACV
2022). A reviewer can ask for that baseline, so this script builds it on the same cut, detector, frames and metric.

Design
  cut / codec   k = 4 of the VisDrone YOLOv8s, frozen; encoder and decoder as learned_bottleneck.Bottleneck (width
                128, stride 2, 2 decoder layers, 32 code channels at 40 x 40), initialised from the trained k4_c32 code
  quantiser     y = E(x) * exp(g) with a learned per-channel gain g; y_hat = round(y); the decoder sees y_hat * exp(-g).
                Training: the decoder path rounds with a straight-through gradient, the rate term sees y + U(-1/2, 1/2)
                (the usual mixed scheme)
  entropy model factorised prior (Balle et al., ICLR 2018, appendix 6.1): per channel a monotone cumulative density c
                (3 hidden layers of 3), p(y_hat) = c(y_hat + 1/2) - c(y_hat - 1/2)
  loss          learned_bottleneck's distillation (neck layers 15, 18, 21 + 0.1 x the cut, each MSE / teacher var) +
                lambda x rate in KiB per image; lambda sets the operating point (--lam)
  bitstream     per image and channel the integer range [min, max] (2 x int16, the header: 4 bytes per channel) and the
                symbols, range-coded (constriction 0.4, queue RangeEncoder) with the model's probabilities on that range,
                renormalised; channels with min = max cost only the header. Every image is decoded again and checked to
                equal the encoder's symbols. Payload = header + compressed words
  training      VisDrone2019-DET train minus the last 471 images (held out for monitoring), letterbox 640, flips,
                AdamW, lr 1e-3 for the codec and 1e-2 for the entropy model, OneCycle, 20 epochs, batch 8; detector
                frozen
  measurement   mAP@[.5:.95] on the 548 VisDrone-DET val frames, batch 1, paired bootstrap against the unsplit model
                (as every learned code); payload per image from the bitstream; host times: encoder-side rounding +
                range coding (CPU), decoder-side range decoding (CPU) + decoder (GPU), medians of 50
usage: entropy_bottleneck.py train --lam 0.01 [--epochs 20]
       entropy_bottleneck.py eval  --lam 0.01          -> experiments/results/entropy_bottleneck/eval_ec_k4_c32_l<lam>.json
"""
import argparse
import json
import math
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from evaluation import learned_bottleneck as L

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "experiments" / "results" / "entropy_bottleneck"
CKPT = REPO / "weights" / "entropy_bottleneck"
INIT = "k4_c32_w128_d2"
CUT = 4


class FactorizedPrior(nn.Module):
    """Balle et al. 2018's non-parametric factorised density, one per channel (as CompressAI's EntropyBottleneck)."""

    def __init__(self, channels, filters=(3, 3, 3), init_scale=10.0):
        super().__init__()
        f = (1,) + tuple(filters) + (1,)
        scale = init_scale ** (1 / (len(filters) + 1))
        self.H, self.b, self.a = nn.ParameterList(), nn.ParameterList(), nn.ParameterList()
        for i in range(len(filters) + 1):
            init = math.log(math.expm1(1 / scale / f[i + 1]))
            self.H.append(nn.Parameter(torch.full((channels, f[i + 1], f[i]), init)))
            self.b.append(nn.Parameter(torch.rand(channels, f[i + 1], 1) - 0.5))
            if i < len(filters):
                self.a.append(nn.Parameter(torch.zeros(channels, f[i + 1], 1)))

    def logits_cdf(self, x):
        """x: (C, 1, N) -> logits of the cumulative density, (C, 1, N)."""
        for i in range(len(self.H)):
            x = torch.matmul(F.softplus(self.H[i]), x) + self.b[i]
            if i < len(self.a):
                x = x + torch.tanh(self.a[i]) * torch.tanh(x)
        return x

    def likelihood(self, y):
        """y: (B, C, H, W) -> p(y) of each value on the integer grid shifted by y, (B, C, H, W), in float32."""
        with torch.autocast("cuda", enabled=False):          # the density in float32, also under AMP
            return self._likelihood(y)

    def _likelihood(self, y):
        B, C, H, W = y.shape
        v = y.float().permute(1, 0, 2, 3).reshape(C, 1, -1)
        lo, up = self.logits_cdf(v - 0.5), self.logits_cdf(v + 0.5)
        s = -torch.sign(lo + up).detach()            # evaluate in the tail where the sigmoid is accurate
        p = (torch.sigmoid(s * up) - torch.sigmoid(s * lo)).abs().clamp_min(1e-9)
        return p.reshape(C, B, H, W).permute(1, 0, 2, 3)

    def pmf(self, c, lo, hi):
        """Probabilities of the integers lo..hi for channel c (float64 numpy, renormalised)."""
        v = torch.arange(lo, hi + 1, dtype=torch.float32, device=self.H[0].device)
        x = torch.zeros(len(self.H[0]), 1, len(v), device=v.device)
        x[c, 0] = v
        with torch.no_grad():
            u = torch.sigmoid(self.logits_cdf(x + 0.5))[c, 0] - torch.sigmoid(self.logits_cdf(x - 0.5))[c, 0]
        p = u.double().cpu().numpy().clip(1e-9, None)
        return p / p.sum()


class EntropyCode(nn.Module):
    def __init__(self, bn, channels):
        super().__init__()
        self.enc, self.dec = bn.enc, bn.dec
        self.log_gain = nn.Parameter(torch.zeros(1, channels, 1, 1))
        self.prior = FactorizedPrior(channels)

    def latent(self, x):
        return self.enc(x) * torch.exp(self.log_gain)

    def forward(self, x):
        y = self.latent(x).float()
        y_hat = y + (torch.round(y) - y).detach()                 # straight-through rounding for the decoder path
        noisy = y + torch.empty_like(y).uniform_(-0.5, 0.5)       # the rate term's relaxation
        bits = -torch.log2(self.prior.likelihood(noisy)).sum(dim=(1, 2, 3))
        rec = self.dec((y_hat * torch.exp(-self.log_gain)).to(x.dtype))
        return rec, bits


def run_detector(det, x, code):
    """learned_bottleneck.run_detector with the entropy code at the cut; also returns the rate (bits per image)."""
    holder = {}

    class Wrap(nn.Module):
        def forward(self, z):
            rec, bits = code(z)
            holder["bits"] = bits
            return rec, None
    out = L.run_detector(det, x, CUT, Wrap())
    out["bits"] = holder["bits"]
    return out


def name(lam):
    return f"ec_k{CUT}_c32_l{lam:g}"


def cmd_train(a):
    torch.manual_seed(a.seed)
    random.seed(a.seed)
    np.random.seed(a.seed)
    dev = torch.device("cuda")
    det = L.load_detector(dev)
    bn, ck = L.load_bottleneck(L.CKPT / f"{INIT}.pt", dev)
    code = EntropyCode(bn, ck["channels"]).to(dev)
    tr, ho = L.files_split()
    if a.limit:
        tr, ho = tr[:a.limit], ho[:max(8, a.limit // 4)]
    dl = torch.utils.data.DataLoader(L.Images(tr, True), batch_size=a.batch, shuffle=True, num_workers=a.workers,
                                     drop_last=True, persistent_workers=a.workers > 0)
    dh = torch.utils.data.DataLoader(L.Images(ho, False), batch_size=a.batch, shuffle=False, num_workers=a.workers)
    # initial gain: one quantisation step = the uint8 step of the init code (its per-image range / 255), so training
    # starts from about the init code's precision
    with torch.no_grad():
        z = torch.cat([bn.enc(L.run_detector(det, next(iter(dh)).to(dev), CUT)["cut"]).float()])
        rng = (z.amax(dim=(1, 2, 3)) - z.amin(dim=(1, 2, 3))).median()
        code.log_gain.fill_(math.log(255.0 / float(rng)))
    em = list(code.prior.parameters())
    rest = [p for n, p in code.named_parameters() if not n.startswith("prior.")]
    opt = torch.optim.AdamW([{"params": rest, "lr": a.lr, "weight_decay": 1e-4},
                             {"params": em, "lr": a.lr_em, "weight_decay": 0.0}])
    steps = a.epochs * len(dl)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=[a.lr, a.lr_em], total_steps=steps, pct_start=0.05)
    scaler = torch.amp.GradScaler()
    CKPT.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    tagn = name(a.lam) + (f"_smoke{a.limit}" if a.limit else "")
    log = {"name": tagn, "init": INIT, "lam_per_kib": a.lam, "epochs": a.epochs, "batch": a.batch, "lr": a.lr,
           "lr_em": a.lr_em, "w_cut": a.w_cut, "seed": a.seed, "n_train": len(tr), "n_holdout": len(ho),
           "init_log_gain": float(code.log_gain.detach().mean()), "epochs_log": []}
    t0 = time.time()

    def losses(x):
        with torch.no_grad():
            t = L.run_detector(det, x, CUT)
        s = run_detector(det, x, code)
        d = L.distill_loss({k: t[k] for k in L.NECK}, {k: s[k] for k in L.NECK}) \
            + a.w_cut * F.mse_loss(s["cut_rec"].float(), t["cut"].float()) / t["cut"].float().var().clamp_min(1e-6)
        kib = s["bits"].mean() / 8 / 1024
        return d, kib
    for ep in range(a.epochs):
        code.train()
        tot = {"loss": 0.0, "d": 0.0, "kib": 0.0}
        n = 0
        for x in dl:
            x = x.to(dev, non_blocking=True)
            with torch.autocast("cuda", dtype=torch.float16):
                d, kib = losses(x)
                loss = d + a.lam * kib
            if not torch.isfinite(loss):
                raise RuntimeError(f"non-finite loss at epoch {ep + 1}: d {float(d)}, kib {float(kib)}")
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            sched.step()
            tot["loss"] += loss.item()
            tot["d"] += d.item()
            tot["kib"] += kib.item()
            n += 1
        code.eval()
        hd, hk, hn = 0.0, 0.0, 0
        with torch.no_grad(), torch.autocast("cuda", dtype=torch.float16):
            for x in dh:
                x = x.to(dev)
                d, kib = losses(x)
                hd += float(d) * len(x)
                hk += float(kib) * len(x)
                hn += len(x)
        e = {"epoch": ep + 1, **{f"train_{k}": v / n for k, v in tot.items()}, "holdout_distill": hd / hn,
             "holdout_kib_relaxed": hk / hn, "minutes": (time.time() - t0) / 60}
        log["epochs_log"].append(e)
        print(json.dumps({k: round(v, 5) if isinstance(v, float) else v for k, v in e.items()}), flush=True)
        torch.save({"state": code.state_dict(), "c_in": ck["c_in"], "channels": ck["channels"], "cut": CUT,
                    "init": INIT, "lam": a.lam, **{k: ck.get(k, L.ARCH_DEFAULT[k]) for k in L.ARCH}},
                   CKPT / f"{tagn}.pt")
    json.dump(log, open(OUT / f"train_{tagn}.json", "w"), indent=1)


def load_code(path, dev):
    ck = torch.load(path, map_location=dev)
    bn = L.Bottleneck(ck["c_in"], ck["channels"], **{k: ck[k] for k in L.ARCH})
    code = EntropyCode(bn, ck["channels"]).to(dev).eval()
    code.load_state_dict(ck["state"])
    return code, ck


class Coder:
    """The bitstream: per channel int16 (min, max) and the range-coded symbols (constriction queue range coder).
    The model's probabilities of every integer in [-SUPPORT, SUPPORT] are tabulated once per channel at load time (as a
    deployed coder would ship them); an image's range is a slice of the table, renormalised."""
    SUPPORT = 2048

    def __init__(self, code):
        v = torch.arange(-self.SUPPORT, self.SUPPORT + 1, dtype=torch.float32, device=code.log_gain.device)
        C = code.log_gain.shape[1]
        with torch.no_grad(), torch.autocast("cuda", enabled=False):
            x = v.expand(C, 1, -1).contiguous()
            u = torch.sigmoid(code.prior.logits_cdf(x + 0.5)) - torch.sigmoid(code.prior.logits_cdf(x - 0.5))
        self.table = u[:, 0].double().cpu().numpy().clip(1e-9, None)          # (C, 2 SUPPORT + 1)

    def model(self, c, lo, hi):
        import constriction
        assert -self.SUPPORT <= lo and hi <= self.SUPPORT, (c, lo, hi)
        p = self.table[c, lo + self.SUPPORT:hi + self.SUPPORT + 1]
        return constriction.stream.model.Categorical(p / p.sum(), perfect=False)

    def encode(self, sym):
        """sym: (C, H, W) int numpy -> bytes."""
        import constriction
        C = sym.shape[0]
        lo, hi = sym.reshape(C, -1).min(1), sym.reshape(C, -1).max(1)
        assert lo.min() >= -32768 and hi.max() <= 32767
        enc = constriction.stream.queue.RangeEncoder()
        for c in range(C):
            if hi[c] > lo[c]:
                enc.encode((sym[c].reshape(-1) - lo[c]).astype(np.int32), self.model(c, int(lo[c]), int(hi[c])))
        head = np.stack([lo, hi], 1).astype(np.int16).tobytes()
        return head + enc.get_compressed().tobytes()

    def decode(self, data, shape):
        import constriction
        C, H, W = shape
        lohi = np.frombuffer(data[:4 * C], np.int16).reshape(C, 2).astype(np.int64)
        words = np.frombuffer(data[4 * C:], np.uint32)
        dec = constriction.stream.queue.RangeDecoder(words)
        out = np.empty((C, H * W), np.int64)
        for c in range(C):
            lo, hi = lohi[c]
            out[c] = lo if hi == lo else dec.decode(self.model(c, int(lo), int(hi)), H * W) + lo
        return out.reshape(C, H, W)


def cmd_eval(a):
    from ultralytics import YOLO
    from evaluation.detection_eval import paired_bootstrap, run_validation, summary_row
    dev = "cuda"
    nm = name(a.lam) + a.suffix
    code, ck = load_code(CKPT / f"{nm}.pt", dev)
    coder = Coder(code)
    yolo = YOLO(str(L.WEIGHTS))
    log = {"bytes": [], "ideal_bytes": [], "values": [], "enc_ms": [], "dec_ms": []}

    def hook(module, inp, out):
        with torch.no_grad():
            rec = []
            for b in range(out.shape[0]):           # batch 1 in validation: per image, as on the drone
                y = code.latent(out[b:b + 1].float()).float()
                t0 = time.perf_counter()
                sym = torch.round(y)[0].to(torch.int64).cpu().numpy()
                data = coder.encode(sym)
                t1 = time.perf_counter()
                back = coder.decode(data, sym.shape)
                t2 = time.perf_counter()
                assert np.array_equal(back, sym), "range decoder did not reproduce the symbols"
                p = code.prior.likelihood(torch.round(y))
                log["ideal_bytes"].append(float(-torch.log2(p).sum()) / 8 + 4 * sym.shape[0])
                log["bytes"].append(len(data))
                log["enc_ms"].append((t1 - t0) * 1e3)
                log["dec_ms"].append((t2 - t1) * 1e3)
                log["values"].append(sym.size)
                y_hat = torch.from_numpy(back).to(out.device, torch.float32)[None]
                rec.append(code.dec(y_hat * torch.exp(-code.log_gain)).to(out.dtype))
            return torch.cat(rec)

    base = run_validation(yolo, "visdrone_val", dev, name="lb_base_yolov8s_visdrone_full_fp32")
    h = yolo.model.model[CUT].register_forward_hook(hook)
    try:
        res = run_validation(yolo, "visdrone_val", dev, name=f"ec_yolov8s_visdrone_{nm}", cache=False)
    finally:
        h.remove()
    for k in log:
        log[k] = L.drop_warmup(log[k], res["num_images"])
    pb = paired_bootstrap(base, res, n_boot=a.n_boot)
    row = {"config": nm, "cut": CUT, "channels": ck["channels"], "lam_per_kib": ck["lam"], "init": ck["init"],
           **{k: ck[k] for k in L.ARCH}, "n": len(log["bytes"]), "code_values": int(np.median(log["values"])),
           "payload_bytes_mean": float(np.mean(log["bytes"])), "payload_bytes_p95": float(np.percentile(log["bytes"], 95)),
           "ideal_bytes_mean": float(np.mean(log["ideal_bytes"])),
           "coder_overhead_pct": 100 * (np.mean(log["bytes"]) / np.mean(log["ideal_bytes"]) - 1),
           "decode_checked_images": len(log["bytes"]),
           "host_range_encode_ms_median": float(np.median(log["enc_ms"])),
           "host_range_decode_ms_median": float(np.median(log["dec_ms"])), "base_map50_95": base["map50_95"],
           **{k: v for k, v in summary_row(res).items() if k != "name"}, **{f"boot_{k}": v for k, v in pb.items()}}
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(row, open(OUT / f"eval_{nm}.json", "w"), indent=1)
    print(json.dumps({k: (round(v, 5) if isinstance(v, float) else v) for k, v in row.items()}), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train")
    t.add_argument("--lam", type=float, required=True, help="weight of the rate (KiB per image) in the loss")
    t.add_argument("--epochs", type=int, default=20)
    t.add_argument("--batch", type=int, default=8)
    t.add_argument("--lr", type=float, default=1e-3)
    t.add_argument("--lr-em", type=float, default=1e-2, help="learning rate of the entropy model")
    t.add_argument("--w-cut", type=float, default=0.1)
    t.add_argument("--workers", type=int, default=3)
    t.add_argument("--seed", type=int, default=0)
    t.add_argument("--limit", type=int, default=0, help="smoke test: this many training images (nothing kept)")
    e = sub.add_parser("eval")
    e.add_argument("--lam", type=float, required=True)
    e.add_argument("--n-boot", type=int, default=300)
    e.add_argument("--suffix", default="", help="checkpoint suffix (e.g. _smoke64 for the smoke test)")
    a = ap.parse_args()
    {"train": cmd_train, "eval": cmd_eval}[a.cmd](a)


if __name__ == "__main__":
    main()
