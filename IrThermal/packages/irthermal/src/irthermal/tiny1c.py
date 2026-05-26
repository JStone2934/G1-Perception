"""Tiny1C / AC010_256 USB 热成像（libiruvc + libirparse，AC010 SDK V2）。"""

from __future__ import annotations

import ctypes
import os
import platform
import time
from ctypes import (
    CDLL,
    POINTER,
    RTLD_GLOBAL,
    Structure,
    c_char_p,
    c_int,
    c_uint,
    c_uint8,
    c_void_p,
)
from pathlib import Path

import numpy as np

from irthermal.usb_setup import prepare_tiny1c
from irthermal.visualize import temps_to_bgr

TINY1C_VID = 0x0BDA
TINY1C_PID = 0x5840
KEEP_CAM_SIDE_PREVIEW = 1

_DEFAULT_SDK_ROOTS = (
    Path("/home/unitree/JS_test/thermal/AC010_256_SDK/SINGLE_USB"),
    Path(__file__).resolve().parents[5] / "AC010_256_SDK" / "SINGLE_USB",
)


class _DevCfg(Structure):
    _fields_ = [("pid", c_uint), ("vid", c_uint), ("name", c_char_p)]


class _CameraStreamInfo(Structure):
    _fields_ = [
        ("format", c_char_p),
        ("width", c_uint),
        ("height", c_uint),
        ("frame_size", c_uint),
        ("fps", c_uint * 32),
    ]


class _CameraParam(Structure):
    _fields_ = [
        ("dev_cfg", _DevCfg),
        ("format", c_char_p),
        ("width", c_uint),
        ("height", c_uint),
        ("frame_size", c_uint),
        ("fps", c_uint),
        ("timeout_ms_delay", c_uint),
    ]


def _sdk_lib_dir() -> Path:
    env = os.environ.get("IRTHERMAL_AC010_SDK")
    roots = [Path(env)] if env else []
    roots.extend(_DEFAULT_SDK_ROOTS)
    arch = platform.machine()
    sub = {
        "aarch64": "aarch64-linux-gnu_libs",
        "x86_64": "x86-linux_libs",
        "amd64": "x86-linux_libs",
    }.get(arch, "aarch64-linux-gnu_libs")
    for root in roots:
        lib = root / "libs" / "linux" / sub
        if (lib / "libiruvc.so").is_file():
            return lib
    raise FileNotFoundError(
        "未找到 AC010 SDK 库目录。请解压 AC010_256_SDK_V2.0.2.tar.gz 并设置:\n"
        "  export IRTHERMAL_AC010_SDK=/path/to/AC010_256_SDK/SINGLE_USB"
    )


def temp_raw_to_celsius(raw: np.ndarray) -> np.ndarray:
    """Y16 温度帧 → 摄氏度（与 SDK sample temperature.cpp 一致）。"""
    u16 = np.asarray(raw, dtype=np.uint16)
    return u16.astype(np.float32) / 64.0 - 273.15


