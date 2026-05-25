#!/usr/bin/env bash
# =============================================================================
# RealSense RGB + teleimager 一键修复脚本
# （robot-perception 副本，conda 环境：thermal）
#
# 典型问题：
#   - /dev/video4 busy（videohub_pc4 占用，仅 stop wlr-video-hub 无效）
#   - video_id 指到深度/红外节点，画面非真彩色
#   - YUYV 原始缓冲未正确转 BGR
#
# 用法：
#   ./fix_realsense_rgb_teleimager.sh              # 释放摄像头 + 检测 + 启动 teleimager-server
#   ./fix_realsense_rgb_teleimager.sh --check      # 仅检测，不停止服务、不启动 server
#   ./fix_realsense_rgb_teleimager.sh --fix-only   # 释放 + 检测，不启动 server
#   ./fix_realsense_rgb_teleimager.sh --restore    # 恢复 videohub_pc4 / wlr-video-hub
#   ./fix_realsense_rgb_teleimager.sh --reinstall  # 额外 pip install -e ".[server]"
#
# 详见：REALSENSE_RGB_OPENCV_TROUBLESHOOTING.md
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MSCLI="/unitree/sbin/mscli"
VIDEOHUB_SVC="video_hub_pc4"
WLR_SVC="wlr-video-hub.service"

CONDA_BASE="${CONDA_BASE:-$HOME/miniconda3}"
CONDA_ENV="${CONDA_ENV_NAME:-thermal}"
TELEIMAGER_BIN="${TELEIMAGER_BIN:-$CONDA_BASE/envs/$CONDA_ENV/bin/teleimager-server}"

DO_CHECK=0
DO_FIX=1
DO_START=1
DO_RESTORE=0
DO_REINSTALL=0
STOP_WLR=1

usage() {
    sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
    echo ""
    echo "选项:"
    echo "  --check       仅检测 RGB 节点与占用情况"
    echo "  --fix-only    释放摄像头并检测，不启动 teleimager-server"
    echo "  --restore     恢复 Unitree 默认头摄服务"
    echo "  --reinstall   修复前执行 pip install -e \".[server]\""
    echo "  --no-stop-wlr 不停止 wlr-video-hub.service"
    echo "  -h, --help    显示帮助"
    echo ""
    echo "环境: conda activate ${CONDA_ENV}  （可通过 CONDA_ENV_NAME 覆盖）"
}

log()  { echo "[$(date '+%H:%M:%S')] $*"; }
warn() { echo "[$(date '+%H:%M:%S')] WARNING: $*" >&2; }
die()  { echo "[$(date '+%H:%M:%S')] ERROR: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --check)      DO_CHECK=1; DO_FIX=0; DO_START=0 ;;
        --fix-only)   DO_START=0 ;;
        --restore)    DO_RESTORE=1; DO_FIX=0; DO_START=0 ;;
        --reinstall)  DO_REINSTALL=1 ;;
        --no-stop-wlr) STOP_WLR=0 ;;
        -h|--help)    usage; exit 0 ;;
        *) die "未知参数: $1（使用 --help）" ;;
    esac
    shift
done

# --- V4L2 helpers（与 image_server.py 逻辑一致）---
v4l2_is_rgb_node() {
    local dev="$1"
    command -v v4l2-ctl >/dev/null 2>&1 || die "未安装 v4l2-ctl，请执行: sudo apt install v4l-utils"
    [[ -e "$dev" ]] || return 1
    v4l2-ctl -d "$dev" --list-formats-ext 2>/dev/null | grep -qE "YUYV|YUY2" || return 1
    v4l2-ctl -d "$dev" --list-ctrls 2>/dev/null | grep -qi "saturation" || return 1
    v4l2-ctl -d "$dev" --list-formats-ext 2>/dev/null | grep -q "Type: Video Capture" || return 1
    return 0
}

v4l2_can_stream() {
    local dev="$1"
    local out
    out="$(v4l2-ctl -d "$dev" \
        --set-fmt-video=width=640,height=480,pixelformat=YUYV \
        --stream-mmap=3 --stream-count=1 2>&1)" || true
    if echo "$out" | grep -qE "VIDIOC_STREAMON returned -1|Device or resource busy|Input/output error"; then
        return 1
    fi
    return 0
}

find_rgb_devices() {
    local dev
    for dev in /dev/video*; do
        [[ -e "$dev" ]] || continue
        if v4l2_is_rgb_node "$dev"; then
            echo "$dev"
        fi
    done
}

videohub_running() {
    pgrep -x videohub_pc4 >/dev/null 2>&1
}

