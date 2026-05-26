#!/bin/bash
# 激活 conda 环境 teleimager（优先）或 thermal（monorepo 根目录），或回退 .venv
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/IrThermal/packages/irthermal/src${PYTHONPATH:+:$PYTHONPATH}"
CONDA_ENV_NAME="${CONDA_ENV_NAME:-teleimager}"
if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
  # shellcheck source=/dev/null
  source "$HOME/miniconda3/etc/profile.d/conda.sh"
  if conda env list | grep -qE "^${CONDA_ENV_NAME}[[:space:]]"; then
    conda activate "${CONDA_ENV_NAME}"
    # 避免 ~/.local/bin 中 python3.8 的 pip/teleimager-server 覆盖 conda 环境
    export PATH="${CONDA_PREFIX}/bin:${PATH}"
    exec "$@"
  fi
  if [ "${CONDA_ENV_NAME}" = "teleimager" ] && conda env list | grep -qE '^thermal[[:space:]]'; then
    conda activate thermal
    export PATH="${CONDA_PREFIX}/bin:${PATH}"
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
