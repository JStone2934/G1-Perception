#!/usr/bin/env python3
"""GY-MCU90640 串口热成像（MicroUSB + CH340 → /dev/ttyUSB*，460800）。"""

from __future__ import annotations

import argparse
import sys
import time

import matplotlib.pyplot as plt
import numpy as np
import serial
from matplotlib import cm
from matplotlib.animation import FuncAnimation

FRAME_SIZE = 1544
HEADER = b"\x5a\x5a"

# 启动自动上报（115200 固件常用；460800 多数已自动发送，发送也无害）
CMD_START = bytes([0xA5, 0x35, 0x02, 0xDC])
CMD_STOP = bytes([0xA5, 0x35, 0x01, 0xDB])
CMD_4HZ = bytes([0xA5, 0x25, 0x01, 0xCB])


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="GY-MCU90640 串口热成像")
    p.add_argument("--port", default="/dev/ttyUSB1", help="串口设备")
    p.add_argument("--baud", type=int, default=460800, help="波特率（本模块常用 460800）")
    p.add_argument("--init", action="store_true", help="发送启动/4Hz 配置命令")
    p.add_argument("--save", type=str, default=None, help="保存单帧 PNG")
    p.add_argument("--list-ports", action="store_true", help="列出 ttyUSB 并探测帧头")
    return p.parse_args()


def sync_frame(ser: serial.Serial) -> bytes:
    """读取一帧 1544 字节，帧头 0x5A5A。"""
    buf = bytearray()
    while True:
        b = ser.read(1)
        if not b:
            raise TimeoutError("串口超时，未收到数据")
        buf += b
        if len(buf) >= 2 and buf[-2:] == HEADER:
            buf = bytearray(HEADER)
            rest = ser.read(FRAME_SIZE - 2)
            if len(rest) < FRAME_SIZE - 2:
                raise TimeoutError("帧数据不完整")
            buf.extend(rest)
            return bytes(buf)
        if len(buf) > 4096:
            buf.clear()


def frame_to_temps(raw: bytes) -> tuple[float, np.ndarray]:
    if len(raw) != FRAME_SIZE or raw[:2] != HEADER:
        raise ValueError("无效帧")
    ta = (raw[1540] + raw[1541] * 256) / 100.0
    arr = np.frombuffer(raw[4:1540], dtype=np.int16).reshape(24, 32) / 100.0
    return ta, arr


def probe_ports() -> int:
    import glob

    for path in sorted(glob.glob("/dev/ttyUSB*")):
        print(f"\n{path}:")
        for baud in (460800, 115200):
            try:
                ser = serial.Serial(path, baud, timeout=0.8)
                time.sleep(0.15)
                ser.reset_input_buffer()
                chunk = ser.read(200)
                ser.close()
                tag = "GY-MCU90640?" if chunk[:2] == HEADER else "—"
                print(f"  {baud}: len={len(chunk)} head={chunk[:4].hex() if chunk else 'empty'}  {tag}")
            except Exception as e:
                print(f"  {baud}: {e}")
    return 0


def main() -> int:
    args = parse_args()
    if args.list_ports:
        return probe_ports()

    print(f"打开 {args.port} @ {args.baud} …")
    ser = serial.Serial(args.port, args.baud, timeout=2)
    time.sleep(0.1)
    ser.reset_input_buffer()

    if args.init or args.baud == 115200:
        ser.write(CMD_4HZ)
        time.sleep(0.05)
        ser.write(CMD_START)
        time.sleep(0.1)
        ser.reset_input_buffer()

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
        r = sync_frame(ser)
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
