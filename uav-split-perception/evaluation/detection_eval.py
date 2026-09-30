"""Shared detection-accuracy machinery for the accuracy, quantization-mode, and codec benchmarks.

* ``resolve_dataset``      maps a short name to a dataset YAML inside the repository.
* ``install_split_quant_hooks`` quantizes exactly the tensors that cross the edge/cloud
  boundary for cut k, and nothing else (edge-side layers keep full-precision inputs).
* ``run_validation``       runs Ultralytics validation and captures per-image statistics.
* ``paired_bootstrap``     gives a confidence interval for the mAP difference between two
  configurations evaluated on the same images (resampling images with replacement).
"""

import copy
import pickle
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from ultralytics.utils import metrics as ul_metrics

from core.dynamic_submodels import analyze_split_dependencies
from quantization import nbit
from quantization.quantizer import DTYPE_FP32, FeatureMapQuantizer

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASETS = {
    "coco_val2017": REPO_ROOT / "datasets" / "coco_val2017.yaml",
    "coco128": REPO_ROOT / "datasets" / "coco128.yaml",
    "visdrone_val": REPO_ROOT / "datasets" / "visdrone_val.yaml",
}
DEFAULT_DATASET = "coco_val2017"
STATS_CACHE = REPO_ROOT / "experiments" / "cache" / "val_stats"
NBIT_DTYPES = {f"int{b}" for b in range(2, 8)}


def resolve_dataset(name_or_path: str) -> Path:
    if name_or_path in DATASETS:
        path = DATASETS[name_or_path]
    else:
        path = Path(name_or_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset config {path} not found; run `make data` first")
    return path


def _quant_roundtrip(t: torch.Tensor, dtype: str) -> torch.Tensor:
    if dtype in NBIT_DTYPES:  # "int2" .. "int7": symmetric per-tensor n-bit (quantization/nbit.py)
        return nbit.roundtrip(t, int(dtype[3:]))
    q, s = FeatureMapQuantizer.quantize(t, dtype=dtype)
    return FeatureMapQuantizer.dequantize(q, s, dtype=dtype, device=t.device, target_dtype=t.dtype)


def install_split_quant_hooks(model: nn.Module, cut: int, dtype: str) -> List[Any]:
    """Quantize->dequantize every activation that crosses cut k, where the cloud consumes it.

    Layer k's own output is consumed only by cloud layers, so a forward hook on layer k is
    exact. Earlier live tensors (skip connections, e.g. L4 and L6 for k=9) are also used by
    edge layers, so they are quantized in forward *pre*-hooks of the cloud layers that read
    them, leaving the edge-side computation in full precision.
    """
    seq = model.model
    if dtype == DTYPE_FP32 or cut >= len(seq) - 1:
        return []
    _, live = analyze_split_dependencies(seq, cut)
    handles = [seq[cut].register_forward_hook(lambda m, i, out: _quant_roundtrip(out, dtype))]

    for d in range(cut + 1, len(seq)):
        f = getattr(seq[d], "f", -1)
        if not isinstance(f, (list, tuple)):
            continue
        positions = [pos for pos, s in enumerate(f)
                     if (s if s >= 0 else d + s) in live and (s if s >= 0 else d + s) != cut]
        if not positions:
            continue

        def pre_hook(module, args, positions=positions):
            inputs = list(args[0])
            for pos in positions:
                inputs[pos] = _quant_roundtrip(inputs[pos], dtype)
            return (inputs,) + tuple(args[1:])

        handles.append(seq[d].register_forward_pre_hook(pre_hook))
    return handles


@contextmanager
def capture_per_image_stats():
    """Records the per-image (tp, conf, pred_cls, target_cls) lists Ultralytics accumulates."""
    captured: Dict[str, List[np.ndarray]] = {}
    original = ul_metrics.DetMetrics.process

    def process(self, *args, **kwargs):
        for k in ("tp", "conf", "pred_cls", "target_cls"):
            captured[k] = [np.asarray(v) for v in self.stats[k]]
        return original(self, *args, **kwargs)

    ul_metrics.DetMetrics.process = process
    try:
        yield captured
    finally:
        ul_metrics.DetMetrics.process = original


def run_validation(yolo, data: str, device: str, name: str, imgsz: int = 640,
                   pre_forward_hook=None, split_hook: Optional[Tuple[int, str]] = None,
                   cache: bool = True) -> Dict[str, Any]:
    """Validates ``yolo`` (batch=1, so per-tensor scales are per image) and returns metrics + stats."""
    data_path = resolve_dataset(data)
    cache_file = STATS_CACHE / Path(data_path).stem / f"{name}.pkl"
    if cache and cache_file.exists():
        with open(cache_file, "rb") as f:
            return pickle.load(f)

    model = yolo.model
    handles = []
    if split_hook is not None:
        handles += install_split_quant_hooks(model, *split_hook)
    if pre_forward_hook is not None:
        handles.append(model.model[0].register_forward_pre_hook(pre_forward_hook))
    try:
        with capture_per_image_stats() as stats:
            m = yolo.val(data=str(data_path), split="val", batch=1, imgsz=imgsz, device=device,
                         plots=False, save_json=False, verbose=False, seed=0, workers=4)
    finally:
        for h in handles:
            h.remove()

    result = {
        "name": name,
        "precision": float(m.box.mp),
        "recall": float(m.box.mr),
        "map50": float(m.box.map50),
        "map50_95": float(m.box.map),
        "num_images": len(stats["tp"]),
        "stats": stats,
    }
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "wb") as f:
        pickle.dump(result, f)
    return result


