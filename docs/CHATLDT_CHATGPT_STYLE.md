# ChatLDT 对话界面优化与验收

2026-11-16。分支 `fix/chatldt-chatgpt-style`。直接修改现有 SvelteKit 前端；FastAPI 状态机、数据库和业务 API 未改动，没有新增运行依赖。开始时工作区干净；没有 commit、push、merge、rebase、同步上游或部署。已阅读 README、现有 UI/手机验证记录和相关源码；仓库及父目录未找到 AGENTS.md。参考截图里的文档正文仅作为图片内容处理。

## 实际差异与原有能力

- 普通用户/游客在当前源码中已经没有独立开始按钮；用户所附第二张图是管理员状态，原按钮负责收件人选择。本次分别设计两种欢迎状态，保留管理员流程。
- 原欢迎语与底部真实输入框分离，桌面空编辑器约 144px；现在欢迎语和编辑器为同一组，桌面输入框实测约 104px、手机约 96px，欢迎语与输入框间距分别 28px/24px。
- 原有消息方向、隐藏姓名、复制和编辑图标工具栏、原生弹窗退出动画、手机覆盖抽屉、动态视口与安全区已存在。本次复用，没有重新实现业务。
- 原来没有桌面折叠，也没有可靠的底部跟随逻辑；搜索框常显，聊天项操作始终可见，消息和输入框的内外留白不同。本次集中修正这些差异。
- 原有游客持久 Cookie、注册迁移、权限与实时同步均经过已有回归。没有因截图假定这些业务正确，也没有发现需要在本次重写状态机的问题。

## 最终行为

欢迎页将小图标、轻字重欢迎语和真实编辑器置于主区中心略偏上。编辑器始终是同一个组件和 textarea DOM 节点；首发成功才显示消息列表并切为底部输入。失败重试、昵称弹窗取消、附件和等待草稿沿用现有状态。管理员未选收件人时隐藏并 inert 编辑器，显示“选择用户开始对话”；选择注册用户后才可主动发起。

会话与输入框共享 768px 最大宽度，按扣除侧边栏的主区居中。顶栏显示对话标题或“新建聊天”。自己的消息右侧低对比气泡，对方回复以正文显示；正文 16px/1.7，代码与表格自行横向滚动，图片保持比例且限制高度。保留桌面 hover/focus 和触屏常显工具栏及原有权限。

输入框采用圆形上箭头和明确的禁用色，取消回合为可访问的停止图标。继续支持 Enter 发送、Shift+Enter 换行，保留 isComposing 并补充 229 键值保护。文字自动增高、附件区域限制高度。检测到手机键盘压缩视口时收起欢迎语，将编辑器留在可用区域；没有移除原动态视口、安全区和缩放降级。

侧边栏保留原创品牌、管理员分组、昵称、展开状态、未读和排序。搜索改为顶部图标入口，展开轻量输入面板，复用原权限范围和搜索 API。聊天项操作桌面 hover/focus 显示，触屏常显；账号固定底部，游客增加直接登录入口。桌面折叠状态持久化，主区保留恢复入口；手机继续覆盖抽屉。

新增 ResizeObserver 观察内容变化：处于底部才跟随渐进回复或图片加载；阅读历史时保持位置并显示“回到底部”。主动发送或选择聊天进入底部。回到底部控件按编辑器区域定位，多图和长草稿不会把它压在按钮下。

## 修改文件

| 文件                                                              | 修改                                                                                           |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `src/app.css`                                                     | 集中深浅主题变量、表面层次、共享列宽、柔和表单边框、Inter 可变字重声明，合并重复变量和焦点规则 |
| `src/lib/components/chat/Chat.svelte`                             | 欢迎/对话布局、管理员入口、标题、消息宽度与留白、底部跟随和恢复按钮、折叠状态                  |
| `src/lib/components/chat/MessageInput.svelte`                     | 编辑器高度、圆形发送/停止按钮、状态色、附件高度、输入法保护                                    |
| `src/lib/components/chat/Messages/Markdown.svelte`                | 正文、标题、段落、列表、代码与表格排版                                                         |
| `src/lib/components/common/ActionIcon.svelte`                     | 搜索、侧边栏、上下箭头和停止线性图标                                                           |
| `src/lib/components/common/ResponsiveDrawer.svelte`               | 桌面折叠、inert、宽度过渡，保留手机退出和 reduced-motion                                       |
| `src/lib/components/layout/Sidebar.svelte`                        | 品牌区、按需搜索、紧凑聊天行、操作显隐、底部账号和游客登录                                     |
| `src/lib/utils/mobile-viewport.ts`                                | 在原视口测量上暴露键盘状态，清理时移除属性                                                     |
| `src/lib/i18n/locales/{en-US,zh-CN}/translation.json`             | 新增恢复侧边栏、回到底部、管理员欢迎文案                                                       |
| `scripts/{browser-smoke,ui-polish-smoke,mobile-layout-smoke}.mjs` | 适配图标可访问名称与欢迎布局、明确测试语言初始值、顶部懒加载图片定位、补充键盘欢迎页检查       |
| `scripts/chat-style-smoke.mjs`                                    | 本轮布局、输入法、附件、发送、折叠、搜索与滚动验收                                             |
| `scripts/chat-style-captures.mjs`                                 | 可复用同状态前后截图工具                                                                       |
| `package.json`                                                    | 增加 `test:chat-style`，依赖未变                                                               |
| 本报告及 `docs/screenshots/chatgpt-style/`                        | 测试数据截图、录屏、测量和构建记录                                                             |

