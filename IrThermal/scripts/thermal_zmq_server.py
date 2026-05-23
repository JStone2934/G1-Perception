#!/usr/bin/env python3
"""GY-MCU90640 热成像 → ZMQ JPEG 发布（与 teleimager RGB 图传并行，方案 2）。"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap  # noqa: E402, F401

import cv2
import serial

from irthermal import (
    CMD_STOP,
    frame_to_temps,
    open_serial,
    poll_frame,
    temps_to_bgr,
    wake_gy_mcu,
)

try:
    from teleimager.image_client import ZMQ_PublisherManager
except ImportError as exc:
    raise SystemExit(
        "缺少 teleimager，请在 conda env thermal 中执行:\n"
        "  pip install -e \"./teleimager[server]\""
    ) from exc


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="热成像 ZMQ 发布服务（JPEG，兼容 teleimager-client 订阅格式）"
    )
    p.add_argument("--port", default="/dev/ttyUSB0", help="热成像串口")
    p.add_argument("--baud", type=int, default=460800)
    p.add_argument("--init", action="store_true", help="115200 固件：发送初始化命令")
    p.add_argument("--bind", default="0.0.0.0", help="ZMQ 绑定地址")
    p.add_argument("--zmq-port", type=int, default=55556, help="ZMQ 端口（RGB 默认 55555）")
    p.add_argument("--width", type=int, default=640, help="伪彩色输出宽度")
    p.add_argument("--height", type=int, default=480, help="伪彩色输出高度")
    p.add_argument(
        "--fps",
        type=float,
        default=2.0,
        help="发布帧率上限（模块实测约 2Hz）",
    )
    p.add_argument("--jpeg-quality", type=int, default=85, help="JPEG 质量 1-100")
    p.add_argument(
        "--overlay",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="在图像上叠加温度文字",
    )
    return p.parse_args()


def overlay_label(bgr, label: str):
    import numpy as np

    out = bgr.copy()
    cv2.putText(
        out,
        label,
        (10, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
    )
    return out


def main() -> int:
    args = parse_args()
    interval = max(1.0 / max(args.fps, 0.5), 0.05)
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), max(1, min(args.jpeg_quality, 100))]

    try:
        ser = open_serial(args.port, args.baud, use_init=args.init, timeout=2)
    except serial.SerialException as exc:
        print(f"[thermal-zmq] 无法打开 {args.port}: {exc}", file=sys.stderr)
        return 1

    try:
        raw = poll_frame(ser, settle_s=0.12, read_timeout=2.0)
        ta, temps = frame_to_temps(raw)
        print(
            f"[thermal-zmq] 首帧 OK  Ta={ta:.1f}C  "
            f"min={temps.min():.1f}C  max={temps.max():.1f}C"
        )
    except (TimeoutError, ValueError) as exc:
        print(f"[thermal-zmq] 首帧失败: {exc}", file=sys.stderr)
        ser.close()
        return 1

    publisher = ZMQ_PublisherManager.get_instance()
    running = True

    def _stop(*_):
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
    last_wake = time.time()

    try:
        while running:
            loop_start = time.monotonic()
            try:
                raw = poll_frame(ser, settle_s=0.12, read_timeout=1.0)
                ta, temps = frame_to_temps(raw)
            except (TimeoutError, ValueError, serial.SerialException):
                if time.time() - last_wake > 2.0:
                    try:
                        wake_gy_mcu(ser, args.baud)
                        last_wake = time.time()
                    except Exception:
                        pass
                time.sleep(0.15)
                continue

            bgr = temps_to_bgr(temps, args.width, args.height)
            if args.overlay:
                label = (
                    f"Ta={ta:.1f}C  min={temps.min():.1f}C  max={temps.max():.1f}C"
                )
                bgr = overlay_label(bgr, label)

            ok, buf = cv2.imencode(".jpg", bgr, encode_params)
            if not ok:
                print("[thermal-zmq] JPEG 编码失败", file=sys.stderr)
                continue

            publisher.publish(buf.tobytes(), port=args.zmq_port, host=args.bind)
            frames += 1
            if frames % 20 == 0:
                elapsed = time.monotonic() - t0
                if elapsed > 0:
                    print(f"[thermal-zmq] 已发布 {frames} 帧，约 {frames / elapsed:.2f} Hz")

            sleep_for = interval - (time.monotonic() - loop_start)
            if sleep_for > 0:
                time.sleep(sleep_for)
    finally:
        try:
            ser.write(CMD_STOP)
        except Exception:
            pass
        ser.close()
        publisher.close()
        print("[thermal-zmq] 已停止")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
