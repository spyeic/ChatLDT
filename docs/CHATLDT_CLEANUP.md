# ChatLDT 清理报告

基于 `b0e6098e940942281d9c83f3529ea117287a3a22`，没有同步上游或更新保留的前端直接依赖版本。清理前工作区干净，没有用户修改被覆盖。

## 已执行

| 范围 | 处理及证据 |
| --- | --- |
| 后端产品路由 | 原 `routers/` 下模型/Ollama/OpenAI 代理、RAG/retrieval、web search、tools/functions/pipelines/MCP、代码终端、图像、语音、提示词、记忆、任务、分享/导出、标签/摘要/建议等路由及专用实现实际删除；只注册 `routers/manual.py` 和受限制 Google OIDC 路由 |
| 生成运行时 | 原 utils 中推理/chat middleware、插件加载、模型/文档/向量/语音服务、后台生成任务与相关模型运行时删除；唯一 OpenAI 请求在 `manual/jobs.py`，只生成标题 |
| Socket.IO | 原服务器所在 `socket/main.py` 提取为同一 Socket.IO 实例的身份鉴权和失效通知，保留原 `/ws/socket.io` 挂载路径；不保留原模型事件、channels、协同文档、插件调用入口 |
| 前端 | 沿用 SvelteKit route/layout 与原 chat/MessageInput/Sidebar/Markdown 文件位置，移除分支/生成、模型选择、工具、搜索AI、语音、分享、导出及整个 workspace/knowledge/model/function 等路由与专用组件/API/store；不是 CSS 隐藏。聊天账户管理在同页原风格对话框内完成 |
| 共享样式/渲染 | 保留 Tailwind 配色、字体、侧边栏/输入布局、Markdown、高亮、公式，KaTeX 词法扩展沿用并补足类型；移除旧全局 CSS 中语音、编辑器、模型功能专用样式 |
| 国际化 | 保留 i18next，当前只静态导入 en-US/zh-CN；删除其他语言和不再使用的翻译键，不再有语言目录的动态 glob |
| npm | 删除 transformers/MediaPipe/Kokoro/Pyodide、Three/VRM、MCP apps/noVNC/xterm、rich editor、RAG 文档浏览/Office/PDF、导出、地图、图表、协同等专用直接依赖，并由 npm 更新 package-lock。精确清单见 `CHATLDT_REMOVED_DEPENDENCIES.json` |
| Python | requirements/pyproject/uv.lock 移除 OpenAI SDK（标题用最小 httpx 请求）、Anthropic、Ollama/模型相关库、Torch/transformers、LangChain、Chroma/向量数据库、Playwright/文档解析、STT/TTS、OCR/embedding、LDAP/云存储/Redis 等；无模型下载/启动检查。保留基线中实际需要的 FastAPI/SQLAlchemy/Alembic/Authlib/Socket.IO/Pillow 等版本 |
| 静态资源/工具 | 删除 Pyodide 下载与资源、sql.js 执行 WASM、语音音频、emoji picker 目录、地图 marker、加密 channel Rust 构建链等专用资源，保留图片压缩和代码块展示 |
| 部署/文档/CI | 实际删除 Dockerfile、Compose、docker-* 启动脚本、Docker/release 专用 workflow、旧 slim requirements、旧模型启动脚本、多语言宣传 README。替换为准确中英 README、原生自托管和不依赖 Docker 的验证 CI |

## 引用分析与恢复

自动审批最初拒绝粗粒度保留清单删除。随后改为 Python AST 引用闭包、Svelte/TS/CSS 导入闭包、显式 SvelteKit 路由、Alembic 动态迁移发现及静态资源消费者盘点。每个候选都核对为未修改的 Git 跟踪文件，排除迁移/法律文件/数据路径，并先创建逐文件哈希校验的恢复归档。

- `CHATLDT_CLEANUP_PLAN.json`：入口、边、保留闭包、逐路径删除理由和内容哈希。
- `CHATLDT_REMOVED_PATHS.json`：已删除源码清单与本次本机临时恢复归档位置。
- `CHATLDT_RESOURCE_CLEANUP_PLAN.json` / `CHATLDT_REMOVED_RESOURCES.json`：资源、部署、文档、workflow 删除理由与结果。
- 原始内容仍在 Git 基线历史中；没有 commit、重写历史或删除 `.git`。

以上机器清单用于精确核对；功能验证以 `CHATLDT_VERIFICATION.md` 为准，不以删除数量或行数代替验收。

## 保留内容与理由

| 具体路径 | 原因/边界 |
| --- | --- |
| `backend/open_webui/migrations/versions/*`、`migrations/util.py` | 完整历史迁移链；旧模型/RAG/分享等表结构仍被后续 revision 引用。保留结构不代表启用功能，不 drop 历史用户数据 |
| `backend/open_webui/internal/db.py` | 复用原 SQLAlchemy engine、Base、JSONField、session/SQLite WAL 事务基础。包含历史数据库兼容辅助函数；`env.py` 限定 SQLite，不安装/使用外部数据库、IAM 或 SQLCipher 驱动 |
| `backend/open_webui/utils/json_codec.py` | 迁移的 JSONField 与数据库序列化仍使用；无推理能力 |
| 原 `user` / `auth` / `chat` / `file` 数据表 | 保留账号哈希兼容和历史数据。LDT 正规化状态新增而非覆盖树状 AI 历史；现有 AI 聊天不会未经审查转换为人工聊天回合 |
| `LICENSE*`、`CONTRIBUTOR_LICENSE_AGREEMENT`、`src/lib/encryption/vendor/THIRD_PARTY_LICENSES.txt` | 许可证、历史归属、第三方通知不可因代码清理误删 |
| `static/static/*` 与 `backend/open_webui/static/*` 中兼容 logo/favicon/splash 路径、品牌说明 | 2026-11-16 部署者明确确认 LICENSE 第 4(i) 条例外，图标内容已替换为原创 ChatLDT，兼容路径避免旧引用失效。保留品牌条款说明和必要法律归属；无运行页面官方标识。无引用的 `static/assets/welcome.mp4`、`welcome.webp` 和失效的 `static/opensearch.xml` 已删除，详见 `CHATLDT_UI_POLISH.md` |
| `CHANGELOG.md`、社区行为规范 | 上游历史/归属资料，不作为 ChatLDT 功能或安装说明；主 README 已替换 |
| `backend/data`、被忽略的运行目录、`.env`、密钥、数据库和上传文件 | 不在任何清理候选集合；本次所有测试数据位于独立 /tmp 目录 |

没有因“未来同步方便”保留整套 AI 运行时。当前仍需注意：原有 AI 树状历史只保存在原表，未加入人工聊天列表；若计划在有旧生产数据的实例上切换，需单独完成只读历史展示/人工导入策略评审。现有库迁移测试证明原行保持不变，不能据此声称旧 AI 历史已具备人工继续回复能力。

补充：`CHATLDT_REMOVED_PYTHON_DEPENDENCIES.json` 记录 Python 直接依赖/可选组的删除清单；Playwright 仅作为固定版本的前端开发测试工具，生产 Python 不依赖它。原用户导入示例 CSV 和已不被 HTML 引用的旧 splash loader 也已按精确哈希核对、备份后删除，见 `CHATLDT_REMOVED_UNUSED_STATIC.json`。`scripts/licenses.mjs` 将主许可证和实际客户端依赖通知随构建输出；现有 Inter 3.019 与 Vazirmatn 33.003 字体的 SIL OFL 文件从其确切上游版本补齐。
