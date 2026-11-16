# ChatLDT UI 增量修正与验证

2026-11-16。在已有 ChatLDT 第一版与未提交修改上继续开发；当前分支 `fix/chatldt-ui-polish`，HEAD 为 Open WebUI 0.13.3 基线 `b0e6098e940942281d9c83f3529ea117287a3a22`。原分支为 `fix/dev-login-origin`。保留既有工作区、Git 历史与 `origin=git@github.com:spyeic/ChatLDT.git`；没有 commit、push、merge、rebase、同步上游或部署。此前人工聊天实现的大批删除仍在未提交工作区中，不属于本次新增 UI 删除。没有设置 upstream；如需日后自行配置可执行 `git remote add upstream https://github.com/open-webui/open-webui.git`。

## 改动与关键文件

| 文件                                                                                  | 本次修改                                                                                                                                |
| ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/open_webui/manual/security.py`                                               | 以唯一管理员注册记录和账号角色判断管理员，对外名称投影为 `admin`；既有 Duo 账号无需迁移或重新 setup，读取不修改存储名称、ID、邮箱或密码 |
| `backend/open_webui/manual/setup.py`、`routers/manual.py`                             | 新管理员默认 `admin`；管理员设置显示名固定为 `admin`，普通用户昵称正常保留；错误文案使用管理员角色名称                                  |
| `src/lib/components/chat/Chat.svelte`                                                 | 删除所有消息姓名行及空白；保留左右方向、作者元数据、标题与侧边栏分组；接入消息操作与共享原生弹窗                                        |
| `src/lib/components/chat/Messages/MessageActions.svelte`                              | 气泡下方预留高度的图标工具栏：自己的右对齐，对方左对齐；桌面 hover/focus-within 淡入，触屏常显；反馈期间保持可见                        |
| `src/lib/components/common/CopyButton.svelte`、`src/lib/utils/clipboard.ts`           | 复制完整原始文本/Markdown；1.5 秒勾选反馈；异步 Clipboard API、传统用户手势降级及真实失败提示；恢复焦点和选区；纯图片无复制按钮         |
| `src/lib/components/chat/Messages/Markdown.svelte`                                    | 保留消毒、公式与高亮，提供独立代码块复制；代码复制控件不覆盖代码文字                                                                    |
| `src/lib/components/common/ActionIcon.svelte`                                         | 共用线性铅笔、复制、勾选、加号、关闭和菜单 SVG，无新增依赖                                                                              |
| `src/lib/components/common/Modal.svelte`                                              | 原生 dialog 的统一进入/退出动画、遮罩、焦点恢复、Esc；关闭完成前仍保留原生模态；快速重新打开与 reduced-motion 处理                      |
| `src/lib/components/layout/Sidebar.svelte`、`chat/MessageInput.svelte`、`src/app.css` | 单一 ChatLDT 品牌、账号名、上传图标、按钮 hover/active/focus-visible/disabled；输入框圆角焦点，图片移除控件及中英可访问名称             |
| `src/app.html`、`static/chatldt-*`                                                    | 原创圆角聊天气泡与 L 图标，带版本路径的 SVG/PNG favicon、Apple 图标、PWA 名称与 manifest；页面标题只有 ChatLDT                          |
| `backend/tests/test_admin_display.py`                                                 | 既有管理员刷新/重新登录、凭据保持、普通同名用户权限与初始化默认名验证                                                                   |
| `scripts/ui-polish-smoke.mjs`、`scripts/ui-fixture.py`                                | 可重复运行的浏览器交互检查与独立临时数据生成器                                                                                          |
| `scripts/browser-smoke.mjs`                                                           | 适配 admin 名称、隐藏工具栏、弹窗退出等待；测试昵称唯一化，避免重复运行选错分组                                                         |

编辑权限仍为自己最新且未被回复/取消的有效消息，只改文字；服务端校验保留。复制使用 `message.content`，不会复制动画截断后的渲染文本。聊天轮次、幂等、游客迁移、附件授权、搜索、未读和实时通知未作业务改写，无新增数据库迁移或依赖。

## 消息外框检查

实际在隔离 Chrome 中点击原有消息，检查了 body/main/article/气泡的 border、outline、box-shadow、焦点和圆角；鼠标点击的大矩形没有复现，不能断言其截图根因。原 Edit 控件没有圆角，键盘焦点可形成方框；现已替换为圆角图标按钮。新消息容器保持普通 article/div，无按钮角色、tabindex、边框或阴影；仅针对滚动 main 的鼠标焦点抑制非 focus-visible 轮廓，按钮、链接和输入控件仍有清晰的 focus-visible，拖选正常。未使用全局 outline:none。

## 品牌与资源清理

已逐条审阅本地 LICENSE 第 4 条。部署者明确确认“滚动 30 天内不超过 50 位自然用户”，本次依据第 4(i) 条执行产品界面品牌替换；条件变化时须恢复许可要求的品牌，或取得相应书面/企业授权。朋友使用本身不构成豁免。此项目不声称获得 Open WebUI/OpenAI 官方认可。[官方许可证说明](https://docs.openwebui.com/license/)；以当前基线 LICENSE 原文为准。

- 新增原创 `static/chatldt-icon-v1.svg`、32/180/192/512 PNG 和 `chatldt-v1.webmanifest`，页面引用带版本路径避免旧图标缓存。
- `static/static/`、`backend/open_webui/static/` 中兼容 favicon、logo、splash、Apple、PWA 图标文件的内容也换为新图标；旧资源路径继续可用，避免现有浏览器旧引用失效。
- 删除无运行引用的 `static/assets/welcome.mp4`、`static/assets/welcome.webp` 和指向旧 localhost 端口、没有有效入口的 `static/opensearch.xml`。已检查源码引用、动态资源入口、HTML/manifest 与构建产物，不仅依据文件名删除。
- 保留 `LICENSE`、`LICENSE_HISTORY`、`LICENSE_NOTICE`、第三方许可证、历史版权与品牌条款说明；这些归属文本不作为产品品牌 UI 显示。`BRANDING.md`/静态目录 README 加入本次例外与资源更新记录。
- 内部 `open_webui` 包名、导入路径、数据库标识、原有消息作者和正文保持原意；没有全库替换 Duo/Open WebUI。README 与原审计/清理报告已同步品牌决定。

## 已执行验证

测试使用独立临时 SQLite、附件目录与浏览器上下文；没有登录、删除、重置或迁移真实账号数据。未配置 Google/OpenAI。

| 检查                                          | 结果                                                                                                                                                                                                                                                                                                                       |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm run check`                               | 0 errors / 0 warnings                                                                                                                                                                                                                                                                                                      |
| `npm run test:frontend`                       | 2 项通过                                                                                                                                                                                                                                                                                                                   |
| `.venv/bin/python -m pytest backend/tests -q` | 37 项通过，含 3 项管理员显示测试；11 条现有 SQLAlchemy/Alembic 弃用/反射警告                                                                                                                                                                                                                                               |
| 仓库 CI 对应 Ruff `--select F`                | 人工聊天模块、主程序、路由及新增测试通过                                                                                                                                                                                                                                                                                   |
| 新增测试/fixture 的完整 Ruff                  | 通过；对现有后端文件尝试默认完整 Ruff 时，另有既有 I001/E501/C901/E712 问题，本次未为 UI 修改重构这些代码                                                                                                                                                                                                                  |
| `npm run build`                               | 生产构建通过，输出 `build/`                                                                                                                                                                                                                                                                                                |
| 原有 `scripts/browser-smoke.mjs`              | 全部通过：游客昵称与取消、刷新/多标签/重开浏览器、草稿、管理员欢迎/分组与视角、实时编辑与回复、轮次取消、主题语言、注册迁移、组合多图/粘贴、受保护预览、断线恢复                                                                                                                                                           |
| `npm run test:ui`                             | 全部通过：admin 刷新及登录、无姓名行、左右对齐、hover 移动不闪烁、消息尺寸不跳动、编辑权限、完整 Markdown/代码复制、缺失 Clipboard API 降级、权限拒绝提示、焦点及文字拖选、弹窗退出/快速开关/reduced-motion、取消消息复制、渐进回复完整内容复制、纯图片和文字补充、三类身份语言/主题设置、390px 触屏布局、favicon/PWA 资源 |

