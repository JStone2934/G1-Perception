#!/bin/bash
# G1 上启动热成像 ZMQ 发布（与 teleimager-server 并行运行）
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/activate.sh" python "$ROOT/IrThermal/scripts/thermal_zmq_server.py" "$@"
