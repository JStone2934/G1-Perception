#!/bin/bash
# 在 G1 上启动 RGB 图传服务（需先配置 teleimager/cam_config_server.yaml）
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/teleimager"
exec "$ROOT/activate.sh" teleimager-server "$@"
