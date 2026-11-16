# ChatLDT

基于你现有的 Open WebUI Fork，在同一个 SvelteKit/FastAPI/SQLite/Socket.IO 应用中提供管理员人工聊天。日常聊天没有模型调用。OpenAI 配置仅用于首条文字消息生成标题，Google 配置仅用于登录；两个服务均不配置也能使用。

产品界面使用 ChatLDT 名称和原创 LDT 聊天气泡图标；依据本次由部署者明确确认的 LICENSE 第 4(i) 条（滚动 30 天内不超过 50 位自然用户）适用例外进行替换。保留法律文件及必要归属，不表示 OpenAI 或 Open WebUI 官方认可。基线为 Open WebUI `0.13.3`、commit `b0e6098e940942281d9c83f3529ea117287a3a22`。没有切换版本或同步上游。

[English](README.en.md) · [审查与状态机](docs/CHATLDT_AUDIT.md) · [清理报告](docs/CHATLDT_CLEANUP.md) · [自托管](docs/SELF_HOSTING.md) · [验证报告](docs/CHATLDT_VERIFICATION.md)

## 开发与初始化

需要 Node **22** 和 Python **3.12 或 3.11**。本 Fork 原有 engines 不支持 Node 24，Python 不支持 3.13；setup 会如实报错，不会声称成功。Windows 可使用官方 Node 安装器和 `py -3.12`；macOS 可用 nvm 和 Python 安装器。

```sh
# 已安装 nvm 时
nvm install 22
nvm use 22
npm ci
npm run setup
```

setup 检查 Node/Python、前端依赖，创建或识别 `.venv`，安装精简后端依赖，首次复制 `.env.example` 为 `.env`（不覆盖已有文件），执行完整迁移链，再隐藏式询问管理员邮箱和密码。密码至少 12 个字符，使用 Argon2id 安全哈希。已有唯一管理员会被识别；重跑不会覆盖密码。若已有多管理员或注册表不一致，setup 停止并说明原因，绝不自动提升公开注册账号。

```sh
# 终端 1（Windows/macOS 相同）
npm run backend:dev
# 终端 2
npm run dev
```

浏览器打开 `http://127.0.0.1:5173`。当前私有 `.env` 已配置主地址 `https://chat.eurse.me`，并允许 `https://eurse.me`；本地 HTTP 开发需使用 `.env.example` 的开发值，或按 [自托管说明](docs/SELF_HOSTING.md) 临时覆盖后端环境变量。`PUBLIC_ORIGIN` 为主地址；其他访问地址填入逗号分隔的 `ALLOWED_ORIGINS`，不再限制只能使用一个域名。后端默认仅绑定 `127.0.0.1:8080`，前端开发代理转发 API、OAuth 与 Socket.IO。

```sh
npm run check
npm run test:frontend
# 开发测试工具（不进入生产依赖）
# macOS/Linux: .venv/bin/python -m pip install pytest==8.4.2 ruff==0.15.18
# Windows: .venv\Scripts\python.exe -m pip install pytest==8.4.2 ruff==0.15.18
npm run test:backend
npm run build
```

## 使用规则

- 游客直接看到欢迎页，第一次发送才填写昵称；取消弹窗保留文字和图片。随机持久 Cookie + 数据库会话识别身份，同名游客互不关联。连续 30 天没有有效访问才过期；页面访问或用户操作续期，后台事件、心跳、重连读取不续期。清除 Cookie 无法找回游客身份。
- 普通用户可立即注册登录，无审批或邮箱验证。当前有效游客会话在登录/注册普通账号时事务迁移；旧凭证撤销。登录 admin 管理账号不会迁走游客数据。
- 同一聊天只能轮流发送，每条可含文字和最多 8 张图片。不同聊天独立。管理员只能为注册用户主动发起，不能为游客主动创建空聊天。
- 未被回复、未取消的最后一条己方消息只能改文字。图片顺序和内容不可变。仅文字编辑不改变轮次版本，也不使对方草稿失效。
- 用户等待管理员时显示“思考中...”，可停止生成：保留并锁定消息、标记“已取消”、释放用户下一次发送权。管理员不能取消等待用户。发送、编辑、取消、删除均由服务端事务校验。
- 管理员回复先完整入库，再在当前可见用户页面渐进显示文字；刷新完整展示，不重播。图片立即显示。入库后用户即可继续发送，无需等待动画。
- 双方未读由服务器按消息序号记录；只计算对方消息，取消不减少未读。打开可见聊天才标读，展开分组不标读。排序只看成功发送时间。管理员分组可多开并在当前浏览器保存。
- 文字草稿按经过服务端验证的身份与聊天 ID 隔离，刷新恢复。未发送图片只保证当前页面内切换恢复。旧身份不会向新身份显示草稿；游客合并时迁移本浏览器相关草稿。

## 图片、安全与边界

支持静态 JPEG/PNG/WebP。≤10 MiB 的有效图片保留原始字节；>10 MiB 尝试先以高质量 WebP 压缩，再逐步缩小，最终每张 ≤10 MiB，失败明确报错。原始输入最多 **40 MiB**，解码像素最多 **4000 万**；不支持动画、SVG、GIF、HEIC。总 HTTP 请求最多 42 MiB，与单张压缩前上传上限配合。每条消息最多 **32000 个字符 / 8 张图片**。账号头像单独限制为原图 2 MiB，并缩为最多 256×256 JPEG。

