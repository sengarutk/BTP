"""Named split configurations (k4, k6, k9, full) and the multi-cut cloud dispatcher.

EdgeSubmodel / CloudSubmodel are thin, tag-based wrappers around the general
DynamicEdgeSubmodel / DynamicCloudSubmodel, kept for the pipelines and export tools.
"""

import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import torch
import torch.nn as nn

from core.dynamic_submodels import (
    CHECKPOINT_FORMAT,
    DEFAULT_ARCH,
    DynamicCloudSubmodel,
    DynamicEdgeSubmodel,
    _layer_sequence,
    _restore_activations,
    build_architecture,
)

SPLIT_LAYER_MAP = {"k4": 4, "k6": 6, "k9": 9, "full": 22}


def _resolve_split(split_tag: Optional[str], weights_path: Optional[str]) -> Tuple[str, int, Optional[dict]]:
    """Resolves the split from an explicit tag, or from a checkpoint's metadata."""
    ckpt = None
    if weights_path is not None:
        ckpt = torch.load(weights_path, map_location="cpu", weights_only=True)
        if isinstance(ckpt, dict) and ckpt.get("format") == CHECKPOINT_FORMAT:
            cut = int(ckpt["cut_layer"])
            tag = next((t for t, k in SPLIT_LAYER_MAP.items() if k == cut), f"k{cut}")
            if split_tag is not None and SPLIT_LAYER_MAP.get(split_tag) != cut:
                raise ValueError(f"Checkpoint is for cut {cut}, but split_tag={split_tag!r} was requested")
            return tag, cut, ckpt
        m = re.search(r"_(k\d+|full)\b", os.path.basename(weights_path))
        if split_tag is None and m:
            split_tag = m.group(1)
    if split_tag not in SPLIT_LAYER_MAP:
        raise ValueError(f"Unsupported split_tag {split_tag!r}; expected one of {list(SPLIT_LAYER_MAP)}")
    return split_tag, SPLIT_LAYER_MAP[split_tag], ckpt


def _init_named(sub: nn.Module, base_cls: type, base_model: Optional[nn.Module], split_tag: Optional[str],
                weights_path: Optional[str], device: Union[str, torch.device]) -> None:
    """Shared constructor of EdgeSubmodel / CloudSubmodel.

    With only ``weights_path`` the split comes from the checkpoint and ``split_tag`` is ignored.
    """
    tag, cut, ckpt = _resolve_split(split_tag if base_model is not None or weights_path is None else None, weights_path)
    if base_model is None:
        if ckpt is None:
            raise ValueError("Provide base_model or weights_path")
        base_model = build_architecture(ckpt.get("arch", DEFAULT_ARCH) if isinstance(ckpt, dict) else DEFAULT_ARCH)
    base_cls.__init__(sub, base_model, cut_layer=cut)
    sub.split_tag = tag
    sub.split_layer_idx = cut
    if ckpt is not None:
        if isinstance(ckpt, dict):
            _restore_activations(sub, ckpt.get("activations", {}))
        sub.load_state_dict(ckpt["state_dict"] if isinstance(ckpt, dict) and "state_dict" in ckpt else ckpt)
    sub.to(device).eval()


class EdgeSubmodel(DynamicEdgeSubmodel):
    """Onboard part (layers 0..k). k4 returns one tensor; k6/k9 return {'4','6'[,'9']}."""

    def __init__(self, base_model: Optional[nn.Module] = None, split_tag: Optional[str] = "k4",
                 weights_path: Optional[str] = None, device: Union[str, torch.device] = "cpu"):
        _init_named(self, DynamicEdgeSubmodel, base_model, split_tag, weights_path, device)


class CloudSubmodel(DynamicCloudSubmodel):
    """Server part (layers k+1..22) for a named split."""

    def __init__(self, base_model: Optional[nn.Module] = None, split_tag: Optional[str] = "k4",
                 weights_path: Optional[str] = None, device: Union[str, torch.device] = "cpu"):
        _init_named(self, DynamicCloudSubmodel, base_model, split_tag, weights_path, device)
        self.start_layer_idx = self.split_layer_idx + 1


def build_split_submodels(weights: str = "yolov8s.pt", split_tag: str = "k4",
                          device: Optional[str] = None) -> Tuple[EdgeSubmodel, CloudSubmodel]:
    """Builds an (edge, cloud) pair for a named split from pretrained weights."""
    from ultralytics import YOLO

    target = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
    base = YOLO(weights).model.to(target).eval()
    return EdgeSubmodel(base, split_tag=split_tag).to(target), CloudSubmodel(base, split_tag=split_tag).to(target)


class DynamicCloudDispatcher(nn.Module):
    """Serves any split point from ONE copy of the model weights.

    Each branch references the base model's own layer modules (no copies). Branches are
    created lazily for valid cuts only; the split code comes from untrusted packets, so it
    is validated against [0, L-2] before anything is built.
    """

    def __init__(self, base_model: nn.Module, candidate_cuts: Optional[List[int]] = None,
                 device: Union[str, torch.device] = "cpu"):
        super().__init__()
        self.device = torch.device(device)
        self.full_seq = _layer_sequence(base_model).to(self.device)
        self.total_layers = len(self.full_seq)
        self.full_index = self.total_layers - 1
        for p in self.full_seq.parameters():
            p.requires_grad_(False)
        self.branches = nn.ModuleDict()
        for k in [2, 4, 9, 12] if candidate_cuts is None else candidate_cuts:
            self.get_branch(k)
        self.eval()

    def _cut_from_code(self, split_code: Union[str, int]) -> Optional[int]:
        if isinstance(split_code, str):
            key = split_code.strip().lower()
            if key in ("full", "sentinel"):
                return None
            if key.startswith("k"):
                key = key[1:]
            if not key.isdigit():
                raise ValueError(f"Invalid split code {split_code!r}")
            cut = int(key)
        elif isinstance(split_code, int) and not isinstance(split_code, bool):
            cut = split_code
        else:
            raise TypeError(f"Invalid split code type {type(split_code).__name__}")
        if cut == 255 or cut == self.full_index:
            return None
        if not 0 <= cut < self.full_index:
            raise ValueError(f"Split code {split_code!r} outside valid cut range [0, {self.full_index - 1}]")
        return cut

    def get_branch(self, split_code: Union[str, int]) -> Optional[nn.Module]:
        cut = self._cut_from_code(split_code)
        if cut is None:
            return None
        key = f"k{cut}"
        if key not in self.branches:
            self.branches[key] = DynamicCloudSubmodel(self.full_seq, cut_layer=cut, share_modules=True)
        return self.branches[key]

    def forward(self, received_features: Union[torch.Tensor, Dict[str, torch.Tensor]],
                split_code: Union[str, int] = "k4") -> Any:
        branch = self.get_branch(split_code)
        return received_features if branch is None else branch(received_features)
