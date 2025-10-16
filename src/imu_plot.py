#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Reads MPU6050, prints values to stdout and plots live.
Good for quick sanity checks before logging and labeling.
"""

import time
import math
from smbus2 import SMBus
import matplotlib.pyplot as plt
import matplotlib.animation as animation

# I2C config
MPU_ADDR = 0x68
ACC_SENS = 16384.0   # LSB/g (±2 g)
GYRO_SENS = 131.0    # LSB/(°/s) (±250 dps)

bus = SMBus(1)
bus.write_byte_data(MPU_ADDR, 0x6B, 0x00)  # wake MPU

def read_raw(reg):
    """Read 16-bit signed from register pair."""
    hi = bus.read_byte_data(MPU_ADDR, reg)
    lo = bus.read_byte_data(MPU_ADDR, reg + 1)
    val = (hi << 8) | lo
    return val - 65536 if val > 32767 else val

def read_mpu():
    """Return (ax,ay,az) in g and (gx,gy,gz) in °/s."""
    ax = read_raw(0x3B) / ACC_SENS
    ay = read_raw(0x3D) / ACC_SENS
    az = read_raw(0x3F) / ACC_SENS
    gx = read_raw(0x43) / GYRO_SENS
    gy = read_raw(0x45) / GYRO_SENS
    gz = read_raw(0x47) / GYRO_SENS
    return (ax, ay, az), (gx, gy, gz)

# Plot buffers
window = 200
xs = list(range(-window + 1, 1))
ax_buf = [0.0] * window; ay_buf = [0.0] * window; az_buf = [0.0] * window
gx_buf = [0.0] * window; gy_buf = [0.0] * window; gz_buf = [0.0] * window

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6))
lax = ax1.plot(xs, ax_buf, label='Ax')[0]
lay = ax1.plot(xs, ay_buf, label='Ay')[0]
laz = ax1.plot(xs, az_buf, label='Az')[0]
lgx = ax2.plot(xs, gx_buf, label='Gx')[0]
lgy = ax2.plot(xs, gy_buf, label='Gy')[0]
lgz = ax2.plot(xs, gz_buf, label='Gz')[0]
for a in (ax1, ax2):
    a.set_xlim(-window + 1, 0); a.grid(True); a.legend(loc='upper left')
ax1.set_ylim(-2.5, 2.5); ax1.set_title("Acceleration (g)")
ax2.set_ylim(-400, 400); ax2.set_title("Gyroscope (°/s)")

def update(_):
    """Animation callback: read, print, push into buffers, update lines."""
    (acc, gyr) = read_mpu()
    ax, ay, az = acc; gx, gy, gz = gyr

    # Print once per frame
    a_mag = math.sqrt(ax*ax + ay*ay + az*az)
    w_mag = math.sqrt(gx*gx + gy*gy + gz*gz)
    print(f"Acc(g): {ax:+.3f} {ay:+.3f} {az:+.3f} | "
          f"Gyr(°/s): {gx:+.1f} {gy:+.1f} {gz:+.1f} | "
          f"|a|={a_mag:.3f} | |ω|={w_mag:.1f}", flush=True)

    # Slide buffers
    for buf, val in ((ax_buf, ax), (ay_buf, ay), (az_buf, az),
                     (gx_buf, gx), (gy_buf, gy), (gz_buf, gz)):
        buf.append(val); buf.pop(0)

    # Update plot lines
    lax.set_ydata(ax_buf); lay.set_ydata(ay_buf); laz.set_ydata(az_buf)
    lgx.set_ydata(gx_buf); lgy.set_ydata(gy_buf); lgz.set_ydata(gz_buf)
    return lax, lay, laz, lgx, lgy, lgz

ani = animation.FuncAnimation(fig, update, interval=50, blit=False)
plt.tight_layout()
try:
    plt.show()
finally:
    bus.close()
