# G1 + GY-MCU90640 排查备忘

本文记录 Unitree G1 上实测结论，供接线与排障时查阅。主文档见 [../README.md](../README.md) 与 [../../README.md](../../README.md)。

---

## 1. USB 枚举：叫什么名字？

`lsusb` 显示的是 **USB 桥接芯片**，不是 MLX90640：

| 常见显示 | VID:PID | 设备节点 |
|----------|---------|----------|
| QinHeng HL-340 / CH340 | `1a86:7523` | `/dev/ttyUSB0` |
| CH340 变种 | `1a86:5523` 等 | `ttyUSB*` |
| CP2102 | `10c4:ea60` | `ttyUSB*` |
| STM32 CDC | `0483:xxxx` | `/dev/ttyACM0` |

**没有任何新增 `lsusb` 行** = 主机未看到模块（线、口、供电），与 Python 无关。

---

## 2. 插拔拓展坞 / OTG 时的表现

| 阶段 | `lsusb` 特征 |
|------|----------------|
| 拓展坞（VIA `2109:0817`） | 仅 Hub 芯片，下游无 CH340 → 模块未挂到总线 |
| 换 OTG | VIA 消失；仍无 CH340 → 模块未插或未供电 |
| 模块 MicroUSB 接好 | 出现 `1a86:7523`，`dmesg` 有 `ch341-uart ... ttyUSB0` |

---

## 3. 有 ttyUSB 但无串口数据

### 现象

- `/dev/ttyUSB0` 存在
- `python -c "import serial; ... read()"` 或 `thermal_view_serial.py --list-ports` 长期 **0 字节** 或帧头不是 `5a5a`

### 原因（本机已验证）

GY-MCU90640 + CH340 在 **460800** 下需 **DTR/RTS 电平翻转** 才会开始发送 1544 字节热图帧。  
仅插拔、仅发 `A5 35 02 DC` 不一定够。

### 有效步骤

```python
ser.dtr = False; ser.rts = False
time.sleep(0.05)
ser.dtr = True;  ser.rts = True
time.sleep(0.25)
ser.reset_input_buffer()
ser.write(bytes([0xA5, 0x35, 0x02, 0xDC]))  # START
# 再 sync 帧头 0x5A5A，读满 1544 字节
```

已封装在：`IrThermal/scripts/capture_serial.py` → `wake_gy_mcu()`。

### 错误做法

- 裸 `serial.read()` 不翻转 DTR/RTS  
- 仅用 `IrThermal/scripts/thermal_view_serial.py` 且未改唤醒逻辑  
- 采集后发送 `CMD_STOP` 再期望持续流（需重新唤醒或 START）

---

## 4. 权限与驱动

```bash
# 串口组（需重新登录）
sudo usermod -aG dialout $USER

# CH341 驱动
lsmod | grep ch341
sudo modprobe ch341

# 内核日志
sudo dmesg | grep -iE 'ch34|1-3|ttyUSB'
```

用户 `unitree` 已在 `dialout`、`i2c` 组。

---

## 5. I2C 扫描说明

```bash
# 在 monorepo 根目录
python IrThermal/scripts/i2c_scan.py
# 或在 IrThermal/ 目录内
python scripts/i2c_scan.py
```

本机 GY-MCU **MicroUSB 方案** 下，主板 I2C 上 **通常没有** `0x33`。  
仅当 MLX90640 的 I2C 引脚直插 G1 时，才用 `thermal_view.py --bus N`。

---

## 6. 推荐工作流

```bash
cd /home/unitree/JS_test/thermal/robot-perception
conda activate thermal

lsusb | grep 1a86 && ls /dev/ttyUSB0
python IrThermal/scripts/capture_serial.py --port /dev/ttyUSB0
ls -la IrThermal/output/mlx90640_latest.png
```

---

## 7. 环境创建记录

| 方式 | 说明 |
|------|------|
| `conda activate thermal` | `conda create -n thermal --clone base` + pip 安装 IrThermal 依赖 |
| `conda env create -f environment.yml` | 需网络；本机曾因 conda-forge 超时失败 |
| `source .venv/bin/activate` | 本地 venv，依赖已安装，离线可用 |
