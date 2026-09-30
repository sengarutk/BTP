"""Split-point submodels for YOLOv8 at an arbitrary cut layer k.

``DynamicEdgeSubmodel`` runs layers 0..k and returns every activation that a layer
after k still needs (the "live set"); ``DynamicCloudSubmodel`` runs layers k+1..22 from
those activations. Together they reproduce the monolithic forward pass exactly.
"""

import copy
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import torch
import torch.nn as nn

from utils.logger import get_logger

logger = get_logger("DynamicSubmodels")

CHECKPOINT_FORMAT = "aegis-submodel-v1"
DEFAULT_ARCH = "yolov8s.yaml"


def _layer_sequence(model: nn.Module) -> nn.Module:
    """Returns the nn.Sequential of layers from a YOLO wrapper, DetectionModel, or Sequential."""
    if hasattr(model, "model") and isinstance(getattr(model, "model"), nn.Module):
        inner = model.model
        if hasattr(inner, "model") and isinstance(getattr(inner, "model"), nn.Module):
            return inner.model
        return inner
    return model


def _sources(layer: nn.Module, idx: int) -> List[int]:
    f = getattr(layer, "f", -1)
    items = f if isinstance(f, (list, tuple)) else [f]
    return [s if s >= 0 else idx + s for s in items]


def get_all_save_indices(sequential_layers) -> Set[int]:
    """Indices whose outputs are consumed by a non-adjacent later layer (skip connections)."""
    save: Set[int] = set()
    for idx, layer in enumerate(sequential_layers):
        f = getattr(layer, "f", -1)
        items = f if isinstance(f, (list, tuple)) else [f]
        for s in items:
            if s != -1:
                save.add(s if s >= 0 else idx + s)
    return save


def analyze_split_dependencies(pytorch_model: nn.Module, cut_layer: int) -> Tuple[Set[int], List[int]]:
    """Returns the set (and sorted list) of layers <= cut_layer whose outputs cross the cut."""
    seq = _layer_sequence(pytorch_model)
    total = len(seq)
    if cut_layer >= total - 1:
        return set(), []
    required: Set[int] = {cut_layer}
    for j in range(cut_layer + 1, total):
        for src in _sources(seq[j], j):
            if 0 <= src <= cut_layer:
                required.add(src)
    return required, sorted(required)


def validate_cut(cut_layer: int, total_layers: int) -> int:
    cut = int(cut_layer)
    if not 0 <= cut <= total_layers - 1:
        raise ValueError(f"Cut layer {cut} outside [0, {total_layers - 1}]")
    return cut


def build_architecture(arch: Union[str, dict] = DEFAULT_ARCH) -> nn.Module:
    """Builds an untrained YOLOv8 DetectionModel from a config name or config dict (no download)."""
    from ultralytics.nn.tasks import DetectionModel

    model = DetectionModel(copy.deepcopy(arch) if isinstance(arch, dict) else arch, verbose=False)
    model.eval()
    return model


def _arch_of(base_model: nn.Module) -> Union[str, dict]:
    for m in (base_model, getattr(base_model, "model", None)):
        if isinstance(getattr(m, "yaml", None), dict):
            return copy.deepcopy(m.yaml)
    return DEFAULT_ARCH


def _activation_map(module: nn.Module) -> Dict[str, str]:
    """Activation class per submodule. Needed because Ultralytics versions differ in which
    activations a config builds (e.g. SPPF.cv1), so structure alone does not pin the function."""
    return {name: type(m.act).__name__ for name, m in module.named_modules() if isinstance(getattr(m, "act", None), nn.Module)}


def _restore_activations(module: nn.Module, acts: Dict[str, str]) -> None:
    for name, m in module.named_modules():
        want = acts.get(name)
        if want and type(getattr(m, "act", None)).__name__ != want:
            m.act = getattr(nn, want)()


