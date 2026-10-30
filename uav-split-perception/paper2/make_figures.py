#!/usr/bin/env python3
"""Figures of paper2/main.tex, from the result files (30 Oct 2026).
  figures/decay.pdf  share of fresh streaming AP kept by a result shown late, measured on the VisDrone-VID train clips:
                     no correction (staleness_decay.json), velocity forecaster v1 (staleness_decay_forecast.json),
                     camera-aligned forecaster v2 (staleness_decay_forecast_v2.json); the 300 ms deadline marked.
usage: python paper2/make_figures.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HW = Path(__file__).resolve().parent.parent / "experiments" / "results" / "hardware"
FIG = Path(__file__).resolve().parent / "figures"
plt.rcParams.update({
    "font.family": "serif", "font.size": 8, "axes.labelsize": 8, "legend.fontsize": 6.5, "xtick.labelsize": 7,
    "ytick.labelsize": 7, "axes.grid": True, "grid.alpha": 0.3, "grid.linewidth": 0.5, "lines.linewidth": 1.2,
    "lines.markersize": 3.0, "savefig.bbox": "tight", "savefig.pad_inches": 0.02, "pdf.fonttype": 42,
    "axes.spines.top": False, "axes.spines.right": False})


def main():
    FIG.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(3.45, 2.1))
    for f, lab, col in (("staleness_decay.json", "no correction", "#000000"),
                        ("staleness_decay_forecast.json", "forecaster v1 (object velocity)", "#56B4E9"),
                        ("staleness_decay_forecast_v2.json", "forecaster v2 (camera-aligned)", "#0072B2")):
        d = json.load(open(HW / f))
        ax.plot(d["lag_ms"], d["ratio"], "o-", color=col, label=lab)
    ax.axvline(300, color="#999999", lw=0.8, ls="--")
    ax.text(312, 0.64, "300 ms deadline", fontsize=6, color="#666666", rotation=90)
    ax.set_xlabel("age of the shown result (ms)")
    ax.set_ylabel("share of fresh sAP kept")
    ax.set_ylim(0, 1.03)
    ax.legend(loc="upper right", frameon=False)
    fig.savefig(FIG / "decay.pdf")
    plt.close(fig)
    print("paper2/figures/decay.pdf")


if __name__ == "__main__":
    main()
