# fall-detector-imu-fuzzy-logic
Fall detection prototype using accelerometer and gyroscope data from MPU6050 with fuzzy logic modeling.

## Hardware
- Raspberry Pi with I2C enabled
- MPU6050 connected at `0x68` (or `0x69` if AD0=1)

## Quickstart

### 1) Enable I2C and tools
```bash
sudo raspi-config            # Interface Options → I2C → Enable
sudo apt-get update
sudo apt-get install -y i2c-tools
i2cdetect -y 1               # You should see 68 or 69

```

```bash

python3 -m venv venv --system-site-packages
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# Alternative (PiWheels):
# pip install -i https://www.piwheels.org/simple -r requirements.txt
```