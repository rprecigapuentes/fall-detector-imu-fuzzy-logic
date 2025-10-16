#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Reads labeled IMU logs (CSV-like .txt), computes windowed features and suggests
initial fuzzy membership parameters based on ADL vs FALL distributions.

Input format expected (header):
t,ax,ay,az,gx,gy,gz,a_mag,w_mag,label,event_id,label_change

Outputs:
- CSV with windowed features per segment
- JSON with suggested universes and triangular membership params for:
  - acceleration magnitude (g)
  - angular speed magnitude (deg/s)
  - tilt delta (deg)

Threshold heuristic:
- For each feature, take ADL p95 and FALL p50, then set a decision threshold as
  the midpoint. Membership triangles are built around these anchors.
"""

import argparse
import json
import math
import os
from typing import Dict, Tuple

import numpy as np
import pandas as pd


def tilt_deg(ax: np.ndarray, ay: np.ndarray, az: np.ndarray) -> np.ndarray:
    """
    Trunk tilt relative to gravity axis. 0 deg = upright, ~90 deg = horizontal.
    Robust and cheap using only accelerometer.
    """
    horiz = np.sqrt(ax * ax + ay * ay)
    ang = np.degrees(np.arctan2(horiz, np.abs(az) + 1e-9))
    return np.clip(ang, 0, 180)


def compute_window_features(df: pd.DataFrame, win_s: float, hop_s: float) -> pd.DataFrame:
    """
    Slice the stream into windows and compute features:
      - impact_g: max |a| in window
      - omega_peak: max |w| in window
      - tilt_mean: mean tilt in deg
      - tilt_delta: tilt_end - tilt_start in deg
      - label: majority label in the window (ignoring NONE when mixed)
    """
    # Ensure numeric dtypes
    for c in ["t", "ax", "ay", "az", "gx", "gy", "gz"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["label"] = df["label"].astype(str).fillna("NONE")
    df = df.dropna().reset_index(drop=True)

    # Estimate sampling rate
    dt = df["t"].diff().median()
    fs = 1.0 / dt if dt and dt > 0 else 50.0

    win_n = max(1, int(round(win_s * fs)))
    hop_n = max(1, int(round(hop_s * fs)))

    ax = df["ax"].values
    ay = df["ay"].values
    az = df["az"].values
    gx = df["gx"].values
    gy = df["gy"].values
    gz = df["gz"].values
    t = df["t"].values
    labels = df["label"].values

    a_mag = np.sqrt(ax * ax + ay * ay + az * az)
    w_mag = np.sqrt(gx * gx + gy * gy + gz * gz)
    tilt = tilt_deg(ax, ay, az)

    rows = []
    i = 0
    while i + win_n <= len(df):
        sl = slice(i, i + win_n)
        t0, t1 = float(t[sl.start]), float(t[sl.stop - 1])

        impact_g = float(np.max(a_mag[sl]))
        omega_peak = float(np.max(w_mag[sl]))
        tilt_mean = float(np.mean(tilt[sl]))
        tilt_delta = float(tilt[sl.stop - 1] - tilt[sl.start])

        # Window label: majority, ignoring NONE when mixed
        labs, counts = np.unique(labels[sl], return_counts=True)
        if len(labs) > 1 and "NONE" in labs:
            mask = labs != "NONE"
            labs = labs[mask]; counts = counts[mask]
        win_label = str(labs[np.argmax(counts)]) if len(labs) else "NONE"

        rows.append({
            "t_start": t0,
            "t_end": t1,
            "impact_g": impact_g,
            "omega_peak": omega_peak,
            "tilt_mean": tilt_mean,
            "tilt_delta": tilt_delta,
            "label": win_label
        })

        i += hop_n

    return pd.DataFrame(rows)


def summarize_thresholds(feat: pd.DataFrame, feature: str) -> Dict[str, float]:
    """
    Compute key percentiles for ADL and FALL, then a suggested decision threshold.
    Returns dict with p50/p95 and threshold.
    """
    out = {}
    for lab in ["ADL", "FALL"]:
        sub = feat[feat["label"] == lab][feature]
        if len(sub) == 0:
            out[f"{lab}_p50"] = np.nan
            out[f"{lab}_p95"] = np.nan
        else:
            out[f"{lab}_p50"] = float(np.nanpercentile(sub, 50))
            out[f"{lab}_p95"] = float(np.nanpercentile(sub, 95))

    # Midpoint heuristic between ADL p95 and FALL p50
    adl_p95 = out.get("ADL_p95", np.nan)
    fall_p50 = out.get("FALL_p50", np.nan)
    if not np.isnan(adl_p95) and not np.isnan(fall_p50):
        out["thr"] = float((adl_p95 + fall_p50) / 2.0)
    else:
        out["thr"] = np.nan
    return out


def triangle_around_threshold(thr: float, low_max: float, high_min: float,
                              lo_bound: float, hi_bound: float) -> Tuple[list, list, list]:
    """
    Build 3 triangular membership functions (low, medium, high) around a decision threshold:
      - 'low' peaks near lower range, tapers off to thr
      - 'medium' centered at thr, with overlap
      - 'high' rises near thr and peaks near upper range

    Returns three [a, b, c] lists for trimf.
    """
    if np.isnan(thr):
        # Fallback into a generic partition if no threshold available
        span = hi_bound - lo_bound
        a1, b1, c1 = lo_bound, lo_bound, lo_bound + span * 0.4
        a2, b2, c2 = lo_bound + span * 0.2, lo_bound + span * 0.5, lo_bound + span * 0.8
        a3, b3, c3 = lo_bound + span * 0.6, hi_bound, hi_bound
        return [a1, b1, c1], [a2, b2, c2], [a3, b3, c3]

    # Gentle overlaps (20–30% of each side)
    # Clamp everything to universe bounds
    low = [
        max(lo_bound, lo_bound),
        max(lo_bound, (lo_bound + low_max) / 2.0),
        max(lo_bound, min(thr, low_max))
    ]
    mid = [
        max(lo_bound, thr - (thr - lo_bound) * 0.3),
        thr,
        min(hi_bound, thr + (hi_bound - thr) * 0.3)
    ]
    high = [
        min(hi_bound, max(thr, high_min)),
        min(hi_bound, (high_min + hi_bound) / 2.0),
        min(hi_bound, hi_bound)
    ]
    # Ensure monotonic a<=b<=c
    def sort_tri(x): 
        x = sorted(x)
        # collapse duplicates a bit
        if x[0] == x[1]: x[1] = min(hi_bound, x[1] + 1e-6)
        if x[1] == x[2]: x[2] = min(hi_bound, x[2] + 1e-6)
        return x
    return sort_tri(low), sort_tri(mid), sort_tri(high)


def build_fuzzy_params(summary: Dict[str, Dict[str, float]],
                       max_g: float, max_dps: float) -> Dict:
    """
    Create universes and triangular membership params for:
      - accel magnitude (impact_g)
      - angular speed magnitude (omega_peak)
      - tilt delta (tilt_delta)
    """
    params = {
        "accel": {
            "universe": [0.0, max_g],
            "labels": ["low", "medium", "high"],
            "trimf": {}
        },
        "omega": {
            "universe": [0.0, max_dps],
            "labels": ["slow", "medium", "fast"],
            "trimf": {}
        },
        "tilt_delta": {
            "universe": [0.0, 120.0],
            "labels": ["small", "medium", "large"],
            "trimf": {}
        },
        "suggested_thresholds": summary  # keep raw stats too
    }

    # Acceleration magnitude
    a_thr = summary["impact_g"]["thr"]
    a_low, a_mid, a_high = triangle_around_threshold(
        thr=a_thr,
        low_max=min(max_g * 0.6, a_thr),
        high_min=max(a_thr, max_g * 0.4),
        lo_bound=0.0, hi_bound=max_g
    )
    params["accel"]["trimf"] = {"low": a_low, "medium": a_mid, "high": a_high}

    # Angular speed magnitude
    w_thr = summary["omega_peak"]["thr"]
    w_low, w_mid, w_high = triangle_around_threshold(
        thr=w_thr,
        low_max=min(max_dps * 0.6, w_thr),
        high_min=max(w_thr, max_dps * 0.4),
        lo_bound=0.0, hi_bound=max_dps
    )
    params["omega"]["trimf"] = {"slow": w_low, "medium": w_mid, "fast": w_high}

    # Tilt delta
    td_thr = summary["tilt_delta"]["thr"]
    td_low, td_mid, td_high = triangle_around_threshold(
        thr=td_thr,
        low_max=min(90.0, td_thr),
        high_min=max(td_thr, 15.0),
        lo_bound=0.0, hi_bound=120.0
    )
    params["tilt_delta"]["trimf"] = {"small": td_low, "medium": td_mid, "large": td_high}

    return params


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True, help="Input labeled .txt (CSV-like)")
    ap.add_argument("--out-features", dest="out_features", required=True, help="Output CSV for windowed features")
    ap.add_argument("--out-json", dest="out_json", default="fuzzy_params.json", help="Output JSON for fuzzy params")
    ap.add_argument("--win", type=float, default=1.0, help="Window size in seconds")
    ap.add_argument("--hop", type=float, default=0.5, help="Hop size in seconds")
    ap.add_argument("--max-g", type=float, default=3.0, help="Universe upper bound for accel (g)")
    ap.add_argument("--max-dps", type=float, default=400.0, help="Universe upper bound for omega (deg/s)")
    args = ap.parse_args()

    # Load
    df = pd.read_csv(args.infile)
    # Basic sanity: ensure label col exists
    if "label" not in df.columns:
        raise RuntimeError("Input file has no 'label' column. Did you use the labeled logger?")

    # Compute windowed features
    feat = compute_window_features(df, args.win, args.hop)
    os.makedirs(os.path.dirname(args.out_features) or ".", exist_ok=True)
    feat.to_csv(args.out_features, index=False)
    print(f"[OK] Features saved -> {args.out_features}  (rows={len(feat)})")

    # Summaries and thresholds
    summaries = {}
    for col in ["impact_g", "omega_peak", "tilt_delta"]:
        summaries[col] = summarize_thresholds(feat, col)

    print("\n=== Summary (percentiles) ===")
    for k, v in summaries.items():
        print(f"{k}: ADL p50={v.get('ADL_p50'):.3f}  ADL p95={v.get('ADL_p95'):.3f}  "
              f"FALL p50={v.get('FALL_p50'):.3f}  thr≈{v.get('thr'):.3f}")

    # Build fuzzy params
    fuzzy_params = build_fuzzy_params(summaries, args.max_g, args.max_dps)
    with open(args.out_json, "w") as f:
        json.dump(fuzzy_params, f, indent=2)
    print(f"\n[OK] Fuzzy params saved -> {args.out_json}")

    # Console hints for scikit-fuzzy usage
    print("\n--- How to use these in scikit-fuzzy (pseudo) ---")
    print("import numpy as np, skfuzzy as fuzz")
    print("from skfuzzy import control as ctrl")
    print("accel = ctrl.Antecedent(np.linspace(0, {0:.1f}, 301), 'accel')".format(args.max_g))
    print("omega = ctrl.Antecedent(np.linspace(0, {0:.0f}, 401), 'omega')".format(args.max_dps))
    print("tiltD = ctrl.Antecedent(np.linspace(0, 120, 241), 'tilt_delta')")
    print("# Then assign trimfs using the JSON: fuzz.trimf(universe, [a,b,c])")
    print("# Example: accel['low'] = fuzz.trimf(accel.universe, fuzzy_params['accel']['trimf']['low'])")


if __name__ == "__main__":
    main()
