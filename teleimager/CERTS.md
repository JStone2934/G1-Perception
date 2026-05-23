# TLS 证书说明

本目录下的 `cert.pem` / `key.pem` 为**符号链接**，指向原图传目录中的文件：

- `JS_test/thermal/teleimager/cert.pem`
- `JS_test/thermal/teleimager/key.pem`

运行时 **优先** 使用 `~/.config/xr_teleoperate/` 中的证书（若存在），与 `image_server.py` 逻辑一致。  
请勿在 monorepo 内重新生成或覆盖证书；新证书请仍放在 `~/.config/xr_teleoperate/` 或原 `teleimager/` 目录。
