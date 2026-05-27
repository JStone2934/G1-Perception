# AC010_256 SDK 运行时库（厂商预编译）

本目录为 **IrThermal 内置** 的 Tiny1C USB 驱动依赖，来源：

- 包：`AC010_256_SDK_V2.0.2`（`SINGLE_USB/libs/linux/`）
- 厂商：AC010 / libiruvc + libirparse 等

## 包含架构

| 子目录 | 用途 |
|--------|------|
| `linux/aarch64-linux-gnu_libs/` | Unitree G1（Jetson aarch64） |
| `linux/x86-linux_libs/` | PC 开发机调试 |

运行时由 `irthermal.tiny1c` 通过 ctypes 加载，**无需**在仓库外解压 SDK。

## 覆盖路径（可选）

仅当使用自定义库目录时设置：

```bash
export IRTHERMAL_AC010_SDK=/path/to/libs/linux/aarch64-linux-gnu_libs
```
