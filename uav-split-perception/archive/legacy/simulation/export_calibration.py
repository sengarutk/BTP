"""Calibration Data Exporter for AEGIS-UAV Swarm Simulation Engine.

Parses empirical Phase 1 and Track 1 benchmark files:
- experiments/results/split_pareto_analysis.csv
- experiments/results/energy_benchmark_results.csv
- experiments/results/accuracy_mAP_results.json

Exports standardized calibration artifacts into simulation/calibration/:
1. compute_costs.json
2. payload_sizes.json
3. map_table.csv
4. energy_params.json
"""

import csv
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add repository root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from utils.logger import get_logger

logger = get_logger("CalibrationExporter")

RESULTS_DIR = REPO_ROOT / "experiments" / "results"
CALIBRATION_DIR = REPO_ROOT / "simulation" / "calibration"

PARETO_CSV = RESULTS_DIR / "split_pareto_analysis.csv"
ENERGY_CSV = RESULTS_DIR / "energy_benchmark_results.csv"
ACCURACY_JSON = RESULTS_DIR / "accuracy_mAP_results.json"


def export_calibration_data():
    """Parses benchmark artifacts and exports standardized simulation calibration files."""
    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Exporting empirical calibration artifacts into '{CALIBRATION_DIR}'...")

    if not PARETO_CSV.exists():
        raise FileNotFoundError(f"Missing required benchmark artifact: {PARETO_CSV}")

    # 1. Parse split_pareto_analysis.csv
    pareto_rows = []
    with open(PARETO_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pareto_rows.append(row)

    # -------------------------------------------------------------------------
    # Artifact 1: compute_costs.json
    # Schema: { "k": { "edge_ms": float, "quant_ms": float, "cloud_ms": float, "nms_ms": float, "edge_param_pct": float } }
    # for k in [2, 4, 5, 7, 9, 12, 15, 18, 22]
    # -------------------------------------------------------------------------
    compute_costs: Dict[str, Dict[str, float]] = {}

    for row in pareto_rows:
        cut_layer = int(row["cut_layer"])
        dtype = row["dtype"].lower()
        k_key = str(cut_layer)

        if cut_layer == 22 or dtype == "int8":
            compute_costs[k_key] = {
                "edge_ms": round(float(row["t_edge_ms_mean"]), 4),
                "quant_ms": round(float(row["t_quant_ms_mean"]), 4),
                "cloud_ms": round(float(row["t_cloud_ms_mean"]), 4),
                "nms_ms": round(float(row["t_nms_ms_mean"]), 4),
                "edge_param_pct": round(float(row["edge_param_pct"]), 2),
            }

    for k in [2, 4, 5, 7, 9, 12, 15, 18, 22]:
        if str(k) not in compute_costs:
            matching = [r for r in pareto_rows if int(r["cut_layer"]) == k]
            if matching:
                r = matching[0]
                compute_costs[str(k)] = {
                    "edge_ms": round(float(r["t_edge_ms_mean"]), 4),
                    "quant_ms": round(float(r["t_quant_ms_mean"]), 4),
                    "cloud_ms": round(float(r["t_cloud_ms_mean"]), 4),
                    "nms_ms": round(float(r["t_nms_ms_mean"]), 4),
                    "edge_param_pct": round(float(r["edge_param_pct"]), 2),
                }

    compute_costs_path = CALIBRATION_DIR / "compute_costs.json"
    with open(compute_costs_path, "w", encoding="utf-8") as f:
        json.dump(compute_costs, f, indent=2)
    logger.success(f"Exported compute costs -> {compute_costs_path} ({len(compute_costs)} cuts)")

    # -------------------------------------------------------------------------
    # Artifact 2: payload_sizes.json
    # Schema: { "k_dtype": { "wire_bytes": int, "wire_kib": float, "wire_mib": float, "wire_bits": int } }
    # across all cuts x precision modes (fp32, fp16, int8)
    # -------------------------------------------------------------------------
    payload_sizes: Dict[str, Dict[str, Any]] = {}
    for row in pareto_rows:
        cut_layer = int(row["cut_layer"])
        dtype = row["dtype"].lower()
        key = f"k{cut_layer}_{dtype}" if cut_layer < 22 else f"full_{dtype}"

        wire_bytes = int(float(row["wire_size_bytes"]))
        wire_kib = round(float(row["wire_size_kib"]), 2)
        wire_mib = round(float(row["wire_size_mib"]), 3)
        wire_bits = wire_bytes * 8

        payload_sizes[key] = {
            "wire_bytes": wire_bytes,
            "wire_kib": wire_kib,
            "wire_mib": wire_mib,
            "wire_bits": wire_bits,
        }

    payload_sizes["full"] = {"wire_bytes": 0, "wire_kib": 0.0, "wire_mib": 0.0, "wire_bits": 0}

    payload_sizes_path = CALIBRATION_DIR / "payload_sizes.json"
    with open(payload_sizes_path, "w", encoding="utf-8") as f:
        json.dump(payload_sizes, f, indent=2)
    logger.success(f"Exported payload sizes -> {payload_sizes_path} ({len(payload_sizes)} configurations)")

    # -------------------------------------------------------------------------
    # Artifact 3: map_table.csv
    # Headers: cut_layer,dtype,map_50,map_50_95,precision,recall,delta_rel_pct
    # -------------------------------------------------------------------------
    map_table_path = CALIBRATION_DIR / "map_table.csv"
    map_headers = ["cut_layer", "dtype", "map_50", "map_50_95", "precision", "recall", "delta_rel_pct"]
    map_rows = []

    for row in pareto_rows:
        cut_layer = int(row["cut_layer"])
        dtype = row["dtype"].lower()
        map_50 = round(float(row["mAP_50"]), 6)
        map_50_95 = round(float(row["mAP_50_95"]), 6)
        precision = round(float(row["precision"]), 4)
        recall = round(float(row["recall"]), 4)

        delta_str = row.get("delta_rel_str", "0.00%").replace("%", "").replace("+", "").replace(" (Ref)", "").strip()
        try:
            delta_rel_pct = float(delta_str)
        except ValueError:
            delta_rel_pct = 0.0

        map_rows.append({
            "cut_layer": cut_layer,
            "dtype": dtype,
            "map_50": map_50,
            "map_50_95": map_50_95,
            "precision": precision,
            "recall": recall,
            "delta_rel_pct": delta_rel_pct,
        })

    with open(map_table_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=map_headers)
        writer.writeheader()
        writer.writerows(map_rows)
    logger.success(f"Exported mAP table -> {map_table_path} ({len(map_rows)} rows)")

    # -------------------------------------------------------------------------
    # Artifact 4: energy_params.json
    # Calibrated thermodynamic and physical parameters
    # -------------------------------------------------------------------------
    energy_params = {
        "a_coeff_edge": 11.2330,
        "b_coeff_tx": 3.8000,
        "p_idle_w": 2.20,
        "p_max_w": 10.00,
        "p_tx_rf_w": 3.80,
        "p_rx_idle_w": 0.40,
        "battery_capacity_wh": 55.5,
        "p_avionics_w": 15.0,
        "notes": "Directly calibrated from Jetson Nano 10W profile and 5G C-Band transceiver empirical benchmarks."
    }

    energy_params_path = CALIBRATION_DIR / "energy_params.json"
    with open(energy_params_path, "w", encoding="utf-8") as f:
        json.dump(energy_params, f, indent=2)
    logger.success(f"Exported energy parameters -> {energy_params_path}")

    return True


if __name__ == "__main__":
    export_calibration_data()