class DynamicEdgeSubmodel(nn.Module):
    """Runs layers 0..k and returns the activations that cross the cut."""

    def __init__(self, base_model: nn.Module, cut_layer: int, weights_path: Optional[str] = None,
                 device: Union[str, torch.device] = "cpu"):
        super().__init__()
        full_seq = _layer_sequence(base_model)
        self.total_layers = len(full_seq)
        self.cut_layer = validate_cut(cut_layer, self.total_layers)
        self.is_full = self.cut_layer >= self.total_layers - 1
        _, self.output_layer_indices = analyze_split_dependencies(full_seq, self.cut_layer)
        self.save_indices = get_all_save_indices(full_seq) | set(self.output_layer_indices)
        self.layers = nn.ModuleList([copy.deepcopy(full_seq[i]) for i in range(self.cut_layer + 1)])
        self.arch_cfg = _arch_of(base_model)
        if weights_path is not None:
            load_dynamic_submodel_weights(self, weights_path, device=device)
        self.eval()

    def forward(self, x: torch.Tensor) -> Union[torch.Tensor, Dict[str, torch.Tensor], Any]:
        y: List[Optional[torch.Tensor]] = []
        outputs: Dict[str, torch.Tensor] = {}
        for i, layer in enumerate(self.layers):
            f = layer.f
            if f != -1:
                x = y[f] if isinstance(f, int) else [x if j == -1 else y[j] for j in f]
            x = layer(x)
            y.append(x if i in self.save_indices else None)
            if i in self.output_layer_indices:
                outputs[str(i)] = x
        if self.is_full:
            return x
        if len(outputs) == 1 and str(self.cut_layer) in outputs:
            return outputs[str(self.cut_layer)]
        return outputs


class DynamicCloudSubmodel(nn.Module):
    """Runs layers k+1..22 from the activations produced by DynamicEdgeSubmodel."""

    def __init__(self, base_model: nn.Module, cut_layer: int, weights_path: Optional[str] = None,
                 device: Union[str, torch.device] = "cpu", share_modules: bool = False):
        super().__init__()
        full_seq = _layer_sequence(base_model)
        self.total_layers = len(full_seq)
        self.cut_layer = validate_cut(cut_layer, self.total_layers)
        self.is_full = self.cut_layer >= self.total_layers - 1
        self.save_indices = get_all_save_indices(full_seq)
        _, self.required_inputs = analyze_split_dependencies(full_seq, self.cut_layer)
        pick = (lambda m: m) if share_modules else copy.deepcopy
        self.layers = nn.ModuleList(
            [] if self.is_full else [pick(full_seq[i]) for i in range(self.cut_layer + 1, self.total_layers)]
        )
        self.arch_cfg = _arch_of(base_model)
        if weights_path is not None:
            load_dynamic_submodel_weights(self, weights_path, device=device)
        self.eval()

    def forward(self, received_features: Union[torch.Tensor, Dict[str, torch.Tensor]]) -> Any:
        if self.is_full:
            return received_features
        y: List[Optional[torch.Tensor]] = [None] * self.total_layers
        if isinstance(received_features, torch.Tensor):
            if self.required_inputs != [self.cut_layer]:
                raise ValueError(f"Cut k={self.cut_layer} needs layers {self.required_inputs}, got a single tensor")
            y[self.cut_layer] = received_features
        elif isinstance(received_features, dict):
            got = sorted(int(k) for k in received_features)
            if got != self.required_inputs:
                raise ValueError(f"Cut k={self.cut_layer} needs layers {self.required_inputs}, got {got}")
            for k, tensor in received_features.items():
                y[int(k)] = tensor
        else:
            raise TypeError(f"Unsupported feature type: {type(received_features).__name__}")

        x = y[self.cut_layer]
        for layer in self.layers:
            f = layer.f
            if f != -1:
                # y spans every layer, so a relative source j < -1 must be resolved against this
                # layer's index (the edge side gets this for free from its growing list).
                src = lambda j: y[j if j >= 0 else layer.i + j]
                x = src(f) if isinstance(f, int) else [x if j == -1 else src(j) for j in f]
            x = layer(x)
            y[layer.i] = x if layer.i in self.save_indices else None
        return x


def save_submodel_checkpoint(submodel: nn.Module, path: Union[str, Path], role: str) -> None:
    """Saves weights plus everything needed to rebuild the submodule exactly (config, activations)."""
    torch.save(
        {"format": CHECKPOINT_FORMAT, "role": role, "cut_layer": int(submodel.cut_layer),
         "arch": getattr(submodel, "arch_cfg", DEFAULT_ARCH), "activations": _activation_map(submodel),
         "state_dict": submodel.state_dict()},
        str(path),
    )


