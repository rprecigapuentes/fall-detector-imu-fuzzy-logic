#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fuzzy fall scoring (refined):

- Extends "high" memberships to the end of the universe to avoid dead zones
  (e.g., acc 3.2 g or gyro 550 °/s still contribute).
- Adds rules for slip-like events (high gyro, low/medium acc).
- Covers the "medium & medium" case.
- Keeps inputs clamped. Output in [0..1].

You still need an application-level decision rule, e.g.:
  FALL if (avg of last 200 ms scores) >= 0.7 AND peak(acc) >= 1.6g in same window.
"""

import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

# --- Universes ---
acc_range  = np.arange(0.0, 3.50 + 1e-9, 0.01)   # g
gyro_range = np.arange(0.0, 600.0 + 1e-9, 1.0)   # deg/s
fall_range = np.arange(0.0, 1.00 + 1e-9, 0.01)   # dimensionless

acc  = ctrl.Antecedent(acc_range,  'aceleracion')
gyro = ctrl.Antecedent(gyro_range, 'giro')
fall = ctrl.Consequent(fall_range, 'caida')

# --- Memberships ---
# Keep the original shapes but extend "high" to the universe end to avoid zero-membership gaps.
# At the low end, extend "low" down to 0 to keep coverage.
# If you prefer trapezoids at edges, use fuzz.trapmf.

# Acceleration (g)
acc['bajo']   = fuzz.trimf(acc.universe,  [0.0, 0.4, 0.9])
acc['medio']  = fuzz.trimf(acc.universe,  [0.7, 1.0, 1.6])
acc['alto']   = fuzz.trimf(acc.universe,  [1.2, 2.2, 3.50])  # extended to 3.50 (universe max)

# Gyro (deg/s)
gyro['lento']  = fuzz.trimf(gyro.universe, [0,   40,  90])
gyro['medio']  = fuzz.trimf(gyro.universe, [60, 160, 260])
gyro['rapido'] = fuzz.trimf(gyro.universe, [180, 320, 600])   # extended to 600 (universe max)

# Output fall score
fall['bajo']  = fuzz.trimf(fall.universe, [0.0, 0.2, 0.5])
fall['medio'] = fuzz.trimf(fall.universe, [0.3, 0.5, 0.7])
fall['alto']  = fuzz.trimf(fall.universe, [0.6, 0.85, 1.0])

# --- Rules ---
rules = [
    # High-impact + fast rotation → very likely fall
    ctrl.Rule(acc['alto']  & gyro['rapido'], fall['alto']),

    # High-impact + medium rotation → likely
    ctrl.Rule(acc['alto']  & gyro['medio'],  fall['medio']),

    # Medium impact + fast rotation → possible fall (slip or awkward landing)
    ctrl.Rule(acc['medio'] & gyro['rapido'], fall['medio']),

    # Slip-like: low/medium impact but very fast rotation should not be 'bajo'
    ctrl.Rule(acc['bajo']  & gyro['rapido'], fall['medio']),

    # Ambiguous: medium & medium → medium
    ctrl.Rule(acc['medio'] & gyro['medio'],  fall['medio']),

    # Low gyro and medium acc: often a brisk ADL; keep it low unless impact grows
    ctrl.Rule(gyro['lento'] & acc['medio'],  fall['bajo']),

    # Low acc globally nudges to 'bajo' unless rotation says otherwise
    ctrl.Rule(acc['bajo']  & gyro['lento'],  fall['bajo']),

    # High acc but low rotation (e.g., bump without fall) → medium rather than high
    ctrl.Rule(acc['alto']  & gyro['lento'],  fall['medio']),
]

system = ctrl.ControlSystem(rules)

def fuzzy_fall_score(acc_mag_g: float, gyro_mag_dps: float) -> float:
    """
    Compute fuzzy fall score in [0..1].
    Inputs are clamped to the universe to avoid out-of-range artifacts.
    """
    sim = ctrl.ControlSystemSimulation(system)
    # Clamp to universes
    sim.input['aceleracion'] = max(0.0, min(acc_mag_g, 3.50))
    sim.input['giro']        = max(0.0, min(gyro_mag_dps, 600.0))
    try:
        sim.compute()
        return float(sim.output['caida'])
    except Exception as e:
        # If something goes south, return safe low score
        print(f"[FUZZY ERROR] acc={acc_mag_g:.3f}g gyro={gyro_mag_dps:.1f}dps -> {e}")
        return 0.0

# Optional helper: threshold with hysteresis over a short window (pseudo)
# Keep your real-time layer separate from fuzzy itself.
def decision_from_scores(scores, hi=0.7, lo=0.5):
    """
    Simple 2-level hysteresis: returns True (fall) if last score >= hi,
    stays True until it drops below lo. 'scores' is a list of recent values.
    """
    if not scores:
        return False
    last = scores[-1]
    # If previously active, require clear below 'lo' to drop; otherwise need 'hi' to activate.
    was_active = any(s >= hi for s in scores[:-1])
    if was_active:
        return last >= lo
    return last >= hi