## 验证结果

使用 Node 22.23.5、项目现有 Python 3.12 虚拟环境、macOS 本机 Chrome/Playwright。后端使用新建临时 SQLite 与附件目录，不打开应用配置的真实数据目录；凭据保存于 0600 临时文件，没有进入截图或仓库。

| 检查                                          | 结果                                                                                                                                                                                                                                                               |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `npm run check`                               | 0 errors、0 warnings                                                                                                                                                                                                                                               |
| `npm run test:frontend`                       | 2 文件、5 测试通过                                                                                                                                                                                                                                                 |
| `.venv/bin/python -m pytest backend/tests -q` | 45 测试通过，11 条现有弃用/反射警告                                                                                                                                                                                                                                |
| `npm run build`                               | 生产构建通过，产物为 `build/`；见 [构建日志](screenshots/chatgpt-style/build.txt)                                                                                                                                                                                  |
| `npm run test:browser`                        | 全部通过：游客昵称取消/持久 Cookie/浏览器重启、跨标签草稿、管理员分组和方向、实时编辑回复、取消轮次、注册迁移、多图/粘贴/受保护图片、断线恢复                                                                                                                      |
| `npm run test:ui`                             | 全部通过：复制完整原文/代码/渐进回复、Clipboard 降级与失败反馈、hover 无位移、键盘焦点、编辑限制、取消消息、纯图片补文字保留附件、三种身份设置、弹窗退出/快速开关/reduced-motion                                                                                   |
| `npm run test:chat-style`                     | 全部通过：管理员选人后主动创建、无管理员取消、组合输入 Enter 不发送、Shift+Enter、昵称取消保留两图与草稿、首发 DOM 节点保持、等待草稿、取消锁定、一次在途发送、长代码/表格/公式边界、底部跟随、编辑和新消息到来时历史位置保持、回到底部、桌面折叠/恢复/持久化/搜索 |
| `npm run test:mobile`                         | 360/390/430 CSS px × 中英 × 深浅，共 12 组欢迎与对话状态全部通过；抽屉覆盖/退出后卸载/快速反向开关/inert/滚动恢复、横屏、键盘模拟、缺失 VisualViewport/Popover 降级、安全区模拟、reduced-motion 通过                                                               |
| `git diff --check`                            | 通过                                                                                                                                                                                                                                                               |

动画通过实际点击与中间状态检查验证，不以静态截图证明。弹窗保留原生模态直到退出结束；抽屉退出期间仍挂载、结束后隐藏，快速反向开关后无残留 inert/遮罩。按钮沿用 150ms、弹窗 190/150ms、抽屉 230ms；减少动态效果设置继续生效。

手机测量见 [measurements.json](screenshots/chatgpt-style/measurements.json)。欢迎页长草稿和两张附件在模拟可用高度 340px、顶部偏移 80px 时完整留在输入区域，关闭后欢迎语恢复。手机录屏包含欢迎/键盘、抽屉、弹窗、长消息与草稿、多图、横竖屏和快速开关操作：[mobile-demo.webm](screenshots/chatgpt-style/mobile-demo.webm)。

## 同视口、同状态前后截图

桌面均为 1440×900 CSS px，手机均为 390×844 CSS px。前后使用同一段合成对话、语言与主题；欢迎页只与欢迎页比较，对话页只与同一对话比较。为避免其他回归生成的测试会话干扰对比，截图脚本将侧边栏响应限制为这一个既定测试对话；页面、编辑器和消息均为真实实现。

