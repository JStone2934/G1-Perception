#!/usr/bin/env python3
"""MLX90640 实时热成像查看（matplotlib）。"""

from __future__ import annotations

import argparse
import sys
import time

import numpy as np

try:
    from adafruit_extended_bus import ExtendedI2C as I2C
except ImportError:
    print("请安装: pip install adafruit-extended-bus", file=sys.stderr)
    sys.exit(1)

import adafruit_mlx90640
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.animation import FuncAnimation


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="MLX90640 热成像实时显示")
    p.add_argument("--bus", type=int, default=1, help="I2C 总线编号，对应 /dev/i2c-N")
    p.add_argument("--hz", type=float, default=2.0, help="刷新率（Hz），建议 2~4")
    p.add_argument("--save", type=str, default=None, help="保存单帧 PNG 路径后退出")
    p.add_argument("--no-show", action="store_true", help="无 GUI 时仅保存或打印统计")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    refresh = adafruit_mlx90640.RefreshRate
    rate_map = {
        0.5: refresh.REFRESH_0_5_HZ,
        1.0: refresh.REFRESH_1_HZ,
        2.0: refresh.REFRESH_2_HZ,
        4.0: refresh.REFRESH_4_HZ,
        8.0: refresh.REFRESH_8_HZ,
        16.0: refresh.REFRESH_16_HZ,
        32.0: refresh.REFRESH_32_HZ,
    }
    closest = min(rate_map.keys(), key=lambda x: abs(x - args.hz))
    refresh_rate = rate_map[closest]

    print(f"连接 I2C 总线 {args.bus} …")
    i2c = I2C(args.bus)
    mlx = adafruit_mlx90640.MLX90640(i2c)
    mlx.refresh_rate = refresh_rate
    frame = [0.0] * 768

    def read_frame() -> np.ndarray:
        for _ in range(5):
            try:
                mlx.getFrame(frame)
                break
            except ValueError:
                time.sleep(0.05)
        else:
            raise RuntimeError("连续读取 MLX90640 失败（too many retries）")
        # 24x32，行优先
        return np.array(frame, dtype=np.float32).reshape(24, 32)

    if args.save:
        img = read_frame()
        fig, ax = plt.subplots(figsize=(6, 4.5))
        im = ax.imshow(img, cmap=cm.inferno, vmin=img.min(), vmax=img.max())
        plt.colorbar(im, ax=ax, label="°C")
        ax.set_title(f"MLX90640  i2c-{args.bus}")
        fig.savefig(args.save, dpi=150, bbox_inches="tight")
        print(f"已保存: {args.save}  min={img.min():.1f}°C  max={img.max():.1f}°C")
        return 0

    if args.no_show:
        img = read_frame()
        print(f"min={img.min():.2f}°C  max={img.max():.2f}°C  mean={img.mean():.2f}°C")
        return 0

    fig, ax = plt.subplots(figsize=(7, 5))
    img0 = read_frame()
    im = ax.imshow(img0, cmap=cm.inferno, vmin=20, vmax=40)
    plt.colorbar(im, ax=ax, label="°C")
    ax.set_title(f"MLX90640  i2c-{args.bus}  ({closest} Hz)")

    def update(_):
        img = read_frame()
        im.set_data(img)
        im.set_clim(vmin=img.min(), vmax=img.max())
        ax.set_xlabel(f"min={img.min():.1f}°C  max={img.max():.1f}°C")
        return [im]

    interval_ms = int(1000 / max(closest, 0.5))
    ani = FuncAnimation(fig, update, interval=interval_ms, cache_frame_data=False)
    print("关闭窗口结束。Ctrl+C 可中断。")
    plt.show()
    return 0


if __name__ == "__main__":
    sys.exit(main())
