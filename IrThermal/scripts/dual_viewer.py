#!/usr/bin/env python3
"""双窗口实时预览：Tiny1C 热成像 + USB 摄像头（供远程桌面查看）。"""

from __future__ import annotations

import argparse
import glob
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap  # noqa: E402, F401

import cv2
import numpy as np
from irthermal import Tiny1CCamera

THERMAL_WIN = "Tiny1C Thermal"
CAMERA_WIN = "Camera"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="热成像 + 摄像头双窗口预览")
    p.add_argument("--warmup", type=float, default=3.0, help="Tiny1C 开流预热秒数")
    p.add_argument("--camera", type=int, default=None, help="摄像头索引（对应 /dev/videoN）")
    p.add_argument(
        "--device",
        default=None,
        help="直接指定设备路径，例如 /dev/video2（优先于 --camera）",
    )
    p.add_argument(
        "--list-cameras",
        action="store_true",
        help="列出可读帧的 V4L2 设备后退出",
    )
    p.add_argument("--thermal-size", default="640,480", help="热图窗口显示尺寸 W,H")
    p.add_argument(
        "--thermal-hz",
        type=float,
        default=15.0,
        help="热图显示刷新上限（Hz）",
    )
    p.add_argument(
        "--display",
        choices=("matplotlib", "opencv"),
        default="matplotlib",
        help="显示后端（默认 matplotlib，避免 opencv-python-headless 无窗口）",
    )
    return p.parse_args()


def cv2_has_gui() -> bool:
    try:
        cv2.namedWindow("__gui_test__", cv2.WINDOW_NORMAL)
        cv2.destroyWindow("__gui_test__")
        return True
    except cv2.error:
        return False