桌面浏览器为 macOS 本机 Chrome，通过 Playwright 自动化运行；触屏为 Chrome 移动设备模拟。未执行真实 iOS/Android、Safari/Firefox、Windows/Linux UI、真实 PWA 安装与操作系统缓存升级测试；未调用真实 Google/OAuth 或 OpenAI 付费接口。没有把这些未执行项目算作通过。

截图均来自临时测试身份：[修改前](screenshots/ui-polish/before-dark.png)、[修改后管理员深色](screenshots/ui-polish/after-admin-dark.png)、[普通用户浅色](screenshots/ui-polish/after-user-light.png)、[游客触屏中文](screenshots/ui-polish/after-guest-mobile-dark.png)。

## 运行与复验

开发仍使用 Node 22 和 Python 3.11/3.12，两个终端分别运行 `npm run backend:dev` 与 `npm run dev`；生产使用 `npm run build` 后 `npm start`。`npm run setup` 仍识别既有管理员且不覆盖密码。请保持浏览器 Origin 与 `PUBLIC_ORIGIN` 完全一致。此环境系统 Node 24 超过仓库 engines 范围，验证使用 Node 22.23.5，而非升级项目依赖。

新 UI 脚本会创建/编辑测试会话，必须指向隔离服务。macOS/Linux 示例：

