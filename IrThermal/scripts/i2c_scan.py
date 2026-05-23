#!/usr/bin/env python3
"""扫描 /dev/i2c-* 总线，查找 MLX90640（默认地址 0x33）。"""

from __future__ import annotations

import argparse
import glob
import struct
import sys

MLX90640_ADDR = 0x33


def scan_bus(bus: int) -> list[int]:
    path = f"/dev/i2c-{bus}"
    found: list[int] = []
    try:
        with open(path, "rb+", buffering=0) as dev:
            for addr in range(0x03, 0x78):
                try:
                    # I2C_SLAVE + 读 1 字节
                    import fcntl

                    fcntl.ioctl(dev, 0x0703, addr)  # I2C_SLAVE
                    dev.read(1)
                    found.append(addr)
                except OSError:
                    pass
    except OSError as e:
        print(f"  i2c-{bus}: 无法打开 ({e})")
    return found


def probe_mlx90640(bus: int, addr: int = MLX90640_ADDR) -> bool:
    """尝试读取 MLX90640 控制寄存器 0x800D（设备 ID 相关）。"""
    path = f"/dev/i2c-{bus}"
    try:
        import fcntl

        I2C_SLAVE = 0x0703
        I2C_SMBUS = 0x0720
        I2C_SMBUS_READ = 2

        with open(path, "rb+", buffering=0) as dev:
            fcntl.ioctl(dev, I2C_SLAVE, addr)
            # SMBus read word: reg 0x240E (status) 简化探测 — 写寄存器地址后读
            reg = 0x800D
            write_buf = struct.pack(">H", reg)
            fcntl.ioctl(dev, I2C_SLAVE, addr)
            dev.write(write_buf)
            data = dev.read(2)
            return len(data) == 2
    except OSError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="I2C 总线扫描（查找 MLX90640 @ 0x33）")
    parser.add_argument("--bus", type=int, default=None, help="只扫描指定总线编号")
    args = parser.parse_args()

    buses = [args.bus] if args.bus is not None else sorted(
        int(p.split("i2c-")[-1]) for p in glob.glob("/dev/i2c-*")
    )

    mlx_buses: list[int] = []
    print("扫描 I2C 总线…")
    for bus in buses:
        addrs = scan_bus(bus)
        if not addrs:
            continue
        hex_addrs = ", ".join(f"0x{a:02X}" for a in addrs)
        mark = "  <-- MLX90640?" if MLX90640_ADDR in addrs else ""
        print(f"  i2c-{bus}: [{hex_addrs}]{mark}")
        if MLX90640_ADDR in addrs:
            mlx_buses.append(bus)

    if mlx_buses:
        print(
            f"\n在 i2c-{mlx_buses[0]} 上发现地址 0x33，可用: "
            f"python IrThermal/scripts/thermal_view.py --bus {mlx_buses[0]}"
        )
        return 0

    print("\n未发现 0x33。请检查接线、供电，以及当前用户是否有 /dev/i2c-* 访问权限。")
    print("若需安装 i2c-tools 或加入 i2c 用户组，需要 sudo 密码 — 请告知后再执行。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
