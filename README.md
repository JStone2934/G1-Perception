# IrThermal — G1 红外热成像（MLX90640 / GY-MCU90640）

本机通过 **MicroUSB（CH340 串口）** 连接 **GY-MCU90640** 模块时，请用串口脚本（见下）。  
模块内部 MCU 经 I2C 读 MLX90640，PC 侧为 **UART 460800**，设备一般为 `/dev/ttyUSB1`。

## 环境

```bash
cd /home/a24/robot/Thermal/G1
conda env create -f environment.yml   # 首次
conda activate g1-mlx90640
```

## 使用（MicroUSB / 串口，推荐）

```bash
# 探测哪个 ttyUSB 在出热图（帧头 5a5a）
python scripts/thermal_view_serial.py --list-ports

# 实时热图（默认 /dev/ttyUSB1 @ 460800）
python scripts/thermal_view_serial.py

# 保存一帧
python scripts/thermal_view_serial.py --save thermal.png

# 指定端口 / 115200 固件需初始化
python scripts/thermal_view_serial.py --port /dev/ttyUSB1 --baud 115200 --init
```

## 使用（裸 I2C 接线，可选）

若模块 I2C 直接接到主板 `/dev/i2c-*`（非本机 MicroUSB 方案）：

```bash
python scripts/i2c_scan.py
python scripts/thermal_view.py --bus <编号>
```

## 权限说明

- 串口：用户需在 `dialout` 组（本机用户 `a24` 已具备）。
- I2C：若无法访问 `/dev/i2c-*`，需 `sudo usermod -aG i2c $USER` 后重新登录（**需密码，请自行执行**）。

本仓库脚本**不会**自动调用 `sudo`。
