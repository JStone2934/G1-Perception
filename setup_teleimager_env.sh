#!/usr/bin/env bash
# 在 conda 环境 teleimager 中配置 robot-perception（须用环境内 python -m pip）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

CONDA_BASE="${CONDA_BASE:-$HOME/miniconda3}"
ENV_PY="${CONDA_BASE}/envs/teleimager/bin/python"

if [[ ! -x "$ENV_PY" ]]; then
  echo "未找到 conda 环境 teleimager，请先: conda create -n teleimager python=3.11 -y" >&2
  exit 1
fi

echo "==> 使用: $ENV_PY ($("$ENV_PY" --version))"
echo "==> 安装 irthermal + teleimager[server] ..."
"$ENV_PY" -m pip install -U pip
"$ENV_PY" -m pip install -e "./IrThermal/packages/irthermal[gui,i2c]" -e "./teleimager[server]"

echo "==> 验证导入 ..."
"$ENV_PY" -c "
import irthermal
import teleimager.image_server as srv
print('irthermal:', irthermal.__file__)
print('teleimager:', srv.__file__)
"

echo "==> verify_setup ..."
"$ENV_PY" IrThermal/scripts/verify_setup.py

if ! "$ENV_PY" -c "import pyrealsense2" 2>/dev/null; then
  echo ""
  echo "[!!] pyrealsense2 未安装（depth_camera 需 teleimager-server --rs）"
  echo "     aarch64 无 pip wheel，需从源码编译 Python 绑定，例如:"
  echo "     cd ~/workspace/unitree_g1_vibes/librealsense/build"
  echo "     cmake .. -DBUILD_PYTHON_BINDINGS=ON -DPYTHON_EXECUTABLE=$ENV_PY"
  echo "     make -j\$(nproc) && sudo make install"
fi

echo ""
echo "完成。启动图传:"
echo "  conda activate teleimager"
echo "  export PATH=\"\$CONDA_PREFIX/bin:\$PATH\""
echo "  teleimager-server --rs    # RGB + 深度 + 热成像"
echo "  # 或仅 RGB+热成像（无深度 SDK）: teleimager-server"
