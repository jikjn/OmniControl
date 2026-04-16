from __future__ import annotations

from omnicontrol.models import AdapterPlan, DetectionResult


def summarize_contracts(detection: DetectionResult, plan: AdapterPlan) -> list[str]:
    contracts = []
    for method in plan.verification_methods:
        if method == "backend_query":
            contracts.append("通过后端查询或返回值确认动作已落地。")
        elif method == "http_status":
            contracts.append("验证 HTTP 状态码和响应结构。")
        elif method == "file_exists":
            contracts.append("验证目标文件是否生成。")
        elif method == "file_hash":
            contracts.append("对输出文件做哈希或稳定性比对。")
        elif method == "file_schema":
            contracts.append("验证文件结构或 schema。")
        elif method == "ui_object":
            contracts.append("验证目标 UI 对象是否存在或状态是否变化。")
        elif method == "network_trace":
            contracts.append("检查网络/调试事件是否符合预期。")
        elif method == "command_exit":
            contracts.append("检查命令退出码并读取错误输出。")
        elif method == "screenshot_diff":
            contracts.append("仅在没有结构化真值时做截图差分。")
        elif method == "manual_review":
            contracts.append("保留人工复核作为最后一道防线。")
    return contracts
