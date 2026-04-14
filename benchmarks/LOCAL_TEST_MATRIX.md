# Local Closed-Source Test Matrix

这份矩阵分两层：

1. 已经通过 `OmniControl benchmark` 跑过的本地闭源类型样本
2. 下一批适合做真实 adapter / live smoke 的高优先级目标

当前基准报告：

- JSON 报告：`benchmark-output/local_closed_source_windows/benchmark-report.json`
- 结果摘要：8 个本地样本，`primary_matches=8`，`language_matches=8`

## Benchmarked Now

| Sample | Local Target | Category | Current Primary | Fallback Order | Language | Meaning |
| --- | --- | --- | --- | --- | --- | --- |
| Illustrator 2025 | `C:\Program Files\Adobe\Adobe Illustrator 2025` | official script/plugin | `native_script` | `plugin -> uiautomation -> file_format -> vision` | `javascript` | 已确认官方脚本/插件型闭源桌面可被正确识别 |
| Microsoft Office | `C:\Program Files\Microsoft Office` | COM / native script | `native_script` | `uiautomation -> file_format -> vision` | `powershell` | 已确认 Office/COM 场景会优先走原生脚本面 |
| `.docx` 文档 | `C:\Users\33032\Downloads\环境物理.docx` | file-format bypass | `file_format` | `vision` | `python` | 已确认文件格式层会绕开 GUI，直接走文档处理 |
| Siemens NX | `C:\Program Files\Siemens\NX1953` | native SDK / heavy desktop | `native_script` | `plugin -> uiautomation -> vision` | `python` | 已确认 UGOPEN / automated testing / Python 痕迹能被识别 |
| SIMULIA Isight | `C:\SIMULIA\Isight\2021` | structured API / SDK | `api` | `uiautomation -> vision` | `python` | 已确认安装目录 API 文档可触发结构化接口路线 |
| Quark | `C:\Users\33032\AppData\Local\Programs\Quark` | Electron / CDP | `cdp` | `existing_cli -> plugin -> uiautomation -> vision` | `typescript` | 已确认 Electron/Chromium 桌面壳可优先走 CDP |
| WeChat | `C:\Program Files\Tencent\WeChat` | UIA desktop | `uiautomation` | `cdp -> vision` | `powershell` | 已确认“带 Chromium 组件但无明显 Electron bundle”的桌面客户端不会被误判成强 CDP |
| CadViewerVE | `C:\Program Files (x86)\CadViewerVE` | weak surface | `uiautomation` | `vision` | `powershell` | 已确认弱结构闭源桌面会走 `UIA + vision fallback` |
| Quark | `C:\Users\33032\AppData\Local\Programs\Quark\quark.exe` | Electron / CDP | `cdp` | `existing_cli -> plugin -> uiautomation -> vision` | `typescript` | 已真实附着内部页面并读取 `uccd://` 页面标题/地址 |
| Trae | `C:\Users\33032\AppData\Local\Programs\Trae` | CLI + isolated desktop | `existing_cli` or `cdp` candidate | `uiautomation -> vision` | `powershell` | 已真实用 CLI 在隔离 user-data 下打开工作区 |

## Next Live Smoke

这些目标还没进入真实 adapter 执行阶段，但已经适合按下面顺序做 live smoke：

### Chrome

- Target: `C:\Program Files\Google\Chrome\Application\chrome.exe`
- Planned control order: `cdp -> existing_cli -> vision`
- Planned language: `typescript`
- First 3 smoke cases:
  - 打开 3 个标签页，切换并读取标题
  - 导航到本地 PDF 或设置页并读取 DOM 关键节点
  - 触发下载或文件上传对话流程并验证事件链
- Risk:
  - 会触发真实浏览器状态变更
  - 需要隔离 profile，避免污染当前用户会话

### Trae

- Target: `C:\Users\33032\AppData\Local\Programs\Trae`
- Planned control order: `cdp -> existing_cli -> uiautomation -> vision`
- Planned language: `typescript`
- First 3 smoke cases:
  - 打开工作区并读取当前窗口标题
  - 打开命令面板并搜索命令
  - 打开终端并验证命令执行回显
