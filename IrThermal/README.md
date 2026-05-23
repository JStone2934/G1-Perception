# IrThermal（robot-perception 子目录）

GY-MCU90640 / MLX90640 热成像：串口协议、采集与本地预览脚本。

完整 monorepo 说明见上级 [../README.md](../README.md)。  
排障：[docs/G1_TROUBLESHOOTING.md](docs/G1_TROUBLESHOOTING.md)

---

## 环境

使用 monorepo 统一的 **conda `thermal`** 环境：

```bash
cd /home/unitree/JS_test/thermal/robot-perception
conda activate thermal
pip install -e "./IrThermal/packages/irthermal[gui,i2c]"
```

仅在本子目录工作时：

```bash
cd /home/unitree/JS_test/thermal/robot-perception/IrThermal
conda activate thermal
pip install -e "./packages/irthermal[gui,i2c]"
# 或: pip install -r requirements.txt
```

---

## 快速开始

```bash
conda activate thermal
cd /home/unitree/JS_test/thermal/robot-perception

python IrThermal/scripts/capture_serial.py --port /dev/ttyUSB0
python IrThermal/scripts/thermal_view_serial.py --port /dev/ttyUSB0
python IrThermal/scripts/dual_viewer.py --port /dev/ttyUSB0 --camera 4
```

在 `IrThermal/` 目录内（路径可省略前缀）：

```bash
./activate.sh python scripts/capture_serial.py --port /dev/ttyUSB0
```

默认输出：`output/mlx90640_latest.png`（相对本目录）

---

## 图传集成（teleimager `type: thermal`）

monorepo 内通过 `teleimager/cam_config_server.yaml` 的 `left_wrist_camera` 槽位接入。串口读帧使用 `poll_frame(..., read_timeout=...)`；**勿将串口 `timeout` 设为 0**，否则 ZMQ 热图会频繁卡顿。实测帧率约 **2Hz**，详见 [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)。

## 目录结构

```
IrThermal/
├── packages/irthermal/
├── scripts/
│   ├── capture_serial.py
│   ├── thermal_view_serial.py
│   ├── dual_viewer.py
│   ├── dual_zmq_viewer.py      # 方案 2：RGB+热成像 ZMQ 预览
│   ├── thermal_zmq_server.py   # 方案 2：独立热成像 ZMQ 发布
│   ├── thermal_zmq_client.py
│   ├── thermal_view.py
│   ├── i2c_scan.py
│   └── verify_setup.py
├── docs/
├── output/
├── environment.yml      # 仅热成像依赖（name: thermal）
├── requirements.txt
└── activate.sh
```