def load_dynamic_submodel_weights(model: nn.Module, ckpt_path: Union[str, Path], device: Union[str, torch.device] = "cpu") -> None:
    """Loads weights (safe ``weights_only`` loading) into an already-built submodel."""
    ckpt = torch.load(str(ckpt_path), map_location=device, weights_only=True)
    if isinstance(ckpt, dict) and "activations" in ckpt:
        _restore_activations(model, ckpt["activations"])
    state = ckpt["state_dict"] if isinstance(ckpt, dict) and "state_dict" in ckpt else ckpt
    model.load_state_dict(state)


def load_submodel(ckpt_path: Union[str, Path], device: Union[str, torch.device] = "cpu") -> nn.Module:
    """Rebuilds an edge or cloud submodel from its checkpoint alone (no original .pt needed)."""
    ckpt = torch.load(str(ckpt_path), map_location=device, weights_only=True)
    if not (isinstance(ckpt, dict) and ckpt.get("format") == CHECKPOINT_FORMAT):
        raise ValueError(f"{ckpt_path} is not an {CHECKPOINT_FORMAT} checkpoint; re-export it")
    arch = build_architecture(ckpt["arch"])
    cls = DynamicEdgeSubmodel if ckpt["role"] == "edge" else DynamicCloudSubmodel
    sub = cls(arch, cut_layer=ckpt["cut_layer"])
    _restore_activations(sub, ckpt.get("activations", {}))
    sub.load_state_dict(ckpt["state_dict"])
    return sub.to(device).eval()


def build_dynamic_split_submodels(
    weights_path: str = "yolov8s.pt",
    cut_layer: int = 4,
    device: str = "cpu",
) -> Tuple[DynamicEdgeSubmodel, Optional[DynamicCloudSubmodel]]:
    """Builds an (edge, cloud) pair from pretrained weights; cloud is None for the full model."""
    from ultralytics import YOLO

    base = YOLO(weights_path).model.to(device).eval()
    edge = DynamicEdgeSubmodel(base, cut_layer=cut_layer).to(device)
    cloud = None if edge.is_full else DynamicCloudSubmodel(base, cut_layer=cut_layer).to(device)
    return edge, cloud


def verify_arbitrary_split_parity(
    weights_path: str = "yolov8s.pt",
    candidate_cuts: Optional[List[int]] = None,
    device: Optional[str] = None,
    tolerance: float = 0.0,
) -> Dict[int, float]:
    """Checks that edge->cloud reproduces the monolithic output for every cut.

    Both paths execute identical kernels on identical inputs, so the expected
    difference is exactly zero; ``tolerance`` exists only for non-deterministic backends.
    """
    from ultralytics import YOLO

    candidate_cuts = list(range(0, 22)) if candidate_cuts is None else candidate_cuts
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    base = YOLO(weights_path).model.to(device).eval()
    torch.manual_seed(42)
    x = torch.rand(1, 3, 640, 640, device=device)
    with torch.no_grad():
        ref = base(x)
    ref = ref[0] if isinstance(ref, (list, tuple)) else ref

    results: Dict[int, float] = {}
    for k in candidate_cuts:
        edge = DynamicEdgeSubmodel(base, cut_layer=k).to(device)
        cloud = DynamicCloudSubmodel(base, cut_layer=k).to(device)
        with torch.no_grad():
            out = cloud(edge(x))
        out = out[0] if isinstance(out, (list, tuple)) else out
        delta = float((ref - out).abs().max().item())
        results[k] = delta
        if delta > tolerance:
            raise AssertionError(f"Split parity failed at k={k}: max |diff| = {delta:.3e}")
        logger.success(f"[k={k:2d}] edge->cloud output identical to monolithic (max |diff| = {delta:.1e})")
    return results


if __name__ == "__main__":
    res = verify_arbitrary_split_parity()
    print(f"\nAll {len(res)} cut points reproduce the monolithic output exactly.")
