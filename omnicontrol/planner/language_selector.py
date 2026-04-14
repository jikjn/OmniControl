from __future__ import annotations

from collections import defaultdict

from omnicontrol.models import DetectionResult, LanguageDecision, LanguageOption, dedupe_keep_order


class LanguageSelector:
    """Choose a scripting language based on platform, adapter and workload."""

    def select(self, adapter: str, detection: DetectionResult) -> LanguageDecision:
        scores: dict[str, list[tuple[float, str]]] = defaultdict(list)
        needs = set(detection.needs)
        signals = set(detection.signals)

        def add(language: str, score: float, reason: str) -> None:
            scores[language].append((score, reason))

        add("python", 0.55, "Python 作为跨平台编排语言保底可用。")

        if adapter in {"file_format", "api"}:
            add("python", 0.95, "文件格式和服务编排最适合 Python。")
        if adapter == "cdp":
            add("typescript", 0.96, "CDP/Electron/浏览器任务与 TypeScript/Node 最贴合。")
            add("python", 0.72, "Python 可以做外围编排，但不是第一优先。")
        if adapter == "existing_cli":
            if detection.platform == "windows":
                add("powershell", 0.88, "Windows 上包现有 CLI 更适合 PowerShell。")
            else:
                add("bash", 0.88, "类 Unix 平台包现有 CLI 更适合 Bash。")
            add("python", 0.80, "如果需要跨平台包装层，Python 是第二选择。")
        if adapter in {"native_script", "uiautomation"} and detection.platform == "windows":
            add("powershell", 0.94, "Windows 原生脚本、COM 和 UIA 场景优先 PowerShell。")
            if needs & {"provider", "etw", "hook", "shim", "deep-native"}:
                add("csharp", 0.97, "深 Windows 原生能力更适合 C#。")
            else:
                add("csharp", 0.78, "需要更强类型绑定时可以升级到 C#。")
        if adapter in {"native_script", "accessibility"} and detection.platform == "macos":
            add("applescript", 0.93, "macOS App 脚本化和 System Events 更适合 AppleScript。")
            add("python", 0.74, "Python 适合作为外围编排层。")
        if detection.platform == "linux" and adapter == "accessibility":
            add("python", 0.83, "Linux 可访问性自动化通常先用 Python。")
            add("bash", 0.72, "简单命令包装也可用 Bash。")

        if needs & {"browser", "dom", "network", "extension"}:
            add("typescript", 0.92, "需求指向浏览器和前端调试生态。")
        if needs & {"document", "data", "schema", "transform", "export"}:
            add("python", 0.90, "文档、数据和导出任务更适合 Python。")
        if needs & {"shell", "batch", "ops"}:
            if detection.platform == "windows":
                add("powershell", 0.86, "Windows 运维和批处理更适合 PowerShell。")
            else:
                add("bash", 0.86, "类 Unix 运维和批处理更适合 Bash。")
        if needs & {"office", "com"}:
            add("powershell", 0.92, "Office/COM 任务更适合 PowerShell。")
        if "preferred_language=javascript" in signals:
            add("javascript", 0.97, "检测到 JSX/脚本目录，Adobe 类脚本面更适合 JavaScript/ExtendScript。")
        if "preferred_language=python" in signals:
            add("python", 0.97, "检测到 Python 自动化痕迹，优先使用 Python。")

        ranking = [
            LanguageOption(
                language=language,
                score=round(max(score for score, _ in entries), 2),
                reasons=[reason for _, reason in entries],
            )
            for language, entries in scores.items()
        ]
        ranking.sort(key=lambda option: option.score, reverse=True)

        primary = ranking[0].language
        alternatives = dedupe_keep_order([option.language for option in ranking[1:3]])
        return LanguageDecision(
            primary=primary,
            alternatives=alternatives,
            ranking=ranking,
            reasons=ranking[0].reasons[:3],
        )
