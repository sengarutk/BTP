#!/usr/bin/env python3
"""v4.1 with a conformal (distribution-free) deadline probability against the Gaussian one (paper 2, roadmap L8,
12 Nov 2026; predictions in docs/conformal_predictions_nov12.md).

Both run in the replay (replay.py, the validated setting: --netem reset, the "power" onboard model) on the same link
draws, 4 scenarios x 10 seeds, 20-s phases. Every offloaded frame's predicted p_on is logged against whether its result
arrived within the 300 ms deadline (replay_oracle.OracleReplay's logging), so calibration is measured on the frames
each controller actually sent.
usage: replay_conformal.py [--seeds 1-10] [--shard K/N]  -> experiments/results/hardware/replay/conformal_nov12/
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import replay as R  # noqa: E402
from replay_oracle import OracleReplay, calib_table  # noqa: E402
from stream_ap import evaluate, load_labels  # noqa: E402

OUT = R.HW / "replay" / "conformal_nov12"
SCEN = ("mission", "mission_mirror", "random", "static_good")
POLS = ("v41", "v41_conf")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1-10")
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--analyse", action="store_true")
    a = ap.parse_args()
    rows_d = OUT / "rows"
    rows_d.mkdir(parents=True, exist_ok=True)
    if not a.analyse:
        R.NETEM_LEGACY, R.ONB_POWER = False, "power"
        k, n = (int(x) for x in a.shard.split("/"))
        lo, hi = (int(x) for x in a.seeds.split("-"))
        jobs = [(sc, s, p) for sc in SCEN for s in range(lo, hi + 1) for p in POLS][k::n]
        gp = R.load_goodput()
        c, decays, accs, vd = R.load_all()
        labels = load_labels()
        fp = R.FORECAST_PARAMS if hasattr(R, "FORECAST_PARAMS") else None
        for sc, seed, pol in jobs:
            row_f = rows_d / f"{sc}__{pol}__{seed}.json"
            if row_f.exists():
                continue
            rp = OracleReplay(pol, sc, 20.0, seed, gp, c, decays, vd, accs)
            path, m = rp.run(OUT / "runs")
            m["sAP"] = R.score(path)
            run = json.load(open(path))
            cal = []
            for f in run["frames"]:
                key = (f["id"], f.get("server"), f.get("variant"))
                if key in rp.pred:
                    lat = (f["t_res"] - f["id"] * R.PERIOD) * 1e3 if f.get("t_res") is not None else None
                    cal.append([*rp.pred[key], lat])
            row = dict(policy=pol, scenario=sc, seed=seed, **m, calib=cal)
            json.dump(row, open(row_f, "w"))
            print(json.dumps({k_: (round(v, 4) if isinstance(v, float) else v) for k_, v in row.items()
                              if k_ not in ("calib", "price")}), flush=True)
        return
    rows = [json.load(open(f)) for f in rows_d.glob("*.json")]
    by = {(r["scenario"], r["seed"], r["policy"]): r for r in rows}
    out = {"method": __doc__, "policies": {}}
    for pol in POLS:
        pairs = [(c_[0], 1.0 if (c_[2] is not None and c_[2] <= R.D) else 0.0)
                 for r in rows if r["policy"] == pol for c_ in r["calib"]]
        hi = [y for p, y in pairs if p >= 0.95]
        out["policies"][pol] = {"calibration": calib_table(pairs), "frames_p_ge_095": len(hi),
                                "miss_rate_p_ge_095": float(1 - np.mean(hi)) if hi else None,
                                "sAP": float(np.mean([r["sAP"] for r in rows if r["policy"] == pol])),
                                "availability": float(np.mean([r["availability"] for r in rows if r["policy"] == pol])),
                                "pi_w": float(np.mean([r["pi_w"] for r in rows if r["policy"] == pol]))}
    keys = sorted({(sc, s) for sc, s, _ in by})
    d = np.array([by[(sc, s, "v41_conf")]["sAP"] - by[(sc, s, "v41")]["sAP"] for sc, s in keys
                  if (sc, s, "v41_conf") in by and (sc, s, "v41") in by])
    from summarize_vid import t975
    out["paired_sAP_conf_minus_v41"] = {"mean": float(d.mean()),
                                        "ci95": float(t975(len(d) - 1) * d.std(ddof=1) / np.sqrt(len(d))), "n": int(len(d))}
    json.dump(out, open(OUT / "summary.json", "w"), indent=1)
    for pol, v in out["policies"].items():
        print(pol, "ECE %.3f" % v["calibration"]["ece"], "pred %.3f obs %.3f" % (v["calibration"]["mean_pred"],
              v["calibration"]["observed"]), "miss|p>=.95", v["miss_rate_p_ge_095"], "n", v["frames_p_ge_095"],
              "sAP %.4f fresh %.3f W %.2f" % (v["sAP"], v["availability"], v["pi_w"]))
    print("paired sAP conf - v41", out["paired_sAP_conf_minus_v41"])


if __name__ == "__main__":
    main()
