# ChatLDT 交付验证与边界

本次在原 Fork 中实现了可运行的人工聊天版本，并进行了真实后端、构建和浏览器验证。这里不把本机通过等同于所有目标系统和外部服务的生产验收。

## 环境与执行结果

本机 macOS；隔离 Node **22.23.5**、Python **3.12.7**；pytest **8.4.2**、Ruff **0.15.18**。机器原默认 Node 24/Python 3.13 未被全局替换。生产账号和测试数据没有混用，临时测试实例位于 `/private/tmp`，仓库 `backend/data` 原文件未变。

| 检查 | 实际结果 |
| --- | --- |
| `npm ci` | 精简锁文件正常干净安装，未使用模型/语音/RAG 下载脚本；保留的前端直接依赖实际解析版本无变化，新增固定 Playwright 仅用于开发测试 |
| 后端干净安装 | 新建 `/private/tmp/chatldt-clean-env`，只从 `backend/requirements.txt` 安装及解析依赖；完整迁移、FastAPI lifespan、health/session、旧推理 API 404 验证通过。没有 Torch/Ollama/Chroma/LangChain/STT 等组件 |
| `uv lock --check` | 与精简 pyproject 一致；删除未使用的 pytest-asyncio，pytest 使用原锁版本 |
| `npm run setup` | 在独立 `/private/tmp/chatldt-setup-check` 实际 TTY 运行，隐藏录入管理员邮箱/密码，完成依赖检测、迁移和唯一管理员创建 |
| setup 再运行 | 实际成功识别已有管理员，无密码提示、不覆盖密码；另有哈希一致性回归测试 |
| `npm run check` | Svelte/TypeScript 0 errors、0 warnings |
| Python Ruff F 检查 | 修改的运行时模块、初始化/恢复/备份、路由、Socket、测试通过 |
| Python 回归 | **28 passed**，覆盖下述业务和安全场景 |
| `npm run test:frontend` | **2 passed**，保留 KaTeX/Markdown 词法扩展验证 |
| `npm run build` | 生产静态构建成功；prebuild 同步主许可证及客户端依赖通知，无 Pyodide/模型资源下载 |
| 生产入口本机启动 | Uvicorn 在 localhost 实际提供生产 build、API、鉴权图片和 `/ws/socket.io`，不是 UI mock 或另一个 Node API |
| 真实 Chrome | 双身份 + 多标签页 + 中文/英文、亮/暗、390px 移动视口交互通过；详细场景如下 |
| 备份与恢复 | setup 数据备份归档完整性、SQLite 读取通过；停止测试服务后对真实测试聊天/图片再备份，恢复到独立目录，启动应用、Duo 登录、历史读取、鉴权图片读取全部通过 |
| 迁移 | 空库完整迁移链通过；另建立到基线 head 的旧库，插入账号/哈希/分支 JSON/附件元数据，SQLite backup 创建副本后升级至 ldt001，逐表原行不变，源库版本保持原 head |
| 清理/法律/Git | 当前引用审查无悬空前端 import，未发现剩余源码候选；旧专用 API 不能调用。LICENSE 系列、CLA、原数据路径与 Git HEAD/远程保持不变；`git diff --check` 通过 |

历史迁移/SQLAlchemy 仍有上游弃用与表达式索引反射警告；测试成功不是“零警告”。未修改历史迁移来抹掉这些警告。

## Python 回归覆盖

