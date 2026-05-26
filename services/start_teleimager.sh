#!/bin/bash
# 在 G1 上启动 RGB 图传服务（conda: teleimager，需先配置 cam_config_server.yaml）
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/teleimager"
export CONDA_ENV_NAME="${CONDA_ENV_NAME:-teleimager}"
exec "$ROOT/activate.sh" teleimager-server --rs "$@"
