#!/usr/bin/env python3
"""检查 robot-perception 在 conda env thermal 下是否配置正确。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap  # noqa: E402, F401

IRTHERMAL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MONOREPO = os.path.abspath(os.path.join(IRTHERMAL_ROOT, ".."))
EXPECTED_IRTHERMAL = os.path.join(IRTHERMAL_ROOT, "packages", "irthermal", "src", "irthermal")
EXPECTED_TELEIMAGER = os.path.join(MONOREPO, "teleimager", "src", "teleimager")


def ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def warn(msg: str) -> None:
    print(f"  [!!] {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def main() -> int:
    print(f"Python: {sys.version.split()[0]}  ({sys.executable})")
    print(f"monorepo 根目录: {MONOREPO}")
    print(f"IrThermal 目录: {IRTHERMAL_ROOT}\n")

    errors = 0

    print("1) 目录结构")
    for rel in (
        "IrThermal/packages/irthermal/src/irthermal/mlx90640_serial.py",
        "IrThermal/scripts/capture_serial.py",
        "teleimager/src/teleimager/image_server.py",
        "teleimager/cam_config_server.yaml",
    ):
        path = os.path.join(MONOREPO, rel)
        if os.path.isfile(path):
            ok(rel)
        else:
            fail(f"缺少 {rel}")
            errors += 1

    print("\n2) irthermal 包")
    try:
        import irthermal

        pkg_dir = os.path.dirname(os.path.abspath(irthermal.__file__))
        ok(f"可导入 irthermal → {pkg_dir}")
        if os.path.normpath(pkg_dir) != os.path.normpath(EXPECTED_IRTHERMAL):
            warn(
                f"irthermal 未指向本仓库（期望 {EXPECTED_IRTHERMAL}）\n"
                f"       请执行: pip install -e {IRTHERMAL_ROOT}/packages/irthermal[gui,i2c]"
            )
        from irthermal import find_port, frame_to_temps, temps_to_bgr, HEADER

        ok(f"API 正常 (HEADER={HEADER.hex()})")
    except Exception as e:
        fail(f"irthermal: {e}")
        errors += 1

    print("\n3) teleimager 图传")
    try:
        import teleimager.image_server as srv

        mod = os.path.abspath(srv.__file__)
        ok(f"可导入 teleimager.image_server → {mod}")
        if not mod.startswith(EXPECTED_TELEIMAGER):
            warn(
                f"teleimager 仍指向旧路径\n"
                f"       请执行: pip install -e {MONOREPO}/teleimager[server]"
            )
    except Exception as e:
        fail(f"teleimager: {e}")
        errors += 1

    try:
        import cv2
        import numpy as np
        import serial
        import yaml
        import zmq

        ok("依赖: cv2, numpy, serial, yaml, zmq")
    except ImportError as e:
        warn(f"缺少依赖: {e}（图传服务端需 pip install -e ./teleimager[server]）")

    print("\n4) 入口命令")
    import shutil

    for cmd in ("teleimager-server", "teleimager-client"):
        path = shutil.which(cmd)
        if path:
            ok(f"{cmd} → {path}")
        else:
            warn(f"未找到 {cmd}（需 pip install -e ./teleimager[server]）")

    print()
    if errors:
        print("结论: 存在问题，请按上方 [FAIL] / [!!] 提示修复。")
        return 1
    print("结论: 基本检查通过。若已接硬件，可再运行:")
    print(f"  python {IRTHERMAL_ROOT}/scripts/capture_serial.py --port /dev/ttyUSB0")
    print(f"  cd {MONOREPO}/teleimager && teleimager-server --cf")
    return 0


if __name__ == "__main__":
    sys.exit(main())
