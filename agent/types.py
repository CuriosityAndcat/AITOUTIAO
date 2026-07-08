"""
Pydantic 数据模型 — 严格对齐 LangGraph Reflexion 官方源码

对齐框架: LangGraph Reflexion (https://github.com/langchain-ai/langgraph/tree/main/examples/reflexion)
参考源码: examples/reflexion/reflexion/cool_classes.py
           - Reflection(missing, superfluous) 字段名与官方一致
           - AnswerQuestion 模型结构
           - ReviseAnswer 模型结构
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ─── Reflexion 核心模型 ─────────────────────────────────────────


class Reflection(BaseModel):
    """
    反思/审查结果 — 对齐 LangGraph Reflexion 官方 cool_classes.py

    用于 Evaluator-Optimizer 循环中的评估节点输出。

    字段名 missing 和 superfluous 与官方源码完全一致：
    https://github.com/langchain-ai/langgraph/blob/main/examples/reflexion/reflexion/cool_classes.py
    """

    missing: str | None = Field(
        default=None,
        description="输出中缺少的必要内容。如果有缺失则填写具体说明，无缺失则为 None。",
    )
    superfluous: str | None = Field(
        default=None,
        description="输出中多余、不相关或可能有害的内容。无多余内容则为 None。",
    )
    score: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="对输出的综合评分，0-100 分。",
    )
    is_sufficient: bool = Field(
        default=False,
        description="输出是否满足质量标准，无需再修正。",
    )
    feedback: str | None = Field(
        default=None,
        description="给执行节点的改进建议，用于下一轮迭代。",
    )


class ResearchQuery(BaseModel):
    """
    搜索/研究查询 — 由 Agent 自己生成的查询对象
    """

    query: str = Field(description="搜索查询字符串")
    rationale: str = Field(description="为什么需要这个查询，预期获得什么信息")


class AnswerQuestion(BaseModel):
    """
    问答输出 — 对齐 LangGraph Reflexion 官方

    参考: examples/reflexion/reflexion/cool_classes.py 中的 AnswerQuestion
    """

    answer: str = Field(description="经过推理后的最终回答")
    reasoning: str = Field(description="推理过程，包含引用的来源")
    research_queries: list[ResearchQuery] | None = Field(
        default=None,
        description="如果答案不确定，生成的后续研究查询",
    )


class ReviseAnswer(BaseModel):
    """
    修正后的回答 — 对齐 LangGraph Reflexion 官方

    参考: examples/reflexion/reflexion/cool_classes.py 中的 ReviseAnswer
    """

    revised_answer: str = Field(description="根据反思结果修正后的回答")
    changes_made: list[str] = Field(
        description="相对于上一版的具体变更列表",
    )
    reflection_incorporated: bool = Field(
        default=True,
        description="是否已纳入反思建议",
    )


# ─── Agent 生命周期状态 ──────────────────────────────────────────


class AgentStatus:
    """Agent 任务完成状态常量"""

    DONE = "DONE"
    DONE_WITH_CONCERNS = "DONE_WITH_CONCERNS"
    BLOCKED = "BLOCKED"
    NEEDS_CONTEXT = "NEEDS_CONTEXT"

    VALID_STATUSES = {DONE, DONE_WITH_CONCERNS, BLOCKED, NEEDS_CONTEXT}


class TaskResult(BaseModel):
    """
    任务最终结果 — 包含状态、输出和反思历史
    """

    status: str = Field(description=f"完成状态，取值: {', '.join(AgentStatus.VALID_STATUSES)}")
    output: str = Field(description="最终输出内容")
    iterations: int = Field(default=1, ge=1, le=5, description="实际迭代次数")
    reflections: list[Reflection] = Field(
        default_factory=list,
        description="每轮迭代的审查结果历史",
    )
    error: str | None = Field(default=None, description="如果失败，记录错误原因")


# ─── 搜索增强结果 ────────────────────────────────────────────────


class SearchResult(BaseModel):
    """搜索增强阶段的结果"""

    queries: list[str] = Field(description="执行的搜索查询列表")
    findings: str = Field(description="汇总后的搜索结果")
    sources: list[str] = Field(default_factory=list, description="引用来源列表")
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="搜索结果的置信度",
    )
