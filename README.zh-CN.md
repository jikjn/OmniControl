# OmniControl

[English](./README.md) | 简体中文

> **GUI离死期不远了！💀🖥️ 自动化，不该停在 SDK 结束的地方。**
>
> 大多数软件从来不是为自动化设计的。  
> 它们没有完美 API，没有完整插件，没有统一脚本入口。  
> 但这不代表它们不能被接入。
>
> **OmniControl** 让自动化系统先识别目标暴露了什么控制面，再选择最稳的执行路径、回退链和验证方式。
     
---

## OmniControl 是什么 🚀

OmniControl 是一个**控制面优先（control-surface-first）**的自动化控制层与脚手架。

它不预设某一种自动化栈，也不假设所有目标都会友好地暴露 API。  
相反，它把自动化问题拆成三个更现实的问题：

1. **这个目标暴露了哪些控制面？**
2. **哪条路径最稳？失败后应该退到哪里？**
3. **这条路径最适合用哪种脚本语言实现？**

然后，OmniControl 会为这个目标生成：

- 可执行的路径规划
- 主适配器与回退适配器
- 轻量 manifest 与脚本模板
- 必要的 runtime smoke 验证入口

---

## 为什么需要 OmniControl ⚠️

今天很多自动化方案默认了一件事：

**软件会配合你。**

现实并不是这样。

有的软件适合走原生脚本。  
有的软件更适合插件或 vendor CLI。  
有的目标只能通过文件格式写入来间接控制。  
Web 场景有时最稳的是 CDP。  
而有些桌面软件，最后只能退到 UI 自动化或 vision fallback。

问题从来不是“能不能自动化”。  
问题是：

- **该走哪条控制路径？**
- **当主路径失效时，怎样平稳退化？**
- **怎样验证结果是真的生效，而不是命令看起来执行成功？**

OmniControl 就是为这个问题而设计的。

---

## 你可以用它做什么 🔥

OmniControl 可以帮助自动化系统和 agent：

- 识别目标可能提供的控制面
- 为目标和任务选择更稳的主路径
- 设计可落地的 fallback chain，而不是单点押注
- 根据控制面选择合适的脚本语言，而不是默认绑死一种语言
- 生成轻量的 manifest 和脚本模板
- 在必要时接入 runtime smoke，验证方案不是纸上谈兵
- 用结构化状态描述真实执行结果，而不是只有“成功 / 失败”二元判断

支持的结果状态包括：

- `ok`
- `partial`
- `blocked`
- `error`

---

## OmniControl 的核心思路 🧠

OmniControl 不把“自动化”理解成单一技术问题。  
它更接近一个**控制面路由器**：

- 先识别目标暴露了什么
- 再选择最可靠的路径
- 再决定语言和执行方式
- 最后验证现实结果

它的默认倾向是：

- **控制面优先**，而不是源码优先
- **验证优先**，而不是只看命令是否发出
- **路径优先**，而不是接口宗教
- **语言服从控制面**，而不是先选语言再硬适配目标
- **允许 pivot**，而不是主路径一断就整体失败

---

## CLI ⚙️

OmniControl 提供 5 个顶层命令：

- `detect`
- `plan`
- `scaffold`
- `benchmark`
- `smoke`

帮助：

```bash
python -m omnicontrol --help
python -m omnicontrol smoke --help
```

## 快速开始

```bash
cd OmniControl

python -m omnicontrol detect "SomeDesktopApp" --platform windows --kind desktop --need ui
python -m omnicontrol plan "https://example.com" --kind web --need browser --need dom --json
python -m omnicontrol scaffold "LegacyDesktopApp" --platform windows --kind desktop --need ui --output .\generated\legacy-app
```

## Benchmark 配置

`benchmark` 接收一个 JSON 文件，用来描述本地目标和预期规划结果。

最小示例：

```json
{
  "items": [
    {
      "name": "sample_web_target",
      "target": "https://example.com",
      "platform": "windows",
      "kind": "web",
      "needs": ["browser", "dom"],
      "expected_primary": "cdp",
      "expected_language": "typescript"
    }
  ]
}
```

运行方式：

```bash
python -m omnicontrol benchmark .\my-benchmark.json --json
```

## Runtime Smoke

`smoke` 是 runtime 验证入口。
这些 profile 是定向设计的，不是通用万能接口。根据 profile 类型，验证可能包括：

- 文件导出或文件格式写入
- CDP 读写流程
- 桌面 UI 自动化检查
- vendor CLI 或原生脚本入口
- 多步 workflow 验证
- 返回 `partial` 而不是硬失败的诊断型流程

示例：

```bash
python -m omnicontrol smoke chrome-cdp --json
python -m omnicontrol smoke chrome-form-write --json
python -m omnicontrol smoke word-write --json
python -m omnicontrol smoke nx-diagnose --json
```

## 设计原则

- 控制面优先，而不是源码优先。
- 验证优先，而不是只看命令有没有执行。
- 默认保持轻量脚手架，只在必要时加厚 runtime 路径。
- 语言选择应服从控制面，而不是被单一语言绑死。
- 公开仓库内容应尽量避免本机运行痕迹和内部工作笔记。

## 仓库结构

- `omnicontrol/`: 包源码
- `tests/`: 单元测试
- `pyproject.toml`: 打包配置和 CLI 入口

`smoke-output/`、`benchmark-output/`、缓存文件和本地学习状态等 runtime 产物默认不纳入版本控制。

## 边界

OmniControl 不是通用 RPA 平台。

- 不承诺对任意 GUI 自动发现控件并完成全流程自动化。
- CDP 和 runtime 集成是轻量、profile 化的入口，不是完整 vendor SDK 封装。
- 部分 profile 依赖本地安装的第三方软件和环境配置。
- 内部研究文档、本地 benchmark 样本清单和机器相关运行痕迹不会保留在公开仓库中。

## 开发

可编辑安装：

```bash
pip install -e .
```

运行一组轻量测试：

```bash
python -m unittest tests.test_invocation tests.test_staging tests.test_transports
```
