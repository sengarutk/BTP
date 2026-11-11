#!/usr/bin/env python3
"""A constrained deep-RL baseline in the validated replay (paper 2, roadmap P2-7, 11 Nov 2026).

What reviewers expect next to a hand-built dual controller: a policy learned end to end under the same power budget.
PPO with a Lagrange multiplier on the budget (PPO-Lagrangian, the standard constrained-RL baseline), trained in the
replay (replay.py, the settings of replay_theory_sweep.py: netem reset, "power" onboard model) and scored there with
the same streaming AP as every other policy.

  decision   every camera tick (30 Hz), as v4.1: skip, or one of the idle servers with one of its settings (the
             laptop's and the Jetson's JPEG variants, the Pi's three onboard models); actions on busy servers masked
  state      per link: up, idle, log goodput estimate, relative spread, round trip; for every remote setting the ratio
             of its transfer time at the estimate to the deadline; onboard free; board temperature; age of the newest
             result; the policy's own modelled camera energy over the last second
  reward     per tick, the accuracy of the newest result (relative to the full model, the replay's accuracy table) when
             it is younger than the 300 ms deadline, else 0 (the quantity streaming AP rewards); minus lambda times
             the modelled camera energy of the action (J, replay.e_onb / e_off, the energies v4.1 prices)
  constraint after each batch lambda <- max(0, lambda + alpha (mean measured board power - B)), B = 2.8 W (v4.1's)
  PPO        MLP 64-64 (tanh), masked categorical policy and value head; GAE (gamma 0.99, lambda 0.95), clip 0.2,
             4 epochs, minibatch 1024, Adam 3e-4, entropy 0.01; batch = one episode per worker; alpha = 0.2
  training   2-min episodes (mission and random faults alternating), seeds 1001+ (the evaluation uses seeds 1-5 and
             1-10); the run with the best mean training reward among the last checkpoints is kept
  evaluation the greedy policy (argmax) on the theory sweep's scenarios: the 24-min mission, seeds 1-5, and the 2-min
             mission and random scenarios, against v4.1 rows on the same seeds (common random numbers)
usage: rl_baseline.py train [--iters 120] [--workers 3]   -> experiments/results/hardware/replay/rl_baseline/
       rl_baseline.py eval                                  (runs + rows + summary.json)
"""
import argparse
import json
import math
import multiprocessing as mp
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import replay as R  # noqa: E402

OUT = R.HW / "replay" / "rl_baseline"
BUDGET, ALPHA_L, E_SCALE = 2.8, 0.2, 1.0
SERVERS = ("laptop", "jetson")
ACTIONS = ([None] + [("laptop", v) for v in dict(R.PATH_VARIANTS, **R.LAPTOP_EXTRA)]
           + [("jetson", v) for v in R.PATH_VARIANTS] + [("onboard", v) for v in R.ONBOARD_VARIANTS])
_W = {}          # per-process data (load_all once)


def setup():
    R.NETEM_LEGACY, R.ONB_POWER = False, "power"        # replay_theory_sweep.py's settings
    if not _W:
        _W["gp"] = R.load_goodput()
        _W["c"], _W["decays"], _W["accs"], _W["vd"] = R.load_all()
    return _W


def variant(srv, v):
    if srv == "onboard":
        m, res = R.ONBOARD_VARIANTS[v]
        return m, res, None
    return dict(R.PATH_VARIANTS, **(R.LAPTOP_EXTRA if srv == "laptop" else {}))[v]


def n_features():
    return 5 * len(SERVERS) + sum(1 for a in ACTIONS if a and a[0] != "onboard") + 4


