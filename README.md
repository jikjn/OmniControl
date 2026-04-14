# OmniControl

OmniControl 是一个能力优先的软件适配框架。它不复制 `CLI-Anything` 的重型 7 阶段生成链，而是把流程拆成三层核心决策：

1. `Capability Detector`
   先判断目标软件暴露了哪些控制面。
2. `Adapter Planner`
   在 `native script / plugin / CLI / file-format / UIA/AX / CDP / vision fallback` 之间选最稳的主适配器和回退链。
3. `Language Selector`
   按平台、控制面和任务需求选择最合适的脚本语言。

首版重点是打通“检测、规划、模板生成”，默认产出轻量 manifest 和脚本骨架，而不是一上来就生成厚 CLI、REPL、undo/redo。

## 核心原则

- 控制面优先，不再默认源码优先。
- 真值验证优先，不只关心“能不能控”，还关心“怎么验证成功”。
- 默认薄适配，按需加厚。
- 脚本语言按需求决策，而不是所有事情都用一种语言硬做。

## 通用执行策略

通用策略文档在 [EXECUTION_STRATEGY.md](/C:/Users/33032/Downloads/OmniControl/docs/EXECUTION_STRATEGY.md:1)。

闭源软件的后台优先接入约束在 [BACKGROUND_FIRST_POLICY.md](/C:/Users/33032/Downloads/OmniControl/docs/BACKGROUND_FIRST_POLICY.md:1)。

通用后台 transport 设计在 [GENERIC_BACKGROUND_TRANSPORTS.md](/C:/Users/33032/Downloads/OmniControl/docs/GENERIC_BACKGROUND_TRANSPORTS.md:1)。

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

当前已经实测跑通两个真实 smoke profile：

```bash
python -m omnicontrol smoke word-export --source "C:\Users\33032\Downloads\环境物理.docx" --json
python -m omnicontrol smoke word-write --json
python -m omnicontrol smoke chrome-cdp --json
python -m omnicontrol smoke chrome-form-write --json
python -m omnicontrol smoke everything-search --query "environment-physics.pdf" --json
python -m omnicontrol smoke illustrator-export --json
python -m omnicontrol smoke masterpdf-pagedown --source "C:\Users\33032\Downloads\OmniControl\smoke-output\word-export\environment-physics.pdf" --json
python -m omnicontrol smoke quark-cdp --json
python -m omnicontrol smoke quark-cdp-write --json
python -m omnicontrol smoke trae-open --source "C:\Users\33032\Downloads\OmniControl" --json
python -m omnicontrol smoke cadv-view --source "C:\Program Files (x86)\CadViewerVE\Sample\示例图1.dwg" --json
python -m omnicontrol smoke nx-diagnose --json
python -m omnicontrol smoke isight-diagnose --json
python -m omnicontrol smoke ue-diagnose --json
```

它们分别验证：

- `word-export`
  - 用 PowerShell + Word COM 打开本地 `.docx`
  - 导出为 PDF
  - 验证输出文件存在、大小大于 0、magic bytes 为 `%PDF-`
- `chrome-cdp`
  - 用独立 profile 启动 Chrome `--remote-debugging-port`
  - 用 Node 内置 `fetch` + `WebSocket` 直连 CDP
  - 打开 `data:` 页面，读取 `document.title`，并保存截图
- `chrome-form-write`
  - 用 CDP 打开带 textarea 的页面
  - 真实写入文本和值标记
  - 读回 DOM 状态并截图
- `everything-search`
  - 用 `Everything.exe -new-window -search <query>` 打开临时搜索窗口
  - 用 UIA 读取窗口标题和状态栏
  - 验证搜索匹配数和首个匹配项
- `illustrator-export`
  - 用 Illustrator COM 附着官方脚本面
  - 新建矢量文档并导出 SVG
  - 验证输出文件存在且包含 `<svg`
- `masterpdf-pagedown`
  - 用 MasterPDF 打开 PDF
  - 发送 `PageDown`
  - 尝试对比翻页前后窗口截图，判断是否拿到稳定页面变化
- `quark-cdp`
  - 用 Quark 自己的 `--remote-debugging-port`
  - 附着其内部页面 target
  - 读取真实页面标题和 `uccd://...` 地址
- `quark-cdp-write`
  - 附着 Quark 内部页面
  - 真实写入页面标题和标记变量
  - 再次读回确认写入成功
- `trae-open`
  - 用官方 CLI 在隔离 `user-data-dir` 下打开工作区
  - 验证窗口、进程命令行和隔离配置目录
- `cadv-view`
  - 用 `CAD看图编辑王` 打开内置 `.dwg` 样例
  - 验证正确窗口已被拉起
- `nx-diagnose`
  - 跑 `run_journal.exe -help`
  - 真实尝试官方 NXOpen Python 样例
  - 如果 NXOpen 路径被许可/UFUN 挡住，再 pivot 到 `display_nx_help.exe -help`，把结果记成结构化 `partial`
- `isight-diagnose`
  - 跑 `fipercmd -help`
  - 真实尝试本地 `.zmf` 示例
  - 如果真实模型路径被 profile / DSLS 挡住，再 pivot 到 `fiperenv.bat && fipercmd.bat help`，把结果记成结构化 `partial`
- `ue-diagnose`
  - 预检 `UnrealEditor(.exe/-Cmd)` 与 `BuildPatchTool`
  - 真实尝试 `UnrealEditor.exe -help`
  - 把重型引擎启动超时转成结构化 `blocked`

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
- [UE Diagnose Result](/C:/Users/33032/Downloads/OmniControl/smoke-output/ue-diagnose/result.json)
- [Effect Report](/C:/Users/33032/Downloads/OmniControl/smoke-output/EFFECT_REPORT.md)

## 当前边界

首版是 MVP，不会直接实现完整 UI 自动化、CDP 客户端或 hook 注入，而是先把决策和生成层做实。后续可以在不改 CLI 入口的前提下继续加厚 runtime、registry、truth collectors 和真实 adapter。

## Latest Coverage

新增的通用能力：

- `adaptive_startup`
  - 自动决定附着已有实例、注入调试端口重启、或隔离 user-data 启动
- `orchestrator`
  - 统一 preflight / attempts / blocked 汇总
- `knowledge base`
  - 记录 blocked case、修复尝试和成功方案，并在后续运行中复用
- `selfdraw write probe`
  - 统一处理焦点、按键、截图前后差分，覆盖弱结构/自绘 UI 软件

最新新增的写入型成功案例：

- `Trae`：`trae-cdp-write`
- `MasterPDF`：`masterpdf-zoom`
- `CadViewerVE`：`cadv-zoom`
- `UE 5.7`：`ue-python-write`

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
- `UE 5.7`
  - `ue-diagnose`

最新新增的通用恢复动作：

- `drop_project_context`
  - 当项目级入口失败时，自动退回更小粒度的无项目命令面