- Risk:
  - 可能改动当前 IDE 会话状态
  - 若直接操控用户工作区，需要隔离测试目录

### MasterPDF

- Target: `C:\Program Files (x86)\MasterPDF\MasterPDF.exe`
- Planned control order: `uiautomation -> file_format -> existing_cli -> vision`
- Planned language: `powershell`
- First 3 smoke cases:
  - 打开 PDF 并定位页码输入框/缩放控件
  - 翻页、搜索文本、读取窗口状态
  - 导出或另存为到临时目录并验证文件生成
- Risk:
  - UI 名称和控件层级可能随版本变化
  - 真正的 PDF 结构验证仍要靠输出文件检查

Status now:

- 已实测稳定打开指定 PDF 并定位正确窗口
- `PageDown` 翻页动作仍不稳定，截图差分有波动

### NX

- Target: `C:\Program Files\Siemens\NX1953`
- Planned control order: `native_script -> api -> uiautomation -> vision`
- Planned language: `python`
- Status now:
  - `run_journal.exe -help` 已真实成功
  - 官方样例 `ValidateNXOpenSetup.py` 已真实尝试，但失败于 `failed to initialize UFUN 949885`
- Current blocker:
  - 许可/UFUN 初始化

### SIMULIA Isight

- Target: `C:\SIMULIA\Isight\2021`
- Planned control order: `api -> uiautomation -> vision`
- Planned language: `python`
- Status now:
  - `fipercmd -help` 已真实成功
  - `fipercmd contents ...I_Beam.zmf -nogui` 已真实尝试，但失败于 `A connection profile is required for logon`
- Current blocker:
  - connection profile / DSLS 初始化

### Everything

- Target: `C:\Program Files\Everything\Everything.exe`
- Planned control order: `uiautomation -> existing_cli -> vision`
- Planned language: `powershell`
- First 3 smoke cases:
  - 聚焦搜索框并输入关键字
  - 读取结果列表并验证首项
  - 切换排序或过滤条件并观察结果变化
- Risk:
  - 结果集依赖本机索引实时状态
  - 需要避免把真实用户搜索上下文当成测试基线

### FileZilla

- Target: `C:\Program Files\FileZilla FTP Client\filezilla.exe`
- Planned control order: `uiautomation -> existing_cli -> vision`
- Planned language: `powershell`
- First 3 smoke cases:
  - 打开站点管理器并读取树结构
  - 在本地文件面板切换目录
  - 不连接远程，只验证多面板焦点和日志区域更新
- Risk:
  - 一旦接入真实远程站点就有网络副作用
  - 表格控件和树控件可能需要更细粒度 UIA 模式

### MobaXterm

- Target: `C:\Program Files (x86)\Mobatek\MobaXterm\MobaXterm.exe`
- Planned control order: `uiautomation -> existing_cli -> vision`
- Planned language: `powershell`
- First 3 smoke cases:
  - 打开本地终端 tab
  - 粘贴命令并验证终端回显
  - 滚动终端历史并检查文本可见性
- Risk:
  - 终端区域很可能最终要落到视觉或 OCR 辅助
  - 文本读取和焦点同步会比普通桌面控件更脆弱

## Interpretation

- 当前 `OmniControl` 已经可以可靠做“控制面探测 + 适配器规划 + 语言决策 + scaffold 生成”。
- 当前还没有真实 UIA runtime、真实 CDP client、真实 COM / AppleScript / hook bridge，所以这份矩阵代表的是“接入准备度”，不是“动作已经被软件真实执行成功”。
- 例外是以下几类已经进入真实执行层：
  - `Word COM`
  - `Word 写入并保存 DOCX`
  - `Chrome CDP`
  - `Chrome DOM 写入`
  - `Everything 搜索`
  - `Illustrator 官方脚本面`
  - `MasterPDF 打开指定 PDF`
  - `Quark CDP`
  - `Quark 页面写入`
  - `Trae CLI`
  - `CadViewerVE 打开图纸`
- 真正进入深度验证时，最应该优先做的顺序是：
  - `Office`
  - `Illustrator`
  - `Chrome`
  - `Trae`
  - `MasterPDF`
  - `NX`
