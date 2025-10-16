#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Analyze labeled IMU logs WITHOUT pandas:
- Focus on FALL segments.
- Compute windowed features over FALL: per-axis peaks (ax,ay,az,gx,gy,gz),
  magnitudes (impact_g, omega_peak), and tilt_delta.
- Summarize with percentiles and propose 3 fuzzy ranges (low/medium/high)
  for each feature (triangular membership parameters).

Input expected header (CSV-like .txt):
t,ax,ay,az,gx,gy,gz,a_mag,w_mag,label,event_id,label_change
(If a_mag/w_mag are missing, they will be computed.)

Run:
  python3 -u analyze_fall_no_pandas.py --in data/datos_imu.txt \
    --out-json fall_fuzzy_params.json --out-report fall_report.txt \
    --win 1.0 --hop 0.5
"""

import argparse
import csv
import json
import math
import os
from typing import List, Dict, Tuple, Any

# ---------- Small utilities (no numpy, no pandas) ----------

def safe_float(x: str, default: float = float("nan")) -> float:
    try:
        return float(x)
    except Exception:
        return default

def percentile(values: List[float], p: float) -> float:
    """
    Simple percentile (0..100) with linear interpolation between closest ranks.
    values must be a non-empty list of floats.
    """
    vs = sorted(v for v in values if not math.isnan(v))
    if not vs:
        return float("nan")
    if p <= 0: return vs[0]
    if p >= 100: return vs[-1]
    k = (len(vs)-1) * (p/100.0)
    f = math.floor(k); c = math.ceil(k)
    if f == c: return vs[int(k)]
    d0 = vs[f] * (c-k)
    d1 = vs[c] * (k-f)
    return d0 + d1

def tilt_deg(ax: float, ay: float, az: float) -> float:
    """
    Trunk tilt relative to gravity axis. 0 deg = upright, ~90 deg = horizontal.
    Uses only accelerometer. Clamped to [0,180].
    """
    horiz = math.sqrt(ax*ax + ay*ay)
    ang = math.degrees(math.atan2(horiz, abs(az) + 1e-9))
    return max(0.0, min(180.0, ang))

def slice_windows(n: int, win_n: int, hop_n: int):
    """Yield index slices [i, i+win_n) for a signal of length n."""
    i = 0
    while i + win_n <= n:
        yield (i, i + win_n)
        i += hop_n

# ---------- Core analysis ----------

def load_labeled_rows(path: str) -> Dict[str, List[Any]]:
    """
    Load CSV-like file and return dict of columns. Detect column indices by header names.
    """
    with open(path, "r") as f:
        reader = csv.reader(f)
        header = next(reader)
        name_to_idx = {name.strip(): idx for idx, name in enumerate(header)}

        required = ["t","ax","ay","az","gx","gy","gz","label"]
        for r in required:
            if r not in name_to_idx:
                raise RuntimeError(f"Missing required column '{r}' in {path}")

        cols = {name: [] for name in header}
        for row in reader:
            if not row or len(row) < len(header):
                continue
            for name, idx in name_to_idx.items():
                cols[name].append(row[idx])
    return cols

def compute_sampling(dt_list: List[float], default_fs: float = 50.0) -> float:
    """Estimate sampling rate from dt median; fallback to default_fs."""
    dts = [dt_list[i+1]-dt_list[i] for i in range(len(dt_list)-1)]
    dts = [d for d in dts if d > 0]
    if not dts:
        return default_fs
    dts_sorted = sorted(dts)
    mid = len(dts_sorted)//2
    dt_med = dts_sorted[mid] if len(dts_sorted)%2==1 else 0.5*(dts_sorted[mid-1]+dts_sorted[mid])
    return 1.0 / dt_med if dt_med > 0 else default_fs

def window_features_fall(cols: Dict[str, List[Any]], win_s: float, hop_s: float) -> List[Dict[str, float]]:
    """
    Compute features over windows restricted to rows labeled FALL:
      - per-axis peak abs: ax_pk, ay_pk, az_pk, gx_pk, gy_pk, gz_pk
      - impact_g = max(|a|) in window
      - omega_peak = max(|ω|) in window
      - tilt_delta = tilt_end - tilt_start (deg)
    """
    # Parse base columns
    t = [safe_float(x) for x in cols["t"]]
    ax = [safe_float(x) for x in cols["ax"]]
    ay = [safe_float(x) for x in cols["ay"]]
    az = [safe_float(x) for x in cols["az"]]
    gx = [safe_float(x) for x in cols["gx"]]
    gy = [safe_float(x) for x in cols["gy"]]
    gz = [safe_float(x) for x in cols["gz"]]
    label = [str(x).strip().upper() for x in cols["label"]]

    n = min(len(t), len(ax), len(ay), len(az), len(gx), len(gy), len(gz), len(label))
    t = t[:n]; ax = ax[:n]; ay = ay[:n]; az = az[:n]; gx = gx[:n]; gy = gy[:n]; gz = gz[:n]; label = label[:n]

    # Keep only FALL rows
    idx_fall = [i for i in range(n) if label[i] == "FALL"]
    if not idx_fall:
        raise RuntimeError("No FALL rows found. Check your labels.")

    # Build compact arrays for FALL segment(s)
    t_f = [t[i] for i in idx_fall]
    ax_f = [ax[i] for i in idx_fall]
    ay_f = [ay[i] for i in idx_fall]
    az_f = [az[i] for i in idx_fall]
    gx_f = [gx[i] for i in idx_fall]
    gy_f = [gy[i] for i in idx_fall]
    gz_f = [gz[i] for i in idx_fall]

    # Estimate sampling rate on FALL only
    fs = compute_sampling(t_f, default_fs=50.0)
    win_n = max(1, int(round(win_s * fs)))
    hop_n = max(1, int(round(hop_s * fs)))

    feats = []
    for i0, i1 in slice_windows(len(t_f), win_n, hop_n):
        # Per-axis peaks (absolute)
        ax_pk = max(abs(v) for v in ax_f[i0:i1])
        ay_pk = max(abs(v) for v in ay_f[i0:i1])
        az_pk = max(abs(v) for v in az_f[i0:i1])
        gx_pk = max(abs(v) for v in gx_f[i0:i1])
        gy_pk = max(abs(v) for v in gy_f[i0:i1])
        gz_pk = max(abs(v) for v in gz_f[i0:i1])

        # Magnitude peaks
        impact_g = max(math.sqrt(ax_f[k]**2 + ay_f[k]**2 + az_f[k]**2) for k in range(i0, i1))
        omega_pk = max(math.sqrt(gx_f[k]**2 + gy_f[k]**2 + gz_f[k]**2) for k in range(i0, i1))

        # Tilt delta
        tilt_start = tilt_deg(ax_f[i0], ay_f[i0], az_f[i0])
        tilt_end   = tilt_deg(ax_f[i1-1], ay_f[i1-1], az_f[i1-1])
        tilt_delta = tilt_end - tilt_start

        feats.append({
            "t_start": t_f[i0],
            "t_end": t_f[i1-1],
            "ax_pk": ax_pk, "ay_pk": ay_pk, "az_pk": az_pk,
            "gx_pk": gx_pk, "gy_pk": gy_pk, "gz_pk": gz_pk,
            "impact_g": impact_g, "omega_peak": omega_pk,
            "tilt_delta": tilt_delta
        })
    return feats

def summarize_percentiles(values: List[float], name: str) -> Dict[str, float]:
    clean = [v for v in values if not math.isnan(v)]
    if not clean:
        return {"p10": float("nan"), "p25": float("nan"), "p50": float("nan"),
                "p75": float("nan"), "p90": float("nan"), "min": float("nan"), "max": float("nan")}
    return {
        "min": min(clean), "max": max(clean),
        "p10": percentile(clean, 10), "p25": percentile(clean, 25),
        "p50": percentile(clean, 50), "p75": percentile(clean, 75), "p90": percentile(clean, 90)
    }

def trimf_from_quartiles(stats: Dict[str, float], lo_bound: float, hi_bound: float) -> Dict[str, List[float]]:
    """
    Build 3 triangular sets from FALL quartiles:
      low    ~ [min, p25, p50]
      medium ~ [p25, p50, p75]
      high   ~ [p50, p75, max]
    Clamped to [lo_bound, hi_bound] and slightly widened if degenerate.
    """
    def clamp(x): return max(lo_bound, min(hi_bound, x))
    def tri(a,b,c):
        a,b,c = clamp(a), clamp(b), clamp(c)
        # ensure increasing and non-degenerate
        if b <= a: b = min(hi_bound, a + 1e-6)
        if c <= b: c = min(hi_bound, b + 1e-6)
        return [a,b,c]

    mn, mx = stats.get("min", lo_bound), stats.get("max", hi_bound)
    p25, p50, p75 = stats.get("p25", lo_bound), stats.get("p50", (lo_bound+hi_bound)/2), stats.get("p75", hi_bound)

    low = tri(mn, p25, p50)
    med = tri(p25, p50, p75)
    hig = tri(p50, p75, mx)
    return {"low": low, "medium": med, "high": hig}

def build_fuzzy_from_fall(feats: List[Dict[str, float]],
                          max_g: float, max_dps: float) -> Dict[str, Any]:
    """
    Using FALL-only distribution to propose 3-range memberships for:
      - per-axis peaks (ax, ay, az, gx, gy, gz)
      - impact_g, omega_peak, tilt_delta
    Universes:
      accel axes in g → [-max_g, +max_g] but we use abs peaks so [0, max_g]
      gyro axes in °/s → [0, max_dps]
      impact_g → [0, max_g]
      omega_peak → [0, max_dps]
      tilt_delta → [0, 120]
    """
    # collect lists
    get = lambda k: [w[k] for w in feats]

    stats = {}
    for key in ["ax_pk","ay_pk","az_pk","gx_pk","gy_pk","gz_pk",
                "impact_g","omega_peak","tilt_delta"]:
        stats[key] = summarize_percentiles(get(key), key)

    params = {
        "universes": {
            "ax_pk": [0.0, max_g], "ay_pk": [0.0, max_g], "az_pk": [0.0, max_g],
            "gx_pk": [0.0, max_dps], "gy_pk": [0.0, max_dps], "gz_pk": [0.0, max_dps],
            "impact_g": [0.0, max_g], "omega_peak": [0.0, max_dps], "tilt_delta": [0.0, 120.0],
        },
        "trimf": {},
        "percentiles": stats
    }

    # Build trimfs from quartiles per feature
    params["trimf"]["ax_pk"]      = trimf_from_quartiles(stats["ax_pk"], 0.0, max_g)
    params["trimf"]["ay_pk"]      = trimf_from_quartiles(stats["ay_pk"], 0.0, max_g)
    params["trimf"]["az_pk"]      = trimf_from_quartiles(stats["az_pk"], 0.0, max_g)
    params["trimf"]["gx_pk"]      = trimf_from_quartiles(stats["gx_pk"], 0.0, max_dps)
    params["trimf"]["gy_pk"]      = trimf_from_quartiles(stats["gy_pk"], 0.0, max_dps)
    params["trimf"]["gz_pk"]      = trimf_from_quartiles(stats["gz_pk"], 0.0, max_dps)
    params["trimf"]["impact_g"]   = trimf_from_quartiles(stats["impact_g"], 0.0, max_g)
    params["trimf"]["omega_peak"] = trimf_from_quartiles(stats["omega_peak"], 0.0, max_dps)
    params["trimf"]["tilt_delta"] = trimf_from_quartiles(stats["tilt_delta"], 0.0, 120.0)

    return params

def write_report(report_path: str, fs: float, feats: List[Dict[str, float]], params: Dict[str, Any]):
    with open(report_path, "w") as f:
        f.write("# FALL analysis report (no pandas)\n")
        f.write(f"Windows: {len(feats)} | Sampling ~ {fs:.2f} Hz\n\n")
        f.write("Features per window: ax_pk, ay_pk, az_pk, gx_pk, gy_pk, gz_pk, impact_g, omega_peak, tilt_delta\n\n")
        f.write("## Percentiles (FALL only)\n")
        for k, st in params["percentiles"].items():
            f.write(f"- {k:12s}: min={st['min']:.3f} p25={st['p25']:.3f} p50={st['p50']:.3f} "
                    f"p75={st['p75']:.3f} p90={st['p90']:.3f} max={st['max']:.3f}\n")
        f.write("\n## Suggested trimf (a,b,c) per feature\n")
        for k, tri in params["trimf"].items():
            f.write(f"- {k}:\n")
            for name, abc in tri.items():
                f.write(f"    {name:6s}: [{abc[0]:.4f}, {abc[1]:.4f}, {abc[2]:.4f}]\n")
        f.write("\nNotes:\n")
        f.write("- These ranges come from FALL quartiles only. Later merge with ADL to adjust universes/overlaps.\n")
        f.write("- Consider using impact_g + omega_peak + tilt_delta for a compact fuzzy model.\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True, help="Input labeled .txt/.csv")
    ap.add_argument("--out-json", dest="out_json", default="fall_fuzzy_params.json", help="Output JSON with trimf")
    ap.add_argument("--out-report", dest="out_report", default="fall_report.txt", help="Text report")
    ap.add_argument("--win", type=float, default=1.0, help="Window size (s)")
    ap.add_argument("--hop", type=float, default=0.5, help="Hop size (s)")
    ap.add_argument("--max-g", type=float, default=3.0, help="Accel universe upper bound (g)")
    ap.add_argument("--max-dps", type=float, default=400.0, help="Gyro universe upper bound (deg/s)")
    args = ap.parse_args()

    cols = load_labeled_rows(args.infile)

    # Rough sampling from entire file for reporting
    t_all = [safe_float(x) for x in cols["t"]]
    fs_report = compute_sampling(t_all, default_fs=50.0)

    feats = window_features_fall(cols, win_s=args.win, hop_s=args.hop)
    params = build_fuzzy_from_fall(feats, max_g=args.max_g, max_dps=args.max_dps)

    # Save JSON
    with open(args.out_json, "w") as jf:
        json.dump(params, jf, indent=2)
    # Save text report
    write_report(args.out_report, fs_report, feats, params)

    # Console summary
    print(f"[OK] Windows (FALL): {len(feats)} | fs≈{fs_report:.2f} Hz")
    print(f"[OK] JSON saved -> {os.path.abspath(args.out_json)}")
    print(f"[OK] Report saved -> {os.path.abspath(args.out_report)}")
    print("\nUse these 'trimf' arrays to set fuzz.trimf(universe, [a,b,c]) for each feature.")
    print("Next step: run the SAME script later for ADL to compare ranges or compute mixed thresholds.")
if __name__ == "__main__":
    main()
