"""Tiny1C USB 准备：解除内核 uvcvideo 占用并确保 libusb 可访问。"""

from __future__ import annotations

import glob
import os
import subprocess
from pathlib import Path

TINY1C_VID = 0x0BDA
TINY1C_PID = 0x5840


def _sysfs_tiny1c_nodes() -> list[Path]:
    nodes: list[Path] = []
    for dev in Path("/sys/bus/usb/devices").iterdir():
        vendor = dev / "idVendor"
        product = dev / "idProduct"
        if not vendor.is_file() or not product.is_file():
            continue
        try:
            if int(vendor.read_text().strip(), 16) != TINY1C_VID:
                continue
            if int(product.read_text().strip(), 16) != TINY1C_PID:
                continue
        except ValueError:
            continue
        nodes.append(dev)
    return nodes


def find_usb_device_path() -> Path | None:
    """返回 /dev/bus/usb/BBB/DDD，若不存在则为 None。"""
    for dev in _sysfs_tiny1c_nodes():
        devnum = dev / "devnum"
        busnum = dev / "busnum"
        if not devnum.is_file() or not busnum.is_file():
            continue
        bus = busnum.read_text().strip()
        num = devnum.read_text().strip()
        path = Path(f"/dev/bus/usb/{bus.zfill(3)}/{num.zfill(3)}")
        if path.exists():
            return path
    return None


def detach_uvc_driver() -> list[str]:
    """从 uvcvideo 解绑 Tiny1C 接口；返回已解绑的接口名。"""
    unbound: list[str] = []
    driver = Path("/sys/bus/usb/drivers/uvcvideo")
    if not driver.is_dir():
        return unbound
    for dev in _sysfs_tiny1c_nodes():
        for iface in dev.glob("*:*"):
            name = iface.name
            link = driver / name
            if link.is_symlink():
                try:
                    (driver / "unbind").write_text(name)
                    unbound.append(name)
                except OSError:
                    pass
    return unbound


def ensure_usb_permissions(device_path: Path | None = None) -> Path | None:
    """若当前用户无读写权限，尝试 chmod（需 sudo 或 udev 规则）。"""
    path = device_path or find_usb_device_path()
    if path is None:
        return None
    if os.access(path, os.R_OK | os.W_OK):
        return path
    try:
        subprocess.run(
            ["sudo", "chmod", "666", str(path)],
            check=True,
            capture_output=True,
            timeout=10,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return path if os.access(path, os.R_OK | os.W_OK) else None
    return path if os.access(path, os.R_OK | os.W_OK) else None


def prepare_tiny1c(detach_uvc: bool = True) -> Path | None:
    """
    启动 SDK 前的推荐步骤：
    1. 可选：解绑 uvcvideo（否则 libiruvc 打开设备会失败 IRUVC_DEVICE_OPEN_FAIL）
    2. 确保 USB 节点可读写

    返回 USB 设备路径。
    """
    if detach_uvc:
        detach_uvc_driver()
    return ensure_usb_permissions()


def rebind_uvc_driver() -> None:
    """将 Tiny1C 接口重新交给 uvcvideo（恢复 /dev/video*）。"""
    driver = Path("/sys/bus/usb/drivers/uvcvideo")
    if not driver.is_dir():
        return
    for dev in _sysfs_tiny1c_nodes():
        for iface in sorted(dev.glob("*:*")):
            name = iface.name
            if not (driver / name).exists():
                try:
                    (driver / "bind").write_text(name)
                except OSError:
                    pass
