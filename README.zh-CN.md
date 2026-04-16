# OmniControl

[English](./README.md) | 简体中文

OmniControl 是一个能力优先的自动化控制面脚手架。
它不预设单一自动化栈，而是把问题拆成三个决策：

1. 识别目标暴露了哪些控制面。
2. 选择最稳的适配策略和回退链。
3. 为该目标和任务选择合适的脚本语言。

项目在生成层保持轻量，同时在需要时支持针对性的 runtime 验证。

## 功能概览

- 探测目标可能提供的控制面，例如原生脚本、插件、CLI、文件格式、UI 自动化、CDP 和 vision fallback。
- 生成包含主适配器、回退适配器、语言选择和验证提示的执行方案。
- 生成轻量的 manifest 和脚本模板。
- 为部分 profile 提供 runtime smoke 入口。
- 使用 `ok`、`partial`、`blocked`、`error` 这样的结构化结果，而不是简单成功/失败二分。
- 支持策略 pivot，当主路径被阻塞时可退化到更轻的 sibling 路径。
- 当复杂脚本不适合内联到命令行时，优先落盘为脚本文件再传递。

## CLI

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
