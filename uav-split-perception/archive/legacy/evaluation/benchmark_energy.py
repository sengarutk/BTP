#!/usr/bin/env python3
"""AEGIS-UAV Track 1.4: UAV Energy & Power Modeling Benchmark Suite

Evaluates thermodynamic energy per frame (mJ), 5G transmission energy under
link-capacity duty cycle bounds, energy savings vs. FP32, and mission flight lifetime (hours).
"""

import argparse
import csv
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from tabulate import tabulate

repo_root = Path(__file__).resolve().parent.parent

from evaluation.energy_model import JETSON_NANO_PROFILE, UAVEnergyModel

from utils.logger import get_logger

logger = get_logger("AEGIS-EnergyBenchmark")

PARETO_CSV_PATH = repo_root / "experiments" / "results" / "split_pareto_analysis.csv"
JSON_EXPORT_PATH = repo_root / "experiments" / "results" / "energy_benchmark_results.json"
CSV_EXPORT_PATH = repo_root / "experiments" / "results" / "energy_benchmark_results.csv"

BANDWIDTHS_MBPS = [5.0, 10.0, 20.0, 50.0, 100.0]


def load_pareto_records(csv_path: Path = PARETO_CSV_PATH) -> List[Dict[str, Any]]:
    """Loads benchmarked latency and accuracy records from split_pareto_analysis.csv."""
    if not csv_path.exists():
        logger.warning(f"Pareto CSV not found at {csv_path}. Using fallback default records.")
        return [
            {
                "config_id": "monolithic_baseline",
                "split_cut": "full",
                "dtype_precision": "fp32",
                "map_50": 0.7594,
                "map_50_95": 0.2711,
                "wire_payload_bytes": 0,
                "wire_payload_kib": 0.0,
                "edge_param_pct": 100.0,
                "t_edge_ms": 6.99,
                "t_quant_ms": 0.0,
                "t_cloud_ms": 0.0,
                "t_e2e_compute_ms": 6.99,
            },
            {
                "config_id": "k4_int8",
                "split_cut": "k4",
                "dtype_precision": "int8",
                "map_50": 0.4068,
                "map_50_95": 0.2718,
                "wire_payload_bytes": 819236,
                "wire_payload_kib": 800.04,
                "edge_param_pct": 2.87,
                "t_edge_ms": 1.48,
                "t_quant_ms": 0.28,
                "t_cloud_ms": 7.26,
                "t_e2e_compute_ms": 9.02,
            },
            {
                "config_id": "k4_fp32",
                "split_cut": "k4",
                "dtype_precision": "fp32",
                "map_50": 0.7594,
                "map_50_95": 0.2711,
                "wire_payload_bytes": 3276836,
                "wire_payload_kib": 3200.04,
                "edge_param_pct": 2.87,
                "t_edge_ms": 1.48,
                "t_quant_ms": 0.0,
                "t_cloud_ms": 7.26,
                "t_e2e_compute_ms": 8.74,
            },
            {
                "config_id": "k9_int8",
                "split_cut": "k9",
                "dtype_precision": "int8",
                "map_50": 0.4046,
                "map_50_95": 0.2712,
                "wire_payload_bytes": 1433668,
                "wire_payload_kib": 1400.07,
                "edge_param_pct": 45.46,
                "t_edge_ms": 3.65,
                "t_quant_ms": 0.52,
                "t_cloud_ms": 5.02,
                "t_e2e_compute_ms": 9.19,
            },
            {
                "config_id": "k9_fp32",
                "split_cut": "k9",
                "dtype_precision": "fp32",
                "map_50": 0.7594,
                "map_50_95": 0.2711,
                "wire_payload_bytes": 5734468,
                "wire_payload_kib": 5600.07,
                "edge_param_pct": 45.46,
                "t_edge_ms": 3.65,
                "t_quant_ms": 0.0,
                "t_cloud_ms": 5.02,
                "t_e2e_compute_ms": 8.67,
            },
        ]

    records = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cut = str(row.get("split_tag", row.get("cut_layer", "")))
            if not cut.startswith("k") and cut != "full":
                cut = f"k{cut}"
            dtype = str(row["dtype"]).lower()
            cfg_name = row.get("config_name", f"{cut}_{dtype}")
            records.append({
                "config_id": cfg_name,
                "split_cut": cut,
                "dtype_precision": dtype,
                "map_50": float(row.get("mAP_50", 0.7594)),
                "map_50_95": float(row.get("mAP_50_95", 0.2711)),
                "wire_payload_bytes": int(float(row.get("wire_size_bytes", 0))),
                "wire_payload_kib": float(row.get("wire_size_kib", 0.0)),
                "edge_param_pct": float(row.get("edge_param_pct", 50.0)),
                "t_edge_ms": float(row.get("t_edge_ms_mean", 1.5)),
                "t_quant_ms": float(row.get("t_quant_ms_mean", 0.0)),
                "t_cloud_ms": float(row.get("t_cloud_ms_mean", 5.0)),
                "t_e2e_compute_ms": float(row.get("t_e2e_compute_ms_mean", 6.5)),
            })
    return records


