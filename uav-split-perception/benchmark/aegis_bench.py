#!/usr/bin/env python3
"""AEGIS-UAV open benchmark (hardening plan, Phase 8; 11 Nov 2026): score a perception-offloading controller for a
fanless drone computer against the measured system, without the boards.

What it packages (nothing here re-implements the system; it calls the code the papers use):
  replay    validation/hardware/replay.py: the trace-driven replay of the three-board testbed (Pi 5 camera drone,
            Jetson Orin Nano edge drone, laptop ground station): measured goodput traces, onboard times, power and
            the thermal plant, the netem fault scenarios, real detections of every variant on every frame, scored
            with streaming AP exactly as the live runs. Validated against the 240-run main hardware campaign.
  oracle    validation/hardware/replay_oracle.py: v4.1, a clairvoyant-link v4.1, every fixed configuration and the
            per-phase hindsight best, on the same seeds (common random numbers); stored in replay/oracle_oct29_plant.
  traces    the hardware runs (experiments/results/hardware/vid_campaign_*): per-run power, temperature, decisions.
  theory    paper2/theory_check.py: paper 2's Theorem 1 bound and Proposition 1 on every logged price sequence.

usage:
  python -m benchmark.aegis_bench check                      one-command check (about 3 min): data hashes, the replay
                                                             reproduces stored results bit for bit, the example policy
                                                             runs, the theory and break-even checks pass
  python -m benchmark.aegis_bench score POLICY.py [--scenario mission random] [--seeds 1-5]
                                                             score your policy (a file defining decide(rp, t)) next to
                                                             v4.1 and the stored oracle bounds
  python -m benchmark.aegis_bench manifest                   (maintainers) rewrite benchmark/MANIFEST.json

A policy is one function, decide(rp, t) -> (server, variant) or None, called every camera frame (30 fps) at time t
(seconds) with the replay rp. Servers: "laptop", "jetson" (variants adaptive2.PATH_VARIANTS, plus LAPTOP_EXTRA on
the laptop) and "onboard" (ONBOARD_VARIANTS). Return None to send nothing this frame. Useful state: rp.links[p].est(t)
(goodput estimate in Mbit/s and its spread), rp.links[p].idle(t), rp.onb_free (time the onboard model is free),
rp.onboard_ms(v), rp.aoi (age of the shown result, ms), rp.temp (board temperature, C), rp.last_onboard_det
(detections, columns x1 y1 x2 y2 conf cls). A choice of a busy server is dropped, as the live harness does.
See benchmark/example_policy.py.
"""
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HWDIR = ROOT / "validation" / "hardware"
RES = ROOT / "experiments" / "results" / "hardware"
ORACLE = RES / "replay" / "oracle_oct29_plant"
MANIFEST = Path(__file__).resolve().parent / "MANIFEST.json"
PY = sys.executable
sys.path.insert(0, str(HWDIR))


def _replay():
    import replay as R
    return R


def load_policy(path):
    spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.decide


def register(name, decide):
    R = _replay()

    def guarded(rp, t):
        c = decide(rp, t)
        if c is None:
            return None
        srv, var = c
        if srv == "onboard":
            return c if rp.onb_free <= t else None
        return c if rp.links[srv].idle(t) else None
    R.POLICIES[name] = dict(base="custom", decide=guarded)


def run(policies, scenarios, seeds, out, phase_s=20.0):
    """The replay's own main loop (replay.main), for policies registered here. Returns one row per run."""
    R = _replay()
    R.NETEM_LEGACY, R.ONB_POWER = False, "energy"    # replay.py's command-line defaults (--netem reset, energy model)
    out.mkdir(parents=True, exist_ok=True)
    gp = R.load_goodput()
    c, decays, accs, vd = R.load_all()
    rows = []
    for sc in scenarios:
        for seed in seeds:
            for pol in policies:
                path, m = R.Replay(pol, sc, phase_s, seed, gp, c, decays, vd, accs).run(out)
                m["sAP"] = R.score(path)
                rows.append(dict(policy=pol, scenario=sc, seed=seed, **m))
                print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in rows[-1].items()}),
                      flush=True)
    return rows


