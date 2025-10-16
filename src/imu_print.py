#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Reads MPU6050 and prints raw values to stdout at a fixed rate.
Use this to eyeball ranges and derive thresholds without plotting.
"""

import time
import math
import sys
import argparse
from smbus2 import SMBus

# Force line-buffered stdout when available
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

# I2C config
MPU_ADDR = 0x68
ACC_SENS = 16384.0    # LSB/g (±2 g)
GYRO_SENS = 131.0     # LSB/(°/s) (±250 dps)

def mpu_init(bus):
    """Wake and set ±2 g and ±250 dps scales."""
    bus.write_byte_data(MPU_ADDR, 0x6B, 0x00)
    time.sleep(0.05)
    bus.write_byte_data(MPU_ADDR, 0x1C, 0x00)
    bus.write_byte_data(MPU_ADDR, 0x1B, 0x00)

def read_raw(bus, reg):
    hi = bus.read_byte_data(MPU_ADDR, reg)
    lo = bus.read_byte_data(MPU_ADDR, reg + 1)
    val = (hi << 8) | lo
    return val - 65536 if val > 32767 else val

def read_mpu(bus):
    ax = read_raw(bus, 0x3B) / ACC_SENS; ay = read_raw(bus, 0x3D) / ACC_SENS; az = read_raw(bus, 0x3F) / ACC_SENS
    gx = read_raw(bus, 0x43) / GYRO_SENS; gy = read_raw(bus, 0x45) / GYRO_SENS; gz = read_raw(bus, 0x47) / GYRO_SENS
    return (ax, ay, az), (gx, gy, gz)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hz", type=int, default=50, help="Sampling rate (Hz)")
    args = ap.parse_args()

    period = 1.0 / max(1, args.hz)
    bus = SMBus(1); mpu_init(bus)
    frame = 0; t0 = time.time()

    try:
        next_t = time.perf_counter()
        while True:
            (acc, gyr) = read_mpu(bus)
            ax, ay, az = acc; gx, gy, gz = gyr
            a_mag = math.sqrt(ax*ax + ay*ay + az*az)
            w_mag = math.sqrt(gx*gx + gy*gy + gz*gz)
            frame += 1; t = time.time() - t0
            print(f"[{frame:06d}] t={t:7.3f}s | "
                  f"Acc(g): X={ax:+.3f} Y={ay:+.3f} Z={az:+.3f} | "
                  f"Gyr(°/s): X={gx:+.1f} Y={gy:+.1f} Z={gz:+.1f} | "
                  f"|a|={a_mag:.3f} | |ω|={w_mag:.1f}", flush=True)
            next_t += period
            sleep_t = next_t - time.perf_counter()
            time.sleep(sleep_t if sleep_t > 0 else 0)
    except KeyboardInterrupt:
        print("\nExiting cleanly...")
    finally:
        bus.close()

if __name__ == "__main__":
    main()
