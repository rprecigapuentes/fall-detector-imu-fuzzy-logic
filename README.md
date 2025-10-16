# fall-detector-imu-fuzzy-logic
Fall detection prototype using accelerometer and gyroscope data from MPU6050 with fuzzy logic modeling.

---

## Overview

This project aims to identify potential **fall events** by analyzing acceleration and angular velocity patterns from an IMU device.  
Instead of using fixed thresholds, it implements a **fuzzy inference system (FIS)** that interprets the sensor data in a more flexible and human-like way.

The system is still **under development** — the logic, rules, and calibration are being refined.

---

## Hardware

| Component | Description |
|------------|-------------|
| IMU Sensor | MPU6050 or compatible (3-axis accelerometer + 3-axis gyroscope) |
| Microcontroller | Raspberry Pi / ESP32 (data acquisition and processing) |
| Connection | I2C |
| Optional | LoRa or Bluetooth module for future alert transmission |

---

## Software & Dependencies

Written in **Python 3.9+**.  
The fuzzy logic implementation uses the [scikit-fuzzy](https://pythonhosted.org/scikit-fuzzy/) library.

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # (Linux/Mac)
venv\Scripts\activate     # (Windows)

# Install dependencies
pip install numpy matplotlib scikit-fuzzy
```

---

## Fuzzy System Design

- **Inputs**
  - `acc`: Acceleration magnitude (0–3.5 g)
  - `gyro`: Angular velocity magnitude (0–600 °/s)
- **Output**
  - `fall`: Probability of fall event (0–1)

### Example membership functions

| Variable | Range | Fuzzy Sets |
|-----------|--------|------------|
| acc | 0–3.5 g | low, medium, high |
| gyro | 0–600 °/s | slow, moderate, fast |
| fall | 0–1 | no_fall, uncertain, fall |

Rules are defined such as:  
- If acceleration is **high** and angular speed is **fast**, then **fall = high**.  
- If acceleration is **medium** and angular speed is **slow**, then **fall = low**.

---

## Running the Simulation

```bash
python3 fall_detector.py
```

It will generate fuzzy surface plots and intermediate decision results.  
Sensor input can later be integrated from the IMU through serial or I2C communication.

---

## Current Status

| Stage | Progress |
|--------|-----------|
| Fuzzy logic base | ✅ Implemented |
| Rule testing | ⚙️ In progress |
| IMU integration | 🕐 Under development |
| Real-time alert system | ⏳ Planned |

---

## Future Work

- Calibrate fuzzy sets using real human motion data.  
- Implement real-time data streaming from the IMU.  
- Add fall event logging and remote alert capability.  
- Evaluate performance using confusion matrix metrics.

---

### Team 

- **Andres Camilo Castiblanco Cruz**  
- **Luis Guillermo Vaca Rincon**  
- **Edwin Fernando Mosquera Gomez**  
- **Santiago Alejandro Ochoa Quesada**  
- **Rosemberth Steeven Preciga Puentes**
