# OmniControl

OmniControl 是一个能力优先的软件适配框架。它不复制 `CLI-Anything` 的重型 7 阶段生成链，而是把流程拆成三层核心决策：

1. `Capability Detector`
   先判断目标软件暴露了哪些控制面。
2. `Adapter Planner`
   在 `native script / plugin / CLI / file-format / UIA/AX / CDP / vision fallback` 之间选最稳的主适配器和回退链。
3. `Language Selector`
   按平台、控制面和任务需求选择最合适的脚本语言。

早期版本重点是打通“检测、规划、模板生成”。当前版本已经在不改变 CLI 入口的前提下加厚了 runtime smoke、策略 pivot、知识库复用和一批真实闭源软件 adapter；默认 scaffold 仍保持轻量，不强制生成厚 CLI、REPL、undo/redo。

## 核心原则

- 控制面优先，不再默认源码优先。
- 真值验证优先，不只关心“能不能控”，还关心“怎么验证成功”。
- 默认薄适配，按需加厚。
- 脚本语言按需求决策，而不是所有事情都用一种语言硬做。

## 通用执行策略

通用策略文档在 [EXECUTION_STRATEGY.md](/C:/Users/33032/Downloads/OmniControl/docs/EXECUTION_STRATEGY.md:1)。

闭源软件的后台优先接入约束在 [BACKGROUND_FIRST_POLICY.md](/C:/Users/33032/Downloads/OmniControl/docs/BACKGROUND_FIRST_POLICY.md:1)。

通用后台 transport 设计在 [GENERIC_BACKGROUND_TRANSPORTS.md](/C:/Users/33032/Downloads/OmniControl/docs/GENERIC_BACKGROUND_TRANSPORTS.md:1)。

Sidecar / secondary control plane 的一等结果语义在 [SIDECAR_CONTROL_PLANE_UPDATE.md](/C:/Users/33032/Downloads/OmniControl/docs/SIDECAR_CONTROL_PLANE_UPDATE.md:1)。

核心不是给某个软件打补丁，而是统一：

- `ok / partial / blocked / error` 状态机
- `required / desired` 合同式验证
- blocker 分类与 recovery hints
- evidence 采集格式

## 自演化知识库

运行时知识库在 [kb.json](/C:/Users/33032/Downloads/OmniControl/knowledge/kb.json:1)。

它会自动记录：

- blocked case
- remediation attempts
- verified solution
- launch_overrides

当前已经能做到：

- 先跑一次真实任务
- 把成功方案写进 `kb.json`
- 下次运行时读出最相近的方案并作为启动偏好

目前已验证的一条闭环是 `quark-cdp-write`：

- 第一次运行写入成功后，知识库保存 `restart_with_debug_port`
- 第二次运行时，`learned_overrides` 已经会读回这个偏好

## 支持的语言决策

| 场景 | 优先语言 | 原因 |
| --- | --- | --- |
| Windows UIA / COM / Office / 桌面编排 | PowerShell | 原生系统自动化和管理能力强 |
| Web / CDP / Electron / 浏览器 DOM | TypeScript | Node 生态和 DevTools 协议贴合 |
| 文件格式处理 / 跨平台编排 / 数据转换 | Python | 标准库和跨平台能力稳 |
| 现有 CLI 胶水层 | Bash 或 PowerShell | 直接包命令管道最轻 |
| macOS 原生 App 脚本化 | AppleScript | 对 Finder、System Events、脚本化 app 贴合 |
| 深 Windows 原生 provider / ETW / hook | C# | 原生 API 绑定与类型系统更稳 |

## 快速开始

```bash
cd C:\Users\33032\Downloads\OmniControl
python -m omnicontrol detect "Excel" --platform windows --kind desktop --need office --need export
python -m omnicontrol plan "http://localhost:3000" --kind web --need browser --need dom
python -m omnicontrol scaffold "LegacyDesktopApp" --platform windows --kind desktop --need ui --need export --output .\generated\legacy-app
```

JSON 输出：

```bash
python -m omnicontrol plan "report.docx" --platform windows --need export --json
```

## 命令

- `detect`
  输出控制面探测结果。
- `plan`
  输出主适配器、回退链、语言选择、状态模型、验证策略和建议动作。
- `scaffold`
  生成 `manifest.json`、`SKILL.md`、脚本模板和验证模板。
- `benchmark`
  批量读取 JSON 配置，对一组本地软件样本执行 `detect + plan + scaffold`，输出基准报告。
- `smoke`
  对少量高价值本地目标执行真实 runtime smoke，而不是只做 detect/plan。

## 本地闭源基准

项目内置了一份 Windows 本地闭源样本配置：

```bash
python -m omnicontrol benchmark .\benchmarks\local_closed_source_windows.json --json
```

当前这份基准覆盖：

- Adobe Illustrator 2025：官方脚本/插件面
- Microsoft Office：COM/原生脚本面
- `.docx` 文档：文件格式旁路面
- Siemens NX：原生 SDK / Python 自动化面
- SIMULIA Isight：结构化 API / SDK 面
- Quark：Electron / CDP 面
- WeChat：UIA / 桌面对象面
- CadViewerVE：弱结构桌面面，回退到 `UIA + vision fallback`

