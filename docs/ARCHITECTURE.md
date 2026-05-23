# robot-perception 架构

## 目录

```
robot-perception/
├── IrThermal/              # 热成像子项目
│   ├── packages/irthermal/ # 库（串口协议、伪彩色）
│   │   └── src/irthermal/
│   ├── scripts/            # CLI：采集、本地预览、独立 ZMQ（备用）
│   ├── docs/
│   └── output/             # 脚本默认输出
├── teleimager/             # RGB + 热成像图传（ZMQ / WebRTC）
├── services/               # start_teleimager.sh / start_thermal_zmq.sh
└── docs/
```

## 数据流

| 源 | YAML 槽位 | type | 发布 |
|----|-----------|------|------|
| RealSense RGB | `head_camera` | `opencv` | ZMQ `:55555` / WebRTC `:60001` |
| GY-MCU90640 串口 | `left_wrist_camera` | `thermal` | ZMQ `:55556` |

远端使用标准 **`teleimager-client --host <G1_IP>`** 即可：RGB 为 **Head Camera**，热成像为 **Left Wrist Camera**（无需改客户端代码）。

### `type: thermal`（image_server 扩展）

- 依赖：`pip install -e ./IrThermal/packages/irthermal`
- 配置字段：`serial_port`、`baud`、`use_init`、`overlay`、`jpeg_quality`、`image_shape`、`fps`、`settle_s`、`read_timeout`
- `optional: true`（默认）：热成像未接或首帧超时时仍启动 RGB 图传

#### 帧率与串口读帧

GY-MCU90640 经 CH340 串口通信，**每帧须 `CMD_START` 请求**，非 UVC 连续流。G1 实测单帧周期约 **500ms → ~2Hz**。

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| `fps` | `2` | 发布线程限速；设过高只会空转 |
| `settle_s` | `0.12` | START 后等待模块出帧（秒） |
| `read_timeout` | `1.0` | `poll_frame` 读帧超时；**勿设 0**（会导致大量丢帧卡顿） |

底层 `irthermal.poll_frame(..., read_timeout=...)` 在读帧期间临时设置串口超时，避免 `sync_frame` 在 `settle_s` 后立即失败。

### 方案 2（备用）：独立热成像 ZMQ

不经过 `teleimager-server`，单独进程发布 JPEG（与 RGB 并行）：

- 服务端：`IrThermal/scripts/thermal_zmq_server.py` 或 `./services/start_thermal_zmq.sh`
- 客户端：`IrThermal/scripts/dual_zmq_viewer.py`（需专用脚本，非 teleimager-client）

## 依赖关系

```bash
conda activate thermal
pip install -e "./IrThermal/packages/irthermal[gui,i2c]"
python3.8 -m pip install -e "./teleimager[server]"   # G1 上常用 python3.8；editable 安装
```

- `IrThermal/scripts/*` → `irthermal`
- `teleimager-server` → `teleimager` + `[server]` extras（aiortc 等）
- 配置：`teleimager/cam_config_server.yaml`（`cam_config_client.yaml` 由客户端首次连接时自动生成，不入库）

## RealSense RGB 采集说明

- RGB 节点一般为 `/dev/video4`，yaml：`fourcc: YUYV`、`video_id: 4`
- `OpenCVCamera` 对 YUYV **固定手动解码**（WebRTC 负载下比 `CAP_PROP_CONVERT_RGB` 稳定）
- 启动前需释放 Unitree 头摄：`/unitree/sbin/mscli stopservice video_hub_pc4`（详见 `teleimager/REALSENSE_RGB_OPENCV_TROUBLESHOOTING.md`）

## 与旧目录的关系

| 旧路径 | 说明 |
|--------|------|
| `JS_test/thermal/IrThermal` | 热成像历史仓库；逻辑在 monorepo 的 `IrThermal/` 子目录 |
| `JS_test/thermal/teleimager` | 图传上游副本；monorepo 内以 `robot-perception/teleimager/` 为准 |

更新嵌套 teleimager：在独立 teleimager 仓库开发后 `rsync` 或 `git subtree pull` 到本目录。
