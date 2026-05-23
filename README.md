# robot-perception

Unitree G1 **RGB 图传 + MLX90640 热成像** 单体仓库（monorepo）。

| 组件 | 路径 | 作用 |
|------|------|------|
| 热成像 | [`IrThermal/`](IrThermal/) | `packages/irthermal` 库 + CLI 脚本 |
| 图传 | [`teleimager/`](teleimager/) | 多路相机 ZMQ / WebRTC（[上游文档](teleimager/README_zh-CN.md)） |

架构说明：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)  
热成像排障：[IrThermal/docs/G1_TROUBLESHOOTING.md](IrThermal/docs/G1_TROUBLESHOOTING.md)

---

## 环境（conda `thermal`）

```bash
cd /home/unitree/JS_test/thermal/robot-perception

# 推荐：继续使用已有 conda 环境 thermal
conda activate thermal
pip install -e "./IrThermal/packages/irthermal[gui,i2c]"
python3.8 -m pip install -e "./teleimager[server]"   # G1 常用 python3.8；须与运行 teleimager-server 的解释器一致
# 无网时: python3.8 -m pip install -e "./teleimager" --no-deps

# 全新机器才需要：
# conda env create -f environment.yml && conda activate thermal

# 一键检查目录与导入是否正常：
python IrThermal/scripts/verify_setup.py
```

串口权限：`sudo usermod -aG dialout $USER` 后重新登录。  
相机权限：`cd teleimager && bash setup_uvc.sh`（首次）。

---

## 热成像

```bash
conda activate thermal
cd /home/unitree/JS_test/thermal/robot-perception

lsusb | grep 1a86
python IrThermal/scripts/capture_serial.py --port /dev/ttyUSB0
python IrThermal/scripts/thermal_view_serial.py --port /dev/ttyUSB0
python IrThermal/scripts/dual_viewer.py --port /dev/ttyUSB0 --camera 4
```

也可用：

```bash
./activate.sh python IrThermal/scripts/capture_serial.py --port /dev/ttyUSB0
# 或仅在热成像子目录：
./IrThermal/activate.sh python scripts/capture_serial.py --port /dev/ttyUSB0
```

默认输出：`IrThermal/output/mlx90640_latest.png`

---

## 图传（RGB + 热成像，单进程）

`teleimager-server` 已支持 `type: thermal`（串口 MLX90640）。热成像配置在 **`left_wrist_camera`** 槽位，远端标准 `teleimager-client` 会自动显示 **Left Wrist Camera** 窗口，**无需改远端代码**。

```bash
conda activate thermal
cd /home/unitree/JS_test/thermal/robot-perception

# 确认 irthermal + teleimager 已安装（改 image_server 后需重装）
pip install -e "./IrThermal/packages/irthermal[gui,i2c]"
python3.8 -m pip install -e "./teleimager[server]"

# G1 上启动（RGB + 热成像，单进程）
./services/start_teleimager.sh
# 或: python3.8 -m teleimager.image_server

# 远端 PC（标准客户端，零改动）
teleimager-client --host <G1_IP>
# WebRTC RGB: https://<G1_IP>:60001
```

配置见 `teleimager/cam_config_server.yaml`：

| 槽位 | 类型 | 端口 | 说明 |
|------|------|------|------|
| `head_camera` | `opencv` | ZMQ `55555` / WebRTC `60001` | RealSense RGB |
| `left_wrist_camera` | `thermal` | ZMQ `55556` | 热成像（串口 `/dev/ttyUSB0`，约 2Hz） |

`type: thermal` 可用字段：`serial_port`、`baud`、`use_init`、`overlay`、`jpeg_quality`、`image_shape`、`fps`、`settle_s`、`read_timeout`、`optional`。

热成像为 GY-MCU **请求-应答串口流**（每帧发 START），非 UVC 连续视频；G1 实测稳定约 **2fps**。若画面卡顿，检查 yaml 中 **`read_timeout` 勿为 0**，并确认已重装 `irthermal` 包。

**G1 启动前**（若 RGB 打不开或被占用）：

```bash
/unitree/sbin/mscli stopservice video_hub_pc4
lsof /dev/video4
```

排障详见 [`teleimager/REALSENSE_RGB_OPENCV_TROUBLESHOOTING.md`](teleimager/REALSENSE_RGB_OPENCV_TROUBLESHOOTING.md)、[`IrThermal/docs/G1_TROUBLESHOOTING.md`](IrThermal/docs/G1_TROUBLESHOOTING.md)。

---

## 热成像 ZMQ 图传（方案 2，独立进程，备用）

若不想改 `image_server.py`，可用独立脚本发布热成像 ZMQ（与 `teleimager-server` 并行）：

```bash
# G1 — 终端 1
./services/start_teleimager.sh
# G1 — 终端 2
./services/start_thermal_zmq.sh --port /dev/ttyUSB0

# 远端 — 需专用客户端
python IrThermal/scripts/dual_zmq_viewer.py --host <G1_IP>
```

---

## 目录结构

```
robot-perception/
├── IrThermal/              # 热成像子项目（原 IrThermal 仓库内容）
│   ├── packages/irthermal/
│   ├── scripts/
│   ├── docs/
│   ├── output/
│   └── activate.sh
├── teleimager/
├── services/
│   ├── start_teleimager.sh
│   └── start_thermal_zmq.sh   # 方案 2 备用
├── docs/
├── environment.yml         # conda 环境名: thermal
├── requirements.txt
└── activate.sh
```

---

## 迁移说明

本仓库由 `JS_test/thermal/IrThermal` 与 `JS_test/thermal/teleimager` 收敛而成。  
**新开发请以 `robot-perception/` 为准**；图传配置见 `robot-perception/teleimager/cam_config_server.yaml`。
