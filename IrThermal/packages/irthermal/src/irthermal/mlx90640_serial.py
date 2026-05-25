"""GY-MCU90640 串口协议（MicroUSB + CH340 → /dev/ttyUSB*，460800）。"""

from __future__ import annotations

import glob
import time

import numpy as np
import serial

FRAME_SIZE = 1544
HEADER = b"\x5a\x5a"

CMD_START = bytes([0xA5, 0x35, 0x02, 0xDC])
CMD_STOP = bytes([0xA5, 0x35, 0x01, 0xDB])
CMD_4HZ = bytes([0xA5, 0x25, 0x01, 0xCB])


def wake_gy_mcu(ser: serial.Serial, baud: int) -> None:
    """CH340 模块常需 DTR/RTS 翻转后 MCU 才开始发 0x5A5A 帧（460800）。"""
    ser.dtr = False
    ser.rts = False
    time.sleep(0.05)
    ser.dtr = True
    ser.rts = True
    time.sleep(0.25)
    ser.reset_input_buffer()
    if baud == 460800:
        ser.write(CMD_START)
        time.sleep(0.1)
        ser.reset_input_buffer()


def open_serial(
    port: str,
    baud: int = 460800,
    *,
    use_init: bool = False,
    timeout: float = 2,
) -> serial.Serial:
    """打开串口并完成 GY-MCU 唤醒/启动。"""
    ser = serial.Serial(port, baud, timeout=timeout)
    if baud == 460800 and not use_init:
        wake_gy_mcu(ser, baud)
    else:
        time.sleep(0.1)
        ser.reset_input_buffer()
        if use_init or baud == 115200:
            ser.write(CMD_4HZ)
            time.sleep(0.05)
            ser.write(CMD_START)
            time.sleep(0.1)
            ser.reset_input_buffer()
    return ser


def extract_latest_frame(buf: bytearray) -> tuple[bytes | None, int]:
    """从缓冲区取最后一帧完整数据，返回 (帧字节, 消费到的结束下标)。"""
    last = -1
    start = 0
    while True:
        pos = buf.find(HEADER, start)
        if pos < 0:
            break
        last = pos
        start = pos + 1
    if last < 0 or len(buf) < last + FRAME_SIZE:
        return None, 0
    return bytes(buf[last : last + FRAME_SIZE]), last + FRAME_SIZE


def poll_frame(
    ser: serial.Serial,
    settle_s: float = 0.1,
    *,
    read_timeout: float | None = None,
) -> bytes:
    """请求并读取一帧（本机 GY-MCU 需每帧发 START，非连续流）。"""
    old_timeout = ser.timeout
    if read_timeout is not None:
        ser.timeout = read_timeout
    elif not old_timeout:
        # timeout=0 时 sync_frame 会在 settle 后立即失败，须临时设阻塞读超时
        ser.timeout = 1.0
    try:
        ser.reset_input_buffer()
        ser.write(CMD_START)
        time.sleep(settle_s)
        return sync_frame(ser)
    finally:
        ser.timeout = old_timeout


def drain_latest_frame(ser: serial.Serial, buf: bytearray, wait_s: float = 0.05) -> bytes | None:
    """非阻塞收串口数据，返回缓冲区中最新一帧（适合实时预览）。"""
    deadline = time.time() + wait_s
    while time.time() < deadline:
        n = ser.in_waiting
        if n:
            buf.extend(ser.read(n))
        else:
            time.sleep(0.002)
    if len(buf) > 65536:
        del buf[:-32768]
    raw, end = extract_latest_frame(buf)
    if raw is not None and end > 0:
        del buf[:end]
    return raw


def sync_frame(ser: serial.Serial) -> bytes:
    """读取一帧 1544 字节，帧头 0x5A5A。"""
    buf = bytearray()
    while True:
        chunk = ser.read(256)
        if not chunk:
            raise TimeoutError("串口超时，未收到数据")
        buf.extend(chunk)
        pos = buf.find(HEADER)
        if pos >= 0:
            if len(buf) < pos + FRAME_SIZE:
                rest = ser.read(pos + FRAME_SIZE - len(buf))
                if len(rest) < pos + FRAME_SIZE - len(buf):
                    raise TimeoutError("帧数据不完整")
                buf.extend(rest)
            return bytes(buf[pos : pos + FRAME_SIZE])
        if len(buf) > 4096:
            buf.clear()


def frame_to_temps(raw: bytes) -> tuple[float, np.ndarray]:
    if len(raw) != FRAME_SIZE or raw[:2] != HEADER:
        raise ValueError("无效帧")
    ta = (raw[1540] + raw[1541] * 256) / 100.0
    arr = np.frombuffer(raw[4:1540], dtype=np.int16).reshape(24, 32) / 100.0
    return ta, arr


def probe_ports() -> None:
    for path in sorted(glob.glob("/dev/ttyUSB*")):
        print(f"\n{path}:")
        for baud in (460800, 115200):
            try:
                ser = serial.Serial(path, baud, timeout=0.8)
                if baud == 460800:
                    wake_gy_mcu(ser, baud)
                else:
                    time.sleep(0.15)
                    ser.reset_input_buffer()
                chunk = ser.read(200)
                ser.close()
                tag = "GY-MCU90640?" if chunk[:2] == HEADER else "—"
                print(f"  {baud}: len={len(chunk)} head={chunk[:4].hex() if chunk else 'empty'}  {tag}")
            except Exception as e:
                print(f"  {baud}: {e}")


def find_port(hint: str | None = None) -> str:
    if hint:
        return hint
    for path in sorted(glob.glob("/dev/ttyUSB*")) + sorted(glob.glob("/dev/ttyACM*")):
        for baud in (460800, 115200):
            try:
                ser = serial.Serial(path, baud, timeout=0.8)
                if baud == 460800:
                    wake_gy_mcu(ser, baud)
                else:
                    time.sleep(0.15)
                    ser.reset_input_buffer()
                chunk = ser.read(64)
                ser.close()
                if chunk[:2] == HEADER:
                    return path
            except OSError:
                continue
    return "/dev/ttyUSB0"