所有附件预览/下载均鉴权，没有公开上传目录。临时文件 24 小时后撤销；绑定必须属于当前操作者且未被使用。删除先撤销数据库授权，物理删除由持久重试任务处理。无数据库记录的孤儿文件只清理专用 `ldt-uploads` 目录，并保留 24 小时宽限期。

Markdown 使用 DOMPurify；原始 HTML 按文字显示，危险 URL 清理，代码只高亮展示，公式禁用信任模式。Markdown 不加载外部图片，消息附件通过受保护地址显示。会话 Cookie 为 HttpOnly、SameSite=Lax；`ENV=prod` 时强制 Secure，所有 Cookie 写接口校验 CSRF 和 Origin。生产必须使用 HTTPS。

轻量限流以单进程 IP 为单位：注册/游客创建 5/10 次每小时、登录 12 次每分钟、上传 20 次每分钟、发送 60 次每分钟、全部写请求 120 次每分钟。当前生产运行 **一个应用 worker**；SQLite 写锁仍跨进程保证状态原子性，但 Socket.IO 房间和限流按单 worker 配置，不支持未配置的多 worker。

## Google OAuth（可选）

在 Google Cloud 配置 OAuth 同意屏幕，创建 **Web application** client，设置准确回调地址：

```dotenv
GOOGLE_CLIENT_ID=你的客户端ID
GOOGLE_CLIENT_SECRET=你的服务端密钥
GOOGLE_REDIRECT_URI=http://127.0.0.1:5173/oauth/google/callback
```

当前生产回调为 `https://chat.eurse.me/oauth/google/callback`（Google Cloud 控制台也需添加同一 URI），并同步 `PUBLIC_ORIGIN`。重启后登录弹窗出现 Google 按钮。使用 Authlib/Google OIDC state、nonce 与验证后的 `sub` 标识；同邮箱不会自动绑定已有本地账号。先登录已有账号，在设置中点击“绑定 Google 账号”。未配置则隐藏入口。[Google 官方 OIDC 说明](https://developers.google.com/identity/openid-connect/openid-connect)。

## OpenAI 自动标题（可选）

```dotenv
OPENAI_API_KEY=你的服务端API密钥
OPENAI_TITLE_MODEL=gpt-4o-mini
```

仅后台标题任务可访问固定 OpenAI API 地址。请求包含固定命名指令和第一条成功发送消息的**原始文字快照**，不含图片、后续聊天或编辑后的正文。纯图片首条固定“图片对话”，不创建标题任务。超时 12 秒，最多 3 次尝试，有失败后备标题；无 API key 直接保留首条文字截取。手动标题优先，迟到任务不能覆盖或复活已删聊天。[OpenAI Chat API](https://developers.openai.com/api/reference/resources/chat)。

## 密码恢复、备份与维护

无 SMTP、无邮件找回入口。服务器操作员可执行：

```sh
npm run password:reset
```

隐藏式输入已有本地密码账号邮箱和新密码；不会给 Google-only 账号添加密码。旧 API/Socket 授权立即撤销，闲置 Socket 连接在下一次校验时关闭（最多 30 秒），推送前也会重新校验。admin 同样可通过此命令恢复。

```sh
# 先停止服务器以保证数据库和附件的一致性
npm run backup -- /安全备份目录/chatldt-2026-11-15.zip
# Windows 示例：npm run backup -- D:\ChatLDT-Backups\chatldt.zip
npm run db:migrate
```

备份包含 SQLite、附件、服务端密钥及 `.env`；不得放在公开静态目录或提交 Git。恢复和生产运行见[自托管说明](docs/SELF_HOSTING.md)。历史迁移与旧表保留，不自动 drop；升级前对副本测试，再停机备份和迁移。

## 许可证与 Git

必须保留 [LICENSE](LICENSE)、[LICENSE_HISTORY](LICENSE_HISTORY)、[LICENSE_NOTICE](LICENSE_NOTICE) 和必要归属。当前 LICENSE 第 4 条约束 Open WebUI 品牌；不能仅凭“朋友使用”判定符合例外。部署者已明确确认滚动 30 天内不超过 50 位自然用户，本次依据第 4(i) 条完成产品界面品牌替换。若使用规模超出例外范围，须恢复许可要求的官方品牌或先取得书面/企业授权。[官方许可证说明](https://docs.openwebui.com/license/)，以本基线 LICENSE 原文为准。

当前开发分支 `feature/manual-chat-ldt`，保留 origin 与 Git 历史；没有 commit/push/merge/rebase/发布。未配置 upstream，如你以后需要，可**自行**执行：

```sh
git remote add upstream https://github.com/open-webui/open-webui.git
```

此命令不代表建议现在同步上游。完整测试边界、保留内容和未验证项见[验证报告](docs/CHATLDT_VERIFICATION.md)。

浏览器回归可使用 `npm run test:browser`。它要求显式设置 `CHATLDT_BROWSER_URL` 指向隔离测试实例，以及 `CHATLDT_BROWSER_CREDENTIALS_FILE` 指向权限受限的 `{ "email": "测试管理员邮箱", "password": "测试管理员密码" }` 文件；不要对真实用户实例运行会创建/修改数据的测试。可设置 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 使用本机 Chrome，否则先执行 `npx playwright install chromium`。测试截图输出到系统临时目录或 `CHATLDT_TEST_ARTIFACTS` 指定目录。

本次界面修正、交互验证与前后截图见 [UI 修正记录](docs/CHATLDT_UI_POLISH.md)。

手机布局、浏览器边界、实测截图与录屏见 [手机修正记录](docs/CHATLDT_MOBILE_LAYOUT.md)。
