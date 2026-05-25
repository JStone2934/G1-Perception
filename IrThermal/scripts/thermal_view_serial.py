#!/usr/bin/env python3
"""GY-MCU90640 串口热成像（matplotlib 实时窗口）。"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap  # noqa: E402, F401

import matplotlib.pyplot as plt
import serial
from matplotlib import cm
from matplotlib.animation import FuncAnimation

from irthermal import (
    CMD_STOP,
    frame_to_temps,
    open_serial,
    poll_frame,
    probe_ports,
    sync_frame,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="GY-MCU90640 串口热成像")
    p.add_argument("--port", default="/dev/ttyUSB0", help="串口设备")
    p.add_argument("--baud", type=int, default=460800, help="波特率（本模块常用 460800）")
    p.add_argument("--init", action="store_true", help="发送启动/4Hz 配置命令")
    p.add_argument("--save", type=str, default=None, help="保存单帧 PNG")
    p.add_argument("--list-ports", action="store_true", help="列出 ttyUSB 并探测帧头")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.list_ports:
        probe_ports()
        return 0

    print(f"打开 {args.port} @ {args.baud} …")
    ser = open_serial(args.port, args.baud, use_init=args.init)

    raw = sync_frame(ser)
    ta, img = frame_to_temps(raw)
    print(f"环境温 Ta={ta:.2f}°C  画面 min={img.min():.2f}°C max={img.max():.2f}°C")

    if args.save:
        fig, ax = plt.subplots(figsize=(6.5, 5))
        im = ax.imshow(img, cmap=cm.inferno, vmin=img.min(), vmax=img.max())
        plt.colorbar(im, ax=ax, label="°C")
        ax.set_title(f"GY-MCU90640  {args.port}")
        fig.savefig(args.save, dpi=150, bbox_inches="tight")
        print(f"已保存 {args.save}")
        ser.write(CMD_STOP)
        ser.close()
        return 0

    fig, ax = plt.subplots(figsize=(7, 5))
    show = ax.imshow(img, cmap=cm.inferno)
    plt.colorbar(show, ax=ax, label="°C")
    ax.set_title(f"GY-MCU90640  {args.port}  ({args.baud})")

    def update(_):
        r = poll_frame(ser)
        t, im = frame_to_temps(r)
        show.set_data(im)
        show.set_clim(vmin=im.min(), vmax=im.max())
        ax.set_xlabel(f"Ta={t:.1f}°C  min={im.min():.1f}°C  max={im.max():.1f}°C")
        return [show]

    print("关闭窗口结束。")
    ani = FuncAnimation(fig, update, interval=250, cache_frame_data=False)
    try:
        plt.show()
    finally:
        try:
            ser.write(CMD_STOP)
        except Exception:
            pass
        ser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
