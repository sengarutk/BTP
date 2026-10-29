import json, numpy as np
HW = "/home/sengar/BTP/uav-split-perception/experiments/results/hardware"
C = json.load(open(f"{HW}/report_c_summary.json")); V = json.load(open(f"{HW}/report_c_summary_visdrone.json"))
def rank(x): return np.argsort(np.argsort(x))
for camp in C:
    cells = [(sc, p) for sc in C[camp]["scenarios"] for p in C[camp]["scenarios"][sc]]
    a = np.array([C[camp]["scenarios"][sc][p]["sAP_fc"][0] for sc, p in cells])
    b = np.array([V[camp]["scenarios"][sc][p]["sAP_fc"][0] for sc, p in cells])
    rho = np.corrcoef(rank(a), rank(b))[0, 1]
    print(f"{C[camp]['section']:48s} cells {len(cells):3d}  coco {a.mean():.3f}  vd {b.mean():.3f}  median ratio {np.median(b/a):.2f}  spearman {rho:.2f}")
# sign swaps and significance
sw = 0; sigC = sigV = 0
for camp in C:
    for ref, m in C[camp]["paired"].items():
        for p, r in m["sAP_fc"].items():
            v = V[camp]["paired"][ref]["sAP_fc"][p]
            sw += np.sign(r["mean_diff"]) != np.sign(v["mean_diff"])
            if np.sign(r["mean_diff"]) != np.sign(v["mean_diff"]): print("swap", camp, ref, p, round(r["mean_diff"],4), round(v["mean_diff"],4), round(r["p_holm"],3), round(v["p_holm"],3))
print("sign swaps (incl. mirrored duplicates)", sw)
