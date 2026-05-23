#!/usr/bin/env python3
"""订阅热成像 ZMQ 流并本地显示（配合 thermal_zmq_server.py）。"""

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
    p = argparse.ArgumentParser(description="热成像 ZMQ 客户端")
    p.add_argument("--host", default="127.0.0.1", help="G1 / 服务器 IP")
    p.add_argument("--zmq-port", type=int, default=55556, help="热成像 ZMQ 端口")
    p.add_argument("--window", default="Thermal ZMQ", help="OpenCV 窗口标题")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    try:
        cv2.namedWindow(args.window, cv2.WINDOW_NORMAL)
    except cv2.error:
        print(
            "OpenCV 无 GUI（多为 opencv-python-headless）。\n"
            "  请: pip uninstall opencv-python-headless -y && pip install opencv-python",
            file=sys.stderr,
        )
        return 1

    manager = ZMQ_SubscriberManager.get_instance()
    manager.subscribe(args.host, args.zmq_port, request_bgr=True)

    print(f"[thermal-zmq-client] 连接 tcp://{args.host}:{args.zmq_port}")
    print("[thermal-zmq-client] 按 q 退出")

    running = True
    while running:
        img = manager.subscribe(args.host, args.zmq_port, request_bgr=True)
        if img.bgr is not None:
            cv2.imshow(args.window, img.bgr)
            print(f"\rFPS: {img.fps:.2f}   ", end="", flush=True)
        key = cv2.waitKey(30) & 0xFF
        if key in (ord("q"), ord("Q"), 27):
            running = False

    manager.close()
    cv2.destroyAllWindows()
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
