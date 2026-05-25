#!/bin/bash
# 激活 conda 环境 thermal（monorepo 根目录），或回退 .venv
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/IrThermal/packages/irthermal/src${PYTHONPATH:+:$PYTHONPATH}"
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
echo "请先创建环境: conda env create -f environment.yml" >&2
exit 1
