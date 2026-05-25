#!/bin/bash
# 在 IrThermal 子目录内运行脚本：激活 conda thermal，并加入本包源码路径
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/packages/irthermal/src${PYTHONPATH:+:$PYTHONPATH}"
if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
  # shellcheck source=/dev/null
  source "$HOME/miniconda3/etc/profile.d/conda.sh"
  if conda env list | grep -qE '^thermal\s'; then
    conda activate thermal
    exec "$@"
  fi
fi
if [ -f .venv/bin/activate ]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
  exec "$@"
fi
echo "请先: conda activate thermal  （或 conda env create -f ../environment.yml）" >&2
exit 1
