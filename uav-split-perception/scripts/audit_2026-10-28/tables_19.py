import json, re
HW = "/home/sengar/BTP/uav-split-perception/experiments/results/hardware"
md = open("/home/sengar/BTP/AEGIS-UAV Results Brief.md").read().split("\n")
C = json.load(open(f"{HW}/report_c_summary.json")); V = json.load(open(f"{HW}/report_c_summary_visdrone.json"))
sect = {v["section"]: k for k, v in C.items()}
def f3(x): return float(x.replace("−", "-").replace("**", ""))
bad = n = 0
for i, l in enumerate(md, 1):
    c = [x.strip() for x in l.strip().strip("|").split("|")]
    if len(c) < 5 or c[0] not in sect: continue
    camp = sect[c[0]]; m = re.match(r"(\S+) vs (\S+)", c[1])
    if not m: continue
    ref, pol = m.groups()
    if len(c) == 8 and "±" in c[2]:          # 19.3 table
        r = C[camp]["paired"][ref]; n += 1
        mu, ci = [f3(x) for x in c[2].split("±")]
        e = []
        s = r["sAP_fc"][pol]
        if round(s["mean_diff"], 4) != mu or round(s["ci95"], 4) != ci: e.append(f"diff {s['mean_diff']:+.4f}±{s['ci95']:.4f}")
        if c[3] != f"{s['wins']}/{s['pairs']}": e.append(f"wins {s['wins']}/{s['pairs']}")
        if f"{s['p_perm']:.3f}" != c[4]: e.append(f"p {s['p_perm']:.3f}")
        if f"{s['p_holm']:.3f}" != c[5].strip("*"): e.append(f"holm {s['p_holm']:.3f}")
        if f"{r['sAP_quality_fc'][pol]['p_holm']:.3f}" != c[6]: e.append(f"qholm {r['sAP_quality_fc'][pol]['p_holm']:.3f}")
        if f"{r['sAP_masked_fc'][pol]['p_holm']:.3f}" != c[7]: e.append(f"mholm {r['sAP_masked_fc'][pol]['p_holm']:.3f}")
        if e: bad += 1; print("19.3 line", i, c[1], e)
    else:                                       # 19.5 tables
        s = V[camp]["paired"][ref]["sAP_fc"][pol]; co = C[camp]["paired"][ref]["sAP_fc"][pol]; n += 1
        txt = " ".join(c[2:]); e = []
        mm = re.search(r"([+-]?\d\.\d{4}) \(p Holm (\d\.\d{3})\)", txt)
        if mm and (f"{co['mean_diff']:+.4f}" != (mm.group(1) if mm.group(1)[0] in "+-" else "+" + mm.group(1)) or f"{co['p_holm']:.3f}" != mm.group(2)):
            e.append(f"coco {co['mean_diff']:+.4f} ({co['p_holm']:.3f})")
        mv = re.search(r"([+-]\d\.\d{4}) ± (\d\.\d{4})", txt)
        if mv and (f"{s['mean_diff']:+.4f}" != mv.group(1) or f"{s['ci95']:.4f}" != mv.group(2)): e.append(f"vd {s['mean_diff']:+.4f}±{s['ci95']:.4f}")
        hv = [x for x in c[2:] if re.fullmatch(r"\**\d\.\d{3}\**", x)]
        if hv and f"{s['p_holm']:.3f}" != hv[-1].strip("*"): e.append(f"vd holm {s['p_holm']:.3f}")
        w = [x for x in c[2:] if re.fullmatch(r"\d+/\d+", x)]
        if w and w[0] != f"{s['wins']}/{s['pairs']}": e.append(f"wins {s['wins']}/{s['pairs']}")
        if e: bad += 1; print("19.5 line", i, c[1], e)
print("rows checked", n, "mismatches", bad)
