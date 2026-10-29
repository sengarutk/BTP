import json, glob, re
HW = "/home/sengar/BTP/uav-split-perception/experiments/results/hardware"
md = open("/home/sengar/BTP/AEGIS-UAV Results Brief.md").read()
T = {10: 2.228, 11: 2.201, 15: 2.131, 19: 2.093, 23: 2.069, 35: 2.030}
def t(df): return T.get(df) or (2.228 if df == 10 else 2.093)
old_hits, new_hits, both = [], [], []
for f in sorted(glob.glob(f"{HW}/*_summary*.json")):
    try: d = json.load(open(f))
    except Exception: continue
    pv = d.get("paired_vs_ref") or {}
    for metric, res in pv.items():
        if not isinstance(res, dict): continue
        for pol, r in res.items():
            if not isinstance(r, dict) or "ci95" not in r or r.get("pairs", 0) < 11: continue
            mu, ci = r["mean_diff"], r["ci95"]; cit = round(ci * t(r["pairs"] - 1) / 1.96, 4)
            for sgn in (1, -1):
                m = f"{sgn*mu:+.4f}".lstrip("+")
                pat_old = re.compile(r"[+−-]?" + re.escape(m.lstrip("-")) + r" ± " + re.escape(f"{ci:.4f}"))
                pat_new = re.compile(r"[+−-]?" + re.escape(m.lstrip("-")) + r" ± " + re.escape(f"{cit:.4f}"))
                if abs(cit - ci) < 1e-9: continue
                for mm in pat_old.finditer(md):
                    line = md[:mm.start()].count("\n") + 1
                    old_hits.append((line, mm.group(0), f.split("/")[-1], metric, pol, r["pairs"], f"t-version ±{cit:.4f}"))
                for mm in pat_new.finditer(md):
                    line = md[:mm.start()].count("\n") + 1
                    new_hits.append((line, mm.group(0), f.split("/")[-1], pol))
seen = set()
print("== values still at 1.96 (old) ==")
for h in sorted(set(old_hits)):
    print(h)
print("== values already t-corrected ==")
for h in sorted(set(new_hits)): print(h)
