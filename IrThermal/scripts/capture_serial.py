#!/usr/bin/env python3
"""GY-MCU90640 单帧采集（无 GUI，含 DTR/RTS 唤醒）。"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap  # noqa: E402, F401

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import cm

from irthermal import CMD_STOP, find_port, frame_to_temps, open_serial, sync_frame

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_OUTPUT = os.path.join(REPO_ROOT, "output", "mlx90640_latest.png")


def main() -> int:
    p = argparse.ArgumentParser(description="GY-MCU90640 单帧保存")
    p.add_argument("--port", default=None)
    p.add_argument("--baud", type=int, default=460800)
    p.add_argument("--init", action="store_true")
    p.add_argument("--output", default=DEFAULT_OUTPUT)
    args = p.parse_args()

    port = find_port(args.port)
    if not os.path.exists(port):
        print(f"未找到串口设备（期望 {port}）。请插入 MicroUSB 后执行：")
        print("  lsusb | grep -i '1a86\\|10c4\\|0403'")
        print("  ls /dev/ttyUSB*")
        return 1

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    print(f"打开 {port} @ {args.baud} …")
    ser = open_serial(port, args.baud, use_init=args.init)

    raw = sync_frame(ser)
    ta, img = frame_to_temps(raw)
    print(f"Ta={ta:.2f}°C  min={img.min():.2f}°C  max={img.max():.2f}°C")

    fig, ax = plt.subplots(figsize=(6.5, 5))
    im = ax.imshow(img, cmap=cm.inferno, vmin=img.min(), vmax=img.max())
    plt.colorbar(im, ax=ax, label="°C")
    ax.set_title(f"GY-MCU90640  {port}")
    fig.savefig(args.output, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"已保存 {args.output}")

    try:
        ser.write(CMD_STOP)
    except Exception:
        pass
    ser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
