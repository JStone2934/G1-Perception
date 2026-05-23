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
python -m pip install -e "./teleimager[server]"   # 须用 env 内 pip，勿用 ~/.local/bin/pip
# 无网时: python -m pip install -e "./teleimager" --no-deps

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

## 图传（RGB）

```bash
conda activate thermal
cd teleimager
teleimager-server --cf          # 发现相机，填写 cam_config_server.yaml
teleimager-server

# 另一终端（远端）
teleimager-client --host <G1_IP>
# WebRTC: https://<G1_IP>:60001
```

一键启动：`./services/start_teleimager.sh`

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
├── docs/
├── environment.yml         # conda 环境名: thermal
├── requirements.txt
└── activate.sh
```

---

## 迁移说明

本仓库由 `JS_test/thermal/IrThermal` 与 `JS_test/thermal/teleimager` 收敛而成。  
**新开发请以 `robot-perception/` 为准**；同级旧目录 `JS_test/thermal/IrThermal` 可保留作备份。

图传配置以 **`JS_test/thermal/teleimager/cam_config_server.yaml`** 为准（`video_id: 4`、`fourcc: YUYV`）；`robot-perception/teleimager/` 内为同步副本。勿改原仓库 `teleimager/src/teleimager/image_server.py` / `image_client.py`。

后续可在 `teleimager` 中增加 `type: thermal`，将 `irthermal` 作为图传第二路（见架构文档）。