def bgr_to_rgb(bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _v4l2_formats(device: str) -> str:
    try:
        return subprocess.run(
            ["v4l2-ctl", "-d", device, "--list-formats-ext"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        ).stdout
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return ""


def _preferred_fourcc(formats: str) -> str | None:
    if "'UYVY'" in formats:
        return "UYVY"
    if "'YUYV'" in formats or "'YUY2'" in formats:
        return "YUYV"
    if "'MJPG'" in formats or "'MJPEG'" in formats:
        return "MJPG"
    return None


def v4l2_stream_kind(device: str) -> tuple[str, bool]:
    """返回 (描述, 是否适合作为 RGB 彩色预览)。跳过 RealSense 深度/红外节点。"""
    out = _v4l2_formats(device)
    if not out:
        return "未知(无 v4l2-ctl)", True

    if not out.strip():
        return "无格式", False
    if re.search(r"'Z16\s*'", out) or "16-bit Depth" in out:
        return "深度 Z16（非 RGB）", False
    has_color = bool(
        re.search(r"'MJPG'|'MJPEG'|'YUYV'|'UYVY'|'RGB3'|'BGR3'|'NV12'", out)
    )
    has_grey = bool(re.search(r"'GREY'|'Y8\s*'|'Y16\s*'", out) or "Greyscale" in out)
    if has_color and has_grey:
        return "RealSense 彩色+红外(需 UYVY fourcc)", True
    if has_grey:
        return "红外/灰度（非 RGB）", False
    if has_color:
        return "彩色 UVC", True
    return "其它/元数据节点", False


def _can_read(cap: cv2.VideoCapture) -> tuple[bool, int, int, np.ndarray | None]:
    ok, frame = cap.read()
    if not ok or frame is None or frame.size == 0:
        return False, 0, 0, None
    h, w = frame.shape[:2]
    return True, w, h, frame


def _device_path(path_or_index: str | int) -> str:
    if isinstance(path_or_index, str):
        return path_or_index
    return f"/dev/video{path_or_index}"


def _try_open(path_or_index: str | int, *, allow_non_rgb: bool = False) -> cv2.VideoCapture | None:
    dev = _device_path(path_or_index)
    kind, is_rgb = v4l2_stream_kind(dev)
    if not is_rgb and not allow_non_rgb:
        print(f"[camera] 跳过 {dev}（{kind}）", file=sys.stderr)
        return None

    cap = cv2.VideoCapture(path_or_index, cv2.CAP_V4L2)
    if not cap.isOpened():
        cap.release()
        return None

    fmt = _v4l2_formats(dev)
    fourcc = _preferred_fourcc(fmt)
    if fourcc:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
        cap.set(cv2.CAP_PROP_CONVERT_RGB, 1)

    ok, w, h, frame = _can_read(cap)
    if not ok:
        cap.release()
        return None
    if frame is not None and frame.ndim == 2 and not allow_non_rgb:
        cap.release()
        print(f"[camera] 跳过 {dev}（单通道灰度，疑似红外）", file=sys.stderr)
        return None

    label = dev if isinstance(path_or_index, str) else f"index {path_or_index}"
    print(f"[camera] 使用 {label} ({w}x{h}) [{kind}]")
    return cap


def list_cameras() -> int:
    print("V4L2 设备（robot 头部 RGB 一般为独立 USB 相机，非 RealSense 深度/红外）：")
    any_rgb = False
    for path in sorted(glob.glob("/dev/video*")):
        kind, is_rgb = v4l2_stream_kind(path)
        cap = _try_open(path, allow_non_rgb=True) if is_rgb else None
        if is_rgb:
            if cap is not None:
                any_rgb = True
                cap.release()
                print(f"  {path}: {kind} — 可读彩色帧")
            else:
                print(f"  {path}: {kind} — 未能读帧")
        else:
            print(f"  {path}: {kind} — 跳过")
    if not any_rgb:
        print(
            "\n当前未发现 RGB UVC 相机。"
            "请连接 G1 头部 USB 彩色相机后重试，或运行: teleimager-server --cf"
        )
        return 1
    return 0


def open_camera(device: str | None, index: int | None) -> cv2.VideoCapture | None:
    if device:
        cap = _try_open(device)
        if cap is not None:
            return cap
        kind, _ = v4l2_stream_kind(device)
        print(f"[camera] 无法打开 {device}（{kind}）", file=sys.stderr)

    if index is not None:
        path = f"/dev/video{index}"
        for candidate in (path, index):
            cap = _try_open(candidate)
            if cap is not None:
                return cap
        print(
            f"[camera] 无法打开索引 {index}（非 RGB 或未接设备）",
            file=sys.stderr,
        )
        print("[camera] 尝试自动探测 RGB 设备…", file=sys.stderr)

    for path in sorted(glob.glob("/dev/video*")):
        cap = _try_open(path)
        if cap is not None:
            return cap
    for idx in range(8):
        cap = _try_open(idx)
        if cap is not None:
            return cap
    return None


class ThermalState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.bgr: np.ndarray | None = None
        self.label = "等待热图…"
        self.seq = 0
        self.stale_since = time.time()


def thermal_reader(
    cam: Tiny1CCamera,
    state: ThermalState,
    tw: int,
    th: int,
    stop: threading.Event,
    poll_interval: float,
) -> None:
    while not stop.is_set():
        try:
            bgr, label = cam.read_bgr(tw, th)
            if label:
                label = f"#{state.seq + 1}  {label}"
        except (TimeoutError, RuntimeError):
            time.sleep(0.1)
            continue
        with state.lock:
            state.bgr = bgr
            state.label = label or state.label
            state.seq += 1
            state.stale_since = time.time()
        time.sleep(max(poll_interval, 0.02))


def run_matplotlib_loop(
    cap: cv2.VideoCapture,
    state: ThermalState,
    stop: threading.Event,
    tw: int,
    th: int,
    frame_interval: float,
    poll_interval: float,
) -> None:
    import matplotlib.pyplot as plt

    placeholder = np.zeros((th, tw, 3), dtype=np.uint8)
    fig, (ax_th, ax_cam) = plt.subplots(1, 2, figsize=(14, 6))
    try:
        fig.canvas.manager.set_window_title("robot-perception dual_viewer")
    except AttributeError:
        pass

    with state.lock:
        th0 = state.bgr if state.bgr is not None else placeholder
        lab0 = state.label
    im_th = ax_th.imshow(bgr_to_rgb(th0))
    ax_th.set_title(f"Thermal — {lab0}")
    ax_th.axis("off")

    ok0, cam0 = cap.read()
    if not ok0 or cam0 is None:
        cam0 = np.zeros((480, 640, 3), dtype=np.uint8)
    im_cam = ax_cam.imshow(bgr_to_rgb(cam0))
    ax_cam.set_title("Camera")
    ax_cam.axis("off")

    print(f"[thermal] Tiny1C（约 {1/poll_interval:.1f} Hz）")
    print("[hint] 关闭 matplotlib 窗口退出")

    last_thermal_draw = 0.0
    try:
        while plt.fignum_exists(fig.number):
            ok, cam_frame = cap.read()
            if ok and cam_frame is not None:
                im_cam.set_data(bgr_to_rgb(cam_frame))
            now = time.time()
            if now - last_thermal_draw >= frame_interval:
                with state.lock:
                    thermal_bgr = (
                        state.bgr.copy() if state.bgr is not None else placeholder
                    )
                    label = state.label
                im_th.set_data(bgr_to_rgb(thermal_bgr))
                ax_th.set_title(f"Thermal — {label}")
                fig.canvas.draw_idle()
                last_thermal_draw = now
            plt.pause(0.03)
    finally:
        plt.close(fig)


def run_opencv_loop(
    cap: cv2.VideoCapture,
    state: ThermalState,
    stop: threading.Event,
    tw: int,
    th: int,
    frame_interval: float,
    poll_interval: float,
) -> None:
    if not cv2_has_gui():
        print(
            "[camera] OpenCV 无 GUI（多为安装了 opencv-python-headless）。\n"
            "  请改用: python IrThermal/scripts/dual_viewer.py --display matplotlib\n"
            "  或: python -m pip uninstall opencv-python-headless -y",
            file=sys.stderr,
        )
        raise SystemExit(1)

    cv2.namedWindow(THERMAL_WIN, cv2.WINDOW_NORMAL)
    cv2.namedWindow(CAMERA_WIN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(THERMAL_WIN, tw, th)
    cv2.resizeWindow(CAMERA_WIN, 960, 720)

    placeholder = np.zeros((th, tw, 3), dtype=np.uint8)
    print(f"[thermal] Tiny1C（约 {1/poll_interval:.1f} Hz）")
    print("[hint] 焦点在窗口上时按 q 退出")

    last_thermal_draw = 0.0
    while True:
        ok, cam_frame = cap.read()
        if not ok or cam_frame is None:
            cam_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(
                cam_frame,
                "Camera read failed",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                2,
            )

        now = time.time()
        if now - last_thermal_draw >= frame_interval:
            with state.lock:
                thermal_bgr = state.bgr.copy() if state.bgr is not None else placeholder
                label = state.label
            cv2.putText(
                thermal_bgr,
                label,
                (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2,
            )
            cv2.imshow(THERMAL_WIN, thermal_bgr)
            last_thermal_draw = now

        cv2.imshow(CAMERA_WIN, cam_frame)
        key = cv2.waitKey(30) & 0xFF
        if key in (ord("q"), ord("Q"), 27):
            break
    cv2.destroyAllWindows()


def main() -> int:
    args = parse_args()
    try:
        tw, th = (int(x) for x in args.thermal_size.split(","))
    except ValueError:
        print("--thermal-size 格式应为 宽,高 例如 640,480", file=sys.stderr)
        return 1

    if args.list_cameras:
        return list_cameras()

    cap = open_camera(args.device, args.camera)
    if cap is None:
        print(
            "[camera] 未发现 RGB 彩色相机。\n"
            "  RealSense 的 /dev/video0(深度)、/dev/video2(红外) 不是头部 RGB。\n"
            "  请连接 G1 头部 USB 彩色相机，然后:\n"
            "    python IrThermal/scripts/dual_viewer.py --list-cameras\n"
            "    cd teleimager && teleimager-server --cf",
            file=sys.stderr,
        )
        return 1

    cam = Tiny1CCamera(warmup_s=args.warmup)
    try:
        cam.open()
        init_bgr, init_label = cam.read_bgr(tw, th)
    except Exception as e:
        print(f"[thermal] 打开/首帧失败: {e}", file=sys.stderr)
        print("请先: bash IrThermal/scripts/tiny1c_prepare.sh", file=sys.stderr)
        cap.release()
        return 1

    state = ThermalState()
    state.bgr = init_bgr
    state.label = init_label
    state.seq = 1

    stop = threading.Event()
    poll_interval = max(0.02, 1.0 / max(args.thermal_hz, 1.0))
    worker = threading.Thread(
        target=thermal_reader,
        args=(cam, state, tw, th, stop, poll_interval),
        daemon=True,
    )
    worker.start()

    frame_interval = max(1.0 / max(args.thermal_hz, 1.0), 0.02)
    display = args.display
    if display == "opencv" and not cv2_has_gui():
        print("[hint] OpenCV 无窗口，自动改用 matplotlib", file=sys.stderr)
        display = "matplotlib"

    try:
        if display == "matplotlib":
            run_matplotlib_loop(
                cap,
                state,
                stop,
                tw,
                th,
                frame_interval,
                poll_interval,
            )
        else:
            run_opencv_loop(
                cap,
                state,
                stop,
                tw,
                th,
                frame_interval,
                poll_interval,
            )
    finally:
        stop.set()
        worker.join(timeout=1.0)
        cam.close()
        cap.release()

    return 0


if __name__ == "__main__":
    sys.exit(main())
