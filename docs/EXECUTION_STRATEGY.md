# Execution Strategy

## Goal

OmniControl 需要在通用场景下同时处理两类失败模式：

1. `partial`
   动作看起来跑了，但写入、副作用或状态变化不稳定。
2. `blocked`
   不是动作设计错了，而是环境前提不满足，比如 license、profile、service、port、focus、runtime 初始化。

这份策略的目标不是给某一个软件打补丁，而是给所有闭源软件建立统一执行模型。

## Unified State Model

所有 runtime 结果都要收敛到 4 个状态：

- `ok`
  所有 required contracts 满足。
- `partial`
  required contracts 满足，但 desired contracts 没满足，或者动作只完成了一部分。
- `blocked`
  动作没有真正失败在业务逻辑上，而是被环境/配置/权限/许可阻断。
- `error`
  没有足够证据证明是 blocked，也没有达到 partial/ok。

## Three-Phase Strategy

### 1. Preflight

在任何真实动作前，先探测：

- 可执行文件是否存在
- 关键端口是否监听
- 关键环境变量是否存在
- 是否已经有残留实例
- 是否需要隔离 `user-data-dir` / profile / workspace
- 是否存在 license / profile / service 级 blocker

Preflight 失败时不要直接抛异常结束，而要把失败转成结构化 `blocked`。

### 1.5. Adaptive Startup

不要假设每个软件都应该“直接启动一个新进程”。
真实世界里更常见的是：

- 已经有实例在运行
- 已经有调试端口
- 软件要求单实例
- 软件必须隔离 `user-data-dir`
- 软件只有在清掉旧实例后才会正确响应

因此启动策略必须自适应，而不是硬编码。

当前建议的通用启动策略只有 3 类：

1. `attach_existing_debug`
   适用于已经运行、而且命令行里已经带调试端口的 Electron/Chromium 应用。
2. `restart_with_debug_port`
   适用于需要显式注入 `--remote-debugging-port` 的应用。
3. `isolated_cli_launch`
   适用于 VS Code / IDE 类 CLI，需要独立 `user-data-dir` 打开隔离实例。

这层策略不关心具体是 `Chrome / Quark / Trae` 还是别的软件。
它只关心：

- 是否发现现有实例
- 是否存在可附着调试端口
- 是否应该清理旧实例
- 是否应该创建隔离 profile
- 是否需要窗口级证据

### 2. Action Contract

每个软件动作都必须拆成：

- `required` conditions
  这些没满足，就不能算成功。
- `desired` conditions
  这些没满足，则记为 `partial`，而不是假装成功。

例如：

- `word-write`
  - required: `exists`, `zip_ok`
- `masterpdf-pagedown`
  - required: `window_name`
  - desired: `page_advanced`

这样同一套状态机就能解释：

- 为何 `Word` 是 `ok`
- 为何 `MasterPDF` 是 `partial`

### 3. Evidence and Recovery

每次动作都必须留下证据，而不是只留布尔值：

- 文件证据：路径、大小、magic bytes
- UI 证据：窗口标题、类名、句柄、截图
- CDP 证据：目标标题、URL、DOM 读回值
- Diagnose 证据：help 输出、sample 输出、端口状态、配置文件内容

同时要根据 blocker 类型自动给 recovery hints：

- `license`
  - 检查端口
  - 检查 license env/config
- `profile`
  - 枚举 profile
  - 重新带 profile 参数运行
- `focus`
  - 先激活窗口
  - 附着现有实例
- `timeout`
  - 增加等待预算
  - 缩小动作范围

## Generic Bug-Fix Policy

### For partial

不要靠“多试几次”掩盖问题，应该按顺序收敛：

1. 增加 stronger evidence
2. 增加 focus / activation step
3. 改成隔离实例
4. 拆小动作
5. 将 unstable effect 从 `required` 下沉到 `desired`

### For blocked

不要把 blocker 留在 stderr 里。必须：

1. 分类 blocker
2. 提取环境事实
3. 输出 recovery hints
4. 保留 command + report path

## Practical Consequence

通用策略并不等于“所有软件都一套脚本”。
通用策略真正统一的是：

- 状态模型
- 合同式验证
- blocker 分类
- recovery 输出
- 证据格式

软件特定逻辑只存在于：

- preflight probes
- action scripts
- contract declarations

这才是可扩展的通用方案。
