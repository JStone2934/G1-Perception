# robot-perception 架构

## 目录

```
robot-perception/
├── IrThermal/              # 热成像子项目
│   ├── packages/irthermal/ # 库（串口协议、伪彩色）
│   │   └── src/irthermal/
│   ├── scripts/            # CLI：采集、本地双窗预览
│   ├── docs/
│   └── output/             # 脚本默认输出
├── teleimager/             # RGB 图传（ZMQ / WebRTC）
├── services/               # 启动脚本
└── docs/
```

## 数据流

| 源 | 路径 | 发布方式 |
|----|------|----------|
| USB 相机 | `teleimager` → `head_camera` | ZMQ / WebRTC |
| GY-MCU90640 | `irthermal` → 串口 | `IrThermal/scripts/*`；后续可接入 `teleimager` 的 `thermal_camera` |

## 依赖关系

- `IrThermal/scripts/*` 依赖 `irthermal`（`pip install -e ./IrThermal/packages/irthermal`）
- `teleimager-server` 独立运行，配置见 `teleimager/cam_config_server.yaml`
- 统一环境：**`conda activate thermal`**（`environment.yml` 中 `name: thermal`）

## 与旧目录的关系

| 旧路径 | 说明 |
|--------|------|
| `JS_test/thermal/IrThermal` | 热成像历史仓库；逻辑在 monorepo 的 `IrThermal/` 子目录 |
| `JS_test/thermal/teleimager` | 图传上游副本；monorepo 内以 `robot-perception/teleimager/` 为准 |

更新嵌套 teleimager：在独立 teleimager 仓库开发后 `rsync` 或 `git subtree pull` 到本目录。
