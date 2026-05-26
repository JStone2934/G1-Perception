# IrThermal（robot-perception 子目录）

**Tiny1C** USB 热成像（AC010_256 SDK / `0bda:5840`）：采集、本地预览与 teleimager 图传。

完整 monorepo 说明见上级 [../README.md](../README.md)。

---

## 环境

```bash
cd /home/unitree/JS_test/thermal/robot-perception
conda activate thermal
pip install -e "./IrThermal/packages/irthermal[gui,i2c]"
```

AC010 运行时库（`libiruvc.so` 等）已内置在 `packages/irthermal/src/irthermal/vendor/ac010/`，**无需**在仓库外解压 SDK。仅当使用自定义库路径时设置 `IRTHERMAL_AC010_SDK`。

---

## 首次使用（重要）

Tiny1C 通过 **libusb** 访问，与内核 **uvcvideo** 冲突。每次上电或插拔后执行一次：

```bash
bash IrThermal/scripts/tiny1c_prepare.sh   # 需 sudo，解绑 uvc + USB 权限
```

可选：安装 udev 规则后无需每次 chmod：

```bash
sudo cp IrThermal/udev/99-tiny1c-thermal.rules /etc/udev/rules.d/
sudo udevadm control --reload && sudo udevadm trigger
```

---

## 快速开始

```bash
conda activate thermal
cd /home/unitree/JS_test/thermal/robot-perception

# 仅热成像预览
python IrThermal/scripts/thermal_view_tiny1c.py

# 热成像 + RGB 摄像头
python IrThermal/scripts/dual_viewer.py --camera 4

# ZMQ 发布（端口见 cam_config_server.yaml）
python IrThermal/scripts/thermal_zmq_server.py
```

---

## 图传（teleimager `type: thermal`）

`teleimager/cam_config_server.yaml` 中 `thermal_camera` 槽位。启动 image server 前同样执行 `tiny1c_prepare.sh`。

---

## 目录结构

```
IrThermal/
├── packages/irthermal/src/irthermal/
│   ├── tiny1c.py          # Tiny1C 驱动（ctypes + 内置 vendor 库）
│   └── vendor/ac010/      # AC010 预编译 .so（aarch64 / x86）
│   └── usb_setup.py       # 解绑 uvc / USB 权限
├── scripts/
│   ├── thermal_view_tiny1c.py
│   ├── tiny1c_prepare.sh
│   ├── dual_viewer.py
│   └── thermal_zmq_server.py
├── udev/99-tiny1c-thermal.rules
└── docs/G1_TROUBLESHOOTING.md
```

旧版 GY-MCU90640 串口脚本（`thermal_view_serial.py` 等）已弃用，仅作参考保留。
