from __future__ import annotations

from omnicontrol.adapters.catalog import ADAPTER_PROFILES
from omnicontrol.models import AdapterPlan, DetectionResult, dedupe_keep_order
from omnicontrol.planner.language_selector import LanguageSelector


class AdapterSelector:
    """Choose the best adapter, fallback chain and verification strategy."""

    def __init__(self) -> None:
        self.language_selector = LanguageSelector()

    def select(self, detection: DetectionResult) -> AdapterPlan:
        scored: list[tuple[float, str, str]] = []
        needs = set(detection.needs)

        for capability in detection.capabilities:
            profile = ADAPTER_PROFILES.get(capability.name)
            if profile is None:
                continue
            score = profile.priority * capability.confidence
            reason = (
                f"{capability.name} 基础优先级 {profile.priority:.2f} x "
                f"检测置信度 {capability.confidence:.2f}"
            )

            if detection.target_kind == "web" and capability.name == "cdp":
                score += 0.12
                reason += "，Web 目标加分"
            if detection.target_kind == "service" and capability.name == "api":
                score += 0.12
                reason += "，Service 目标加分"
            if detection.target_kind == "document" and capability.name == "file_format":
                score += 0.12
                reason += "，Document 目标加分"
            if detection.platform == "windows" and capability.name in {"native_script", "uiautomation"}:
                score += 0.08
                reason += "，Windows 桌面场景加分"
            if detection.platform == "macos" and capability.name in {"native_script", "accessibility"}:
                score += 0.08
                reason += "锛宮acOS 妗岄潰鍦烘櫙鍔犲垎"
            if {"browser", "dom"} & needs and capability.name == "cdp":
                score += 0.08
                reason += "，需求侧浏览器控制加分"
            if {"office", "com"} & needs and capability.name == "native_script":
                score += 0.10
                reason += "，需求侧 Office/COM 加分"
            if {"shell", "batch"} & needs and capability.name == "existing_cli":
                score += 0.06
                reason += "，需求侧 CLI 编排加分"

            scored.append((score, capability.name, reason))

        if not scored:
            scored.append((0.4, "vision", "未识别到结构化控制面，退回视觉 fallback。"))

        scored.sort(key=lambda item: item[0], reverse=True)
        primary_adapter = scored[0][1]
        fallback_adapters = dedupe_keep_order(
            [name for _, name, _ in scored[1:4]] + (["vision"] if primary_adapter != "vision" else [])
        )

        profile = ADAPTER_PROFILES[primary_adapter]
        language = self.language_selector.select(primary_adapter, detection)
        verification_methods = list(profile.default_verification)
        verification_methods.extend(self._extra_verification(detection))
        suggested_actions = self._suggest_actions(detection)

        top_capability_reasons = detection.capabilities[0].reasons[:2] if detection.capabilities else []
        rationale = [scored[0][2], *top_capability_reasons]

        return AdapterPlan(
            primary_adapter=primary_adapter,
            fallback_adapters=dedupe_keep_order(fallback_adapters),
            state_model=self._state_model_for(primary_adapter, detection),
            verification_methods=dedupe_keep_order(verification_methods),
            suggested_actions=suggested_actions,
            language=language,
            rationale=dedupe_keep_order(rationale),
        )

    def _state_model_for(self, adapter: str, detection: DetectionResult) -> str:
        if adapter == "vision":
            return "shadow_session"
        if detection.target_kind in {"service", "document"}:
            return "stateless"
        return ADAPTER_PROFILES[adapter].default_state_model

    def _extra_verification(self, detection: DetectionResult) -> list[str]:
        methods: list[str] = []
        if detection.target_kind == "document":
            methods.extend(["file_hash", "file_schema"])
        if detection.target_kind == "desktop":
            methods.append("ui_object")
        if detection.target_kind == "web":
            methods.extend(["ui_object", "network_trace"])
        if "export" in detection.needs:
            methods.append("file_exists")
        return methods

    def _suggest_actions(self, detection: DetectionResult) -> list[str]:
        actions_by_kind = {
            "desktop": ["inspect_state", "invoke_action", "query_selection", "export_artifact"],
            "document": ["load_document", "transform_document", "query_metadata", "export_artifact"],
            "web": ["open_surface", "query_dom", "invoke_action", "capture_artifact"],
            "service": ["call_endpoint", "poll_status", "download_artifact", "query_result"],
            "codebase": ["inspect_target", "generate_adapter", "run_command", "verify_outputs"],
        }
        actions = list(actions_by_kind.get(detection.target_kind, ["inspect_target", "invoke_action"]))
        need_action_map = {
            "export": "export_artifact",
            "document": "transform_document",
            "browser": "query_dom",
            "dom": "query_dom",
            "batch": "batch_transaction",
            "shell": "run_command",
            "api": "call_endpoint",
            "ui": "query_selection",
        }
        for need in detection.needs:
            action = need_action_map.get(need)
            if action is not None:
                actions.append(action)
        return dedupe_keep_order(actions)
