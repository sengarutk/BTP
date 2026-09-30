"""Exports edge/cloud submodels for deployment: TorchScript always, ONNX and TensorRT when available.

    python deployment/jetson/export_trt.py --cuts 4 9 [--fp16]

TorchScript files run anywhere PyTorch runs. ONNX export needs the `onnx` package; building a
TensorRT engine needs the `tensorrt` package (typically on the Jetson itself, via JetPack).
Nothing is reported as exported unless the file was actually written and re-loaded.
"""

import argparse
from pathlib import Path
from typing import Dict, List, Tuple

import torch
import torch.nn as nn
from ultralytics import YOLO

from core.dynamic_submodels import DynamicCloudSubmodel, DynamicEdgeSubmodel
from utils.logger import get_logger

logger = get_logger("ExportTRT")
REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "experiments" / "checkpoints"

try:
    import onnx  # noqa: F401
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False
try:
    import tensorrt as trt
    TRT_AVAILABLE = True
except ImportError:
    TRT_AVAILABLE = False


class EdgeTupleWrapper(nn.Module):
    """Emits the live tensors of a cut as an ordered tuple (graph exporters need fixed outputs)."""

    def __init__(self, edge: DynamicEdgeSubmodel):
        super().__init__()
        self.edge, self.keys = edge, [str(i) for i in edge.output_layer_indices]

    def forward(self, x):
        out = self.edge(x)
        return (out,) if isinstance(out, torch.Tensor) else tuple(out[k] for k in self.keys)


class CloudTupleWrapper(nn.Module):
    """Takes the live tensors positionally and returns the (1, 84, 8400) prediction tensor."""

    def __init__(self, cloud: DynamicCloudSubmodel):
        super().__init__()
        self.cloud, self.keys = cloud, [str(i) for i in cloud.required_inputs]

    def forward(self, *feats):
        inp = feats[0] if len(feats) == 1 else dict(zip(self.keys, feats))
        out = self.cloud(inp)
        return out[0] if isinstance(out, (list, tuple)) else out


def build_engine(onnx_path: Path, engine_path: Path, fp16: bool) -> bool:
    if not TRT_AVAILABLE:
        return False
    log = trt.Logger(trt.Logger.WARNING)
    builder = trt.Builder(log)
    network = builder.create_network(0)
    parser = trt.OnnxParser(network, log)
    if not parser.parse(onnx_path.read_bytes()):
        for i in range(parser.num_errors):
            logger.error(f"TensorRT parser: {parser.get_error(i)}")
        return False
    config = builder.create_builder_config()
    config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, 1 << 30)
    if fp16 and builder.platform_has_fast_fp16:
        config.set_flag(trt.BuilderFlag.FP16)
    engine = builder.build_serialized_network(network, config)
    if engine is None:
        return False
    engine_path.write_bytes(bytes(engine))
    return True


def export_cut(base: nn.Module, cut: int, fp16: bool) -> Dict[str, List[Path]]:
    written: Dict[str, List[Path]] = {"torchscript": [], "onnx": [], "engine": []}
    x = torch.rand(1, 3, 640, 640)
    edge = EdgeTupleWrapper(DynamicEdgeSubmodel(base, cut)).eval()
    cloud = CloudTupleWrapper(DynamicCloudSubmodel(base, cut)).eval()
    with torch.no_grad():
        feats = edge(x)
        ref = cloud(*feats)
    for role, module, inputs, in_names, out_names in (
        ("edge", edge, (x,), ["image"], [f"feat_{k}" for k in edge.keys]),
        ("cloud", cloud, feats, [f"feat_{k}" for k in cloud.keys], ["predictions"]),
    ):
        ts_path = OUT_DIR / f"yolov8s_{role}_k{cut}.torchscript"
        with torch.no_grad():
            traced = torch.jit.trace(module, inputs)
        traced.save(str(ts_path))
        written["torchscript"].append(ts_path)
        if ONNX_AVAILABLE:
            onnx_path = OUT_DIR / f"yolov8s_{role}_k{cut}.onnx"
            torch.onnx.export(module, inputs, str(onnx_path), input_names=in_names, output_names=out_names,
                              opset_version=17, dynamo=False)
            written["onnx"].append(onnx_path)
            engine_path = onnx_path.with_suffix(".engine")
            if build_engine(onnx_path, engine_path, fp16):
                written["engine"].append(engine_path)

    # Re-load the TorchScript pair and check it reproduces the eager output.
    edge_ts = torch.jit.load(str(written["torchscript"][0]))
    cloud_ts = torch.jit.load(str(written["torchscript"][1]))
    with torch.no_grad():
        out = cloud_ts(*edge_ts(x))
    diff = float((out - ref).abs().max())
    if diff > 1e-4:
        raise AssertionError(f"TorchScript k{cut} pair deviates from eager model (max |diff| = {diff:.2e})")
    logger.success(f"k{cut}: TorchScript pair verified (max |diff| = {diff:.1e})")
    return written


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--weights", default="yolov8s.pt")
    ap.add_argument("--cuts", type=int, nargs="+", default=[4, 9])
    ap.add_argument("--fp16", action="store_true")
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = YOLO(args.weights).model.eval()
    for k in args.cuts:
        w = export_cut(base, k, args.fp16)
        logger.info(f"k{k}: {sum(map(len, w.values()))} files written: " + ", ".join(p.name for v in w.values() for p in v))
    if not ONNX_AVAILABLE:
        logger.warning("`onnx` not installed: ONNX export skipped (pip install onnx)")
    if not TRT_AVAILABLE:
        logger.warning("`tensorrt` not installed: no TensorRT engines built (run this on the Jetson with JetPack)")
