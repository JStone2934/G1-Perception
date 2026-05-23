# RealSense RGB OpenCV 排障记录

> **本仓库路径：** `/home/unitree/JS_test/thermal/robot-perception/teleimager`  
> **Conda 环境：** `thermal`（与 `JS_test/thermal/teleimager` 的 `teleimager` 环境为平行副本）

## 背景

目标是在 `teleimager-server` 中保持 `type: opencv`，通过 OpenCV 传输 RealSense 的**可见光真彩色 RGB** 图像，而不是红外或深度图像。

- 设备：Intel RealSense Depth Camera 435i  
- 序列号：`351623061215`  
- 平台：Unitree G1 / PC4（Jetson，`conda activate thermal`）

---

## 现象汇总

| 阶段 | 现象 |
|------|------|
| 早期 | `video_id: 4` 报错 `Cannot find OpenCVCamera`（系统仅有 `/dev/video0`–`3`） |
| 中期 | `/dev/video2` 用 OpenCV 能读出 `640×480×3`，但画面为红外/深度伪彩色，非真 RGB |
| 绑定 UVC 后 | 出现 `/dev/video5`（RGB）、`/dev/video6`（metadata）；V4L2 曾报 `Input/output error` |
| 当前现场 | RGB 节点为 **`/dev/video4`**；`teleimager-server` 报 **device busy**，停止 `wlr-video-hub` 仍失败 |
| 修复后 | 停止 `videohub_pc4` 并修正 YUYV 解码后，可正常出真彩色 JPEG / WebRTC |

---

## 问题原因（根因分析）

### 1. `/dev/videoX` 编号会变化

RealSense 在 USB 上会枚举多个 V4L2 节点（深度 Z16、红外 GREY、RGB YUYV、metadata 等）。  
**`/dev/video` 编号随重启、插拔、驱动绑定顺序变化**，不能写死某次观察到的编号。

历史上曾出现：

- 仅 `video0`–`3` 时 → `video_id: 4` 不存在  
- 绑定 RGB UVC 后 → RGB 在 `video5`，metadata 在 `video6`  
- 再次枚举后（仅保留 RGB 相关节点时）→ **RGB 在 `video4`，metadata 在 `video5`**

**结论：** 每次部署前用 `teleimager-server --cf` 或 `v4l2-ctl --list-devices` 确认；本仓库推荐配置 **`serial_number`** 自动解析 RGB 节点。

### 2. 用 OpenCV「3 通道」判断 RGB 会误判

`/dev/video2` 等深度/红外节点支持 `UYVY`/`GREY`，OpenCV 读出来也可能是 `H×W×3`，但三通道均值接近、无真实色彩，例如：

```text
mean BGR: [213, 213, 213]   # 近似灰度，非真彩色
```

**真 RGB 节点特征（V4L2）：**

- 像素格式含 **`YUYV`**
- 控制项含 **`saturation`、`white_balance`** 等彩色相机项
- **不是** metadata-only 节点（`--list-formats-ext` 为空或仅有 Metadata Capture）

`/dev/video2` 典型格式：`GREY`、`UYVY`、`Y8I` —— 属深度/红外链路。  
**不要把 `/dev/video2` 当 RGB 使用。**

### 3. RGB UVC 未绑定时无彩色节点

USB 层若 RGB 接口未绑定 `uvcvideo`：

```text
If 3, Class=Video, Driver=
If 4, Class=Video, Driver=
```

可尝试手动绑定（总线号以 `lsusb -t` 为准）：

```bash
echo '2-2.1:1.3' | sudo tee /sys/bus/usb/drivers/uvcvideo/bind
# 1.4 可能报 No such device，不一定失败；绑定后 lsusb -t 应显示 Driver=uvcvideo
```

绑定异常时 V4L2 可能报：

```text
VIDIOC_STREAMON returned -1 (Input/output error)
```

此时需 USB 复位（见下文「USB 恢复步骤」），而非改 YAML。

### 4. Unitree `videohub_pc4` 独占 `/dev/video4`（最常见阻塞）

在 G1/PC4 上，**真正占用 RGB 设备的是 `videohub_pc4`**，而非 `wlr-video-hub.service` alone：

```text
/unitree/module/video_hub_pc4/videohub_pc4
  → GStreamer: v4l2src device=/dev/video4 ! video/x-raw, format=YUY2, ...
```