## Real Smoke

当前已经覆盖多类真实 smoke profile，既包含读/导出，也包含写入、工作流和诊断型入口：

```bash
python -m omnicontrol smoke word-export --source "C:\Users\33032\Downloads\环境物理.docx" --json
python -m omnicontrol smoke word-write --json
python -m omnicontrol smoke word-workflow --json
python -m omnicontrol smoke chrome-cdp --json
python -m omnicontrol smoke chrome-form-write --json
python -m omnicontrol smoke chrome-workflow --json
python -m omnicontrol smoke everything-search --query "environment-physics.pdf" --json
python -m omnicontrol smoke qqmusic-play --query "周杰伦" --json
python -m omnicontrol smoke illustrator-export --json
python -m omnicontrol smoke masterpdf-pagedown --source "C:\Users\33032\Downloads\OmniControl\smoke-output\word-export\environment-physics.pdf" --json
python -m omnicontrol smoke masterpdf-zoom --source "C:\Users\33032\Downloads\OmniControl\smoke-output\word-export\environment-physics.pdf" --json
python -m omnicontrol smoke masterpdf-workflow --source "C:\Users\33032\Downloads\OmniControl\smoke-output\word-export\environment-physics.pdf" --json
python -m omnicontrol smoke quark-cdp --json
python -m omnicontrol smoke quark-cdp-write --json
python -m omnicontrol smoke quark-workflow --json
python -m omnicontrol smoke trae-open --source "C:\Users\33032\Downloads\OmniControl" --json
python -m omnicontrol smoke trae-cdp-write --source "C:\Users\33032\Downloads\OmniControl" --json
python -m omnicontrol smoke trae-workflow --source "C:\Users\33032\Downloads\OmniControl" --json
python -m omnicontrol smoke cadv-view --source "C:\Program Files (x86)\CadViewerVE\Sample\示例图1.dwg" --json
python -m omnicontrol smoke cadv-zoom --source "C:\Program Files (x86)\CadViewerVE\Sample\示例图1.dwg" --json
python -m omnicontrol smoke cadv-workflow --source "C:\Program Files (x86)\CadViewerVE\Sample\示例图1.dwg" --json
python -m omnicontrol smoke nx-diagnose --json
python -m omnicontrol smoke isight-diagnose --json
```

它们分别验证：

- `word-export`
  - 用 PowerShell + Word COM 打开本地 `.docx`
  - 导出为 PDF
  - 验证输出文件存在、大小大于 0、magic bytes 为 `%PDF-`
- `word-write` / `word-workflow`
  - 用 Word COM 新建/写入 `.docx`
  - 验证 DOCX ZIP 结构和正文 marker
- `chrome-cdp`
  - 用独立 profile 启动 Chrome `--remote-debugging-port`
  - 用 Node 内置 `fetch` + `WebSocket` 直连 CDP
  - 打开 `data:` 页面，读取 `document.title`，并保存截图
- `chrome-form-write`
  - 用 CDP 打开带 textarea 的页面
  - 真实写入文本和值标记
  - 读回 DOM 状态并截图
- `chrome-workflow`
  - 用同一 CDP 管道执行多步写入
  - 每一步都读回 title / marker 验证状态推进
- `everything-search`
  - 用 `Everything.exe -new-window -search <query>` 打开临时搜索窗口
  - 用 UIA 读取窗口标题和状态栏
  - 验证搜索匹配数和首个匹配项
- `qqmusic-play`
  - 优先使用 QQMusic 的软件原生命令/协议面
  - 记录 transport plan、命令尝试、runtime auth 信息和播放验证结果
- `illustrator-export`
  - 用 Illustrator COM 附着官方脚本面
  - 新建矢量文档并导出 SVG
  - 验证输出文件存在且包含 `<svg`
- `masterpdf-pagedown`
  - 用 MasterPDF 打开 PDF
  - 发送 `PageDown`
  - 尝试对比翻页前后窗口截图，判断是否拿到稳定页面变化
- `masterpdf-zoom` / `masterpdf-workflow`
  - 面向弱结构/自绘 UI 走按键 + 截图差分
  - 验证缩放、翻页等连续操作是否真实改变界面
- `quark-cdp`
  - 用 Quark 自己的 `--remote-debugging-port`
  - 附着其内部页面 target
  - 读取真实页面标题和 `uccd://...` 地址
- `quark-cdp-write`
  - 附着 Quark 内部页面
  - 真实写入页面标题和标记变量
  - 再次读回确认写入成功
- `quark-workflow`
  - 在 Quark CDP 面执行多步写入
  - 使用 target selection 和 marker 读回确认每一步
- `trae-open`
  - 用官方 CLI 在隔离 `user-data-dir` 下打开工作区
  - 验证窗口、进程命令行和隔离配置目录
- `trae-cdp-write` / `trae-workflow`
  - 附着 Trae / VS Code 系 WebView CDP 面
  - 执行单步或三步连续写入，并读回 marker
- `cadv-view`
  - 用 `CAD看图编辑王` 打开内置 `.dwg` 样例
  - 验证正确窗口已被拉起
