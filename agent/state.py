"""
LangGraph StateGraph 状态定义 — 严格对齐 LangGraph StateGraph API

对齐框架: LangGraph (https://github.com/langchain-ai/langgraph)
参考源码: langgraph.graph.StateGraph, langgraph.graph.message.add_messages

TypedDict State 定义是 LangGraph StateGraph 编译的前提条件。
消息列表使用 add_messages reducer 实现追加式更新。
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages

from agent.types import Reflection, SearchResult


class AgentState(TypedDict):
    """
    Agent 工作流共享状态 — 对齐 LangGraph StateGraph TypedDict 模式

    每个节点函数签名为 `func(state: AgentState) -> dict`，
    返回的 dict 会被浅合并到当前 state 中。
    messages 字段使用 add_messages reducer 实现追加而非覆盖。
    """

    # ── 消息历史（add_messages reducer） ──
    messages: Annotated[list, add_messages]
    # 使用 LangGraph 内置的 add_messages reducer，
    # 节点返回 {"messages": [new_msg]} 时会追加而非替换。

    # ── 任务定义 ──
    task: str
    # 当前任务描述，由调用方在启动时设置。

    # ── 搜索增强 ──
    search_results: list[SearchResult]
    # 执行前搜索阶段的结果列表。

    # ── 工作记忆 ──
    working_memory: Any
    # WorkingMemory 实例，在 Runner.run_sync 初始化时注入。
    # 各节点函数从中读写 search_context 和 reflections。

    # ── 执行产物 ──
    draft: str
    # 当前草稿/执行输出，供 evaluate 节点审查。

    # ── 迭代控制 ──
    iteration: int
    # 当前迭代轮次，从 0 开始。
    max_iterations: int
    # 最大允许迭代次数，默认 5。

    # ── 审查状态 ──
    reflection: Reflection | None
    # 最近一轮的审查结果。
    reflections: list[Reflection]
    # 所有历史审查结果。

    # ── 路由决策 ──
    next_action: str
    # 路由函数输出的下一步动作: "PASS" | "FIXABLE" | "BLOCKED"

    # ── 最终结果 ──
    final_output: str
    # 达标后的最终输出内容。
    status: str
    # 完成状态: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
    error: str
    # 失败时的错误描述。
