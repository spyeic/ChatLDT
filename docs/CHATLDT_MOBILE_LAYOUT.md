# ChatLDT 手机布局与交互修正

2026-11-16，基于现有 Fork 和全部既有未提交工作，在 `fix/mobile-chat-layout` 分支增量修改。保留此前 `https://eurse.me` 的配置与许可证决定；没有 commit、push、merge、同步上游或部署，没有新增运行时依赖、数据库迁移或修改真实账号/聊天数据。

## 原因与截图边界

提供的 iPhone 截图中，顶部时间/动态岛与底部含 `eurse.me` 的原生地址栏属于系统/浏览器区域，不能当作可删除的网页 div。截图物理像素没有用于推断 CSS 视口。右侧灰色悬浮控件未在当前源码或隔离浏览器 DOM 中出现，无法确认其具体宿主来源，没有删除、重画或模仿它。

修改前在 **390×844 CSS px 的 Chrome 移动模拟**中实际测量：

| 检查           | 修改前                                                      | 本次处理                                                                                                                          |
| -------------- | ----------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| html/body 背景 | 两者都是透明 `rgba(0,0,0,0)`                                | 与聊天画布统一为浅色 `#ffffff` / 深色 `#171717`，初始加载也设置相应背景，减少网页自身的颜色闪变/断层                              |
| theme-color    | 固定 `#0f766e`，没有跟随主题                                | 初始根据上次主题提示/系统主题设置，身份校验后以账号或游客偏好更新；manifest 默认浅色，图标保持原样                                |
| viewport       | 已有 `viewport-fit=cover` 与 `h-dvh`                        | 保留 cover；完善 vh/dvh 回退、明确唯一滚动容器、安全区与实际可见视口的处理，并非把旧问题笼统归因于 100vh                          |
| 欢迎语         | `30px`、`text-align:start`，图标与多行文字没有统一居中      | 图标 52px，文字实测 27.04–28.72px，1.3 行高，18px 间距；限制文字宽度并 `text-wrap:balance`，三种宽度英文均自然排为两行，无固定 br |
| 空输入区       | 外层 form 实测 166px                                        | 手机空白输入盒实测 96px（不含所需安全区）；文字增长后到上限内部滚动，至少 16px 字体、44px 上传/发送触摸目标                       |
| 手机侧边栏     | 固定 256px，`display:none` 立即关闭，没有遮罩               | 覆盖式抽屉，宽 `min(84vw,320px)`，230ms 位移动画与同步遮罩；完成退出后才隐藏，不挤压主页面                                        |
| 弹窗           | 源码已有 190/150ms CSS 过渡；静态照片不能证明设备上没有动画 | 保留统一 dialog，在不依赖 `@starting-style` 的显式入场状态下触发进入过渡；退出仍完成后关闭，尊重系统 reduced-motion               |

根背景与 theme-color 的改善只作用于网页及浏览器愿意采用的颜色提示。`theme-color` 是浏览器 UI 的**建议颜色**，无法强制原生工具栏透明、浮动或采用特定颜色，参见 [MDN theme-color](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/meta/name/theme-color)。没有伪造地址栏、隐藏系统 UI、固定预留“浏览器工具栏高度”或使用负 margin 把输入框推到工具栏后。

**没有物理 iPhone 或远程真机连接条件。本轮未验证真实 iPhone 浏览器的原生工具栏展开/收起、软键盘和不同 iOS 版本，不能声称消除了全部浏览器黑边。** 桌面模拟、视口高度变化和录屏不替代这项验收。

## 实现与关键文件

