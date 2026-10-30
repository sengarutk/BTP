"""Board-session tools of 29 Oct 2026: the hardware calibration check bins exactly as the replay's, and the camera-motion
step keeps its 320 px default unless EGO_W_SMALL is set."""
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

HW = Path(__file__).resolve().parent.parent / "validation" / "hardware"
sys.path.insert(0, str(HW))


def test_calib_table_matches_replay():
    pytest.importorskip("cv2")
    O = pytest.importorskip("replay_oracle")
    import calib_hw
    rng = np.random.default_rng(3)
    p = rng.random(500)
    pairs = [(float(x), float(rng.random() < x ** 1.3)) for x in p] + [(1.0, 1.0), (0.0, 0.0)]
    assert calib_hw.calib_table(pairs) == O.calib_table(pairs)
    assert calib_hw.calib_table([]) is None


def test_calib_pairs_from_frames():
    import calib_hw
    run = {"frames": [{"pred": {"p_on": 0.9, "p_late": 1.0}, "lat_ms": 120.0},
                      {"pred": {"p_on": 0.6, "p_late": 0.9}, "lat_ms": 450.0},
                      {"pred": {"p_on": 0.3, "p_late": 0.5}},            # never came back
                      {"server": "onboard"}]}                             # onboard frames carry no prediction
    on, late = calib_hw.pairs_of(run, 300.0, 1000.0)
    assert on == [(0.9, 1.0), (0.6, 0.0), (0.3, 0.0)]
    assert late == [(1.0, 1.0), (0.9, 1.0), (0.5, 0.0)]


def test_ego_width_default_and_override():
    pytest.importorskip("cv2")
    env = dict(os.environ)
    env.pop("EGO_W_SMALL", None)
    code = "import egomotion; print(egomotion.W_SMALL)"
    out = subprocess.run([sys.executable, "-c", code], cwd=HW, env=env, capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "320"
    env["EGO_W_SMALL"] = "160"
    out = subprocess.run([sys.executable, "-c", code], cwd=HW, env=env, capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "160"
