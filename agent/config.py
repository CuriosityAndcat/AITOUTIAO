"""
运行配置 — 严格对齐 OpenAI Agents SDK RunConfig

对齐框架: OpenAI Agents SDK (https://github.com/openai/openai-agents-python)
参考源码: src/agents/run.py — RunConfig dataclass

RunConfig 定义 Agent 运行时的所有可配置参数，
包括最大迭代次数、追踪、检查点等。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class RunConfig:
    """
    Agent 运行配置 — 对齐 OpenAI Agents SDK RunConfig

    参考: https://github.com/openai/openai-agents-python/blob/main/src/agents/run.py

    Attributes:
        max_iterations: Evaluator-Optimizer 循环的最大迭代次数。
        temperature: LLM 调用温度参数。
        model: 使用的模型名称。
        tracing_enabled: 是否启用追踪。
        trace_id: 追踪 ID。
        checkpointer: 状态持久化回调（可选）。
        callbacks: 生命周期回调列表。
        metadata: 附加元数据。
    """

    # ── 核心配置 ──
    max_iterations: int = 5
    """最大迭代次数，对齐 Anthropic Evaluator-Optimizer 模式的推荐值。"""

    temperature: float = 0.7
    """LLM 温度参数，0.0=确定性，1.0=创造性。"""

    model: str = "deepseek-chat"
    """使用的 LLM 模型名称。"""

    # ── 可观测性 ──
    tracing_enabled: bool = True
    """是否启用分布式追踪。"""

    trace_id: str | None = None
    """追踪 ID，不提供则自动生成 UUID。"""

    # ── 持久化 ──
    checkpointer: Any = None
    """
    状态检查点回调，用于实现断点续跑。
    对齐 LangGraph checkpointer 接口。
    """

    # ── 生命周期回调 ──
    callbacks: list[Callable] = field(default_factory=list)
    """
    生命周期事件回调列表。
    回调签名: callback(event_type: str, state: dict) -> None
    """

    # ── 元数据 ──
    metadata: dict[str, Any] = field(default_factory=dict)
    """附加元数据，用于日志和追踪。"""