| 操作 | 是否释放 `/dev/video4` |
|------|------------------------|
| `sudo systemctl stop wlr-video-hub.service` | **否**（仅停 mediamtx + VideoHub） |
| `/unitree/sbin/mscli stopservice video_hub_pc4` | **是** |

`videohub_pc4` 由 Unitree `master_service` 管理（配置：`/unitree/etc/master_service/service/video_hub_pc4`），与 systemd 的 `wlr-video-hub.service` **相互独立**。

因此用户即使已 `systemctl stop wlr-video-hub`，仍可能看到：

```text
[OpenCVCamera] Cannot open /dev/video4. V4L2 device /dev/video4 is busy ...
```

### 5. OpenCV + YUYV 帧格式与 teleimager 解码

在 `CAP_PROP_CONVERT_RGB=0`、fourcc=`YUYV`/`UYVY` 时，OpenCV V4L2 后端常返回**原始打包缓冲**，而非 `H×W×3`：

```text
shape=(1, 614400)   # 640×480×2 字节 YUYV
```

若直接 `imencode` 会报错：

```text
imencode(): Maximum supported image dimension is 65500 pixels
```

必须先 `reshape(H, W, 2)` 再 `cv2.cvtColor(..., COLOR_YUV2BGR_YUY2)` 得到真彩色 BGR。

### 6. yaml 写 `UYVY` 但设备实际为 `YUYV`（色彩发绿/偏色）

RealSense RGB 节点在 V4L2 上格式为 **`YUYV`**。若在 `cam_config_server.yaml` 中写 `fourcc: UYVY`，且代码按 UYVY 解码，会得到严重偏色（例如 G 通道极高）。

验证：

```bash
v4l2-ctl -d /dev/video4 --list-formats-ext | grep YUYV
# 请求 UYVY 时 OpenCV 仍可能报告实际 fourcc 为 YUYV
```

**处理：**

- yaml 使用 `fourcc: YUYV`（本仓库已修正）  
- 或依赖代码自动读取 `CAP_PROP_FOURCC` 并按实际格式解码（`image_server.py` 已支持）

---

## 修复过程

### A. 一键脚本（推荐）

```bash
cd /home/unitree/JS_test/thermal/robot-perception/teleimager
./fix_realsense_rgb_teleimager.sh              # 停头摄 → 检测 → 启动 teleimager-server
./fix_realsense_rgb_teleimager.sh --fix-only   # 仅释放摄像头并检测
./fix_realsense_rgb_teleimager.sh --check      # 仅检测
./fix_realsense_rgb_teleimager.sh --restore    # 恢复 videohub / wlr-video-hub
./fix_realsense_rgb_teleimager.sh --reinstall  # 修复前重装 teleimager 包（thermal 环境）
```

脚本默认使用 `$HOME/miniconda3/envs/thermal/bin/teleimager-server`。

### B. 运维：手动释放摄像头后再启动 teleimager

```bash
# 1. 停止 Unitree 头摄（必须）
/unitree/sbin/mscli stopservice video_hub_pc4

# 2. 可选：若不需要 WLR 栈，可再停
sudo systemctl stop wlr-video-hub.service

# 3. 确认 RGB 节点可出帧（conda 环境 thermal）
conda activate thermal
/home/unitree/miniconda3/envs/thermal/bin/teleimager-server --cf
```

期望输出示例：

```text
Found V4L2 RGB video devices: ['/dev/video4']
  /dev/video4: stream_test=OK
```

若仍为 `BUSY/FAILED`，检查是否还有进程占用：

```bash
pgrep -a videohub
```

启动图传：

```bash
/home/unitree/miniconda3/envs/thermal/bin/teleimager-server
# WebRTC: https://<机器人IP>:60001  （yaml 中 webrtc_port: 60001）
```

恢复机器人默认头摄：

```bash
/unitree/sbin/mscli startservice video_hub_pc4
sudo systemctl start wlr-video-hub.service
```

> **注意：** 请使用 conda 环境 `thermal` 内的 `teleimager-server`（`~/.local/bin` 可能指向其他 Python 版本）。

### C. 代码：`teleimager` 侧修改（`src/teleimager/image_server.py`）

