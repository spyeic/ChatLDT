# 非 Docker 自托管 / Native self-hosting

运行条件：Node 22 构建前端，Python 3.11/3.12 运行同一个 Open WebUI FastAPI 应用。本地 SQLite + 本地附件目录，无远程数据库或推理服务。仅使用一个应用 worker；不将硬件选择限定为固定内存规格。

## Linux / Mac mini 生产运行

```sh
npm ci
npm run setup
npm run check
npm run test:frontend
npm run test:backend
npm run build
```

修改私有 `.env`，使用实际的绝对路径和域名：

```dotenv
ENV=prod
PUBLIC_ORIGIN=https://chat.eurse.me
ALLOWED_ORIGINS=https://chat.eurse.me,https://eurse.me
GOOGLE_REDIRECT_URI=https://chat.eurse.me/oauth/google/callback
DATA_DIR=/srv/chatldt/data
# 默认数据库在 DATA_DIR/webui.db，可不设置 DATABASE_URL。
# 可选固定密钥；未设置时自动写入 DATA_DIR/.webui_secret_key（权限 0600）。
```

本项目当前主地址为 `https://chat.eurse.me`，同时允许 `https://eurse.me` 访问。修改 `.env` 后重启后端，已启动进程不会自动重新读取环境变量。若启动服务时另行设置了同名环境变量，也需同步更新，进程环境优先于 `.env`。Google Cloud OAuth client 的已获授权重定向 URI 应填写 `https://chat.eurse.me/oauth/google/callback`；未配置 Google client/secret 时，邮箱登录不受影响。

macOS 可将 DATA_DIR 设为用户拥有的 Application Support 路径。后台进程应使用专门的非 root 账号，对代码只需读取，对 DATA_DIR 需要读写。备份与运行目录不放进静态 build。公网只开放反向代理，后端绑定 `127.0.0.1:8080`。

```sh
npm start
# 自定义端口（macOS/Linux）
PORT=8081 npm start
```

`npm start` 启动现有包内的 FastAPI/Socket.IO 应用并直接提供 `build`。不启动另一个 Node API 服务。Python wheel 的 frontend 包装路径也支持静态前端，但本地 checkout + npm build/start 是本项目验证的路径。

## HTTPS 反向代理

例如 Caddy（自行安装，配置域名 DNS，证书申请需要网络）：

```caddyfile
chat.eurse.me, eurse.me {
    reverse_proxy 127.0.0.1:8080
}
```

Caddy 自动支持 WebSocket 升级。若用 Nginx，允许至少 **42 MiB** 请求，并转发 WebSocket：

```nginx
server {
    listen 443 ssl;
    server_name chat.eurse.me eurse.me;
    # 在此配置你的有效 TLS 证书与密钥。
    client_max_body_size 42m;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 90s;
    }
}
```

只有来自 localhost 的代理头被信任；不要让未经认证的外部请求直接访问后端。PUBLIC_ORIGIN 为主地址，ALLOWED_ORIGINS 可额外接受多个完整 HTTPS origin；二者用于后端校验，与 Vite allowedHosts 分别配置。生产 Cookie 使用 Secure，直接访问 HTTP 后端无法建立有效生产会话。不要在反向代理缓存 `/api`、`/oauth` 或受保护图片。

## 服务、重启与日志

Linux systemd 示例（按实际用户和路径修改；不要原样套用不存在的路径）：

```ini
[Unit]
Description=ChatLDT Open WebUI
After=network.target

[Service]
User=chatldt
WorkingDirectory=/srv/chatldt/app
Environment=PYTHONPATH=/srv/chatldt/app/backend
ExecStart=/srv/chatldt/app/.venv/bin/python -c "from open_webui import app; app()" serve
Restart=on-failure
UMask=0077

[Install]
WantedBy=multi-user.target
```

本任务没有安装/启用该服务或修改系统配置。管理员可自行执行 `systemctl restart chatldt`；查看 `journalctl -u chatldt`。Mac mini 可用 launchd，以 `.venv/bin/python` 为 ProgramArguments 第一项，设置 WorkingDirectory/PYTHONPATH，使用上述同一入口；不依赖登录 shell 中的 nvm PATH。日志写到管理员指定的私有目录。手动运行时用 Ctrl+C 停止，再 `npm start` 重启。

## Windows / macOS 开发

