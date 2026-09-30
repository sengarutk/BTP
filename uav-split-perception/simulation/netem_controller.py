"""Optional live link emulation with Linux ``tc netem`` (requires root).

Replays a channel trace onto a network interface so the real ZeroMQ edge/cloud pipelines
(pipeline/edge_pipeline.py, pipeline/cloud_pipeline.py) can be exercised under the same
conditions the simulator uses. None of the reported results depend on this module; they
come from simulation/stream_sim.py, which models the link analytically.
"""

import argparse
import csv
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List

from utils.logger import get_logger

logger = get_logger("NetemController")


class KernelNetemController:
    """Thin wrapper around ``tc qdisc ... netem`` on one interface."""

    def __init__(self, interface: str = "lo", use_sudo: bool = True):
        self.interface = interface
        self.prefix = ["sudo", "-n"] if use_sudo else []

    @staticmethod
    def is_available() -> bool:
        return shutil.which("tc") is not None

    def _tc(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(self.prefix + ["tc", *args], capture_output=True, text=True, check=False)

    def apply(self, bandwidth_mbps: float, delay_ms: float, loss_pct: float) -> bool:
        cmd = ["qdisc", "replace", "dev", self.interface, "root", "netem", "delay", f"{max(delay_ms, 0):.1f}ms"]
        if loss_pct > 0:
            cmd += ["loss", f"{min(loss_pct, 100.0):.3f}%"]
        cmd += ["rate", f"{max(bandwidth_mbps, 0.001):.3f}mbit"]
        res = self._tc(*cmd)
        if res.returncode != 0:
            logger.error(f"tc failed: {res.stderr.strip()}")
        return res.returncode == 0

    def clear(self) -> bool:
        res = self._tc("qdisc", "del", "dev", self.interface, "root")
        return res.returncode == 0


def load_trace(path: Path) -> List[Dict[str, float]]:
    with open(path, newline="", encoding="utf-8") as f:
        return [{k: float(v) for k, v in row.items()} for row in csv.DictReader(f)]


def replay(trace: Path, interface: str, update_ms: float = 100.0) -> None:
    """Applies the trace to ``interface`` in real time, averaging over ``update_ms`` windows."""
    rows = load_trace(trace)
    ctl = KernelNetemController(interface)
    step = max(1, int(update_ms / 10.0))
    t0 = time.perf_counter()
    try:
        for i in range(0, len(rows), step):
            win = rows[i:i + step]
            ok = ctl.apply(sum(r["bandwidth_mbps"] for r in win) / len(win),
                           sum(r["delay_ms"] for r in win) / len(win),
                           sum(r["packet_loss_pct"] for r in win) / len(win))
            if not ok:
                break
            time.sleep(max(0.0, t0 + (i + step) * 0.01 - time.perf_counter()))
    finally:
        ctl.clear()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trace", required=True, type=Path)
    ap.add_argument("--interface", default="lo")
    args = ap.parse_args()
    replay(args.trace, args.interface)
