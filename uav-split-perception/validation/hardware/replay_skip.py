#!/usr/bin/env python3
"""Item 7b of the laptop strengthening (16 Nov 2026; predictions: docs/laptop_strengthening_predictions_nov16.md):
the late-path skip on HELD-OUT replay settings. v4.1 against v4.1 + skip (0.5), seeds 11-20 (never used before),
scenarios random, mission_mirror, static_good (20-s phases), each with independent radios (the validated replay) and
with the camera's one radio shared by both paths (replay --shared-radio: a transfer that starts while the other path
transmits gets half the drawn goodput). Validated setting: --netem reset, the "power" onboard model.
usage: replay_skip.py run --shared {0,1}
       replay_skip.py analyze   -> experiments/results/hardware/replay/skip_nov16/skip_summary.json
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import replay as R  # noqa: E402
import replay_accumo as A  # noqa: E402

OUT = R.HW / "replay" / "skip_nov16"
R.POLICIES["v41_skip"] = dict(R.POLICIES["v41"], late_skip=0.5)
SCEN = ["random", "mission_mirror", "static_good"]


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--shared", type=int, choices=(0, 1), required=True)
    r.add_argument("--seeds", default="11-20")
    sub.add_parser("analyze")
    a = ap.parse_args()
    if a.cmd == "run":
        R.SHARED_RADIO = bool(a.shared)
        A.cmd_run(argparse.Namespace(policy=["v41", "v41_skip"], scenario=SCEN, phase_s=20.0, seeds=a.seeds,
                                     netem="reset", onboard_power="power", out=str(OUT / f"shared{a.shared}")))
        return
    out = {}
    for sh in (0, 1):
        rows = [json.load(open(f)) for f in sorted((OUT / f"shared{sh}" / "rows").glob("*.json"))]
        by = defaultdict(dict)
        for x in rows:
            by[(x["scenario"], x["seed"])][x["policy"]] = x
        ent = {}
        for sc in SCEN + ["all"]:
            ks = [k for k in by if (sc == "all" or k[0] == sc) and len(by[k]) == 2]
            if not ks:
                continue
            ent[sc] = {m: A.paired([by[k]["v41_skip"][m] - by[k]["v41"][m] for k in ks])
                       for m in ("sAP", "pi_w", "fresh_share")}
            ent[sc]["sAP_v41"] = sum(by[k]["v41"]["sAP"] for k in ks) / len(ks)
            print(f"shared {sh} {sc:15s} n {len(ks):2d} dsAP {ent[sc]['sAP']['mean']:+.4f} ± {ent[sc]['sAP']['ci95']:.4f}"
                  f" (skip ahead {ent[sc]['sAP']['wins']}/{len(ks)})  dW {ent[sc]['pi_w']['mean']:+.3f}"
                  f"  dfresh {ent[sc]['fresh_share']['mean']:+.4f}")
        out[f"shared{sh}"] = ent
    json.dump(out, open(OUT / "skip_summary.json", "w"), indent=1)


if __name__ == "__main__":
    main()
