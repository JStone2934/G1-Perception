#!/usr/bin/env python3
"""同时订阅 RGB（teleimager）与热成像（thermal_zmq_server）两路 ZMQ 流。"""

from __future__ import annotations

import argparse
import sys

try:
    from teleimager.image_client import ZMQ_SubscriberManager
except ImportError as exc:
    raise SystemExit(
        "缺少 teleimager，请执行: pip install -e \"./teleimager\""
    ) from exc

import cv2


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RGB + 热成像双路 ZMQ 预览")
    p.add_argument("--host", default="127.0.0.1", help="G1 / 图传服务器 IP")
    p.add_argument("--rgb-port", type=int, default=55555, help="RGB ZMQ 端口")
    p.add_argument("--thermal-port", type=int, default=55556, help="热成像 ZMQ 端口")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    try:
        cv2.namedWindow("RGB", cv2.WINDOW_NORMAL)
        cv2.namedWindow("Thermal", cv2.WINDOW_NORMAL)
    except cv2.error:
        print(
            "OpenCV 无 GUI（多为 opencv-python-headless）。\n"
            "  请: pip uninstall opencv-python-headless -y && pip install opencv-python",
            file=sys.stderr,
        )
        return 1

    manager = ZMQ_SubscriberManager.get_instance()
    manager.subscribe(args.host, args.rgb_port, request_bgr=True)
    manager.subscribe(args.host, args.thermal_port, request_bgr=True)

    print(
        f"[dual-zmq] RGB tcp://{args.host}:{args.rgb_port}  "
        f"Thermal tcp://{args.host}:{args.thermal_port}"
    )
    print("[dual-zmq] 按 q 退出")

    running = True
    while running:
        rgb = manager.subscribe(args.host, args.rgb_port, request_bgr=True)
        thermal = manager.subscribe(args.host, args.thermal_port, request_bgr=True)

        if rgb.bgr is not None:
            cv2.imshow("RGB", rgb.bgr)
        if thermal.bgr is not None:
            cv2.imshow("Thermal", thermal.bgr)

        key = cv2.waitKey(30) & 0xFF
        if key in (ord("q"), ord("Q"), 27):
            running = False

    manager.close()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
