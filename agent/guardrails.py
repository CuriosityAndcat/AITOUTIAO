"""
护栏系统 — 严格对齐 OpenAI Agents SDK Guardrails

对齐框架: OpenAI Agents SDK (https://github.com/openai/openai-agents-python)
参考源码: src/agents/guardrails.py — InputGuardrail / OutputGuardrail

护栏是 Agent 安全体系的核心，分为三层：
- Layer 1: InputGuardrail  — 输入校验
- Layer 2: PolicyGuardrail — 策略合规
- Layer 3: OutputGuardrail — 输出校验
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class GuardrailResult:
    """
    护栏检查结果 — 对齐 OpenAI GuardrailFunctionOutput

    参考: https://github.com/openai/openai-agents-python/blob/main/src/agents/guardrails.py
    """

    passed: bool = True
    """护栏检查是否通过。"""

    reason: str = ""
    """通过/拒绝的原因说明。"""

    severity: str = "info"
    """严重级别: info / warning / error"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """附加上下文元数据。"""


class BaseGuardrail(ABC):
    """
    护栏基类 — 对齐 OpenAI Guardrail 抽象

    所有护栏（InputGuardrail / OutputGuardrail）都继承此类。
    """

    name: str = "base_guardrail"
    description: str = ""

    @abstractmethod
    def check(self, input_data: str, context: dict | None = None) -> GuardrailResult:
        """
        执行护栏检查。

        Args:
            input_data: 待检查的输入/输出文本
            context: 上下文信息（任务描述、历史等）

        Returns:
            GuardrailResult 包含 passed 状态和原因
        """
        ...

    def __call__(self, input_data: str, context: dict | None = None) -> GuardrailResult:
        return self.check(input_data, context)


# ─── 输入护栏 ────────────────────────────────────────────────────


class InputGuardrail(BaseGuardrail):
    """
    输入护栏 — 对齐 OpenAI InputGuardrail

    检查用户输入是否合规，拦截恶意/违规/不合理的请求。
    """

    name: str = "input_guardrail"
    description: str = "检查用户输入的安全性和合规性"

    # ─── 禁止关键词（示例） ───
    BLOCKED_KEYWORDS: tuple = (
        "越狱", "绕过", "忽略规则", "ignore instructions",
        "ignore rules", "jailbreak",
    )

    def check(self, input_data: str, context: dict | None = None) -> GuardrailResult:
        if not input_data or not input_data.strip():
            return GuardrailResult(
                passed=False,
                reason="输入为空",
                severity="error",
            )

        lower_input = input_data.lower()
        for keyword in self.BLOCKED_KEYWORDS:
            if keyword.lower() in lower_input:
                return GuardrailResult(
                    passed=False,
                    reason=f"输入包含禁止关键词: {keyword}",
                    severity="error",
                )

        return GuardrailResult(passed=True, reason="输入检查通过")


# ─── 输出护栏 ────────────────────────────────────────────────────


class OutputGuardrail(BaseGuardrail):
    """
    输出护栏 — 对齐 OpenAI OutputGuardrail

    检查 Agent 输出是否合规，验证格式、内容和安全性。
    """

    name: str = "output_guardrail"
    description: str = "检查 Agent 输出的质量和合规性"

    MIN_OUTPUT_LENGTH: int = 10
    """最小输出长度（字符）。"""

    def check(self, input_data: str, context: dict | None = None) -> GuardrailResult:
        if not input_data or not input_data.strip():
            return GuardrailResult(
                passed=False,
                reason="输出为空",
                severity="error",
            )

        if len(input_data.strip()) < self.MIN_OUTPUT_LENGTH:
            return GuardrailResult(
                passed=False,
                reason=f"输出过短（{len(input_data.strip())} 字符 < {self.MIN_OUTPUT_LENGTH}）",
                severity="warning",
            )

        return GuardrailResult(passed=True, reason="输出检查通过")


# ─── 策略合规护栏 ────────────────────────────────────────────────


class PolicyGuardrail(BaseGuardrail):
    """
    策略合规护栏 — Layer 2：内容审核 + 版权检查

    在输入清洗和输出格式验证之间执行，
    确保生成内容不违反平台政策、不侵犯版权。
    """

    name: str = "policy_guardrail"
    description: str = "检查内容的政策合规性和版权风险"

    # ─── 敏感词名单（示例） ───
    SENSITIVE_KEYWORDS: tuple = (
        "台独", "藏独", "疆独", "港独",
        "宣扬恐怖主义", "煽动民族仇恨",
        "色情", "赌博", "毒品制作",
    )

    # ─── 版权风险模式 ───
    COPYRIGHT_PATTERNS: tuple = (
        "全文转载", "原文来自", "转载自",
        "复制粘贴", "直接引用全文",
    )

    def check(self, input_data: str, context: dict | None = None) -> GuardrailResult:
        if not input_data or not input_data.strip():
            return GuardrailResult(
                passed=False,
                reason="内容为空，无法进行策略检查",
                severity="error",
            )

        # 敏感词检查
        for keyword in self.SENSITIVE_KEYWORDS:
            if keyword in input_data:
                return GuardrailResult(
                    passed=False,
                    reason=f"内容包含敏感关键词: {keyword}",
                    severity="error",
                    metadata={"matched_keyword": keyword},
                )

        # 版权风险检查
        for pattern in self.COPYRIGHT_PATTERNS:
            if pattern in input_data:
                return GuardrailResult(
                    passed=False,
                    reason=f"检测到版权风险模式: {pattern}",
                    severity="warning",
                    metadata={"matched_pattern": pattern},
                )

        return GuardrailResult(
            passed=True,
            reason="策略合规检查通过",
            severity="info",
        )


# ─── 护栏管线 ────────────────────────────────────────────────────


@dataclass
class GuardrailPipeline:
    """
    护栏管线 — 按顺序执行多个护栏检查

    使用示例:
        pipeline = GuardrailPipeline([
            InputGuardrail(),
            PolicyGuardrail(),
            OutputGuardrail(),
        ])
        result = pipeline.run(content, context)
    """

    guardrails: list[BaseGuardrail]
    """护栏列表，按注册顺序执行。"""

    fail_fast: bool = True
    """是否快速失败（遇到第一个失败立即停止）。"""

    def run(self, content: str, context: dict | None = None) -> list[GuardrailResult]:
        """
        按顺序执行所有护栏检查。

        Returns:
            所有护栏的检查结果列表。
            如果 fail_fast=True，遇到第一个失败即停止并返回。
        """
        results: list[GuardrailResult] = []
        for guardrail in self.guardrails:
            result = guardrail.check(content, context)
            results.append(result)
            if self.fail_fast and not result.passed:
                break
        return results

    def is_all_passed(self, results: list[GuardrailResult]) -> bool:
        """检查是否所有护栏都通过"""
        return all(r.passed for r in results)