class Agent:
    """State features, action mask, reward and cost of one episode; decide(rp, t) is the replay's custom policy."""

    def __init__(self, net, greedy=False, rng=None):
        self.net, self.greedy, self.rng = net, greedy, rng or np.random.default_rng(0)
        self.traj, self.sends, self.e_hist, self.last_acc = [], {}, [], 0.0

    def features(self, rp, t):
        f = []
        for s in SERVERS:
            L_ = rp.links[s]
            r, sd = L_.est(t)
            f += [float(L_.up), float(L_.idle(t)), math.log1p(r), min(sd / r, 3.0), L_.rtt / 100.0]
        for a in ACTIONS:
            if a and a[0] != "onboard":
                m, res, q = variant(*a)
                r = rp.links[a[0]].est(t)[0]
                f.append(min(rp.nbytes[(res, q)] * 8 / (r * 1e3) / R.D, 5.0))
        aoi = rp.aoi if math.isfinite(rp.aoi) else 3000.0
        e1 = sum(e for (ts, e) in self.e_hist if t - ts <= 1.0)
        f += [float(rp.onb_free <= t), (rp.temp - 70.0) / 10.0, min(aoi, 3000.0) / 1000.0, e1]
        return np.array(f, np.float32)

    def mask(self, rp, t):
        m = np.zeros(len(ACTIONS), bool)
        m[0] = True
        for i, a in enumerate(ACTIONS[1:], 1):
            m[i] = (rp.onb_free <= t) if a[0] == "onboard" else rp.links[a[0]].idle(t)
        return m

    def energy(self, rp, a, t):
        if a is None:
            return 0.0
        srv, v = a
        if srv == "onboard":
            return rp.e_onb(v)
        m, res, q = variant(srv, v)
        return rp.e_off(res, q, rp.nbytes[(res, q)], rp.links[srv].est(t)[0])

    def reward(self, rp, t):
        """Accuracy of the newest result if it is fresh (the newest result's frame is found from its age)."""
        if not math.isfinite(rp.aoi):
            return 0.0
        fid = int(round((t - rp.aoi / 1e3) / R.PERIOD))
        if fid in self.sends:
            self.last_acc = self.sends[fid]
        return self.last_acc if rp.aoi <= R.D else 0.0

    def __call__(self, rp, t):
        import torch
        tick = int(round(t / R.PERIOD))
        x, mk = self.features(rp, t), self.mask(rp, t)
        r_prev = self.reward(rp, t)
        if self.traj:
            self.traj[-1]["r"] = r_prev - self.traj[-1]["cost"]
        with torch.no_grad():
            logits, v = self.net(torch.from_numpy(x)[None])
            logits = logits[0].numpy().astype(np.float64)
        logits[~mk] = -1e9
        p = np.exp(logits - logits.max())
        p /= p.sum()
        k = int(np.argmax(p)) if self.greedy else int(self.rng.choice(len(p), p=p))
        a = ACTIONS[k]
        e = self.energy(rp, a, t)
        if a is not None:
            self.e_hist = [x_ for x_ in self.e_hist if t - x_[0] <= 1.0] + [(t, e)]
            m, res, q = variant(*a)
            self.sends[tick] = rp.acc_of(m, res, q) / rp.ref
        if not self.greedy:
            self.traj.append({"x": x, "m": mk, "a": k, "logp": float(np.log(p[k] + 1e-12)), "v": float(v[0]),
                              "cost": self.lam * E_SCALE * e, "r": 0.0})
        return a