安装 Node 22、Python 3.12，执行 README 的 `npm ci`、`npm run setup` 和两个开发终端命令即可。脚本选择 Windows `.venv\Scripts\python.exe` 或 POSIX `.venv/bin/python`，使用 Python 的 getpass，不依赖 bash、Docker、Unix-only 激活命令或 Node API 服务。

当前私有 `.env` 使用公网 HTTPS 配置；仅在本机 HTTP 开发时，为后端临时覆盖环境变量（避免本地 HTTP 下的来源错误与 Secure Cookie 问题）：

```sh
PUBLIC_ORIGIN=http://127.0.0.1:5173 ENV=dev \
GOOGLE_REDIRECT_URI=http://127.0.0.1:5173/oauth/google/callback npm run backend:dev
# 另一终端：npm run dev
```

Windows PowerShell 设置测试环境变量的例子：

```powershell
$env:DATA_DIR = 'D:\ChatLDT\data'
npm run setup
```

本次实际执行环境为 macOS。Windows/Linux 命令和配置已按跨平台入口编写，尚未在对应系统运行验证。

## 一致性备份与恢复

先停止 ChatLDT，避免数据库快照与附件复制跨越不同状态；没有把文件系统当作数据库事务的一部分。

```sh
npm run backup -- /secure/backups/chatldt.zip
```

目标不能位于 DATA_DIR，已存在的备份不会被覆盖。使用 SQLite backup API 导出库，并复制附件、数据目录内的服务端密钥和根 `.env`。备份包含隐私数据和凭据，归档权限设置为 0600；由你自行放入受保护/加密存储。没有上传到任何外部服务。

恢复时保持服务器停止，将归档 `data/` 解压到新的私有 DATA_DIR，将 `.env` 恢复到项目根并校正路径。自定义 DATABASE_URL 指向归档数据库的恢复位置，默认使用 `DATA_DIR/webui.db`。不要混用另一份 `.webui_secret_key`。先在副本执行 `npm run db:migrate` 并检查，再切换原实例。

## 升级与迁移

1. 不自动同步上游。先审查目标版本、许可证、依赖与本 Fork 差异。
2. 停机备份代码版本、DATA_DIR、`.env` 和服务配置。
3. 在数据库副本上运行迁移和回归，再安装依赖、检查和构建。
4. 对生产库运行 `npm run db:migrate`，启动并检查 `/health`、登录、附件和 Socket.IO。
5. 回滚使用旧代码 + 一致备份恢复；`ldt001` 明确拒绝自动 downgrade 删除人工聊天数据。

历史迁移链保持原样（迁移环境只去除了对已删除产品运行时模型的导入），因此新库仍会创建旧产品表。它们没有运行时路由，不执行旧功能。当前不会将原有 AI 树状聊天猜测转换成人工轮次；已有旧记录保存在原表中，人工列表只处理 LDT 状态记录。若已有生产聊天，需另外审查其导入策略后再切换，不能依靠 last role 推导轮次。

## 排错

- Node 24 / Python 3.13：使用 Node 22 / Python 3.11–3.12；setup 不绕过基线支持范围。
- CSRF / Origin 403：核对 PUBLIC_ORIGIN、协议、域名与端口；刷新获取新安全令牌；确认代理没有丢失 Cookie/Origin。
- 生产 Cookie 丢失：检查 HTTPS、ENV、SameSite 和代理协议，勿把 Secure 改成不安全来规避。
- Socket 连不上：代理转发 `/ws/socket.io`，保持 WebSocket 升级与足够超时；后端/前端版本应一致；旧身份凭证会被拒绝。
- 图片 413/415：检查原始大小 40 MiB、像素 4000 万、静态 JPEG/PNG/WebP 和代理 42 MiB 上限。
- SQLite 锁/权限错误：检查只有一个 worker、数据目录可写、没有把 SQLite 放到不支持锁语义的网络盘；保留原文件排查，不删除数据库“修复”。
- Google 失败：确认 Cloud OAuth client 类型、回调 URI、同意屏幕测试用户，以及邮箱冲突时的登录后绑定流程。
- 标题未自动生成：检查服务端 API key、模型权限和网络；后备标题不影响人工聊天。最多重试三次，重启不会无限重试。
- 无法迁移的旧管理员/MFA/多管理员数据：先在副本审查，不直接覆盖账号或改角色。