```sh
.venv/bin/python scripts/ui-fixture.py
# 将上条输出的 Isolated UI fixture 路径赋给 CHATLDT_FIXTURE，勿指向真实数据。
export CHATLDT_FIXTURE=/path/from/the/output
# 终端一
PYTHONPATH=backend DATA_DIR="$CHATLDT_FIXTURE/data" ENV=dev \
PUBLIC_ORIGIN=http://127.0.0.1:8091 OPENAI_API_KEY= GOOGLE_CLIENT_ID= GOOGLE_CLIENT_SECRET= \
.venv/bin/python -m uvicorn open_webui.main:app --host 127.0.0.1 --port 8091
# 终端二：仍使用上面的 CHATLDT_FIXTURE
CHATLDT_BROWSER_URL=http://127.0.0.1:8091 \
CHATLDT_BROWSER_CREDENTIALS_FILE="$CHATLDT_FIXTURE/credentials.json" \
PLAYWRIGHT_CHROMIUM_EXECUTABLE='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
npm run test:ui
# 原业务检查使用相同三个环境变量运行 npm run test:browser。
```

fixture 生成器始终新建临时目录，将随机测试密码写入权限 0600 的 credentials.json，不打开应用配置的数据目录。Windows 对应使用 `.venv\Scripts\python.exe`，以 PowerShell `$env:变量=值` 设置相同变量及本机 Chrome 路径；本轮未实测 Windows。

已有数据无需迁移。备份/恢复、HTTPS 和生产重启仍按 [SELF_HOSTING.md](SELF_HOSTING.md)；常规升级先停服务并 `npm run backup -- /secure/backups/chatldt.zip`，保留密钥和附件，再运行 `npm run db:migrate`。本次未更改备份或迁移链。

## 交互实现参考

本次使用 modern-web-guidance 技能检索并完整阅读 `animate-to-from-top-layer`、`motion`、`copy-button` 指南：遵循 “Include `overlay` in your `transition` list”、 “Keep the final state” 和 “Hide with `opacity` only”。对应实现为原生 dialog 保留模态直至退出结束、动效结束状态稳定、工具栏使用 opacity/focus-within 并保持键盘可达；同时保留 reduced-motion、复制降级和真实失败反馈。