def make_net():
    import torch
    import torch.nn as nn

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.body = nn.Sequential(nn.Linear(n_features(), 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh())
            self.pi, self.v = nn.Linear(64, len(ACTIONS)), nn.Linear(64, 1)

        def forward(self, x):
            h = self.body(x)
            return self.pi(h), self.v(h)[:, 0]
    return Net()


def episode(args):
    """One training episode in a worker: returns the trajectory and the run's measured mean power."""
    import torch
    torch.set_num_threads(1)
    state, lam, scenario, seed, phase_s = args
    w = setup()
    net = make_net()
    net.load_state_dict(state)
    ag = Agent(net, rng=np.random.default_rng(seed))
    ag.lam = lam
    name = f"rl_train_{os.getpid()}"
    R.POLICIES[name] = dict(base="custom", decide=ag)
    d = Path(tempfile.mkdtemp(prefix="rl_"))
    try:
        _, m = R.Replay(name, scenario, phase_s, seed, w["gp"], w["c"], w["decays"], w["vd"], w["accs"]).run(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    tr = ag.traj
    return ({k: np.array([s[k] for s in tr]) for k in ("x", "m", "a", "logp", "v", "r", "cost")},
            m["pi_w"], float(np.mean([s["r"] + s["cost"] for s in tr])))


def gae(r, v, gamma=0.99, lam=0.95):
    adv = np.zeros_like(r)
    last = 0.0
    for t in range(len(r) - 1, -1, -1):
        nv = v[t + 1] if t + 1 < len(r) else 0.0
        delta = r[t] + gamma * nv - v[t]
        last = delta + gamma * lam * last
        adv[t] = last
    return adv, adv + v


def cmd_train(a):
    import torch
    torch.manual_seed(0)
    OUT.mkdir(parents=True, exist_ok=True)
    net = make_net()
    opt = torch.optim.Adam(net.parameters(), lr=3e-4)
    lam, log = 0.0, []
    ctx = mp.get_context("spawn")
    best = None
    with ctx.Pool(a.workers) as pool:
        for it in range(a.iters):
            t0 = time.time()
            state = {k: v.detach().clone() for k, v in net.state_dict().items()}
            jobs = [(state, lam, ("mission", "random")[(it * a.workers + j) % 2], 1001 + it * a.workers + j, 20.0)
                    for j in range(a.workers)]
            res = pool.map(episode, jobs)
            pw = float(np.mean([r[1] for r in res]))
            rew = float(np.mean([r[2] for r in res]))
            X, M, A, LP, ADV, RET = [], [], [], [], [], []
            for tr, _, _ in res:
                adv, ret = gae(tr["r"].astype(np.float64), tr["v"].astype(np.float64))
                X.append(tr["x"]); M.append(tr["m"]); A.append(tr["a"]); LP.append(tr["logp"])
                ADV.append(adv); RET.append(ret)
            X, M, A = (torch.tensor(np.concatenate(z)) for z in (X, M, A))
            LP, ADV, RET = (torch.tensor(np.concatenate(z), dtype=torch.float32) for z in (LP, ADV, RET))
            ADV = (ADV - ADV.mean()) / (ADV.std() + 1e-8)
            n = len(A)
            for _ in range(4):
                for idx in torch.randperm(n).split(1024):
                    logits, v = net(X[idx])
                    logits = logits.masked_fill(~M[idx], -1e9)
                    dist = torch.distributions.Categorical(logits=logits)
                    lp = dist.log_prob(A[idx])
                    ratio = torch.exp(lp - LP[idx])
                    pg = -torch.min(ratio * ADV[idx], torch.clamp(ratio, 0.8, 1.2) * ADV[idx]).mean()
                    loss = pg + 0.5 * ((v - RET[idx]) ** 2).mean() - 0.01 * dist.entropy().mean()
                    opt.zero_grad()
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(net.parameters(), 0.5)
                    opt.step()
            lam = max(0.0, lam + ALPHA_L * (pw - BUDGET))
            log.append({"iter": it, "power_w": pw, "reward": rew, "lambda": lam, "steps": n,
                        "s": round(time.time() - t0, 1)})
            print(json.dumps(log[-1]), flush=True)
            torch.save({"state": net.state_dict(), "lambda": lam, "iter": it}, OUT / "last.pt")
            # keep the best feasible policy of the second half (mean power within 0.1 W of the budget)
            if it >= a.iters // 2 and pw <= BUDGET + 0.1 and (best is None or rew > best):
                best = rew
                torch.save({"state": net.state_dict(), "lambda": lam, "iter": it}, OUT / "best.pt")
            json.dump(log, open(OUT / "train_log.json", "w"), indent=1)
    if best is None:
        shutil.copy(OUT / "last.pt", OUT / "best.pt")


def cmd_eval(a):
    import torch
    import replay_theory_sweep  # noqa: F401  (the sweep's policies, for the v4.1 rows of the same seeds)
    w = setup()
    ck = torch.load(OUT / "best.pt")
    net = make_net()
    net.load_state_dict(ck["state"])
    rows = []
    (OUT / "rows").mkdir(parents=True, exist_ok=True)
    for scenario, phase_s, seeds in (("mission", 240.0, range(1, 6)), ("mission", 20.0, range(1, 11)),
                                     ("random", 20.0, range(1, 11))):
        for s in seeds:
            f = OUT / "rows" / f"{scenario}_{phase_s:g}__r{s}.json"
            if f.exists():
                rows.append(json.load(open(f)))
                continue
            ag = Agent(net, greedy=True)
            R.POLICIES["rl_ppo_lag"] = dict(base="custom", decide=ag)
            path, m = R.Replay("rl_ppo_lag", scenario, phase_s, s, w["gp"], w["c"], w["decays"], w["vd"],
                               w["accs"]).run(OUT / "runs")
            m["sAP"] = R.score(path)
            row = dict(policy="rl_ppo_lag", scenario=scenario, phase_s=phase_s, seed=s,
                       **{k: v for k, v in m.items() if k != "price"})
            json.dump(row, open(f, "w"), indent=1)
            rows.append(row)
            print(json.dumps(row), flush=True)
    json.dump({"checkpoint_iter": ck["iter"], "lambda": ck["lambda"], "rows": rows,
               "method": __doc__.split("\n\n")[1]}, open(OUT / "summary.json", "w"), indent=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train")
    t.add_argument("--iters", type=int, default=120)
    t.add_argument("--workers", type=int, default=3)
    t.add_argument("--out", default=None, help="output directory (smoke tests; default the results directory)")
    sub.add_parser("eval")
    a = ap.parse_args()
    global OUT
    if getattr(a, "out", None):
        OUT = Path(a.out)
    {"train": cmd_train, "eval": cmd_eval}[a.cmd](a)


if __name__ == "__main__":
    main()
