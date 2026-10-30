"""The board's planner core (mpc_planner.py) makes the same choices as the replay planner of 19.10 (replay_accumo.py)
when given the same state, frame by frame over short replayed missions."""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

HW = Path(__file__).resolve().parent.parent / "validation" / "hardware"
sys.path.insert(0, str(HW))

R = pytest.importorskip("replay")
pytest.importorskip("cv2")
if not (R.VID / "egomotion.npz").exists() or not (R.HW / "decay_context_train.json").exists():
    pytest.skip("replay data not present", allow_module_level=True)
import mpc_planner as M  # noqa: E402
import replay_accumo as A  # noqa: E402
import replay_oracle as O  # noqa: E402


class Checked(A.AccuMOReplay):
    """Each tick: the core's choice from the replay's state, then the replay's own choice; they must agree."""

    def plan(self, t):
        tick = int(round(t / R.PERIOD))
        lag, rat = (self.ctx_lag, self.ctx_rat[self.tertile(tick)]) if "ctx" in self.cfg else (self.lag, self.rat)
        shown = int(round(tick - self.aoi / 1e3 / R.PERIOD)) if math.isfinite(self.aoi) else -10 ** 9
        sent = {k: v for k, v in self.sent.items() if k == shown or (k > shown and t - v[3] < R.STALL_S)}
        sent = {k: v for k, v in sent.items() if k == shown or v[0] == "onboard" or self.links[v[0]].up}
        inflight = [(shown, sent[shown][2], -math.inf)] if shown in sent else []
        for k, (srv, var, a, t_arr, _, t_send, rest) in sorted(sent.items()):
            if k <= shown:
                continue
            if srv != "onboard":
                L_ = self.links[srv]
                if not L_.up:
                    continue
                if L_.inflight is not None and abs(L_.inflight[0] - t_send) < 1e-9:
                    t_arr = t_send + L_.inflight[1] * 8 / (max(L_.est(t)[0], 1e-3) * 1e6) + rest
            inflight.append((k, a, M.overdue_arrival(t_arr, t, R.PERIOD)))
        free = {"onboard": max(self.onb_free, t)}
        for p in self.links:
            if self.links[p].idle(t):
                free[p] = t
            else:
                fr = [v[4] for v in sent.values() if v[0] == p and v[4] > t]
                free[p] = max(fr) if fr else t + R.PERIOD
        price = self.cam_price() if "energy" in self.cfg else 0.0
        if price and all(self.option(p, v, t) is None for p in self.links for v in A.OPTS[p]):
            price = 0.0
        opts = {s: [(v,) + o for v in A.OPTS[s] if (o := self.option(s, v, t)) is not None] for s in A.SERVERS}
        idle = {"laptop": self.links["laptop"].idle(t), "jetson": self.links["jetson"].idle(t),
                "onboard": self.onb_free <= t}
        got = M.plan(t, tick, R.PERIOD, A.H, opts, free, idle, inflight, lag, rat, price)
        want = super().plan(t)
        self.checked.append((None if got is None else got[:2], want))
        return want


@pytest.mark.parametrize("pol", ["accumo", "accumo_energy"])
def test_core_matches_replay(tmp_path, pol):
    gp = R.load_goodput()
    c, decays, accs, vd = R.load_all()
    rp = Checked(pol, "mission", 3.0, 1, gp, c, decays, vd, accs)
    rp.checked = []
    rp.run(tmp_path)
    assert len(rp.checked) > 300
    assert sum(w is not None for _, w in rp.checked) > 50
    bad = [(i, g, w) for i, (g, w) in enumerate(rp.checked) if g != w]
    assert not bad, bad[:5]


def test_plan_prefers_fresh_accurate_results():
    """A toy state: a fast accurate path beats a slow onboard model; nothing idle -> nothing started."""
    lag, rat = np.array([0.0, 300.0, 1000.0]), np.array([1.0, 0.8, 0.3])
    opts = {"laptop": [("s640q90", 0.06, 0.04, 1.0, 0.1)], "onboard": [("n320", 0.1, 0.1, 0.4, 0.4)]}
    free = {"laptop": 0.0, "onboard": 0.0}
    got = M.plan(0.0, 0, 1 / 30, 30, opts, free, {"laptop": True, "onboard": True}, [], lag, rat)
    assert got is not None and got[:2] == ("laptop", "s640q90") and got[2] > 0
    assert M.plan(0.0, 0, 1 / 30, 30, opts, free, {"laptop": False, "onboard": False}, [], lag, rat) is None