def oracle_rows(scenario, seed):
    out = {}
    for f in ORACLE.glob(f"rows/{scenario}__*__r{seed}.json"):
        d = json.load(open(f))
        out[d["policy"]] = d
    return out


def cmd_score(a):
    lo, hi = (int(x) for x in a.seeds.split("-"))
    name = "user_" + Path(a.policy).stem
    register(name, load_policy(a.policy))
    out = Path(a.out)
    rows = run([name, "v41"], a.scenario, range(lo, hi + 1), out)
    report = []
    for sc in a.scenario:
        for s in range(lo, hi + 1):
            mine = next(r for r in rows if r["policy"] == name and r["scenario"] == sc and r["seed"] == s)
            v41 = next(r for r in rows if r["policy"] == "v41" and r["scenario"] == sc and r["seed"] == s)
            orc = oracle_rows(sc, s)
            fixed = {k: v["sAP"] for k, v in orc.items() if k.startswith("fix_")}
            report.append({"scenario": sc, "seed": s, "sAP": mine["sAP"], "pi_w": mine["pi_w"],
                           "temp_mean_c": mine["temp_mean_c"], "v41_sAP": v41["sAP"], "v41_pi_w": v41["pi_w"],
                           "clairvoyant_v41_sAP": orc.get("v41_clair", {}).get("sAP"),
                           "best_fixed_sAP": max(fixed.values()) if fixed else None})
    json.dump(report, open(out / "score_report.json", "w"), indent=1)
    print("\nscenario seed   sAP    v4.1  clairvoyant v4.1  best fixed   power W (v4.1)")
    for r in report:
        f = lambda x: "  -  " if x is None else f"{x:.4f}"  # noqa: E731
        print(f"{r['scenario']:8s} {r['seed']:4d} {r['sAP']:.4f} {r['v41_sAP']:.4f}   {f(r['clairvoyant_v41_sAP'])}"
              f"        {f(r['best_fixed_sAP'])}   {r['pi_w']:.2f} ({r['v41_pi_w']:.2f})")
    print(f"-> {out / 'score_report.json'}")


# ------------------------------------------------------------------------------------------------ data manifest
def manifest_files():
    """The data the benchmark reads: found by tracing every file the replay, the scorer and the checks open."""
    R = _replay()
    seen = set()

    def hook(ev, args):
        if ev == "open" and isinstance(args[0], (str, Path)) and (len(args) < 2 or "r" in str(args[1] or "r")):
            p = Path(args[0]).resolve()
            if p.is_file() and str(p).startswith(str(ROOT)) and "/venv/" not in str(p) and p.suffix != ".py":
                seen.add(p)
    sys.addaudithook(hook)
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        register("example", load_policy(Path(__file__).resolve().parent / "example_policy.py"))
        run(["v41", "example"], ["mission"], [1], Path(d))
        sys.path.insert(0, str(ROOT / "paper2"))
        import theory_check as T                    # the hardware traces paper 2's checks read
        T.OUT = Path(d)
        T.main()
    seen |= set(ORACLE.glob("rows/*.json")) | {ORACLE / "oracle_summary.json", RES / "theory_check" / "theory_check.json",
                                                RES / "replay" / "validate_main_oct29_plant" / "replay_check.json"}
    return sorted(p for p in seen if "/tmp" not in str(p))


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def cmd_manifest(a):
    files = manifest_files()
    m = {"note": "data read by the open benchmark (benchmark/aegis_bench.py); sha256 and size in bytes; paths relative "
                 "to the repository root", "files": {str(p.relative_to(ROOT)): {"sha256": sha(p), "bytes": p.stat().st_size}
                                                    for p in files}}
    m["total_bytes"] = sum(v["bytes"] for v in m["files"].values())
    json.dump(m, open(MANIFEST, "w"), indent=1)
    print(f"{len(files)} files, {m['total_bytes'] / 2**20:.1f} MiB -> {MANIFEST}")