- `cadv-zoom` / `cadv-workflow`
  - 面向 CAD 自绘窗口执行缩放/工作流按键
  - 用截图差分验证界面变化
- `nx-diagnose`
  - 跑 `run_journal.exe -help`
  - 真实尝试官方 NXOpen Python 样例
  - 如果 NXOpen 路径被许可/UFUN 挡住，再 pivot 到 `display_nx_help.exe -help`，把结果记成结构化 `partial`
- `isight-diagnose`
  - 跑 `fipercmd -help`
  - 真实尝试本地 `.zmf` 示例
  - 如果真实模型路径被 profile / DSLS 挡住，再 pivot 到 `fiperenv.bat && fipercmd.bat help`，把结果记成结构化 `partial`
本轮实测产物：

- [Word Smoke PDF](/C:/Users/33032/Downloads/OmniControl/smoke-output/word-export/environment-physics.pdf)
- [Word Write DOCX](/C:/Users/33032/Downloads/OmniControl/smoke-output/word-write/word-write-smoke.docx)
- [Chrome Smoke Screenshot](/C:/Users/33032/Downloads/OmniControl/smoke-output/chrome-cdp/screenshot.png)
- [Chrome Form Write Screenshot](/C:/Users/33032/Downloads/OmniControl/smoke-output/chrome-form-write/screenshot.png)
- [Chrome PDF Screenshot](/C:/Users/33032/Downloads/OmniControl/smoke-output/chrome-pdf/screenshot.png)
- [Illustrator Smoke SVG](/C:/Users/33032/Downloads/OmniControl/smoke-output/illustrator-export/illustrator-smoke.svg)
- [MasterPDF Before](/C:/Users/33032/Downloads/OmniControl/smoke-output/masterpdf-pagedown/before.png)
- [MasterPDF After](/C:/Users/33032/Downloads/OmniControl/smoke-output/masterpdf-pagedown/after.png)
- [Quark Result](/C:/Users/33032/Downloads/OmniControl/smoke-output/quark-cdp/result.json)
- [Quark Write Result](/C:/Users/33032/Downloads/OmniControl/smoke-output/quark-cdp-write/result.json)
- [Trae Result](/C:/Users/33032/Downloads/OmniControl/smoke-output/trae-open/result.json)
- [CadViewer Result](/C:/Users/33032/Downloads/OmniControl/smoke-output/cadv-view/result.json)
- [NX Diagnose Result](/C:/Users/33032/Downloads/OmniControl/smoke-output/nx-diagnose/result.json)
- [Isight Diagnose Result](/C:/Users/33032/Downloads/OmniControl/smoke-output/isight-diagnose/result.json)
- [Effect Report](/C:/Users/33032/Downloads/OmniControl/smoke-output/EFFECT_REPORT.md)

## 当前边界

当前已经不只是 MVP 的决策/生成层：项目里已经有真实 runtime smoke、CDP 直连、UIA/COM/原生脚本、弱结构截图差分、策略 pivot、知识库复用和脚本 payload 文件化传输。

仍然保留的边界是：

- 这不是通用 RPA 产品，不承诺对任意 GUI 自动发现控件并完成全流程。
- CDP 目前是面向 smoke/profile 的轻量客户端能力，不是完整 DevTools SDK 封装。
- 没有做进程内 hook 注入、二进制 patch 或内存级侵入。
- 每个真实 adapter 仍以 profile + contract 的方式逐步加厚，先保证可观测、可复现、可判断 `ok / partial / blocked / error`。
- 对复杂脚本和闭源软件命令入口，默认优先使用脚本文件、response file 或 argv list，避免把长脚本内联进单个命令行参数。

## 最新覆盖

新增的通用能力：

- `adaptive_startup`
  - 自动决定附着已有实例、注入调试端口重启、或隔离 user-data 启动
- `orchestrator`
  - 统一 preflight / attempts / blocked 汇总
- `knowledge base`
  - 记录 blocked case、修复尝试和成功方案，并在后续运行中复用
- `selfdraw write probe`
  - 统一处理焦点、按键、截图前后差分，覆盖弱结构/自绘 UI 软件
- `script payload transport`
  - 把包含空格、分号、引号、换行、非 ASCII 或超长内容的脚本先 materialize 成文件
  - 支持 `-script=<file>`、`--script <file>`、response file 等闭源软件常见入口

最新新增的写入型成功案例：

- `Trae`：`trae-cdp-write`
- `MasterPDF`：`masterpdf-zoom`
- `CadViewerVE`：`cadv-zoom`

最新新增的复杂交互成功案例：

- `MasterPDF`：`masterpdf-workflow`
  - 两次缩放 + 一次翻页，全部步骤都已验证
- `Trae`：`trae-workflow`
  - 三步连续写入，逐步读回标题和 marker

最新新增的 diagnose / partial 案例：

- `NX`
  - `display_nx_help.exe -help`
- `Isight`
  - `fiperenv.bat && fipercmd.bat help`
最新新增的通用恢复动作：

- `drop_project_context`
  - 当项目级入口失败时，自动退回更小粒度的无项目命令面
