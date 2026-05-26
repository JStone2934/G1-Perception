#!/usr/bin/env python3
"""Tiny1C 热成像 → ZMQ JPEG 发布（与 teleimager RGB 图传并行）。"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap  # noqa: E402, F401

import cv2

from irthermal import Tiny1CCamera

try:
    from teleimager.image_client import ZMQ_PublisherManager
except ImportError as exc:
    raise SystemExit(
        "缺少 teleimager，请在 conda env thermal 中执行:\n"
        '  pip install -e "./teleimager[server]"'
    ) from exc


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Tiny1C 热成像 ZMQ 发布（JPEG，兼容 teleimager-client）"
    )
    p.add_argument("--bind", default="0.0.0.0", help="ZMQ 绑定地址")
    p.add_argument("--zmq-port", type=int, default=55556, help="ZMQ 端口")
    p.add_argument("--width", type=int, default=640, help="输出宽度")
    p.add_argument("--height", type=int, default=480, help="输出高度")
    p.add_argument("--fps", type=float, default=15.0, help="发布帧率上限")
    p.add_argument("--warmup", type=float, default=3.0, help="开流预热秒数")
    p.add_argument("--jpeg-quality", type=int, default=85)
    p.add_argument(
        "--overlay",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    interval = max(1.0 / max(args.fps, 0.5), 0.02)
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), max(1, min(args.jpeg_quality, 100))]

    cam = Tiny1CCamera(warmup_s=args.warmup, overlay=args.overlay)
    try:
        cam.open()
        bgr, temps, ta = cam.read()
        print(
            f"[thermal-zmq] 首帧 OK  Ta={ta:.1f}C  "
            f"min={temps.min():.1f}C  max={temps.max():.1f}C"
        )
    except Exception as exc:
        print(f"[thermal-zmq] 首帧失败: {exc}", file=sys.stderr)
        print("请先: bash IrThermal/scripts/tiny1c_prepare.sh", file=sys.stderr)
        return 1

    publisher = ZMQ_PublisherManager.get_instance()
    running = True

    def _stop(*_) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    print(
        f"[thermal-zmq] 发布 tcp://{args.bind}:{args.zmq_port}  "
        f"{args.width}x{args.height} @ ≤{args.fps:.1f} Hz"
    )
    print("[thermal-zmq] Ctrl+C 退出")

    frames = 0
    t0 = time.monotonic()
    try:
        while running:
            loop_start = time.monotonic()
            try:
                bgr, label = cam.read_bgr(args.width, args.height, overlay=args.overlay)
            except (TimeoutError, RuntimeError) as exc:
                print(f"[thermal-zmq] 读帧: {exc}", file=sys.stderr)
                time.sleep(0.1)
                continue

            ok, buf = cv2.imencode(".jpg", bgr, encode_params)
            if not ok:
                continue
            publisher.publish(buf.tobytes(), port=args.zmq_port, host=args.bind)
            frames += 1
            if frames % 50 == 0:
                elapsed = time.monotonic() - t0
                if elapsed > 0:
                    print(f"[thermal-zmq] 约 {frames / elapsed:.1f} Hz")

            sleep_for = interval - (time.monotonic() - loop_start)
            if sleep_for > 0:
                time.sleep(sleep_for)
    finally:
        cam.close()
        publisher.close()
        print("[thermal-zmq] 已停止")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
