"""Independent recomputation of every paired comparison in report_c_summary(.._visdrone).json from the per-run caches:
mean, t-interval (scipy t), wins, exact sign-flip p (own enumeration), Holm (own). Reports any mismatch > tolerance."""
import json, itertools, sys
from collections import defaultdict
import numpy as np
import mpmath
def tq(df):
    f=lambda x: mpmath.betainc(df/2,0.5,0,df/(df+x*x),regularized=True)/2-0.025
    return float(mpmath.findroot(f,2.0))
HW = "/home/sengar/BTP/uav-split-perception/experiments/results/hardware"
def perm(d):
    d = np.asarray(d); n = len(d); obs = abs(d.sum()); cnt = 0
    for s in itertools.product((1, -1), repeat=n):
        cnt += abs(np.dot(s, d)) >= obs - 1e-12
    return cnt / 2 ** n
def holm(p):
    p = np.asarray(p); o = np.argsort(p); m = len(p); out = np.empty(m); run = 0
    for i, k in enumerate(o):
        run = max(run, min(1, (m - i) * p[k])); out[k] = run
    return out
bad = 0; n = 0
for tag, cname in (("coco", "_eval_cache_c.json"), ("visdrone", "_eval_cache_vd.json")):
    summ = json.load(open(f"{HW}/report_c_summary{'_visdrone' if tag == 'visdrone' else ''}.json"))
    for camp, cs in summ.items():
        cache = json.load(open(f"{HW}/{camp}/{cname}"))
        runs = defaultdict(dict)
        for stem, r in cache.items():
            sc, pol, rep = stem.split("__"); runs[(sc, rep)][pol] = r["fc"]["sAP"]
        for ref, mets in cs["paired"].items():
            fam = mets["sAP_fc"]; pols = list(fam); ps = []
            for p in pols:
                d = [v[ref] - v[p] for v in runs.values() if ref in v and p in v]
                mu = np.mean(d); hw = tq(len(d) - 1) * np.std(d, ddof=1) / np.sqrt(len(d))
                pp = perm(d) if len(d) <= 20 else None; ps.append(pp if pp is not None else fam[p]["p_perm"])
                r = fam[p]; n += 1
                errs = []
                if abs(mu - r["mean_diff"]) > 1e-9: errs.append(f"mean {mu} vs {r['mean_diff']}")
                if abs(hw - r["ci95"]) > 0.005 * hw: errs.append(f"ci {hw:.5f} vs {r['ci95']:.5f}")
                if sum(x > 0 for x in d) != r["wins"] or len(d) != r["pairs"]: errs.append("wins/pairs")
                if pp is not None and abs(pp - r["p_perm"]) > 1e-9: errs.append(f"p {pp} vs {r['p_perm']}")
                if errs: bad += 1; print(tag, camp, ref, p, errs)
            for p, h in zip(pols, holm(ps)):
                if abs(h - fam[p]["p_holm"]) > 1e-9: bad += 1; print(tag, camp, ref, p, "holm", h, fam[p]["p_holm"])
print("comparisons checked", n, "mismatches", bad)