- `src/app.css`：统一根画布/主题与单一消息滚动区；手机触控目标、按下反馈。根 overflow 在应用生命周期固定，不在打开/关闭覆盖层时反复切换；只锁消息滚动容器，保持原 scrollTop。
- `src/app.html`：保留 viewport-fit=cover；在 Svelte 加载前设置背景和 theme-color。只缓存非敏感主题提示，不代替服务端身份与账号偏好校验。
- `src/routes/+layout.svelte`、`src/lib/utils/mobile-viewport.ts`：监听 VisualViewport resize/scroll、窗口与焦点变化。使用**测量的可见高度**而非从 dvh 再减一次键盘高度；系统已经缩小布局视口时不重复补偿，缩放比例变化时退出补偿以保留 pinch zoom。没有 API 时使用 CSS vh/dvh。参考 [MDN VisualViewport](https://developer.mozilla.org/en-US/docs/Web/API/VisualViewport)。
- `src/lib/components/chat/Chat.svelte`：手机布局、响应式居中欢迎组，仅首次欢迎显示短淡入；顶栏承担顶部/左右安全区，输入区承担底部安全区。横屏粗指针设备继续使用抽屉，不因 844px 横屏宽度强制切成桌面侧边栏。
- `src/lib/components/chat/MessageInput.svelte`：紧凑布局、`field-sizing:content`；不支持时由 CSS Grid 镜像文本提供增长回退；限制长文本和图片预览高度。上传、粘贴、图片草稿、发送/取消权限与 IME Enter 校验保留。
- `src/lib/components/common/ResponsiveDrawer.svelte`：复用同一个 Sidebar 内容。手机使用 manual Popover 顶层、inert、焦点约束/恢复、Esc、可点击遮罩，缺少 API 时采用 fixed 回退；桌面仍为常驻 256px 侧边栏。退出期间保留遮罩/模态状态，快速反向开关由序号消除迟到回调，不把已锁定的背景状态误存为原状态。
- `src/lib/components/layout/Sidebar.svelte`：接入抽屉、关闭按钮及底部安全区；侧边栏触发登录/设置前先完成抽屉关闭，避免父子覆盖层重复动画或焦点争夺。
- `src/lib/components/common/Modal.svelte`：补充可见视口内的手机高度限制、显式进入阶段；保留原生焦点、Esc、滚动、退出延迟与 reduced-motion。
- `src/lib/components/chat/Messages/Markdown.svelte`：为手机 44px 代码复制按钮保留足够的代码顶部空间。
- `static/chatldt-v1.webmanifest` 及兼容 manifest：默认 theme-color 由绿色改为浅色画布，图标与品牌归属未变。
- `src/lib/utils/mobile-viewport.test.ts`、`scripts/mobile-layout-smoke.mjs`：视口算法和真实 DOM 布局/交互检查；`npm run test:mobile` 为新统一入口。原浏览器脚本改为检查实际可见性，并在布局测量/退出动画断言前等待初始加载或进入动画完成。

安全区不叠加：聊天顶/左右 inset 由 chat-pane 计算一次；composer 仅计算底部 `max(8px,safe-area)`，不在 root 再加同一底部 padding；抽屉是独立覆盖层，自行计算其顶部与账号底部 inset。键盘缩小 VisualViewport 且输入控件聚焦时去除重复的底部 Home Indicator 留白。未在浏览器模拟中伪造 iPhone 状态栏或真实键盘。

## 已执行验证

全部账号、附件和会话测试使用独立临时 SQLite/数据目录和浏览器配置文件。现有 5173/8080 服务与真实账号未用于测试。

| 检查                                          | 结果                                                                                                                                                                                              |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm run check`                               | 0 errors / 0 warnings                                                                                                                                                                             |
| `npm run test:frontend`                       | 5 项通过：含 3 项视口测量、重复补偿与 pinch zoom 测试                                                                                                                                             |
| `.venv/bin/python -m pytest backend/tests -q` | 38 项通过；11 条现有 SQLAlchemy/Alembic 弃用/反射警告                                                                                                                                             |
| 现有 CI Ruff `--select F`                     | 通过                                                                                                                                                                                              |
| `npm run build`                               | 生产构建通过                                                                                                                                                                                      |
| `npm run test:mobile`                         | 12 组通过：360/390/430 CSS px × 中/英 × 深/浅色；欢迎页和有消息页面、长文本、多图、无横向溢出/根双滚动、抽屉不改变主页面几何、退出保留、反向快速开关、遮罩关闭、滚动位置恢复、登录弹窗、44px 目标 |
| 额外模拟                                      | 844×390 横屏与返回竖屏；可见高度 844→700→844 的工具栏尺寸变化；模拟 VisualViewport 340px 高和 80px offset 的键盘遮挡；缩放时停止补偿；缺少 VisualViewport/Popover 的回退；reduced-motion          |

可见高度/键盘检查是注入测量值或调整浏览器视口的逻辑验证，**没有实际打开 iPhone 原生键盘**。CSS safe-area 规则已审查并使用 Chromium 模拟值验证；真实刘海/Home Indicator 的数值、Safari 原生工具栏的绘制效果、旧 Safari 上 field-sizing 回退以及已安装 PWA 的系统表现仍需真机复验。

原聊天与 UI 回归的最终结果记录于同目录 `screenshots/mobile/validation.txt`，包括管理员名称/双方视角、编辑权限、完整 Markdown 复制与降级、轮次取消、游客草稿/迁移、图片/粘贴、未读相关实时刷新与断线恢复。未运行的设备/浏览器不计为通过。

## 截图与录屏

下列均为 CSS 视口截图，不含真实 iPhone 系统/浏览器栏：

- [修改前欢迎页 390](screenshots/mobile/before-welcome-390.png) / [修改后欢迎页 390 深色英文](screenshots/mobile/welcome-390-en-US-dark.png)
- [修改前侧边栏](screenshots/mobile/before-sidebar-390.png) / [修改后抽屉](screenshots/mobile/drawer-390.png)
- [360 中文浅色](screenshots/mobile/welcome-360-zh-CN-light.png) / [430 英文浅色](screenshots/mobile/welcome-430-en-US-light.png)
- [有消息及多图草稿](screenshots/mobile/chat-390-en-US-dark.png) / [横屏](screenshots/mobile/landscape-844.png)
- [模拟键盘可见区域](screenshots/mobile/simulated-keyboard-390.png)：底部不是实际键盘，不作为系统 UI 的截图。
- [手机交互短录屏 WebM](screenshots/mobile/mobile-demo.webm)：欢迎淡入、抽屉与遮罩、登录弹窗、输入与视口模拟。来自桌面 Chrome 移动模拟。
- [模拟竖屏安全区](screenshots/mobile/safe-area-390.png) / [横屏安全区弹窗](screenshots/mobile/modal-landscape-safe-area.png)：Chromium CDP 模拟，不是真实 iPhone。
- [12 组测量原始数据](screenshots/mobile/measurements.json)：所有空输入盒均为 96px，根/页面/聊天背景一致。

## 复验方法与真机清单

使用 Node 22、Python 3.11/3.12，常规开发/生产入口保持不变。`https://eurse.me` 的 `.env` 仍保留此前设置，没有发布或修改远程服务。真机检查需在你自行更新运行实例后执行。

```sh
npm run check
npm run test:frontend
npm run test:backend
npm run build
# 以下必须使用独立测试数据，脚本会创建测试会话与附件：
.venv/bin/python scripts/ui-fixture.py
# 按输出路径设置 CHATLDT_FIXTURE，启动本地隔离后端，见 CHATLDT_UI_POLISH.md。
# Playwright 视频编码器是开发检查工具，不是运行时依赖：
npx playwright install ffmpeg
CHATLDT_BROWSER_URL=http://127.0.0.1:8091 \
CHATLDT_BROWSER_CREDENTIALS_FILE="$CHATLDT_FIXTURE/credentials.json" \
PLAYWRIGHT_CHROMIUM_EXECUTABLE='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
npm run test:mobile
```

真机复验：使用 Safari/当前截图所用 iPhone 浏览器分别在中英、深浅主题下打开欢迎页与长聊天；展开/收起原生地址栏；打开/关闭键盘，输入多行、切换聊天、选择多图；开关抽屉与弹窗、旋转屏幕；再打开系统“减少动态效果”重复一次。检查输入框始终位于可见区域、Home Indicator 附近可触控、没有重复安全区空白；记录浏览器与 iOS 版本。此清单是尚未执行项目，不能用模拟结果代替。

## 实现参考

本次重新检索并完整读取 modern-web-guidance 的 `responsive-design`、`navigation-drawer`、`form-fields-automatically-fit-contents`、`prevent-page-scroll-under-modal-dialog`。采用动态视口与 clamp 字号、Popover 手动模态/焦点、先退出再隐藏、field-sizing 与增长回退、内部滚动约束。本次依用户要求选择 230ms transform 抽屉，不引入未要求的整套滑动手势或动画依赖。关键规则分别为 “Use dynamic viewport units”、 “Mark the rest of the page `inert` while the drawer is open”、 “apply an explicit width (like `width: 100%`)” 和不要在弹窗开合时修改根节点 overflow。
