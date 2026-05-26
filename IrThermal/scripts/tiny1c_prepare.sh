#!/usr/bin/env bash
# Tiny1C：解绑 uvcvideo、设置 USB 权限（需 sudo）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/packages/irthermal/src${PYTHONPATH:+:$PYTHONPATH}"

if [[ "${EUID}" -ne 0 ]]; then
  exec sudo -E bash "$0" "$@"
fi

python3 -c "
from irthermal.usb_setup import detach_uvc_driver, ensure_usb_permissions, find_usb_device_path
import os, sys
unbound = detach_uvc_driver()
path = ensure_usb_permissions()
print('解绑 uvc 接口:', unbound or '(无)')
print('USB 设备:', path or find_usb_device_path() or '(未找到 0bda:5840)')
if path and not os.access(path, os.R_OK | os.W_OK):
    print('警告: 仍无 USB 读写权限，请安装 udev 规则', file=sys.stderr)
    print('  sudo cp \"${ROOT}/udev/99-tiny1c-thermal.rules\" /etc/udev/rules.d/', file=sys.stderr)
    print('  sudo udevadm control --reload && sudo udevadm trigger', file=sys.stderr)
"

echo "完成。可运行: python ${ROOT}/scripts/thermal_view_tiny1c.py"
