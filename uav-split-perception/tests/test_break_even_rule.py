"""evaluation/break_even_rule.py: the break-even rule must hold at every cell where a split code beats the image family."""
import json
from pathlib import Path

import pytest

RES = Path(__file__).resolve().parent.parent / "experiments" / "results" / "break_even" / "break_even.json"


@pytest.mark.skipif(not RES.exists(), reason="run python -m evaluation.break_even_rule first")
def test_rule_has_no_violation_and_covers_every_win():
    d = json.loads(RES.read_text())
    rc = d["rule_check"]
    assert rc["violations"] == []
    assert rc["cells_with_q_star"] == rc["split_win_cells"] > 0
    for r in d["codes"]:
        if r["max_win_mbps"] is not None and r["b_be_mbps"] is not None:
            assert r["max_win_mbps"] < r["b_be_mbps"]


@pytest.mark.skipif(not RES.exists(), reason="run python -m evaluation.break_even_rule first")
def test_survey_rows_satisfy_proposition_2():
    s = json.loads(RES.read_text())["survey"]
    assert s["rows"] == s["prop2_holds"] and s["models"] >= 19
