"""evaluation/placement_model_check.py: runs on the committed hardware results and writes the expected JSON."""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_placement_model_check_writes_expected_keys(tmp_path):
    out = tmp_path / "placement_model_check.json"
    subprocess.run([sys.executable, "-m", "evaluation.placement_model_check", "--out", str(out)],
                   cwd=REPO_ROOT, check=True, capture_output=True)
    res = json.loads(out.read_text(encoding="utf-8"))
    for key in ("pairs", "unmatched", "one_or_two_devices", "three_devices", "pi_image_vs_split",
                "one_or_two_devices_order"):
        assert key in res
    for group in ("one_or_two_devices", "three_devices"):
        assert set(res[group]) == {"n", "min_ratio", "max_ratio"}
        assert 0 < res[group]["min_ratio"] <= res[group]["max_ratio"]
    assert res["pairs"], "no live placement matched a model row"
    for p in res["pairs"]:
        assert abs(p["ratio_model_over_live"] - p["model_fps"] / p["live_fps_median"]) < 1e-3
    iv = res["pi_image_vs_split"]
    assert isinstance(iv["model_ranks_every_image_above_every_split"], bool)
    assert isinstance(iv["live_ranks_every_image_above_every_split"], bool)