| 状态                         | 修改前                                                         | 修改后                                                        |
| ---------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------- |
| 游客欢迎，桌面英文深色       | [前](screenshots/chatgpt-style/before-guest-welcome-dark.png)  | [后](screenshots/chatgpt-style/after-guest-welcome-dark.png)  |
| 用户欢迎，桌面中文浅色       | [前](screenshots/chatgpt-style/before-user-welcome-light.png)  | [后](screenshots/chatgpt-style/after-user-welcome-light.png)  |
| admin 未选用户，桌面英文深色 | [前](screenshots/chatgpt-style/before-admin-welcome-dark.png)  | [后](screenshots/chatgpt-style/after-admin-welcome-dark.png)  |
| 用户对话，桌面中文深色       | [前](screenshots/chatgpt-style/before-user-chat-dark.png)      | [后](screenshots/chatgpt-style/after-user-chat-dark.png)      |
| admin 对话，桌面英文浅色     | [前](screenshots/chatgpt-style/before-admin-chat-light.png)    | [后](screenshots/chatgpt-style/after-admin-chat-light.png)    |
| 游客欢迎，手机中文深色       | [前](screenshots/chatgpt-style/before-mobile-welcome-dark.png) | [后](screenshots/chatgpt-style/after-mobile-welcome-dark.png) |
| 用户对话，手机中文浅色       | [前](screenshots/chatgpt-style/before-mobile-chat-light.png)   | [后](screenshots/chatgpt-style/after-mobile-chat-light.png)   |

其他证据：[桌面折叠](screenshots/chatgpt-style/desktop-collapsed.png)、[手机抽屉](screenshots/chatgpt-style/drawer-390.png)、[欢迎页键盘模拟](screenshots/chatgpt-style/welcome-keyboard-390.png)、[对话键盘模拟](screenshots/chatgpt-style/simulated-keyboard-390.png)、[横屏](screenshots/chatgpt-style/landscape-844.png)、[安全区](screenshots/chatgpt-style/safe-area-390.png)、[横屏弹窗安全区](screenshots/chatgpt-style/modal-landscape-safe-area.png)。全部 12 组手机欢迎和对话截图保存在同目录。

## 原有警告与未验证项

生产构建仍提示共享 `(app)/+layout.svelte` 没有 slot/render：本项目的两个页面文件本来就是空占位，共享 Chat 由 layout 持有，这也是编辑器跨路由不被重建的现有结构。本次未改该文件。现有 Markdown/语法高亮等主包仍触发 >500kB 的构建提示；本次没有新增运行依赖，也未为 UI 优化调整分包。后端 11 条警告来自现有 FastAPI/Starlette、SQLAlchemy、Alembic 和迁移反射。

没有真机 iPhone/Android、Safari/Firefox 或真实系统输入法环境，因此浏览器原生工具栏、刘海/安全区、软键盘和旋转只做 Chrome 模拟，不声称真机已消除全部空白或黑边。组合事件测试验证防误发逻辑，不能替代真实中文键盘选词。未调用真实 Google OAuth 或 OpenAI 自动标题服务，也未进行真实 PWA 安装；相应实现保持不变。

## 复验方式

先按 `scripts/ui-fixture.py` 创建独立临时数据，再按原 [UI 报告](CHATLDT_UI_POLISH.md#运行与复验) 启动隔离后端。前端设置 `WEBUI_BACKEND_URL` 指向该后端；后端 `PUBLIC_ORIGIN`/`ALLOWED_ORIGINS` 必须包含实际测试前端地址。不要让测试脚本连接真实用户实例。

设置 `CHATLDT_BROWSER_URL`、`CHATLDT_BROWSER_CREDENTIALS_FILE`、`PLAYWRIGHT_CHROMIUM_EXECUTABLE` 和可选 `CHATLDT_TEST_ARTIFACTS` 后依次运行四套浏览器检查，避免共用测试账号的语言偏好相互干扰。手机录屏需安装 Playwright ffmpeg；本轮依赖下载在临时目录，通过 `PLAYWRIGHT_BROWSERS_PATH` 指定，不改项目运行依赖。截图工具先运行 `node scripts/chat-style-captures.mjs before`，修改后再运行 `after`，保留同一个 artifacts 目录和 fixture。

## Modern Web Guidance

采用 `responsive-design` 的 “Use dynamic viewport units” 与 clamp 字体范围建议：保留原 VisualViewport/动态高度降级，欢迎语字号有上下限，避免键盘和浏览器栏改变可用空间时出现固定高度空白。检索的 `scroll-position-aware-elements` 中 scroll-state queries 尚不支持 Safari/Firefox；本项目的底部跟随还需要保存用户阅读意图，因此使用 ResizeObserver 与滚动位置状态，未采用仅 CSS 显隐方案。
