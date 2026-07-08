"""
Runner 执行器 — 严格对齐 OpenAI Agents SDK run.py

对齐框架: OpenAI Agents SDK (https://github.com/openai/openai-agents-python)
参考源码: src/agents/run.py — Runner.run_sync / Runner.run

Runner 是 Agent 的执行引擎，负责编排完整的 Evaluator-Optimizer 循环：
search → execute → evaluate → {PASS:END | FIXABLE:fix | BLOCKED:END}
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from agent.config import RunConfig
from agent.memory import WorkingMemory
from agent.types import AgentStatus, Reflection, TaskResult


@dataclass
class RunResult:
    """
    执行结果 — 对齐 OpenAI Agents SDK RunResult

    参考: https://github.com/openai/openai-agents-python/blob/main/src/agents/run.py

    Attributes:
        final_output: Agent 最终输出文本。
        status: 完成状态（DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT）。
        iterations: 实际执行的迭代次数。
        reflections: 所有迭代的审查记录。
        trace_id: 本次运行的追踪 ID。
        error: 错误信息（仅失败时有值）。
    """

    final_output: str = ""
    status: str = AgentStatus.DONE
    iterations: int = 0
    reflections: list[Reflection] = field(default_factory=list)
    trace_id: str = ""
    error: str | None = None

    @property
    def is_success(self) -> bool:
        """任务是否成功完成"""
        return self.status in (AgentStatus.DONE, AgentStatus.DONE_WITH_CONCERNS)


class Runner:
    """
    Agent 执行引擎 — 对齐 OpenAI Agents SDK Runner

    类方法 run_sync / run 是主要的公共入口。

    使用示例:
        agent = Agent(name="Demo", instructions="你是助手")
        result = Runner.run_sync(agent, "你好", config=RunConfig())
    """

    @classmethod
    def run_sync(
        cls,
        agent,
        task: str,
        config: RunConfig | None = None,
        **kwargs,
    ) -> RunResult:
        """
        同步执行 Agent — 对齐 OpenAI SDK Runner.run_sync

        编排完整的 Evaluator-Optimizer 循环。

        Args:
            agent: Agent 实例（来自 agent.agent.Agent）
            task: 任务描述
            config: 运行配置，不提供则使用 agent.default_config
            **kwargs: 传入 AgentGraph 的额外参数

        Returns:
            RunResult 包含最终输出和迭代信息
        """
        from agent.graph import AgentGraph

        cfg = config or agent.default_config
        trace_id = cfg.trace_id or str(uuid.uuid4())
        reflections: list[Reflection] = []

        try:
            # 初始化工作记忆，由 Runner 统一注入
            wm = WorkingMemory(
                task=task,
                max_iterations=cfg.max_iterations,
            )

            # 构建并运行 StateGraph
            graph = AgentGraph.build(agent, cfg)
            state = graph.invoke(
                {
                    "task": task,
                    "messages": [],
                    "draft": "",
                    "search_results": [],
                    "working_memory": wm,
                    "iteration": 0,
                    "max_iterations": cfg.max_iterations,
                    "reflection": None,
                    "reflections": [],
                    "next_action": "",
                    "final_output": "",
                    "status": "",
                    "error": "",
                }
            )

            # 提取结果
            final = state.get("final_output", "")
            status = state.get("status", AgentStatus.DONE)
            reflections = state.get("reflections", [])
            error = state.get("error", "")

            if error:
                status = AgentStatus.BLOCKED

            return RunResult(
                final_output=final,
                status=status,
                iterations=state.get("iteration", 0),
                reflections=reflections,
                trace_id=trace_id,
                error=error if error else None,
            )

        except Exception as e:
            return RunResult(
                final_output="",
                status=AgentStatus.BLOCKED,
                iterations=0,
                reflections=reflections,
                trace_id=trace_id,
                error=str(e),
            )

    @classmethod
    async def run(
        cls,
        agent,
        task: str,
        config: RunConfig | None = None,
        **kwargs,
    ) -> RunResult:
        """
        异步执行 Agent — 对齐 OpenAI SDK Runner.run

        当前实现委托给 run_sync（LangGraph 的 ainvoke 可在后续迭代中接入）。
        """
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, cls.run_sync, agent, task, config
        )