| 修改项 | 说明 |
|--------|------|
| `_is_like_rgb()` | 改为 V4L2 检测（YUYV + saturation/white_balance + 有 Capture 格式），**不再**用 OpenCV 读帧判 3 通道 |
| `resolve_opencv_video_path()` | `video_id` 指向非 RGB 时，尝试解析到真 RGB 节点 |
| `OpenCVCamera` | 支持 yaml 中的 `fourcc: YUYV`/`UYVY`；处理 `(1, H×W×2)` 缓冲并转 BGR |
| `--cf` | 打印 RGB 列表及 `stream_test=OK/BUSY`；忙时提示 `mscli stopservice video_hub_pc4` |
| 错误提示 | 明确区分 `wlr-video-hub` 与 `videohub_pc4` |
| `logging_mp` | 避免重复 `basicConfig` 导致 `--cf` / 启动崩溃 |

安装/更新 editable 包：

```bash
conda activate thermal
cd /home/unitree/JS_test/thermal/robot-perception/teleimager
pip install -e ".[server]"
```

### D. USB / 驱动异常时的恢复步骤

当 RGB 节点存在但 V4L2 `STREAMON` 报 I/O error 时：

```bash
echo 0 | sudo tee /sys/bus/usb/devices/2-2.1/authorized   # 路径以实际 bus 为准
sleep 2
echo 1 | sudo tee /sys/bus/usb/devices/2-2.1/authorized
sleep 2

lsusb -t
ls -l /dev/video*
v4l2-ctl --list-devices
teleimager-server --cf
```

---

## YAML 设置（本仓库 `cam_config_server.yaml`）

本副本已使用序列号锁定 RGB，示例：

```yaml
head_camera:
  type: opencv
  fourcc: YUYV              # 必须为 YUYV，勿写 UYVY（会色彩错误）
  image_shape: [480, 848]   # [高, 宽]，按所需分辨率
  fps: 30
  serial_number: "351623061215"
```

- 推荐 **`serial_number`**，由 `CameraFinder` 自动匹配真 RGB 节点，不依赖 `/dev/videoX` 编号。  
- 若使用 `video_id`，必须以 `teleimager-server --cf` 为准。  
- **不要**使用 `/dev/video2` 等深度/红外节点。

---

## 判断标准（真 RGB 节点）

满足以下多项即可认为是可见光 RGB：

```text
v4l2-ctl --list-formats-ext  → 含 'YUYV'
v4l2-ctl --list-ctrls        → 含 saturation、white_balance 等
v4l2-ctl --stream-mmap       → 能正常出帧（且未被 videohub_pc4 占用）
OpenCV 读帧                  → BGR 三通道均值差异明显（非 R≈G≈B）
```

**不应**仅根据 `frame.shape == (H, W, 3)` 判断。

---

## 故障对照表

| 报错 / 现象 | 原因 | 处理 |
|-------------|------|------|
| `Cannot find OpenCVCamera ... video_id 4` | 无 `/dev/video4`，RGB 未枚举 | USB 绑定 / 复位；`--cf` 查实际编号 |
| 能开摄像头但画面偏灰/红外 | `video_id` 指到 depth/IR 节点 | 改用 `serial_number` 或 `--cf` 列出的 RGB 节点 |
| `Cannot open /dev/video4` busy | `videohub_pc4` 占用 | `mscli stopservice video_hub_pc4` 或一键脚本 |
| 已 stop `wlr-video-hub` 仍 busy | 未停 `videohub_pc4` | 同上 |
| `imencode ... Maximum supported image dimension` | YUYV 未 reshape 转 BGR | `pip install -e .` 更新本仓库代码 |
| 图传有画面但发绿/色偏 | yaml `fourcc: UYVY` 与设备 YUYV 不符 | 改为 `fourcc: YUYV` 并 `pip install -e .` |
| `--cf` 无 RGB / stream FAILED | 忙或驱动异常 | 停 videohub；或 USB 复位 |

---

## 当前现场结论（2026-05-23）

- 真彩色 RGB：**`/dev/video4`**（YUYV，带 saturation 等控制项）  
- Metadata：**`/dev/video5`**（无采集格式，不可作图传源）  
- 启动 `teleimager-server` 前**必须**执行：`/unitree/sbin/mscli stopservice video_hub_pc4`  
- 本仓库通过 **`serial_number: "351623061215"`** 绑定设备，避免 `video_id` 漂移

---

## 相关文件

- 服务配置：`/unitree/etc/master_service/service/video_hub_pc4`  
- teleimager 源码：`src/teleimager/image_server.py`  
- 服务端配置：`cam_config_server.yaml`  
- 一键修复脚本：`fix_realsense_rgb_teleimager.sh`  
- 平行副本（conda `teleimager`）：`/home/unitree/JS_test/thermal/teleimager`
