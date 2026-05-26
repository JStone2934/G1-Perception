#!/usr/bin/env python3
"""Tiny1C USB 热成像实时预览（AC010 SDK）。"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap  # noqa: E402, F401

import cv2

from irthermal import Tiny1CCamera, prepare_tiny1c


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Tiny1C 热成像预览")
    p.add_argument("--width", type=int, default=640, help="显示宽度")
    p.add_argument("--height", type=int, default=480, help="显示高度")
    p.add_argument("--warmup", type=float, default=3.0, help="开流后预热秒数")
    p.add_argument("--no-overlay", action="store_true", help="不叠加温度文字")
    p.add_argument(
        "--prepare-only",
        action="store_true",
        help="仅解绑 uvc / 检查 USB 权限后退出",
    )
    p.add_argument(
        "--display",
        choices=("opencv", "matplotlib"),
        default="opencv",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.prepare_only:
        path = prepare_tiny1c()
        print(f"USB: {path}")
        return 0

    cam = Tiny1CCamera(warmup_s=args.warmup, overlay=not args.no_overlay)
    try:
        cam.open()
    except Exception as exc:
        print(f"[tiny1c] 打开失败: {exc}", file=sys.stderr)
        print(
            "请先执行（需 sudo）:\n"
            "  bash IrThermal/scripts/tiny1c_prepare.sh",
            file=sys.stderr,
        )
        return 1

    print(
        f"[tiny1c] 分辨率 {cam.native_resolution[0]}x{cam.native_resolution[1]}  "
        f"stream_fps={cam.stream_fps}"
    )
    print("[hint] 按 q 退出")

    display = args.display
    try:
        cv2.namedWindow("__tiny1c_gui_test__", cv2.WINDOW_NORMAL)
        cv2.destroyWindow("__tiny1c_gui_test__")
    except cv2.error:
        if display == "opencv":
            print("[hint] OpenCV 无 GUI，改用 matplotlib", file=sys.stderr)
            display = "matplotlib"

    try:
        if display == "matplotlib":
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(8, 6))
            im = ax.imshow(
                cv2.cvtColor(
                    cam.read_bgr(args.width, args.height)[0], cv2.COLOR_BGR2RGB
                )
            )
            ax.axis("off")
            while plt.fignum_exists(fig.number):
                bgr, _ = cam.read_bgr(args.width, args.height)
                im.set_data(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
                fig.canvas.draw_idle()
                plt.pause(0.03)
            plt.close(fig)
        else:
            cv2.namedWindow("Tiny1C Thermal", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("Tiny1C Thermal", args.width, args.height)
            while True:
                bgr, _ = cam.read_bgr(args.width, args.height)
                cv2.imshow("Tiny1C Thermal", bgr)
                if (cv2.waitKey(1) & 0xFF) in (ord("q"), 27):
                    break
            cv2.destroyAllWindows()
    except KeyboardInterrupt:
        pass
    finally:
        cam.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