# ------------------------------------------------------------------------------------------------ one-command check
def cmd_check(a):
    t0, ok = time.time(), True

    def step(name, passed, detail=""):
        nonlocal ok
        ok &= bool(passed)
        print(f"[{'PASS' if passed else 'FAIL'}] {name}{': ' + detail if detail else ''}", flush=True)

    # 1) data
    m = json.load(open(MANIFEST))
    bad = [f for f, v in m["files"].items() if not (ROOT / f).exists() or sha(ROOT / f) != v["sha256"]]
    step("data files match MANIFEST.json", not bad, f"{len(m['files'])} files, {m['total_bytes'] / 2**20:.0f} MiB"
         + (f"; mismatched: {bad[:5]}" if bad else ""))
    # 2) the replay reproduces the stored oracle results exactly (v4.1, two scenarios, seed 1)
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        register("example", load_policy(Path(__file__).resolve().parent / "example_policy.py"))
        rows = run(["v41", "example"], ["mission", "random"], [1], Path(d))
    for r in rows:
        if r["policy"] != "v41":
            continue
        ref = json.load(open(ORACLE / "rows" / f"{r['scenario']}__v41__r1.json"))
        diff = max(abs(r[k] - ref[k]) for k in ("sAP", "pi_w", "temp_mean_c", "availability"))
        step(f"replay reproduces stored v4.1 {r['scenario']} seed 1", diff < 1e-9,
             f"sAP {r['sAP']:.4f}, Pi {r['pi_w']:.3f} W, {r['temp_mean_c']:.2f} C (max abs diff {diff:.1e})")
    ex = [r for r in rows if r["policy"] == "example"]
    step("example policy scored", len(ex) == 2 and all(0 <= r["sAP"] <= 1 for r in ex),
         ", ".join(f"{r['scenario']} sAP {r['sAP']:.4f}" for r in ex))
    # 3) replay vs hardware: the stored validation against the 240-run main campaign (replay_check.py)
    vc = json.load(open(RES / "replay" / "validate_main_oct29_plant" / "replay_check.json"))["agreement"]
    step("replay agrees with the 240 hardware runs (stored validation, policy means)", vc["sAP"]["pearson"] > 0.9,
         ", ".join(f"{k} r={v['pearson']:.2f}" for k, v in vc.items()))
    # 4) paper 2's Theorem 1 and Proposition 1, recomputed from the hardware traces into a temporary folder and
    #    compared with the stored check
    with tempfile.TemporaryDirectory() as d:
        code = ("import sys, json; from pathlib import Path; sys.path.insert(0, 'paper2'); import theory_check as T; "
                f"T.OUT = Path({d!r}); T.main()")
        r = subprocess.run([PY, "-c", code], cwd=ROOT, capture_output=True, text=True)
        new = json.load(open(Path(d) / "theory_check.json")) if r.returncode == 0 else None
    old = json.load(open(RES / "theory_check" / "theory_check.json"))
    step("paper 2 Theorem 1 holds on every logged price sequence (recomputed from the traces)",
         new is not None and new["theorem1"]["all_hold"] and new == old,
         f"{old['theorem1']['runs']} runs, identical to the stored check" if new == old else (r.stderr or "")[-300:])
    r = subprocess.run([PY, "-m", "pytest", "-q", "tests/test_break_even_rule.py", "tests/test_mpc_planner.py"],
                       cwd=ROOT, capture_output=True, text=True)
    step("break-even rule and planner tests", r.returncode == 0, r.stdout.strip().splitlines()[-1] if r.stdout else "")
    print(f"\n{'ALL CHECKS PASSED' if ok else 'SOME CHECKS FAILED'} in {time.time() - t0:.0f} s")
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("manifest")
    s = sub.add_parser("score")
    s.add_argument("policy")
    s.add_argument("--scenario", nargs="+", default=["mission", "random"])
    s.add_argument("--seeds", default="1-5")
    s.add_argument("--out", default=str(ROOT / "experiments" / "results" / "benchmark_scores"))
    a = ap.parse_args()
    {"check": cmd_check, "manifest": cmd_manifest, "score": cmd_score}[a.cmd](a)


if __name__ == "__main__":
    main()
