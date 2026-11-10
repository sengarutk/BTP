"""Dry run (dryrun_board_session.sh): parse every recorded camera command with adaptive2.py's own parser and expand its scenario."""
import argparse, shlex, sys
sys.path.insert(0, '.')
real = argparse.ArgumentParser.parse_args
class Done(Exception): pass
def fake(self, args=None, ns=None):
    a = real(self, args, ns); raise Done(a)
argparse.ArgumentParser.parse_args = fake
import adaptive2
seen, bad = set(), 0
for line in open(sys.argv[1]):
    lab, cmd = line[4:].split(" :: ")
    key = (lab.split("__")[0], lab.split("__")[1])
    if key in seen: continue
    seen.add(key)
    argv = shlex.split(cmd.replace("--policy ", "--policy '").replace(" --scenario", "' --scenario", 1))
    sys.argv = ["adaptive2.py"] + argv + ["--out", "/dev/null"]
    try:
        adaptive2.main()
    except Done as d:
        a = d.args[0]
        ph = adaptive2.scenario_phases(a.scenario, a.phase_s, a.seed)
        print(f"ok {key[0]:15s} {key[1]:10s} policy={a.policy:22s} energy={a.energy_aware} budget={a.power_budget} fresh={a.fresh_target} paths={a.paths} phases={len(ph)} imp={ph[0][1]}")
    except SystemExit as e:
        bad += 1; print("PARSE FAIL", key, e)
print("unique", len(seen), "failures", bad)
