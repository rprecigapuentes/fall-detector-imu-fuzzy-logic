#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Live logger that prints IMU readings and saves every sample to a .txt (CSV-like).
Keyboard labels:
  - '0' -> ADL
  - '1' -> FALL
  - 'SPACE' -> NONE
Retro-labeling buffer lets you reassign the last N samples on FALL to compensate human delay.

Run:
  python3 -u src/imu_logger_labeled_txt.py --outfile data/datos_imu.txt --hz 50 --pre 0.5 --retro-mode fall_only
"""

import time
import sys
import math
import argparse
import select
import termios
import tty
import os
from collections import deque
from smbus2 import SMBus

# ---------- Non-blocking keyboard helpers (Linux TTY) ----------
def kbhit():
    try:
        return select.select([sys.stdin], [], [], 0)[0] != []
    except Exception:
        return False

def getch_nonblock():
    return sys.stdin.read(1) if kbhit() else None

def setup_stdin_raw():
    if not sys.stdin.isatty():
        return None, None
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    return fd, old

def restore_stdin(fd, old):
    if fd and old:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

# ---------- IMU ----------
MPU_ADDR = 0x68
ACC_SENS = 16384.0   # LSB/g (±2 g)
GYRO_SENS = 131.0    # LSB/(°/s) (±250 dps)

def mpu_init(bus):
    bus.write_byte_data(MPU_ADDR, 0x6B, 0x00)  # wake
    time.sleep(0.05)
    bus.write_byte_data(MPU_ADDR, 0x1C, 0x00)  # ±2 g
    bus.write_byte_data(MPU_ADDR, 0x1B, 0x00)  # ±250 dps

def read_raw(bus, reg):
    hi = bus.read_byte_data(MPU_ADDR, reg)
    lo = bus.read_byte_data(MPU_ADDR, reg + 1)
    val = (hi << 8) | lo
    return val - 65536 if val > 32767 else val

def read_mpu(bus):
    ax = read_raw(bus, 0x3B) / ACC_SENS; ay = read_raw(bus, 0x3D) / ACC_SENS; az = read_raw(bus, 0x3F) / ACC_SENS
    gx = read_raw(bus, 0x43) / GYRO_SENS; gy = read_raw(bus, 0x45) / GYRO_SENS; gz = read_raw(bus, 0x47) / GYRO_SENS
    return (ax, ay, az), (gx, gy, gz)

def write_row(f, row_dict):
    """Safe writer: cast everything to str and flush to disk."""
    f.write(",".join(str(v) for v in row_dict.values()) + "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outfile", default="data/datos_imu.txt", help="Output .txt (CSV-like)")
    ap.add_argument("--hz", type=int, default=50, help="Sampling rate (Hz)")
    ap.add_argument("--pre", type=float, default=0.5, help="Retro-label buffer seconds (0 disables)")
    ap.add_argument("--retro-mode", choices=["off", "fall_only", "all"], default="fall_only",
                    help="off=no retro; fall_only=only when switching to FALL; all=every label change")
    args = ap.parse_args()

    # Unbuffered-ish stdout
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    fs = max(1, args.hz)
    period = 1.0 / fs
    pre_samples = max(0, int(round(args.pre * fs)))

    # Prepare output
    os.makedirs(os.path.dirname(args.outfile) or ".", exist_ok=True)
    out_path = os.path.abspath(args.outfile)
    header_cols = ["t","ax","ay","az","gx","gy","gz","a_mag","w_mag","label","event_id","label_change"]
    header = ",".join(header_cols) + "\n"
    f = open(out_path, "w", buffering=1)
    f.write(header)

    # IMU and keyboard
    bus = SMBus(1); mpu_init(bus)
    fd, old = setup_stdin_raw()

    # State
    buffer = deque(maxlen=max(pre_samples, 1))
    current_label = "NONE"; last_label = current_label
    event_id = 0; frame = 0; t0 = time.time()

    print(f"Logging → {out_path}")
    print("Keys: [0]=ADL, [1]=FALL, [SPACE]=NONE. Ctrl+C to exit.")
    print(f"(pre={args.pre:.2f}s → {pre_samples} samples, retro-mode={args.retro_mode})")
    print(header.strip())

    try:
        next_t = time.perf_counter()
        while True:
            # Handle keyboard
            ch = getch_nonblock()
            label_change = ""
            if ch is not None:
                if ch == "0": current_label = "ADL"
                elif ch == "1": current_label = "FALL"
                elif ch == " ": current_label = "NONE"

                if current_label != last_label:
                    if current_label == "FALL":
                        event_id += 1  # new fall event
                    label_change = f"{last_label}->{current_label}"
                    print(f"[Label] {label_change} (event {event_id})", flush=True)

                    # Retro-label only if requested
                    if pre_samples > 0:
                        do_retro = (
                            args.retro_mode == "all" or
                            (args.retro_mode == "fall_only" and current_label == "FALL")
                        )
                        if do_retro:
                            for i in range(1, min(pre_samples, len(buffer)) + 1):
                                buffer[-i]["label"] = current_label
                                buffer[-i]["event_id"] = event_id
                                if i == 1:
                                    buffer[-i]["label_change"] = label_change
                    last_label = current_label

            # Read IMU
            (acc, gyr) = read_mpu(bus)
            ax, ay, az = acc; gx, gy, gz = gyr
            t = time.time() - t0

            a_mag = math.sqrt(ax*ax + ay*ay + az*az)
            w_mag = math.sqrt(gx*gx + gy*gy + gz*gz)

            frame += 1
            row = {
                "t": f"{t:.6f}",
                "ax": f"{ax:.6f}",
                "ay": f"{ay:.6f}",
                "az": f"{az:.6f}",
                "gx": f"{gx:.2f}",
                "gy": f"{gy:.2f}",
                "gz": f"{gz:.2f}",
                "a_mag": f"{a_mag:.6f}",
                "w_mag": f"{w_mag:.2f}",
                "label": current_label,
                "event_id": event_id,
                "label_change": label_change
            }

            # Buffered write to allow retro-labeling of the last N samples only
            if pre_samples > 0:
                buffer.append(row)
                while len(buffer) > pre_samples:
                    write_row(f, buffer.popleft())
            else:
                write_row(f, row)

            # Console print
            print(
                f"[{frame:06d}] t={t:7.3f}s | "
                f"Acc(g): X={ax:+.3f} Y={ay:+.3f} Z={az:+.3f} | "
                f"Gyr(°/s): X={gx:+.1f} Y={gy:+.1f} Z={gz:+.1f} | "
                f"|a|={a_mag:.3f} | |ω|={w_mag:.1f} | "
                f"label={current_label} ev={event_id}"
            )

            # Timing
            next_t += period
            sleep_t = next_t - time.perf_counter()
            time.sleep(sleep_t if sleep_t > 0 else 0)

    except KeyboardInterrupt:
        print("\nStopping. Flushing buffer...")
        while buffer:
            write_row(f, buffer.popleft())
    finally:
        restore_stdin(fd, old)
        try: bus.close()
        except: pass
        try: f.close()
        except: pass
        print(f"Saved at: {out_path}")

if __name__ == "__main__":
    main()
