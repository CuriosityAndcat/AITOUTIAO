"""
记忆管理 — 对齐 Reflexion + Agentic Engineering 记忆设计

对齐框架: LangGraph Reflexion + 2026 Agentic Engineering 实践
参考: LangGraph checkpointer, Reflexion working memory pattern

三层记忆架构：
1. ConversationMemory — 短期记忆，滑动窗口存储最近 N 轮对话
2. WorkingMemory — 工作记忆，存储当前任务状态、草稿和元数据
3. LongTermMemory — 长期记忆（后续迭代接入向量存储）
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


# ─── 短期记忆 ────────────────────────────────────────────────────


@dataclass
class ConversationTurn:
    """单轮对话记录"""

    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationMemory:
    """
    短期记忆 — 滑动窗口存储最近对话

    对齐 Agentic Engineering 推荐的滑动窗口记忆模式。
    维护最近 N 轮对话，超出的自动淘汰。
    """

    turns: list[ConversationTurn] = field(default_factory=list)
    """对话记录列表。"""

    max_turns: int = 20
    """最大保留轮数（默认 20 轮）。"""

    def add(self, role: str, content: str, **metadata) -> None:
        """添加一条对话记录，自动淘汰超出窗口的记录"""
        turn = ConversationTurn(role=role, content=content, metadata=metadata)
        self.turns.append(turn)
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]

    def add_user(self, content: str, **metadata) -> None:
        """添加用户消息"""
        self.add("user", content, **metadata)

    def add_assistant(self, content: str, **metadata) -> None:
        """添加助手回复"""
        self.add("assistant", content, **metadata)

    def add_system(self, content: str, **metadata) -> None:
        """添加系统消息"""
        self.add("system", content, **metadata)

    def to_messages(self) -> list[dict[str, str]]:
        """转换为 LLM API 兼容的消息格式"""
        return [{"role": t.role, "content": t.content} for t in self.turns]

    def to_text(self, separator: str = "\n---\n") -> str:
        """拼接为纯文本上下文"""
        return separator.join(
            f"[{t.role}]: {t.content}" for t in self.turns
        )

    def clear(self) -> None:
        """清空记忆"""
        self.turns.clear()

    def __len__(self) -> int:
        return len(self.turns)

    def __repr__(self) -> str:
        return f"ConversationMemory(turns={len(self.turns)}, max={self.max_turns})"


# ─── 工作记忆 ────────────────────────────────────────────────────


@dataclass
class WorkingMemory:
    """
    工作记忆 — 存储当前任务状态

    对齐 Reflexion 中 WorkingMemory 的概念：
    在迭代过程中维护草稿、反思记录和路由状态。

    与 AgentState 的区别：
    - AgentState: LangGraph 节点间流转的结构化状态
    - WorkingMemory: 面向 Agent/LLM 的自然语言记忆，可直接注入 prompt
    """

    task: str = ""
    """当前任务描述。"""

    draft: str = ""
    """当前草稿/输出。"""

    reflections: list[str] = field(default_factory=list)
    """历史反思记录（自然语言形式）。"""

    iterations: int = 0
    """已完成迭代次数。"""

    max_iterations: int = 5
    """最大迭代次数。"""

    status: str = ""
    """当前状态。"""

    search_context: str = ""
    """搜索增强获取的上下文。"""

    def to_prompt(self) -> str:
        """将工作记忆格式化为可注入 Prompt 的文本"""
        parts: list[str] = []

        if self.task:
            parts.append(f"## 当前任务\n{self.task}")

        if self.search_context:
            parts.append(f"## 搜索上下文\n{self.search_context}")

        if self.draft:
            parts.append(f"## 当前草稿\n{self.draft}")

        if self.reflections:
            recent = self.reflections[-3:]  # 只展示最近 3 条反思
            parts.append("## 历史反思")
            for i, r in enumerate(recent, 1):
                parts.append(f"  第 {i} 轮: {r}")

        parts.append(f"## 进度\n  迭代: {self.iterations}/{self.max_iterations}")

        return "\n\n".join(parts)

    def add_reflection(self, reflection_text: str) -> None:
        """添加一条反思记录"""
        self.reflections.append(reflection_text)

    def reset(self, task: str = "") -> None:
        """重置工作记忆"""
        self.task = task
        self.draft = ""
        self.reflections.clear()
        self.iterations = 0
        self.status = ""
        self.search_context = ""

    def __repr__(self) -> str:
        return (
            f"WorkingMemory(task={self.task[:30]}..., "
            f"iterations={self.iterations}/{self.max_iterations}, "
            f"status={self.status})"
        )