- 无 Cookie 时不自动建游客；公开首个注册账号也不是管理员。
- 不同会话/同昵称不串身份，Cookie 清除后不能通过聊天 ID 找回旧会话。
- 可控时钟验证 30 天闲置、有效访问滚动续期、只读读取和推送不续期；过期游客的记录仍可由有效管理员回复。
- 当前有效 Cookie 绑定的游客合并、旧会话失效、并发迁移仅转移一次、管理员登录不接收游客归属；迁移中注入数据库失败后事务回滚，原游客仍能访问，返回可重试错误。
- 同邮箱 Google 不自动合并，只有已登录账号可绑定验证后的提供方 subject，重复 state 被拒绝（提供方响应为受控替身）。
- setup 重复识别、密码恢复后旧会话失效、唯一管理员不可删、旧邮箱重注册不恢复旧数据。
- 每聊天独立轮次、管理员为注册用户首发、游客不能成为管理员主动首发目标、管理员不能取消等待用户。
- 幂等成功原结果、并发相同请求只有一条消息、同 key 不同负载拒绝、过时回合拒绝、取消不能重绑后续回合。
- 文字版本与轮次版本分离、并发编辑不静默覆盖、编辑/回复按事务顺序、取消/回复只有一方改变旧轮次、聊天或账号删除/发送竞态不复活数据。
- 空消息、不可修改附件、不可删除单条消息、不可编辑对方/已锁定消息；纯图片补文字/清空文字有效。
- 取消保留消息和灰色标记；允许取消后的连续用户消息；新消息才改变排序时间；取消/编辑/标读不改变排序；双方未读只计对方消息，取消消息仍计未读。
- 用户所有权、跨账号正文搜索和附件访问拒绝、管理员跨用户昵称/正文搜索、删除后不可搜索或访问。
- 原始小 PNG 字节不变，真实 >10MiB PNG 压缩到 <=10MiB；非法图片拒绝、临时文件过期、文件物理删除失败可重试，数据库先撤销访问。
- 首条文字快照、纯图片不建标题任务、文字后改/取消不改快照、手动标题挡住迟到结果、删除不能被标题结果复活、失败尝试最多三次。
- 无 Google/OpenAI 配置时完整人工聊天可用，旧补全/检索/生成/分享等 API 无法提供原功能。

## 真实浏览器交互覆盖

仓库脚本 `scripts/browser-smoke.mjs`，通过 `npm run test:browser` 运行，需要显式指定隔离实例及私有测试管理员凭据文件。所有运行均使用临时测试账号，未将测试密码设置到实际项目数据目录。

1. 欢迎页直接进入；首次发送才弹昵称，取消保留原草稿，确认后自动发送。
2. 刷新保持游客身份和文字草稿；同 profile 多标签页共享身份。
3. Duo 登录保留欢迎页，不自动打开会话；按用户分组进入同一聊天页面。
4. 用户与管理员消息左右视角相反；等待期间只能编辑草稿、不能发送。
5. 用户编辑问题后管理员实时看到，管理员已输入的回复仍保留并可直接发送。
6. 管理员提交后用户恢复发送并看到渐进回复；停止按钮只控制当前待回复轮次。
7. 用户取消后管理员看到已取消，原回复草稿保留、发送禁用，不自动跟随新轮次发送。
8. 中文/英文、桌面亮色与移动暗色布局；页面无 JS uncaught error。
9. 另一旧游客标签页仍在线时，从游客设置直接注册，全部聊天迁移，当前浏览器文字草稿恢复；语言/主题随新账号保存。
10. 文件选择与剪贴板事件路径组合多图为同一消息，受保护图片预览成功，成功发送不残留重试按钮。
11. 所有权改变后管理员仍停留原对话，不自动展开新分组；新消息更新数据。
12. 客户端离线期间管理员成功回复，恢复网络后从数据库补齐完整回复，不自动跳转聊天。
13. 使用独立持久 profile 启动完整 Chrome 进程，创建游客后关闭整个浏览器，再用同一 profile 重开，原身份和聊天恢复。

移动端为 Chrome viewport 模拟，不是所有实体移动设备的兼容认证。粘贴验证通过 ClipboardEvent/DataTransfer 驱动实际页面处理逻辑，未读取系统剪贴板中的用户数据。

## 明确未完成/未验证