stop_unitree_camera_services() {
    if [[ -x "$MSCLI" ]]; then
        log "停止 $VIDEOHUB_SVC (mscli)..."
        if "$MSCLI" stopservice "$VIDEOHUB_SVC" 2>/dev/null; then
            :
        else
            warn "mscli stopservice 返回非 0，继续检查进程..."
        fi
        sleep 1
    else
        warn "未找到 $MSCLI，跳过 mscli stopservice"
    fi

    if videohub_running; then
        warn "videohub_pc4 仍在运行。"
        if [[ "$(id -u)" -eq 0 ]]; then
            pkill -x videohub_pc4 || true
            sleep 1
        else
            die "请手动结束: sudo pkill -x videohub_pc4  或  $MSCLI stopservice $VIDEOHUB_SVC"
        fi
    fi

    if [[ "$STOP_WLR" -eq 1 ]] && systemctl is-active --quiet "$WLR_SVC" 2>/dev/null; then
        log "停止 $WLR_SVC ..."
        if sudo -n systemctl stop "$WLR_SVC" 2>/dev/null; then
            :
        elif sudo systemctl stop "$WLR_SVC"; then
            :
        else
            warn "无法停止 $WLR_SVC（可忽略，若仅 videohub 占用设备）"
        fi
        sleep 1
    fi
}

restore_unitree_camera_services() {
    if [[ -x "$MSCLI" ]]; then
        log "启动 $VIDEOHUB_SVC ..."
        "$MSCLI" startservice "$VIDEOHUB_SVC" || warn "mscli startservice 失败"
    fi
    if systemctl list-unit-files "$WLR_SVC" &>/dev/null; then
        log "启动 $WLR_SVC ..."
        sudo systemctl start "$WLR_SVC" 2>/dev/null || warn "启动 $WLR_SVC 需要 sudo"
    fi
    log "头摄服务已尝试恢复。"
}

ensure_teleimager_installed() {
    if [[ ! -x "$TELEIMAGER_BIN" ]]; then
        die "未找到 $TELEIMAGER_BIN，请先: conda create -n ${CONDA_ENV} python=3.11 && pip install -e \"$SCRIPT_DIR[server]\""
    fi
}

reinstall_teleimager() {
    local pip_bin="$CONDA_BASE/envs/$CONDA_ENV/bin/pip"
    [[ -x "$pip_bin" ]] || die "未找到 $pip_bin"
    log "重新安装 teleimager (editable)..."
    "$pip_bin" install -e "$SCRIPT_DIR[server]"
}

run_camera_find() {
    log "运行 teleimager-server --cf ..."
    "$TELEIMAGER_BIN" --cf
}

verify_rgb_devices() {
    local -a rgb_devs=()
    local dev ok=0 any=0

    mapfile -t rgb_devs < <(find_rgb_devices)

    if [[ ${#rgb_devs[@]} -eq 0 ]]; then
        die "未发现 V4L2 RGB 节点（需 YUYV + saturation）。请检查 RealSense 连接与 uvc 绑定，见 REALSENSE_RGB_OPENCV_TROUBLESHOOTING.md"
    fi

    log "发现 RGB 节点: ${rgb_devs[*]}"

    for dev in "${rgb_devs[@]}"; do
        any=1
        if v4l2_can_stream "$dev"; then
            log "  $dev : stream_test=OK"
            ok=1
        else
            warn "  $dev : stream_test=BUSY/FAILED"
            if videohub_running; then
                warn "    -> videohub_pc4 仍在运行，请执行: $MSCLI stopservice $VIDEOHUB_SVC"
            fi
        fi
    done

    [[ "$any" -eq 1 ]] || die "检测失败"
    [[ "$ok" -eq 1 ]] || return 1
    return 0
}

print_webrtc_hint() {
    local ip
    ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
    [[ -n "$ip" ]] || ip="<机器人IP>"
    log "WebRTC 预览: https://${ip}:60001  （接受自签名证书后点击 Start）"
    log "ZMQ 端口见 cam_config_server.yaml（默认 55555）"
}

start_teleimager_server() {
    log "启动 teleimager-server（Ctrl+C 退出）..."
    print_webrtc_hint
    cd "$SCRIPT_DIR"
    exec "$TELEIMAGER_BIN"
}

# --- main ---
if [[ "$DO_RESTORE" -eq 1 ]]; then
    restore_unitree_camera_services
    exit 0
fi

ensure_teleimager_installed

if [[ "$DO_REINSTALL" -eq 1 ]]; then
    reinstall_teleimager
fi

log "======== RealSense RGB / teleimager 一键修复 (conda: ${CONDA_ENV}) ========"

if [[ "$DO_CHECK" -eq 1 ]]; then
    log "模式: 仅检测"
    videohub_running && warn "videohub_pc4 正在运行（会占用 RGB 设备）"
    verify_rgb_devices || die "检测未通过"
    run_camera_find
    exit 0
fi

if [[ "$DO_FIX" -eq 1 ]]; then
    stop_unitree_camera_services
    sleep 1
fi

if ! verify_rgb_devices; then
    die "RGB 设备仍不可用。详见 $SCRIPT_DIR/REALSENSE_RGB_OPENCV_TROUBLESHOOTING.md"
fi

run_camera_find

if [[ "$DO_START" -eq 1 ]]; then
    start_teleimager_server
else
    log "修复完成。手动启动: $TELEIMAGER_BIN"
    print_webrtc_hint
    log "恢复头摄: $0 --restore"
fi