def map_from_stats(stats: Dict[str, List[np.ndarray]], idx: Optional[np.ndarray] = None) -> Tuple[float, float]:
    """Recomputes (mAP@0.5, mAP@0.5:0.95) from per-image statistics for an image subset."""
    sel = range(len(stats["tp"])) if idx is None else idx
    cat = {k: np.concatenate([stats[k][i] for i in sel], 0) for k in ("tp", "conf", "pred_cls", "target_cls")}
    if cat["tp"].size == 0:
        return 0.0, 0.0
    ap = ul_metrics.ap_per_class(cat["tp"], cat["conf"], cat["pred_cls"], cat["target_cls"])[5]
    return float(ap[:, 0].mean()), float(ap.mean())


_BOOT_STATE: Dict[str, Any] = {}


def _boot_init(base, other, n) -> None:
    _BOOT_STATE.update(base=base, other=other, n=n)


def _boot_worker(seeds: List[int]) -> List[Tuple[float, float]]:
    base, other, n = _BOOT_STATE["base"], _BOOT_STATE["other"], _BOOT_STATE["n"]
    out = []
    for sd in seeds:
        idx = np.random.default_rng(sd).integers(0, n, n)
        b50, b95 = map_from_stats(base, idx)
        o50, o95 = map_from_stats(other, idx)
        out.append((o50 - b50, o95 - b95))
    return out


def _memory_bound_workers(per_worker_gb: float = 1.2, reserve_gb: float = 2.0) -> int:
    """Each spawned worker imports PyTorch (~1 GB resident); stay within the available memory."""
    try:
        with open("/proc/meminfo") as f:
            avail_kb = next(int(line.split()[1]) for line in f if line.startswith("MemAvailable"))
    except (OSError, StopIteration):
        return 4
    return max(1, int((avail_kb / 2**20 - reserve_gb) / per_worker_gb))


def paired_bootstrap(base: Dict[str, Any], other: Dict[str, Any], n_boot: int = 300,
                     seed: int = 0, ci: float = 0.95, workers: Optional[int] = None) -> Dict[str, float]:
    """Paired image-level bootstrap of mAP(other) - mAP(base); both must use the same images.

    Resample r uses np.random.default_rng(seed * 100003 + r), so results do not depend on
    how the resamples are distributed over worker processes.
    """
    import multiprocessing as mp
    import os

    n = base["num_images"]
    if other["num_images"] != n:
        raise ValueError("Paired bootstrap needs both configurations evaluated on the same images")
    seeds = [seed * 100003 + r for r in range(n_boot)]
    _boot_init(base["stats"], other["stats"], n)
    workers = workers or max(1, min(len(os.sched_getaffinity(0)) - 1, 12, n_boot // 25, _memory_bound_workers()))
    if workers > 1:
        # "spawn" is safe in multi-threaded parents (PyTorch); the statistics are sent once per worker.
        chunks = [seeds[i::workers] for i in range(workers)]
        with mp.get_context("spawn").Pool(workers, initializer=_boot_init,
                                          initargs=(base["stats"], other["stats"], n)) as pool:
            diffs = [d for part in pool.map(_boot_worker, chunks) for d in part]
    else:
        diffs = _boot_worker(seeds)
    d50 = [d[0] for d in diffs]
    d95 = [d[1] for d in diffs]
    lo, hi = (1 - ci) / 2 * 100, (1 + ci) / 2 * 100
    return {
        "delta_map50": other["map50"] - base["map50"],
        "delta_map50_ci_low": float(np.percentile(d50, lo)),
        "delta_map50_ci_high": float(np.percentile(d50, hi)),
        "delta_map50_95": other["map50_95"] - base["map50_95"],
        "delta_map50_95_ci_low": float(np.percentile(d95, lo)),
        "delta_map50_95_ci_high": float(np.percentile(d95, hi)),
        "n_boot": n_boot,
    }


def summary_row(result: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in result.items() if k != "stats"}
