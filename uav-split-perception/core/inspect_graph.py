#!/usr/bin/env python3
"""YOLOv8s graph inspection: per-layer compute, parameters, shapes, and per-cut payloads.

Compute is reported in MACs (multiply-accumulates, as counted by thop) and in FLOPs,
using the usual convention FLOPs = 2 x MACs. For every candidate cut k the script records
which activations cross the cut (the live set), their shapes, and their wire size.

Outputs: docs/model_graph_inspection.json, experiments/results/yolov8s_graph_topology.json,
and configs/split_config.yaml.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import thop
import torch
import yaml
from tabulate import tabulate
from ultralytics import YOLO

from core.dynamic_submodels import DynamicEdgeSubmodel, analyze_split_dependencies
from utils.logger import get_logger

REPO_ROOT = Path(__file__).resolve().parent.parent
logger = get_logger("GraphInspector")

CANDIDATE_CUTS = [2, 4, 5, 7, 9, 12, 15, 18]
BYTES_PER_ELEM = {"fp32": 4, "fp16": 2, "int8": 1}


def _macs(module: torch.nn.Module, x: torch.Tensor) -> float:
    macs, _ = thop.profile(module, inputs=(x,), verbose=False)
    return float(macs)


def inspect_yolov8s_graph(weights_path: str = "yolov8s.pt", imgsz: int = 640) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    yolo = YOLO(weights_path)
    model = yolo.model.eval()
    layers = list(model.model.children())
    x = torch.zeros(1, 3, imgsz, imgsz)

    shapes: Dict[int, List[int]] = {}
    hooks = []
    for i, layer in enumerate(layers):
        def hook(_m, _inp, out, i=i):
            t = out if isinstance(out, torch.Tensor) else out[0]
            shapes[i] = list(t.shape)
        hooks.append(layer.register_forward_hook(hook))
    with torch.no_grad():
        model(x)
    for h in hooks:
        h.remove()

    total_params = sum(p.numel() for p in model.parameters())
    cum_macs: Dict[int, float] = {}
    for k in range(len(layers)):
        cum_macs[k] = _macs(DynamicEdgeSubmodel(model, cut_layer=k), x)
    total_macs = cum_macs[len(layers) - 1]
    logger.info(f"Total: {total_macs / 1e9:.3f} GMACs = {2 * total_macs / 1e9:.3f} GFLOPs, {total_params:,} params")

    layers_info: List[Dict[str, Any]] = []
    cum_params = 0
    for i, layer in enumerate(layers):
        params = sum(p.numel() for p in layer.parameters())
        cum_params += params
        layer_macs = cum_macs[i] - (cum_macs[i - 1] if i else 0.0)
        layers_info.append({
            "layer_idx": i,
            "layer_type": layer.__class__.__name__,
            "from_idx": getattr(layer, "f", -1),
            "params": params,
            "cumulative_params": cum_params,
            "cumulative_param_pct": round(100.0 * cum_params / total_params, 2),
            "gmacs": round(layer_macs / 1e9, 4),
            "gflops": round(2 * layer_macs / 1e9, 4),
            "cumulative_gmacs": round(cum_macs[i] / 1e9, 4),
            "cumulative_gflops": round(2 * cum_macs[i] / 1e9, 4),
            "cumulative_flop_pct": round(100.0 * cum_macs[i] / total_macs, 2),
            "section": "backbone" if i <= 9 else ("head" if i == len(layers) - 1 else "neck"),
            "output_shape": shapes[i],
        })

    splits: Dict[str, Any] = {}
    for k in CANDIDATE_CUTS + [len(layers) - 1]:
        _, live = analyze_split_dependencies(model, k)
        tensors = {}
        for idx in live:
            n = int(np.prod(shapes[idx]))
            tensors[str(idx)] = {"shape": shapes[idx], "num_elements": n,
                                 **{f"size_{d}_kib": round(n * b / 1024.0, 1) for d, b in BYTES_PER_ELEM.items()}}
        n_total = sum(t["num_elements"] for t in tensors.values())
        tag = "full" if k == len(layers) - 1 else f"k{k}"
        splits[tag] = {
            "cut_layer": k,
            "edge_layers": list(range(k + 1)),
            "cloud_layers": list(range(k + 1, len(layers))),
            "edge_gmacs": round(cum_macs[k] / 1e9, 3),
            "edge_gflops": round(2 * cum_macs[k] / 1e9, 3),
            "edge_flop_pct": round(100.0 * cum_macs[k] / total_macs, 2),
            "edge_param_pct": round(100.0 * sum(l["params"] for l in layers_info[: k + 1]) / total_params, 2),
            "live_layers": live,
            "tensors": tensors,
            "total_elements": n_total,
            **{f"payload_{d}_kib": round(n_total * b / 1024.0, 1) for d, b in BYTES_PER_ELEM.items()},
        }
    summary = {"total_gmacs": round(total_macs / 1e9, 3), "total_gflops": round(2 * total_macs / 1e9, 3),
               "total_params": total_params, "input_shape": [1, 3, imgsz, imgsz],
               "input_uint8_kib": round(3 * imgsz * imgsz / 1024.0, 1)}
    return layers_info, {"summary": summary, "splits": splits}


def export_inspection_artifacts(layers_info: List[Dict[str, Any]], topology: Dict[str, Any]) -> None:
    payload = {"layers": layers_info, **topology}
    for path in (REPO_ROOT / "docs" / "model_graph_inspection.json",
                 REPO_ROOT / "experiments" / "results" / "yolov8s_graph_topology.json"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.success(f"Wrote {path.relative_to(REPO_ROOT)}")
    cfg = REPO_ROOT / "configs" / "split_config.yaml"
    cfg.write_text("# Generated by core/inspect_graph.py -- do not edit by hand.\n"
                   + yaml.safe_dump(topology["splits"], sort_keys=False), encoding="utf-8")
    logger.success(f"Wrote {cfg.relative_to(REPO_ROOT)}")


def print_inspection_tables(layers_info: List[Dict[str, Any]], topology: Dict[str, Any]) -> None:
    print(tabulate([[f"L{l['layer_idx']}", l["layer_type"], tuple(l["output_shape"]), f"{l['params']:,}",
                     f"{l['gflops']:.3f}", f"{l['cumulative_flop_pct']:.1f}%"] for l in layers_info],
                   headers=["Layer", "Type", "Output", "Params", "GFLOPs", "Cum. FLOP %"], tablefmt="github"))
    print()
    print(tabulate([[t, s["cut_layer"], s["live_layers"], f"{s['edge_flop_pct']:.1f}%", s["payload_int8_kib"]]
                    for t, s in topology["splits"].items()],
                   headers=["Split", "k", "Live layers", "Edge FLOP %", "INT8 payload (KiB)"], tablefmt="github"))


if __name__ == "__main__":
    layers, topo = inspect_yolov8s_graph("yolov8s.pt")
    print_inspection_tables(layers, topo)
    export_inspection_artifacts(layers, topo)