- **真实 Google 登录与真实 OpenAI 请求未执行**：没有提供凭据，也未消耗 API 额度。Google state/subject/同邮箱绑定逻辑和标题 payload/迟到/重试使用替身测试；实际提供方签名/同意屏幕/回调、模型权限、计费和公网连通性需配置凭据后联调。
- **Windows/Linux 实机、Safari/Firefox、实体手机未运行**。已提供跨平台脚本和 Linux/Mac 自托管方案；没有声称在这些环境成功执行。
- **公网部署/HTTPS/反向代理/系统服务未执行**，符合本次不发布、不部署的要求。需要实际域名、证书和目标机器再验证。
- **旧 AI 树状历史未转换/展示在人工聊天列表**。原数据和所有分支完整保留，当前人工状态机只处理 LDT 记录，不能把数据保留测试说成已实现旧 AI 对话继续人工回复。若未来要在有旧生产历史的实例切换，需完成明确的只读展示或管理员审查导入策略。
- **已有 MFA 账号不做隐式降级**：检测到原本启用的 MFA 会拒绝本版本的登录路径，需单独的安全迁移。本次初始工作区没有真实数据库。此限制不会影响本版本新建的邮箱/Google 账号。
- 没有做大规模负载、长时间断电/磁盘损坏、所有操作组合的随机模糊测试，或多 worker/多机部署验证。当前明确只支持本地 SQLite + 一个应用 worker。

## Git 交付状态

当前 `feature/manual-chat-ldt`，HEAD 仍为 `b0e6098e940942281d9c83f3529ea117287a3a22`。
origin 仍为 `git@github.com:spyeic/ChatLDT.git`，无 upstream；没有修改远程、commit、push、merge、rebase 或发布。工作区包含本次业务代码、新迁移、测试、清理与锁文件、文档等未提交改动。

主要修改：`backend/open_webui/manual/*`、`routers/manual.py`、原 main/socket/env/db migration 环境、原 Chat/MessageInput/Sidebar/Markdown 和 SvelteKit route/layout、两语言资源、setup/start/backup/test 脚本、依赖清单/锁文件、原生 CI、自托管及清理报告。删除列表与逐路径理由见 `CHATLDT_REMOVED_*` / `CHATLDT_*CLEANUP_PLAN.json`。

```sh
git status --short --branch
git diff --stat
git diff -- LICENSE LICENSE_NOTICE LICENSE_HISTORY backend/data
```

## Modern Web Guidance

- `dialog`：我使用原生 `<dialog>`/`showModal()` 承担焦点、页面 inert 和 Esc 关闭，删除确认优先提供取消按钮，使用 `:modal`/`::backdrop` 滚动容纳，不增加手写 focus trap（“DON'T add role=\"dialog\", aria-modal, a focus trap”）。
- `accessibility`：我保留语义 button/form/label、为图标按钮命名、保留键盘焦点指示，并对动态错误使用 alert；文字动画尊重 reduced-motion（“Prefer HTML elements and attributes to ARIA”）。

## 开发登录来源修复

截图中的浏览器地址为 `http://127.0.0.1:5173`，此前 `.env`/示例和默认来源却为 `http://localhost:5173`，与 Vite 的 127.0.0.1 绑定/输出地址不一致，导致登录在密码验证前返回 Origin 403。现已统一当前开发配置、示例、后端默认值、OAuth 默认回调和 README 为 127.0.0.1，并让不匹配错误提示配置允许的地址。没有放宽来源白名单或取消 CSRF 校验。

新增 6 项来源回归测试：默认开发地址可登录，localhost 别名/错误端口/外部域名/null 被拒绝，生产环境仍要求准确来源和 CSRF。完整后端回归为 **34 passed**。另通过实际运行的 Vite 5173 代理验证来源错误消失，使用空测试邮箱只进入凭据拒绝阶段（401），外部来源仍为 403；没有读取/修改实际密码或创建测试账号。

修复分支为 `fix/dev-login-origin`，原 `feature/manual-chat-ldt` 保留，现有未提交工作保留，未 commit/push。