def evaluate_energy_across_configs(
    pareto_records: List[Dict[str, Any]],
    bandwidths: List[float] = BANDWIDTHS_MBPS,
) -> Dict[str, Any]:
    """Evaluates energy consumption, energy savings vs FP32, and flight lifetime."""
    energy_model = UAVEnergyModel(profile=JETSON_NANO_PROFILE)
    logger.info(f"Initiating Energy Benchmark using profile: {energy_model.profile.name}")

    all_energy_records: List[Dict[str, Any]] = []
    fitting_dataset: List[Dict[str, Any]] = []

    # Monolithic baseline reference
    mono_record = next((r for r in pareto_records if "monolithic" in r["config_id"].lower() or r["split_cut"] == "full"), None)
    mono_t_edge = mono_record["t_edge_ms"] if mono_record else 6.99
    mono_breakdown = energy_model.compute_energy_breakdown(
        t_edge_ms=mono_t_edge,
        t_quant_ms=0.0,
        t_tx_ms=0.0,
        t_cloud_ms=0.0,
        edge_param_fraction=1.0,
    )
    mono_battery_hours = energy_model.estimate_battery_lifetime_hours(
        e_edge_mj=mono_breakdown["e_edge_mj"],
        e_quant_mj=0.0,
        p_tx_avg_w=energy_model.profile.p_rx_idle_w,
        delivered_fps=30.0,
    )

    # First pass: calculate baseline records and index FP32 energy per cut & bandwidth
    fp32_energy_map: Dict[tuple, float] = {}

    temp_evals = []
    for r in pareto_records:
        cfg_id = r["config_id"]
        cut_k = r["split_cut"]
        dtype = r["dtype_precision"]
        map50 = r["map_50"]
        map50_95 = r["map_50_95"]
        payload_bytes = r["wire_payload_bytes"]
        payload_kib = r["wire_payload_kib"]
        param_fraction = r["edge_param_pct"] / 100.0

        t_edge = r["t_edge_ms"]
        t_quant = r["t_quant_ms"]
        t_cloud = r["t_cloud_ms"]

        for bw in bandwidths:
            dc_info = energy_model.compute_duty_cycle_power(
                payload_bytes=payload_bytes,
                bw_mbps=bw,
                target_fps=30.0,
            )
            t_tx_ms = dc_info["t_tx_ms"]
            delivered_fps = dc_info["delivered_fps"]
            duty_cycle_tx = dc_info["duty_cycle_tx"]
            p_tx_avg_w = dc_info["p_tx_avg_w"]

            e_breakdown = energy_model.compute_energy_breakdown(
                t_edge_ms=t_edge,
                t_quant_ms=t_quant,
                t_tx_ms=t_tx_ms,
                t_cloud_ms=t_cloud,
                edge_param_fraction=param_fraction,
            )

            t_total_ms = t_edge + t_quant + t_tx_ms + t_cloud
            e_uav_mj = e_breakdown["e_uav_total_mj"]

            if dtype == "fp32":
                fp32_energy_map[(cut_k, bw)] = e_uav_mj

            batt_hours = energy_model.estimate_battery_lifetime_hours(
                e_edge_mj=e_breakdown["e_edge_mj"],
                e_quant_mj=e_breakdown["e_quant_mj"],
                p_tx_avg_w=p_tx_avg_w,
                delivered_fps=delivered_fps,
            )
            batt_minutes = energy_model.estimate_battery_lifetime_minutes(
                e_edge_mj=e_breakdown["e_edge_mj"],
                e_quant_mj=e_breakdown["e_quant_mj"],
                p_tx_avg_w=p_tx_avg_w,
                delivered_fps=delivered_fps,
            )
            p_perception_w = ((e_breakdown["e_edge_mj"] + e_breakdown["e_quant_mj"]) * delivered_fps / 1000.0) + p_tx_avg_w
            p_total_w = 125.0 + p_perception_w
            perception_share_pct = (p_perception_w / p_total_w) * 100.0
            batt_extension_factor = (batt_hours / max(mono_battery_hours, 1e-4)) if mono_battery_hours > 0 else 1.0

            temp_evals.append({
                "cfg_id": cfg_id,
                "cut_k": cut_k,
                "dtype": dtype,
                "bw": bw,
                "map50": map50,
                "map50_95": map50_95,
                "payload_bytes": payload_bytes,
                "payload_kib": payload_kib,
                "delivered_fps": delivered_fps,
                "duty_cycle_tx": duty_cycle_tx,
                "p_tx_avg_w": p_tx_avg_w,
                "p_perception_w": round(p_perception_w, 2),
                "p_total_w": round(p_total_w, 2),
                "perception_share_pct": round(perception_share_pct, 2),
                "t_edge": t_edge,
                "t_quant": t_quant,
                "t_tx_ms": t_tx_ms,
                "t_cloud": t_cloud,
                "t_total_ms": t_total_ms,
                "e_breakdown": e_breakdown,
                "e_uav_mj": e_uav_mj,
                "batt_hours": batt_hours,
                "batt_minutes": batt_minutes,
                "batt_extension_factor": batt_extension_factor,
            })

    # Second pass: compute energy savings vs FP32 for the same cut and bandwidth
    for t in temp_evals:
        cut_k = t["cut_k"]
        bw = t["bw"]
        e_uav_mj = t["e_uav_mj"]
        fp32_e_uav = fp32_energy_map.get((cut_k, bw), e_uav_mj)

        if fp32_e_uav > 0 and t["dtype"] != "fp32":
            energy_savings_pct = max(0.0, (1.0 - (e_uav_mj / fp32_e_uav)) * 100.0)
        else:
            energy_savings_pct = 0.0

        rec = {
            "config_id": t["cfg_id"],
            "split_cut": cut_k,
            "dtype_precision": t["dtype"],
            "bandwidth_mbps": bw,
            "map_50": t["map50"],
            "map_50_95": t["map50_95"],
            "payload_bytes": t["payload_bytes"],
            "payload_kib": t["payload_kib"],
            "delivered_fps": t["delivered_fps"],
            "duty_cycle_tx": t["duty_cycle_tx"],
            "p_tx_avg_w": t["p_tx_avg_w"],
            "t_edge_ms": round(t["t_edge"], 2),
            "t_quant_ms": round(t["t_quant"], 2),
            "t_tx_ms": round(t["t_tx_ms"], 2),
            "t_cloud_ms": round(t["t_cloud"], 2),
            "t_total_ms": round(t["t_total_ms"], 2),
            "e_edge_mj": t["e_breakdown"]["e_edge_mj"],
            "e_quant_mj": t["e_breakdown"]["e_quant_mj"],
            "e_tx_mj": t["e_breakdown"]["e_tx_mj"],
            "e_uav_total_mj": e_uav_mj,
            "e_cloud_mj": t["e_breakdown"]["e_cloud_mj"],
            "e_system_total_mj": t["e_breakdown"]["e_system_total_mj"],
            "energy_savings_pct_vs_fp32": round(energy_savings_pct, 2),
            "p_perception_w": t["p_perception_w"],
            "p_total_w": t["p_total_w"],
            "perception_share_pct": t["perception_share_pct"],
            "battery_lifetime_hours": t["batt_hours"],
            "battery_lifetime_minutes": t["batt_minutes"],
            "battery_extension_factor": round(t["batt_extension_factor"], 2),
        }
        all_energy_records.append(rec)

        if "monolithic" not in t["cfg_id"].lower() and cut_k != "full":
            fitting_dataset.append(rec)

    # Fit Parametric Model
    fit_results = UAVEnergyModel.fit_parametric_model(fitting_dataset)
    logger.info(f"Parametric Model Fit: {fit_results['equation']} (R^2 = {fit_results['r_squared']})")

    # Export JSON
    export_payload = {
        "metadata": {
            "title": "AEGIS-UAV Split Perception Energy & Power Benchmark",
            "profile": energy_model.profile.name,
            "battery_capacity_wh": energy_model.profile.battery_capacity_wh,
            "bandwidths_evaluated_mbps": bandwidths,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "parametric_model": fit_results,
        "monolithic_reference": {
            "e_uav_mj": mono_breakdown["e_uav_total_mj"],
            "battery_lifetime_hours": mono_battery_hours,
        },
        "records": all_energy_records,
    }

    with open(JSON_EXPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(export_payload, f, indent=2)
    logger.info(f"Exported Energy Benchmark JSON -> {JSON_EXPORT_PATH}")

    # Export CSV
    csv_headers = [
        "config_id", "split_cut", "dtype_precision", "bandwidth_mbps",
        "map_50", "map_50_95", "payload_kib", "delivered_fps", "duty_cycle_tx",
        "t_edge_ms", "t_quant_ms", "t_tx_ms", "t_cloud_ms", "t_total_ms",
        "e_edge_mj", "e_quant_mj", "e_tx_mj", "e_uav_total_mj", "e_cloud_mj", "e_system_total_mj",
        "energy_savings_pct_vs_fp32", "p_perception_w", "p_total_w", "perception_share_pct",
        "battery_lifetime_hours", "battery_lifetime_minutes", "battery_extension_factor",
    ]

    with open(CSV_EXPORT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers)
        writer.writeheader()
        for r in all_energy_records:
            writer.writerow({k: r.get(k, "") for k in csv_headers})
    logger.info(f"Exported Energy Benchmark CSV -> {CSV_EXPORT_PATH}")

    # Print Summary Table @ 20 Mbps with explicit required columns
    table_rows = []
    recs_20mbps = [r for r in all_energy_records if r["bandwidth_mbps"] == 20.0]
    for r in recs_20mbps:
        cfg_label = r["config_id"]
        if "monolithic" in cfg_label.lower() or r["split_cut"] == "full":
            name_str = "Monolithic Baseline (Full Edge)"
        else:
            cut_str = str(r['split_cut']).lower()
            if cut_str == "k9":
                name_str = f"k9 Multi-Scale Bundle ({r['dtype_precision'].upper()})"
            else:
                name_str = f"{cut_str.upper()} ({r['dtype_precision'].upper()})"

        wire_mib = r['payload_kib'] / 1024.0
        wire_str = f"{r['payload_kib']:.1f} KiB ({wire_mib:.2f} MiB)" if r["payload_kib"] > 0 else "0.0 KiB"

        table_rows.append([
            name_str,
            wire_str,
            f"{r['e_edge_mj']:.1f} mJ",
            f"{r['e_tx_mj']:.1f} mJ",
            f"{r['e_uav_total_mj']:.1f} mJ",
            f"{r['energy_savings_pct_vs_fp32']:.1f}%" if r["energy_savings_pct_vs_fp32"] > 0 else "0.0% (Ref)",
            f"{r.get('battery_lifetime_minutes', r['battery_lifetime_hours']*60):.1f} min ({r['battery_lifetime_hours']:.2f} h)",
        ])

    headers = [
        "Configuration Name",
        "Wire Footprint (KiB / MiB)",
        "E_edge (mJ)",
        "E_tx @ 20 Mbps (mJ)",
        "Total E_uav (mJ)",
        "Energy Savings vs. FP32 (%)",
        "Sustained Flight Time (Hours)"
    ]

    print("\n" + "=" * 145)
    print("                    AEGIS-UAV ON-DRONE ENERGY & BATTERY LIFETIME BENCHMARK (@ 20 Mbps)")
    print("=" * 145)
    print(tabulate(table_rows, headers=headers, tablefmt="fancy_grid"))
    print("=" * 145 + "\n")

    return export_payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run UAV Energy & Power Benchmark Suite")
    args = parser.parse_args()

    pareto_recs = load_pareto_records()
    evaluate_energy_across_configs(pareto_recs)
