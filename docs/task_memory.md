# 任务记忆文档

任务记忆文档的约定格式（请勿修改）：

## 时间

2026-05-23（G1 / robot-perception monorepo）

## 进行到哪一步

**RGB + 热成像双路图传已落地；热成像卡顿问题已修复（待 commit）。**

- **主方案（路径 B）**：`teleimager-server` 单进程同时发布 RGB + 热成像
  - RGB：`head_camera`，`type: opencv`，RealSense `/dev/video4`，ZMQ `:55555` / WebRTC `:60001`
  - 热成像：`left_wrist_camera`，`type: thermal`，串口 `/dev/ttyUSB0`，ZMQ `:55556`，**实测约 2Hz**
  - 远端 **`teleimager-client --host <G1_IP>`** 零改动，热图窗口名为 **Left Wrist Camera**
- **热成像修复**：`poll_frame` 增加 `read_timeout`；去掉运行时 `ser.timeout=0`；yaml `fps: 2`、`settle_s` / `read_timeout`
- **备用方案 2**：独立脚本 `thermal_zmq_server.py` + `dual_zmq_viewer.py`（同步修复）
- **代码**：`image_server.py` 新增 `ThermalCamera`；RealSense YUYV 手动解码 + 读帧容错
- **配置**：`teleimager/cam_config_server.yaml` 已更新
- **文档**：`README.md`、`docs/ARCHITECTURE.md`、`IrThermal/README.md` 已同步

**G1 常用启动：**

```bash
conda activate thermal
cd ~/JS_test/thermal/robot-perception
python3.8 -m pip install -e "./IrThermal/packages/irthermal[gui,i2c]"
python3.8 -m pip install -e "./teleimager[server]"
/unitree/sbin/mscli stopservice video_hub_pc4   # 若 RGB 被占用
python3.8 -m teleimager.image_server
```

## 做了哪些决策

1. **双路图传方案**：先评估 5 种方案；用户选方案 2 验证后，改为 **路径 B**（`type: thermal` 接入 teleimager）作为正式方案。
2. **YAML 槽位**：热成像挂在 **`left_wrist_camera`**，而非新增 `thermal_camera` 键——因 `teleimager-client` 只认 head/left/right 三路，远端无需改代码。
3. **热成像 `optional: true`**：串口未接或首帧失败时不阻断 RGB 图传。
4. **首帧采集**：GY-MCU 非连续流，初始化用 **`poll_frame`（发 START）**，不用被动 `sync_frame`。
5. **RealSense 采集**：YUYV **固定手动解码**；读帧区分 `ok/skip/io`，仅连续 IO 失败才 reopen；WebRTC/ZMQ 发布遇空帧等待而非退出。
6. **安装方式**：G1 上统一 **`python3.8 -m pip install -e`**，与 `python3.8 -m teleimager.image_server` 解释器一致。
7. **方案 2 保留**：独立 ZMQ 脚本与 `start_thermal_zmq.sh` 作调试/回退，不删。
8. **热成像串口读帧**：`poll_frame` 须带 **`read_timeout`**（勿在运行时将 `ser.timeout=0`）；GY-MCU 请求-应答协议实测 **~2Hz**，yaml `fps: 2`。

## 为什么这么决策

| 决策 | 原因 |
|------|------|
| 路径 B 为主 | 单进程、YAML 配置、与 xr 遥操栈的 teleimager 多路架构一致 |
| 占用 `left_wrist_camera` | 客户端硬编码三路订阅，改远端成本最高 |
| `optional: true` | 热成像 USB 串口与 RGB 独立，不应因热模块故障拖垮主图传 |
| `poll_frame` 首帧 | `open_serial` 唤醒后会清缓冲，GY-MCU 需主动 START 才回帧 |
| YUYV 手动解码 | WebRTC 负载下 `CAP_PROP_CONVERT_RGB` 易出假帧，触发误判重连 |
| 保留方案 2 | 不改 teleimager 时仍可快速验证热成像 ZMQ |
| `read_timeout` + `fps: 2` | `timeout=0` 导致 ~93% poll 失败卡顿；模块单帧 ~500ms，上限约 2Hz |

## 还有什么问题没有解决

1. **WebRTC 仅 RGB**：热成像目前只有 ZMQ（`:55556`），PICO 浏览器默认只看 `:60001` head 流。
2. **窗口命名**：远端热图显示为 **Left Wrist Camera**，语义不直观（仅为兼容客户端）。
3. **Unitree 头摄冲突**：未执行 `mscli stopservice video_hub_pc4` 时，RGB 可能打不开或偶发 reopen WARNING。
4. **Python 环境易混**：`~/.local/bin/teleimager-server` 与 conda `thermal` 可能不是同一解释器，须用 `python3.8 -m ...`。
5. **`cam_config_client.yaml`**：被 teleimager `.gitignore` 忽略，客户端配置靠首次连接自动生成。
6. **Git**：上一版双路图传 commit `de23283` 在本地 `main`，是否已 push 到 `origin/unitree-g1` 需确认。
7. **热成像 WebRTC / 画面拼接 / PICO 双路**：若遥操 UI 必须单窗口或浏览器看热图，尚未实现（曾为方案 3，未做）。
8. **热成像帧率上限**：GY-MCU 串口非连续流，单进程稳定约 **2Hz**（非 RGB 级 30fps）；属硬件/协议限制。