class Tiny1CCamera:
    """
    Tiny1C USB 热成像相机。

    使用 256×384（图像+温度）复合流，输出 256×192 BGR 与温度矩阵。
    启动前须 prepare_tiny1c()（解绑 uvcvideo、USB 权限）。
    """

    def __init__(
        self,
        *,
        stream_index: int = 1,
        warmup_s: float = 3.0,
        detach_uvc: bool = True,
        overlay: bool = True,
    ) -> None:
        self._stream_index = stream_index
        self._warmup_s = warmup_s
        self._detach_uvc = detach_uvc
        self._overlay = overlay
        self._lib_dir: Path | None = None
        self._iruvc: CDLL | None = None
        self._irparse: CDLL | None = None
        self._param: _CameraParam | None = None
        self._raw_buf: ctypes.Array[c_uint8] | None = None
        self._image_buf: ctypes.Array[c_uint8] | None = None
        self._temp_buf: ctypes.Array[c_uint8] | None = None
        self._half_h = 0
        self._width = 0
        self._opened = False

    @property
    def native_resolution(self) -> tuple[int, int]:
        """(宽, 高) 热图分辨率。"""
        return self._width, self._half_h

    def _load_libs(self) -> None:
        lib_dir = _sdk_lib_dir()
        prev = os.environ.get("LD_LIBRARY_PATH", "")
        os.environ["LD_LIBRARY_PATH"] = f"{lib_dir}:{prev}" if prev else str(lib_dir)

        for name in (
            "libusb-1.0.so.0",
            "libirparse.so",
            "libirprocess.so",
            "libirtemp.so",
            "libiruvc.so",
        ):
            CDLL(str(lib_dir / name), mode=RTLD_GLOBAL)

        self._iruvc = CDLL(str(lib_dir / "libiruvc.so"))
        self._irparse = CDLL(str(lib_dir / "libirparse.so"))
        self._lib_dir = lib_dir
        u, p = self._iruvc, self._irparse

        u.uvc_camera_init.restype = c_int
        u.uvc_camera_list.argtypes = [POINTER(_DevCfg)]
        u.uvc_camera_list.restype = c_int
        u.uvc_camera_info_get.argtypes = [_DevCfg, POINTER(_CameraStreamInfo)]
        u.uvc_camera_info_get.restype = c_int
        u.uvc_camera_open.argtypes = [_DevCfg]
        u.uvc_camera_open.restype = c_int
        u.uvc_camera_stream_start.argtypes = [_CameraParam, c_void_p]
        u.uvc_camera_stream_start.restype = c_int
        u.uvc_frame_get.argtypes = [c_void_p]
        u.uvc_frame_get.restype = c_int
        u.uvc_camera_stream_close.argtypes = [c_int]
        u.uvc_camera_stream_close.restype = c_int
        u.uvc_camera_close.restype = None
        u.uvc_camera_release.restype = None

        p.yuv422_to_rgb.argtypes = [c_void_p, c_int, c_void_p]
        p.yuv422_to_rgb.restype = c_int
        p.rgb_to_bgr.argtypes = [c_void_p, c_int, c_void_p]
        p.rgb_to_bgr.restype = c_int
        p.raw_data_cut.argtypes = [c_void_p, c_int, c_int, c_void_p, c_void_p]
        p.raw_data_cut.restype = c_int

        if hasattr(u, "vdcmd_init"):
            u.vdcmd_init.restype = c_int
            u.vdcmd_init()
        if hasattr(u, "vdcmd_set_polling_wait_time"):
            u.vdcmd_set_polling_wait_time.argtypes = [c_uint]
            u.vdcmd_set_polling_wait_time(10000)

    def open(self) -> None:
        if self._opened:
            return
        prepare_tiny1c(detach_uvc=self._detach_uvc)
        self._load_libs()
        assert self._iruvc is not None

        u = self._iruvc
        if u.uvc_camera_init() < 0:
            raise RuntimeError("uvc_camera_init 失败")

        devs = (_DevCfg * 64)()
        if u.uvc_camera_list(devs) < 0:
            raise RuntimeError("uvc_camera_list 失败")

        idx = -1
        for i in range(64):
            if devs[i].vid == TINY1C_VID and devs[i].pid == TINY1C_PID:
                idx = i
                break
        if idx < 0:
            raise RuntimeError(
                f"未找到 Tiny1C (VID={TINY1C_VID:#06x} PID={TINY1C_PID:#06x})。"
                "请确认 USB 已连接。"
            )

        streams = (_CameraStreamInfo * 32)()
        if u.uvc_camera_info_get(devs[idx], streams) < 0:
            raise RuntimeError("uvc_camera_info_get 失败")

        ri = self._stream_index
        if streams[ri].width == 0:
            raise RuntimeError(f"流索引 {ri} 无效，请检查 stream_index（0=256×192，1=256×384）")

        rst = u.uvc_camera_open(devs[idx])
        if rst < 0:
            raise RuntimeError(
                f"uvc_camera_open 失败 ({rst})。"
                "请执行: sudo IrThermal/scripts/tiny1c_prepare.sh"
            )

        param = _CameraParam()
        param.dev_cfg = devs[idx]
        param.format = streams[ri].format
        param.width = streams[ri].width
        param.height = streams[ri].height
        param.frame_size = param.width * param.height * 2
        param.fps = streams[ri].fps[0]
        param.timeout_ms_delay = 1000

        if u.uvc_camera_stream_start(param, None) < 0:
            u.uvc_camera_close()
            raise RuntimeError("uvc_camera_stream_start 失败")

        self._param = param
        if ri == 1:
            self._half_h = param.height // 2
            self._width = param.width
            ib = self._width * self._half_h * 2
            self._raw_buf = (c_uint8 * param.frame_size)()
            self._image_buf = (c_uint8 * ib)()
            self._temp_buf = (c_uint8 * ib)()
        else:
            self._half_h = param.height
            self._width = param.width
            self._raw_buf = (c_uint8 * param.frame_size)()
            self._image_buf = None
            self._temp_buf = None

        self._discard_frames(int(max(self._warmup_s, 0) * max(param.fps, 1)))
        self._opened = True

    def _discard_frames(self, count: int) -> None:
        assert self._iruvc is not None and self._raw_buf is not None
        for _ in range(count):
            self._iruvc.uvc_frame_get(self._raw_buf)

    def read(self) -> tuple[np.ndarray, np.ndarray, float]:
        """
        读取一帧。

        Returns:
            bgr: (H, W, 3) uint8
            temps: (H, W) float32 摄氏度
            ta: 画面平均温度（近似环境温）
        """
        if not self._opened:
            raise RuntimeError("相机未 open()")
        assert self._iruvc is not None and self._irparse is not None
        assert self._raw_buf is not None and self._param is not None

        u, p = self._iruvc, self._irparse
        for _ in range(80):
            if u.uvc_frame_get(self._raw_buf) < 0:
                time.sleep(0.02)
                continue

            if self._image_buf is not None and self._temp_buf is not None:
                ib = self._width * self._half_h * 2
                p.raw_data_cut(
                    self._raw_buf,
                    ib,
                    ib,
                    self._image_buf,
                    self._temp_buf,
                )
                pix = self._width * self._half_h
                rgb = (c_uint8 * (pix * 3))()
                p.yuv422_to_rgb(self._image_buf, pix, rgb)
                bgr_arr = (c_uint8 * (pix * 3))()
                p.rgb_to_bgr(rgb, pix, bgr_arr)
                bgr = np.frombuffer(bgr_arr, dtype=np.uint8).reshape(
                    self._half_h, self._width, 3
                ).copy()
                temps = temp_raw_to_celsius(
                    np.frombuffer(self._temp_buf, dtype=np.uint16).reshape(
                        self._half_h, self._width
                    )
                )
            else:
                pix = self._width * self._half_h
                rgb = (c_uint8 * (pix * 3))()
                p.yuv422_to_rgb(self._raw_buf, pix, rgb)
                bgr_arr = (c_uint8 * (pix * 3))()
                p.rgb_to_bgr(rgb, pix, bgr_arr)
                bgr = np.frombuffer(bgr_arr, dtype=np.uint8).reshape(
                    self._half_h, self._width, 3
                ).copy()
                temps = np.zeros((self._half_h, self._width), dtype=np.float32)

            if bgr.max() > 0:
                ta = float(np.nanmean(temps))
                return bgr, temps, ta
            time.sleep(0.02)

        raise TimeoutError("Tiny1C 超时：连续帧无有效图像（全黑）")

    def read_bgr(
        self, out_width: int, out_height: int, overlay: bool | None = None
    ) -> tuple[np.ndarray, str]:
        """读取并缩放到目标尺寸，返回 (bgr, 标签字符串)。"""
        bgr, temps, ta = self.read()
        colored = temps_to_bgr(temps, out_width, out_height)
        if overlay if overlay is not None else self._overlay:
            label = (
                f"Ta={ta:.1f}C  min={temps.min():.1f}C  max={temps.max():.1f}C"
            )
            import cv2

            cv2.putText(
                colored,
                label,
                (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2,
            )
        else:
            label = ""
        return colored, label

    def close(self) -> None:
        if not self._opened or self._iruvc is None:
            return
        u = self._iruvc
        try:
            u.uvc_camera_stream_close(KEEP_CAM_SIDE_PREVIEW)
        except Exception:
            pass
        try:
            u.uvc_camera_close()
        except Exception:
            pass
        try:
            u.uvc_camera_release()
        except Exception:
            pass
        self._opened = False
        self._param = None

    def __enter__(self) -> Tiny1CCamera:
        self.open()
        return self

    def __exit__(self, *_) -> None:
        self.close()
